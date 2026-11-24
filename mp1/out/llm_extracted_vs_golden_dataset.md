
## Raw Extraction vs. Golden Set Comparison

### Strategy: `zero_shot`

| ID | Status | Company(LLMExtracted) | Company(GoldenDataSet) | Role(LLMExtracted) | Role(GoldenDataSet) | Years(LLMExtracted) | Years(GoldenDataSet) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| j01 | MATCH | Acme Corp | Acme Corp | Senior Software Engineer | Senior Software Engineer | 5 | 5 |
| j02 | MATCH | Northwind Ltd | Northwind Ltd | Data Analyst | Data Analyst | 2 | 2 |
| j03 | MATCH | Globex International | Globex International | Product Manager - Growth | Product Manager - Growth | 4 | 4 |
| j04 | MATCH | Initech | Initech | Lead DevOps Engineer | Lead DevOps Engineer | 6 | 6 |
| j05 | DIFF (years_experience_required) | Hooli | Hooli | Junior Frontend Developer | Junior Frontend Developer | null | 0 |
| j06 | MATCH | Pied Piper Inc. | Pied Piper Inc. | Senior ML Engineer | Senior ML Engineer | 7 | 7 |
| j07 | MATCH | Soylent Industries | Soylent Industries | Engineering Manager | Engineering Manager | 3 | 3 |
| j08 | DIFF (company) | Wonka Confectionery Ltd. | Wonka Confectionery Ltd | Senior UX Researcher | Senior UX Researcher | 5 | 5 |
| j09 | DIFF (years_experience_required) | Stark Industries | Stark Industries | Cybersecurity Analyst | Cybersecurity Analyst | 4 | 3 |
| j10 | MATCH | Cyberdyne Systems | Cyberdyne Systems | AI/ML Research Scientist | AI/ML Research Scientist | null | null |

### Strategy: `few_shot`

| ID | Status | Company(LLMExtracted) | Company(GoldenDataSet) | Role(LLMExtracted) | Role(GoldenDataSet) | Years(LLMExtracted) | Years(GoldenDataSet) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| j01 | MATCH | Acme Corp | Acme Corp | Senior Software Engineer | Senior Software Engineer | 5 | 5 |
| j02 | MATCH | Northwind Ltd | Northwind Ltd | Data Analyst | Data Analyst | 2 | 2 |
| j03 | MATCH | Globex International | Globex International | Product Manager - Growth | Product Manager - Growth | 4 | 4 |
| j04 | MATCH | Initech | Initech | Lead DevOps Engineer | Lead DevOps Engineer | 6 | 6 |
| j05 | MATCH | Hooli | Hooli | Junior Frontend Developer | Junior Frontend Developer | 0 | 0 |
| j06 | MATCH | Pied Piper Inc. | Pied Piper Inc. | Senior ML Engineer | Senior ML Engineer | 7 | 7 |
| j07 | MATCH | Soylent Industries | Soylent Industries | Engineering Manager | Engineering Manager | 3 | 3 |
| j08 | MATCH | Wonka Confectionery Ltd | Wonka Confectionery Ltd | Senior UX Researcher | Senior UX Researcher | 5 | 5 |
| j09 | MATCH | Stark Industries | Stark Industries | Cybersecurity Analyst | Cybersecurity Analyst | 3 | 3 |
| j10 | MATCH | Cyberdyne Systems | Cyberdyne Systems | AI/ML Research Scientist | AI/ML Research Scientist | null | null |

### Strategy: `structured`

| ID | Status | Company(LLMExtracted) | Company(GoldenDataSet) | Role(LLMExtracted) | Role(GoldenDataSet) | Years(LLMExtracted) | Years(GoldenDataSet) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| j01 | MATCH | Acme Corp | Acme Corp | Senior Software Engineer | Senior Software Engineer | 5 | 5 |
| j02 | MATCH | Northwind Ltd | Northwind Ltd | Data Analyst | Data Analyst | 2 | 2 |
| j03 | MATCH | Globex International | Globex International | Product Manager - Growth | Product Manager - Growth | 4 | 4 |
| j04 | MATCH | Initech | Initech | Lead DevOps Engineer | Lead DevOps Engineer | 6 | 6 |
| j05 | DIFF (years_experience_required) | Hooli | Hooli | Junior Frontend Developer | Junior Frontend Developer | null | 0 |
| j06 | MATCH | Pied Piper Inc. | Pied Piper Inc. | Senior ML Engineer | Senior ML Engineer | 7 | 7 |
| j07 | MATCH | Soylent Industries | Soylent Industries | Engineering Manager | Engineering Manager | 3 | 3 |
| j08 | DIFF (company) | Wonka Confectionery Ltd. | Wonka Confectionery Ltd | Senior UX Researcher | Senior UX Researcher | 5 | 5 |
| j09 | MATCH | Stark Industries | Stark Industries | Cybersecurity Analyst | Cybersecurity Analyst | 3 | 3 |
| j10 | MATCH | Cyberdyne Systems | Cyberdyne Systems | AI/ML Research Scientist | AI/ML Research Scientist | null | null |

### Strategy: `chain_of_thought`

| ID | Status | Company(LLMExtracted) | Company(GoldenDataSet) | Role(LLMExtracted) | Role(GoldenDataSet) | Years(LLMExtracted) | Years(GoldenDataSet) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| j01 | MATCH | Acme Corp | Acme Corp | Senior Software Engineer | Senior Software Engineer | 5 | 5 |
| j02 | DIFF (company) | Northwind Ltd. | Northwind Ltd | Data Analyst | Data Analyst | 2 | 2 |
| j03 | MATCH | Globex International | Globex International | Product Manager - Growth | Product Manager - Growth | 4 | 4 |
| j04 | MATCH | Initech | Initech | Lead DevOps Engineer | Lead DevOps Engineer | 6 | 6 |
| j05 | DIFF (years_experience_required) | Hooli | Hooli | Junior Frontend Developer | Junior Frontend Developer | null | 0 |
| j06 | MATCH | Pied Piper Inc. | Pied Piper Inc. | Senior ML Engineer | Senior ML Engineer | 7 | 7 |
| j07 | MATCH | Soylent Industries | Soylent Industries | Engineering Manager | Engineering Manager | 3 | 3 |
| j08 | DIFF (company) | Wonka Confectionery Ltd. | Wonka Confectionery Ltd | Senior UX Researcher | Senior UX Researcher | 5 | 5 |
| j09 | DIFF (years_experience_required) | Stark Industries | Stark Industries | Cybersecurity Analyst | Cybersecurity Analyst | 4 | 3 |
| j10 | MATCH | Cyberdyne Systems | Cyberdyne Systems | AI/ML Research Scientist | AI/ML Research Scientist | null | null |
