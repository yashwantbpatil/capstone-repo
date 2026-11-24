import asyncio
import json
import os
import re
import statistics
import time
import pandas as pd
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

load_dotenv()

client = AsyncOpenAI()


# ==============================================================================
# 1. CONFIGURATION, RUBRIC & CONSTANTS
# ==============================================================================

EXTRACTION_MODEL = "gpt-4o-mini"
JUDGE_MODEL = "gpt-4o"

TARGET_FIELDS = ("company", "role", "years_experience_required")

# Token pricing per 1,000,000 (1M) tokens (USD) for tracked models
MODEL_PRICING_PER_1M: Dict[str, Dict[str, float]] = {
    "gpt-4o-mini": {
        "standard_input": 0.15,
        "cached_input": 0.075,
        "output": 0.60,
        "reasoning": 0.60,
    },
    "gpt-4o": {
        "standard_input": 2.50,
        "cached_input": 1.25,
        "output": 10.00,
        "reasoning": 10.00,
    },
}

# Updated 1-25 evaluation rubric for LLM-as-judge scoring
RUBRIC = """
ACCURACY (1-25)
  25 = fully correct given the corpus
  20 = mostly correct, minor issues
  10 = partially correct, significant issues
  1 = incorrect or misleading
GROUNDEDNESS (1-25)
  25 = every claim traces to the corpus
  20 = mostly grounded, small unsupported additions
  10 = mix of grounded and invented content
  1 = substantially invented or hallucinated
FORMAT (1-25)
  25 = clear, appropriately concise, well-structured
  20 = clear but slightly verbose or terse
  10 = confusing structure or wrong length
  1 = badly formatted, hard to read
""".strip()


# ==============================================================================
# 2. DATA STRUCTURES (RAW CALLS, SCORED RECORDS & AGGREGATED METRICS)
# ==============================================================================

class JudgeVerdict(BaseModel):
    """Structured schema returned by the gpt-4o LLM-as-judge."""

    accuracy_rubric: int = Field(..., ge=1, le=25, description="Rubric ACCURACY score (1-25)")
    groundedness_rubric: int = Field(..., ge=1, le=25, description="Rubric GROUNDEDNESS score (1-25)")
    format_rubric: int = Field(..., ge=1, le=25, description="Rubric FORMAT score (1-25)")
    llm_judge_score: int = Field(
        ...,
        ge=1,
        le=25,
        description="Overall quality score on a 1-25 scale informed by the rubric",
    )
    reasoning: str = Field(..., description="Brief explanation of the assigned scores")


@dataclass
class LLMCallRecord:
    """Stores output, cost, and latency for a single extraction LLM call."""

    prompt_name: str
    snippet_id: str
    raw_response: Optional[str]
    parsed_extraction: Optional[Dict[str, Any]]
    cost_usd: float
    latency_seconds: float
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    error: Optional[str] = None


@dataclass
class EvaluatedCallRecord:
    """Combines an extraction call with deterministic & LLM-judge evaluation scores."""

    prompt_name: str
    snippet_id: str
    parse_success: bool
    accuracy: int  # 0 to 3 matching fields against golden_set.jsonl
    llm_judge_score: Optional[int]  # 1 to 25 scale via gpt-4o
    cost_usd: float
    latency_seconds: float
    parsed_extraction: Optional[Dict[str, Any]]
    golden_expected: Dict[str, Any]
    raw_response: Optional[str] = None
    judge_reasoning: Optional[str] = None
    judge_cost_usd: float = 0.0
    error: Optional[str] = None


@dataclass
class StrategyComparisonRow:
    """Aggregated comparison metrics for one prompt strategy."""

    strategy: str
    accuracy_mean: float        # Out of 3
    parse_rate_pct: float       # Percentage (0 - 100)
    judge_score_mean: float     # Out of 25
    total_cost_usd: float       # Sum of LLM call costs ($)
    latency_p50_seconds: float  # 50th percentile latency (s)
    num_snippets: int


# ==============================================================================
# 3. DATASET LOADERS & JSON / COST HELPERS
# ==============================================================================

def load_job_snippets(file_path: Path) -> List[Dict[str, str]]:
    """Loads job_snippets.jsonl into a list of dicts with 'id' and 'snippet'."""
    if not file_path.exists():
        raise FileNotFoundError(f"Job snippets file not found: {file_path}")

    records: List[Dict[str, str]] = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            cleaned = line.strip()
            if not cleaned:
                continue
            item = json.loads(cleaned)
            records.append({
                "id": str(item.get("id", f"unknown_{line_num}")),
                "snippet": str(item.get("snippet", "")),
            })
    return records


def load_golden_set(file_path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Loads golden_set.jsonl and indexes entries by 'id' for O(1) lookup:
        { "j01": {"id": "j01", "company": ..., "role": ..., "years_experience_required": ...}, ... }
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Golden set file not found: {file_path}")

    golden_by_id: Dict[str, Dict[str, Any]] = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            cleaned = line.strip()
            if not cleaned:
                continue
            item = json.loads(cleaned)
            job_id = str(item["id"])
            golden_by_id[job_id] = item
    return golden_by_id


def calculate_call_cost(usage: Dict[str, Any], model: str = EXTRACTION_MODEL) -> float:
    """Calculates total USD cost by multiplying each token type by its model rate."""
    pricing = MODEL_PRICING_PER_1M.get(model, MODEL_PRICING_PER_1M["gpt-4o-mini"])

    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    output_tokens = int(usage.get("completion_tokens", 0) or 0)

    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}

    cached_tokens = int(prompt_details.get("cached_tokens", 0) or 0)
    reasoning_tokens = int(completion_details.get("reasoning_tokens", 0) or 0)

    standard_input_tokens = max(0, prompt_tokens - cached_tokens)
    standard_output_tokens = max(0, output_tokens - reasoning_tokens)

    cost = (
        (standard_input_tokens / 1_000_000) * pricing["standard_input"]
        + (cached_tokens / 1_000_000) * pricing["cached_input"]
        + (standard_output_tokens / 1_000_000) * pricing["output"]
        + (reasoning_tokens / 1_000_000) * pricing["reasoning"]
    )
    return round(cost, 8)


def parse_llm_json_response(raw_text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parses raw LLM text into a dictionary; returns None if invalid or empty."""
    if not raw_text or not raw_text.strip():
        return None

    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    # Fallback: extract outermost JSON object if surrounded by reasoning text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    return None


# ==============================================================================
# 4. PROMPT BUILDERS & ASYNC EXTRACTION BATCHES
# ==============================================================================

def build_prompt_messages(prompt_name: str, snippet_text: str) -> List[Dict[str, str]]:
    """Builds chat messages for zero_shot, few_shot, structured, or chain_of_thought."""
    schema_instruction = (
        'Return a JSON object with keys: '
        '{"company": string|null, "role": string|null, "years_experience_required": int|null}. '
        "Use null for years_experience_required if no years requirement is stated."
    )

    if prompt_name == "zero_shot":
        system_msg = f"Extract job details accurately. {schema_instruction}"
        user_msg = f"Snippet:\n{snippet_text}"

    elif prompt_name == "few_shot":
        system_msg = f"Extract job details following the examples. {schema_instruction}"
        user_msg = (
            "Example 1:\n"
            "Snippet: 'Globex International seeks a Product Manager - Growth. At least 4 years of PM experience.'\n"
            'JSON: {"company": "Globex International", "role": "Product Manager - Growth", "years_experience_required": 4}\n\n'
            "Example 2:\n"
            "Snippet: 'FinSight Analytics is hiring a Data Engineer with 3 to 4 years of hands-on experience in data pipeline architecture. The ideal candidate possesses deep technical expertise in Python, Apache Spark, Snowflake, and SQL to process high-volume financial datasets. You will build automated ETL workflows and ensure data reliability across production environments.'\n"
            'JSON: {"company": "FinSight Analyticsl", "role": "Data Engineer", "years_experience_required": 3}\n\n'
            "Example 3:\n"
            "Snippet: 'Hooli is looking for a Junior Frontend Developer. Fresh grads welcome — no prior experience required.'\n"
            'JSON: {"company": "Hooli", "role": "Junior Frontend Developer", "years_experience_required": 0}\n\n'
            f"Now extract:\nSnippet: '{snippet_text}'\nJSON:"
        )

    elif prompt_name == "structured":
        system_msg = (
            "You are a strict schema extractor. Output valid JSON with keys "
            "'company' (str|null), 'role' (str|null), and 'years_experience_required' (int|null). "
            "For ranges like '3 to 5', use the minimum integer (3). For spelled numbers like 'five', use 5."
        )
        user_msg = f"Extract from snippet:\n{snippet_text}"

    elif prompt_name == "chain_of_thought":
        system_msg = (
            "Think step-by-step about company, role, and years_experience_required first, "
            f"then end your response with the final JSON object. {schema_instruction}"
        )
        user_msg = f"Analyze and extract from snippet:\n{snippet_text}"

    else:
        raise ValueError(f"Unknown prompt strategy: {prompt_name}")

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


async def extract_fields_async(
    prompt_name: str,
    snippet_item: Dict[str, str],
    model: str = EXTRACTION_MODEL,
    openai_client: Optional[AsyncOpenAI] = None,
) -> LLMCallRecord:
    """
    Executes one async extraction call via `client.chat.completions.create()`
    and records cost + latency.
    """
    active_client = openai_client or client
    snippet_id = snippet_item["id"]
    snippet_text = snippet_item["snippet"]
    messages = build_prompt_messages(prompt_name, snippet_text)

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.0,
    }
    if prompt_name == "structured":
        kwargs["response_format"] = {"type": "json_object"}

    start_time = time.perf_counter()
    try:
        resp = await active_client.chat.completions.create(**kwargs)
        latency = time.perf_counter() - start_time

        raw_text = resp.choices[0].message.content if resp.choices else None
        usage = resp.usage.model_dump() if resp.usage else {}
        cost = calculate_call_cost(usage, model=model)
        parsed = parse_llm_json_response(raw_text)

        return LLMCallRecord(
            prompt_name=prompt_name,
            snippet_id=snippet_id,
            raw_response=raw_text,
            parsed_extraction=parsed,
            cost_usd=cost,
            latency_seconds=round(latency, 4),
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            cached_input_tokens=int((usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
            total_tokens=int(usage.get("total_tokens", 0) or 0),
        )
    except Exception as exc:
        latency = time.perf_counter() - start_time
        return LLMCallRecord(
            prompt_name=prompt_name,
            snippet_id=snippet_id,
            raw_response=None,
            parsed_extraction=None,
            cost_usd=0.0,
            latency_seconds=round(latency, 4),
            error=str(exc),
        )


async def run_extraction_batches(
    job_snippets: List[Dict[str, str]],
    strategies: List[str],
    model: str = EXTRACTION_MODEL,
    openai_client: Optional[AsyncOpenAI] = None,
) -> Dict[str, List[LLMCallRecord]]:
    """
    Runs 4 strategy loops; in each loop runs an async batch of size len(job_snippets)
    using `asyncio.gather` and `AsyncOpenAI.chat.completions.create()`.
    """
    active_client = openai_client or client
    results_by_strategy: Dict[str, List[LLMCallRecord]] = {}

    for strategy in strategies:
        tasks = [
            extract_fields_async(
                prompt_name=strategy,
                snippet_item=item,
                model=model,
                openai_client=active_client,
            )
            for item in job_snippets
        ]
        results_by_strategy[strategy] = await asyncio.gather(*tasks)

    return results_by_strategy


# ==============================================================================
# 5. DETERMINISTIC SCORING (parse_success & accuracy)
# ==============================================================================

def normalize_text(value: Any) -> Optional[str]:
    """Trims whitespace and lowercases strings; normalizes whitespace runs."""
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value).strip()).lower()
    return text if text != "" else None


def normalize_years(value: Any) -> Optional[int]:
    """Converts int or numeric string to int; returns None when null/missing."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in ("", "none", "null", "n/a", "na"):
            return None
        match = re.search(r"-?\d+", cleaned)
        if match:
            return int(match.group(0))
    return None


def evaluate_parse_success(parsed: Optional[Dict[str, Any]]) -> bool:
    """
    Returns True if parsed is a dict containing all 3 target fields
    ('company', 'role', 'years_experience_required'), False otherwise.
    """
    if not isinstance(parsed, dict):
        return False
    return all(field in parsed for field in TARGET_FIELDS)


def compute_field_accuracy(
    parsed: Optional[Dict[str, Any]],
    golden_item: Dict[str, Any],
) -> int:
    """
    Compares 'company', 'role', and 'years_experience_required' against golden_set
    (case-insensitive, whitespace trimmed). Returns an integer from 0 to 3.
    """
    if not isinstance(parsed, dict):
        return 0

    matches = 0

    # 1. company (case-insensitive, trimmed)
    pred_company = normalize_text(parsed.get("company"))
    gold_company = normalize_text(golden_item.get("company"))
    if pred_company == gold_company:
        matches += 1

    # 2. role (case-insensitive, trimmed)
    pred_role = normalize_text(parsed.get("role"))
    gold_role = normalize_text(golden_item.get("role"))
    if pred_role == gold_role:
        matches += 1

    # 3. years_experience_required (supports int or null)
    pred_years = normalize_years(parsed.get("years_experience_required"))
    gold_years = normalize_years(golden_item.get("years_experience_required"))
    if pred_years == gold_years:
        matches += 1

    return matches


# ==============================================================================
# 6. LLM-AS-JUDGE (gpt-4o)
# ==============================================================================

async def judge_single_extraction_async(
    openai_client: AsyncOpenAI,
    question_snippet: str,
    candidate_output: Optional[Dict[str, Any]],
    ideal_answer: Dict[str, Any],
    judge_model: str = JUDGE_MODEL,
) -> Tuple[Optional[int], Optional[str], float]:
    """
    Evaluates one (snippet, candidate_output, ideal_answer) using gpt-4o
    with the provided RUBRIC and returns (llm_judge_score [1-25], reasoning, judge_cost_usd).
    """
    ideal_subset = {k: ideal_answer.get(k) for k in TARGET_FIELDS}
    candidate_subset = (
        {k: candidate_output.get(k) for k in TARGET_FIELDS}
        if isinstance(candidate_output, dict)
        else {"error": "Failed to parse valid JSON extraction"}
    )

    ideal_hint = f"\n\nIdeal answer (for reference): {json.dumps(ideal_subset)}" if ideal_subset else ""
    candidate_str = json.dumps(candidate_subset)

    system_prompt = (
        "You are a strict evaluator of LLM answers.\n\n"
        f"{RUBRIC}\n\n"
        "Score the candidate extraction on a 1-25 scale (llm_judge_score) using the rubric above "
        "and provide brief reasoning explaining your scores."
    )
    user_prompt = (
        f"Question (job snippet): {question_snippet}{ideal_hint}\n\n"
        f"Candidate answer to evaluate: {candidate_str}"
    )

    try:
        resp = await openai_client.chat.completions.parse(
            model=judge_model,
            temperature=0.0,
            response_format=JudgeVerdict,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        verdict: Optional[JudgeVerdict] = resp.choices[0].message.parsed
        usage_dict = resp.usage.model_dump() if resp.usage else {}
        judge_cost = calculate_call_cost(usage_dict, model=judge_model)


        if verdict is None:
            return None, "Judge returned no parsed verdict", judge_cost

        return int(verdict.llm_judge_score), verdict.reasoning, judge_cost

    except Exception as exc:
        return None, f"Judge error: {exc}", 0.0


async def score_all_results_async(
    results_by_strategy: Dict[str, List[LLMCallRecord]],
    snippets_by_id: Dict[str, str],
    golden_by_id: Dict[str, Dict[str, Any]],
    judge_model: str = JUDGE_MODEL,
    openai_client: Optional[AsyncOpenAI] = None,
) -> Dict[str, List[EvaluatedCallRecord]]:
    """
    Computes parse_success, accuracy (0-3), and llm_judge_score (1-25) for every
    (snippet x strategy) call concurrently.
    """
    active_client = openai_client or client
    scored_by_strategy: Dict[str, List[EvaluatedCallRecord]] = {}

    async def _score_one(strategy: str, rec: LLMCallRecord) -> EvaluatedCallRecord:
        golden_item = golden_by_id.get(rec.snippet_id, {})
        snippet_text = snippets_by_id.get(rec.snippet_id, "")

        parse_ok = evaluate_parse_success(rec.parsed_extraction)
        acc_score = compute_field_accuracy(rec.parsed_extraction, golden_item)

        judge_score, reasoning, judge_cost = await judge_single_extraction_async(
            openai_client=active_client,
            question_snippet=snippet_text,
            candidate_output=rec.parsed_extraction,
            ideal_answer=golden_item,
            judge_model=judge_model,
        )

        return EvaluatedCallRecord(
            prompt_name=rec.prompt_name,
            snippet_id=rec.snippet_id,
            parse_success=parse_ok,
            accuracy=acc_score,
            llm_judge_score=judge_score,
            cost_usd=rec.cost_usd,
            latency_seconds=rec.latency_seconds,
            parsed_extraction=rec.parsed_extraction,
            golden_expected={k: golden_item.get(k) for k in TARGET_FIELDS},
            raw_response=rec.raw_response,
            judge_reasoning=reasoning,
            judge_cost_usd=judge_cost,
            error=rec.error,
        )

    for strategy, records in results_by_strategy.items():
        tasks = [_score_one(strategy, rec) for rec in records]
        scored_by_strategy[strategy] = await asyncio.gather(*tasks)

    return scored_by_strategy


# ==============================================================================
# 7. AGGREGATION & COMPARISON TABLE PRINTER
# ==============================================================================

def percentile(values: List[float], pct: float) -> float:
    """Computes percentile (e.g., 50 for p50) without external dependencies."""
    if not values:
        return 0.0
    if pct == 50:
        return float(statistics.median(values))
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return float(ordered[f])
    return float(ordered[f] + (k - f) * (ordered[c] - ordered[f]))


def aggregate_by_strategy(
    scored_by_strategy: Dict[str, List[EvaluatedCallRecord]],
) -> List[StrategyComparisonRow]:
    """
    Aggregates scored records by strategy (prompt type) into StrategyComparisonRow items:
      - Accuracy (mean): sum(accuracy) / num_snippets (out of 3)
      - Parse rate: (count(parse_success == True) / num_snippets) * 100 (%)
      - Judge score: sum(llm_judge_score) / num_snippets (out of 25)
      - Cost ($): sum(cost_usd) across calls for that strategy
      - Latency p50 (s): 50th percentile of latency_seconds
    """
    summary_rows: List[StrategyComparisonRow] = []

    for strategy, records in scored_by_strategy.items():
        n = len(records)
        if n == 0:
            summary_rows.append(
                StrategyComparisonRow(
                    strategy=strategy,
                    accuracy_mean=0.0,
                    parse_rate_pct=0.0,
                    judge_score_mean=0.0,
                    total_cost_usd=0.0,
                    latency_p50_seconds=0.0,
                    num_snippets=0,
                )
            )
            continue

        acc_mean = sum(r.accuracy for r in records) / n
        parse_count = sum(1 for r in records if r.parse_success)
        parse_rate = (parse_count / n) * 100.0

        valid_judge_scores = [r.llm_judge_score for r in records if r.llm_judge_score is not None]
        judge_mean = (sum(valid_judge_scores) / n) if valid_judge_scores else 0.0

        total_cost = sum(r.cost_usd for r in records)
        latencies = [r.latency_seconds for r in records]
        p50_latency = percentile(latencies, 50)

        summary_rows.append(
            StrategyComparisonRow(
                strategy=strategy,
                accuracy_mean=round(acc_mean, 2),
                parse_rate_pct=round(parse_rate, 1),
                judge_score_mean=round(judge_mean, 1),
                total_cost_usd=round(total_cost, 6),
                latency_p50_seconds=round(p50_latency, 3),
                num_snippets=n,
            )
        )

    return summary_rows

def print_comparison_table(
    rows: List[StrategyComparisonRow],
    output_path: str | Path = "./out/mp1_comparison.md",
) -> None:
    """Prints the strategy comparison table to stdout and writes it to Markdown."""
    label_map = {
        "zero_shot": "Zero-shot",
        "few_shot": "Few-shot",
        "structured": "Structured",
        "chain_of_thought": "CoT",
    }

    formatted_rows = [
        {
            "Strategy": label_map.get(r.strategy, r.strategy),
            "Accuracy (mean)": f"{r.accuracy_mean:.1f} / 3",
            "Parse rate": f"{r.parse_rate_pct:.0f}%",
            "Judge score": f"{r.judge_score_mean:.1f} / 25",
            "Cost ($)": f"${r.total_cost_usd:.4f}",
            "Latency p50 (s)": f"{r.latency_p50_seconds:.2f}s",
        }
        for r in rows
    ]

    df = pd.DataFrame(formatted_rows)
    print("\n" + df.to_string(index=False))

    headers = list(df.columns)
    md_lines = [
        "## Strategy Comparison Results",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in formatted_rows:
        md_lines.append("| " + " | ".join(str(row[h]) for h in headers) + " |")

    md_path = Path(output_path)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
# ==============================================================================
# 8. ORCHESTRATOR FOR SCRIPTS & JUPYTER NOTEBOOKS
# ==============================================================================

async def run_full_evaluation_pipeline(
    snippets_path: str | Path = "./data/job_snippets.jsonl",
    golden_path: str | Path = "./data/golden_set.jsonl",
    strategies: Optional[List[str]] = None,
    extraction_model: str = EXTRACTION_MODEL,
    judge_model: str = JUDGE_MODEL,
    openai_client: Optional[AsyncOpenAI] = None,
    raw_jsonl_path: str | Path = "./out/LLMCallRecord_data.jsonl",
    scored_jsonl_path: str | Path = "./out/EvaluatedCallRecord_data.jsonl",
    comparison_md_path: str | Path = "./out/llm_extracted_vs_golden_dataset.md"
) -> Dict[str, Any]:
    """
    End-to-end async runner suitable for scripts, notebooks, and Streamlit apps.
    """
    active_client = openai_client or client
    if not os.getenv("OPENAI_API_KEY") and openai_client is None:
        raise EnvironmentError("OPENAI_API_KEY is not set in environment variables.")

    if strategies is None:
        strategies = ["zero_shot", "few_shot", "structured", "chain_of_thought"]

    snippets_list = load_job_snippets(Path(snippets_path))
    golden_by_id = load_golden_set(Path(golden_path))
    snippets_by_id = {item["id"]: item["snippet"] for item in snippets_list}

    # 1. Run async extraction batches
    raw_by_strategy = await run_extraction_batches(
        job_snippets=snippets_list,
        strategies=strategies,
        model=extraction_model,
        openai_client=active_client,
    )
    write_records_jsonl(raw_by_strategy, raw_jsonl_path)

    # 2. Score against golden set + LLM-as-judge
    scored_by_strategy = await score_all_results_async(
        results_by_strategy=raw_by_strategy,
        snippets_by_id=snippets_by_id,
        golden_by_id=golden_by_id,
        judge_model=judge_model,
        openai_client=active_client,
    )
    write_records_jsonl(scored_by_strategy, scored_jsonl_path)

    #3 Render the LLM extracted fileds vs Golden dataset in markdown file for reference 
    render_raw_vs_golden_comparison_to_markdown(
        raw_by_strategy=raw_by_strategy,
        golden_by_id=golden_by_id,
        output_path=comparison_md_path,
    )
    # 4. Aggregate & print comparison table
    comparison_rows = aggregate_by_strategy(scored_by_strategy)
    print_comparison_table(comparison_rows)

    return {
        "raw_by_strategy": raw_by_strategy,
        "scored_by_strategy": scored_by_strategy,
        "comparison_rows": [asdict(row) for row in comparison_rows],
    }

def write_records_jsonl(
    records_by_strategy: Dict[str, List[Any]],
    output_path: str | Path,
) -> Path:
    """Writes dataclass records from each strategy into a .jsonl file with strategy metadata."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for strategy, records in records_by_strategy.items():
            for rec in records:
                row = {"strategy": strategy, **asdict(rec)}
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def format_as_null_if_none(value: Any) -> str:
    if value is None:
        return "null"
    text = str(value).replace("|", "\\|").replace("\n", " ")
    if text.strip().lower() == "none":
        return "null"
    return text


def render_raw_vs_golden_comparison_to_markdown(
    raw_by_strategy: Dict[str, List[LLMCallRecord]],
    golden_by_id: Dict[str, Dict[str, Any]],
    output_path: str | Path = "./out/llm_extracted_vs_golden_dataset.md",
) -> Path:
    """Appends raw extracted fields vs. golden_set.jsonl comparisons per strategy to llm_extracted_vs_golden_dataset.md"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ("company", "role", "years_experience_required")
    lines: List[str] = ["", "## Raw Extraction vs. Golden Set Comparison", ""]

    for strategy, records in raw_by_strategy.items():
        lines.append(f"### Strategy: `{strategy}`")
        lines.append("")
        lines.append(
            "| ID | Status | Company(LLMExtracted) | Company(GoldenDataSet) | Role(LLMExtracted) | Role(GoldenDataSet) | Years(LLMExtracted) | Years(GoldenDataSet) |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")

        for rec in records:
            parsed = rec.parsed_extraction if isinstance(rec.parsed_extraction, dict) else {}
            gold = golden_by_id.get(rec.snippet_id, {})

            mismatches = []
            for field in fields:
                pred_val = parsed.get(field)
                gold_val = gold.get(field)
                if isinstance(pred_val, str) and isinstance(gold_val, str):
                    is_match = pred_val.strip().lower() == gold_val.strip().lower()
                else:
                    is_match = pred_val == gold_val

                if not is_match:
                    mismatches.append(field)

            status = "MATCH" if not mismatches else f"DIFF ({', '.join(mismatches)})"
            row_cells = [
                format_as_null_if_none(rec.snippet_id),
                format_as_null_if_none(status),
                format_as_null_if_none(parsed.get("company")),
                format_as_null_if_none(gold.get("company")),
                format_as_null_if_none(parsed.get("role")),
                format_as_null_if_none(gold.get("role")),
                format_as_null_if_none(parsed.get("years_experience_required")),
                format_as_null_if_none(gold.get("years_experience_required")),
            ]
            lines.append(f"| {' | '.join(row_cells)} |")

        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return path


if __name__ == "__main__":
    asyncio.run(run_full_evaluation_pipeline())