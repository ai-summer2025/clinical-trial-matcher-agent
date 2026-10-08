# 🧬 clinical-trial-matcher-agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![ClinicalTrials.gov](https://img.shields.io/badge/API-ClinicalTrials.gov-orange.svg)](https://clinicaltrials.gov/api/v2/)

**Autonomous agentic AI that matches patients to relevant clinical trials — no paid APIs, no cloud LLM required.**

---

## The Problem

Less than **5% of eligible patients** are enrolled in clinical trials in the United States. The matching process is almost entirely manual: a research coordinator spends **hours or days** searching ClinicalTrials.gov, reading eligibility criteria, and cross-referencing each patient's chart.

The result? Trials fail to enroll. Patients miss potentially life-saving treatments.

---

## How It Works — Agentic Architecture

```
Patient Profile
      │
      ▼
Step 1: Query ClinicalTrials.gov v2 REST API (free, no key)
      │
      ▼
Step 2: Parse trial records (NCT ID, phase, eligibility criteria)
      │
      ▼
Step 3: Eligibility Reasoning Engine
        - Hard disqualifiers: age, sex, brain mets, pregnancy, ECOG
        - Positive signals: condition overlap, eligibility text match
      │
      ▼
Step 4: Rank & Score by match strength
      │
      ▼
Step 5: Generate physician-ready report with match rationale
```

---

## Installation

```bash
git clone https://github.com/ai-summer2025/clinical-trial-matcher-agent.git
cd clinical-trial-matcher-agent
pip install -r requirements.txt
```

Python 3.10+ required. Uses only the standard library (no paid dependencies).

---

## Usage

```bash
# Demo: NSCLC patient
python agent.py --demo demo_nsclc

# Demo: Relapsed lymphoma patient
python agent.py --demo demo_lymphoma

# Custom patient
python agent.py --patient-id PT-001 --age 62 --sex female \
  --conditions "breast cancer,HER2-positive" \
  --prior-treatments "AC-T,Trastuzumab" --ecog 0 --top-n 5
```

---

## Running Tests

```bash
pytest test_agent.py -v
# or: python test_agent.py
```

---

## Why This Matters

| | Manual Process | This Agent |
|---|---|---|
| Time per patient | Hours–Days | Seconds |
| Trials checked | 5–10 | All recruiting |
| Eligibility reasoning | Human memory | Automated multi-step |
| Explainability | None | Score + reasons |

---

## Contributing

Areas most in need: genomic/biomarker matching (EGFR, KRAS, PD-L1), FHIR patient ingestion, distance-based site matching, insurance pre-check.

---

## License

MIT License — free for personal, academic, and commercial use.
