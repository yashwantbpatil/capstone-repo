# MP1 · Prompt Lab — Instructions on running the script and interpreting the results


## What this package contains


| File | Purpose |
|---|---|
| `mp1_prompt_lab.py` | Python script which has end-to-end implementation comparing the four prompting strategies |
| `mp1_writeup.md` | Reflection discussing findings and recommendations |
| `README.md` | Readme about how to run this script and intepret the results |
| `data/job_snippets.jsonl` | 10 job postings (the task input) |
| `data/golden_set.jsonl` | Reference extractions for scoring |
| `requirements.txt` | Python dependencies |
| `out/mp1_comparison.md` | Summary comparison table showing performance metrics (Aggregate by strategy) |
| `out/LLMCallRecord_data.jsonl` | One JSON record per (strategy, snippet_id) extraction call (matching IDs in job_snippets.jsonl), including raw model output, parsed fields, token usage, cost, and latency. |
| `out/EvaluatedCallRecord_data.jsonl` | Per-call evaluation records combining deterministic parse/field accuracy (0–3) against golden_set.jsonl with gpt-4o judge scores (1–25), judge reasoning, and expected values. |
| `out/llm_extracted_vs_golden_dataset.md` | Markdown tables per prompt strategy comparing extracted company, role, and years_experience_required values side by side against golden_set.jsonl (MATCH or DIFF) |



## How to Run

- unzip `Week5_Graded_Mini_Project_YASHWANT_PATIL.zip`
- Navigate into the extracted directory and locate `mp1_prompt_lab.py` file
- Execute the script using your Python environment  
  - Example: run command `python mp1_prompt_lab.py` OR `/bin/python mp1_prompt_lab.py`
## Expected Output & Generated Files
- **Console Output:** Upon successful execution, the script prints the strategy-level comparison table (displaying accuracy, parse rate, judge score, cost, and p50 latency) directly to standard output.
- `out/mp1_comparison.md`: Contains the same aggregated strategy comparison table formatted in Markdown.

- **Additional Reference Files (in out/ directory):**

  - `LLMCallRecord_data.jsonl`: Raw JSON outputs from every LLM extraction call mapped to each snippet ID in job_snippets.jsonl, allowing direct inspection of model responses across prompt strategies.

  - `EvaluatedCallRecord_data.jsonl`: Detailed evaluation records combining deterministic accuracy scores, LLM-as-a-Judge scores, and expected values from the golden dataset for each call in `LLMCallRecord_data.jsonl`.

  - `llm_extracted_vs_golden_dataset.md`: Side-by-side Markdown comparison tables of extracted fields versus the golden dataset per strategy for quick validation and error analysis. 
  
  

## github repo (https://github.com/yashwantbpatil/AI-GenAI)

```
AP-GenAI/
├── mp1/
│   ├── mp1_prompt_lab.py       # Python script which has end-to-end implementation
│   ├── data/                   # directory containing provided data
│   └── mp1_writeup.md          # the 1-page reflection
│   └── requirements.txt        # List of Python packages used
│   └── README.md               # readme about how to run this script and intepret the results
│   └── out/                    # directory containing out files after successfully running the python script mp1_prompt_lab.py 

```

