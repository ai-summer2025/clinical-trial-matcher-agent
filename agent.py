#!/usr/bin/env python3
"""
clinical-trial-matcher-agent
Agentic AI system that autonomously matches patients to relevant clinical trials
using the ClinicalTrials.gov v2 REST API and multi-step eligibility reasoning.
"""

import json
import re
import sys
import time
import argparse
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, date
from typing import Optional
from dataclasses import dataclass, field, asdict


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PatientProfile:
    """Structured patient profile used for matching."""
    patient_id: str
    age: int
    sex: str                          # "male" | "female" | "other"
    conditions: list[str]             # ICD-10 descriptions or free text
    medications: list[str]            # current meds
    prior_treatments: list[str]       # chemotherapy regimens, surgeries, etc.
    ecog_status: int                  # 0-4  (0 = fully active)
    has_brain_metastases: bool = False
    is_pregnant: bool = False
    organ_function_normal: bool = True
    keywords: list[str] = field(default_factory=list)  # extra search terms


@dataclass
class TrialMatch:
    nct_id: str
    title: str
    phase: str
    status: str
    conditions: list[str]
    interventions: list[str]
    eligibility_summary: str
    match_score: float                # 0.0 – 1.0
    match_reasons: list[str]
    disqualifiers: list[str]
    url: str


# ---------------------------------------------------------------------------
# Step 1 – Query ClinicalTrials.gov API
# ---------------------------------------------------------------------------

CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"

def _ctgov_get(params: dict, retries: int = 3) -> dict:
    """Low-level HTTP GET against ClinicalTrials.gov v2 API."""
    url = CTGOV_API + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise RuntimeError(f"ClinicalTrials.gov API unreachable: {exc}") from exc
    return {}


def fetch_trials(patient: PatientProfile, max_trials: int = 20) -> list[dict]:
    """
    AGENT STEP 1 – Retrieve candidate trials from ClinicalTrials.gov.
    Builds a query from the patient's conditions and keywords.
    """
    print(f"\n[Step 1] Querying ClinicalTrials.gov for patient {patient.patient_id} ...")
    condition_query = " OR ".join(patient.conditions[:3])
    params = {
        "query.cond": condition_query,
        "filter.overallStatus": "RECRUITING",
        "fields": (
            "NCTId,BriefTitle,Phase,OverallStatus,"
            "Condition,InterventionName,InterventionType,"
            "EligibilityCriteria,MinimumAge,MaximumAge,Sex,"
            "LeadSponsorName,StartDate,CompletionDate"
        ),
        "pageSize": max_trials,
        "format": "json",
    }
    try:
        data = _ctgov_get(params)
    except RuntimeError as exc:
        print(f"  [warn] Live API unavailable ({exc}). Using mock data for demo.")
        return _mock_trials()
    studies = data.get("studies", [])
    print(f"  Found {len(studies)} recruiting trials for condition query.")
    return studies


def _mock_trials() -> list[dict]:
    """Realistic mock trials when the live API is unavailable (e.g. offline demo)."""
    return [
        {
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT09000001",
                    "briefTitle": "Pembrolizumab Plus Chemotherapy in Advanced NSCLC (Mock Trial A)",
                },
                "statusModule": {"overallStatus": "RECRUITING"},
                "designModule": {"phases": ["PHASE3"]},
                "conditionsModule": {"conditions": ["Non-Small Cell Lung Cancer"]},
                "armsInterventionsModule": {
                    "interventions": [
                        {"name": "Pembrolizumab", "type": "BIOLOGICAL"},
                        {"name": "Carboplatin", "type": "DRUG"},
                    ]
                },
                "eligibilityModule": {
                    "eligibilityCriteria": (
                        "Inclusion Criteria:\n"
                        "- Histologically confirmed NSCLC stage IIIB/IV\n"
                        "- Age >= 18 years\n"
                        "- ECOG performance status 0 or 1\n"
                        "- No prior systemic treatment for advanced NSCLC\n"
                        "Exclusion Criteria:\n"
                        "- Active brain metastases\n"
                        "- Pregnancy or lactation\n"
                        "- Severe autoimmune disease\n"
                    ),
                    "minimumAge": "18 Years",
                    "maximumAge": "N/A",
                    "sex": "ALL",
                },
            }
        },
        {
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT09000002",
                    "briefTitle": "Osimertinib in EGFR-Mutated Lung Cancer (Mock Trial B)",
                },
                "statusModule": {"overallStatus": "RECRUITING"},
                "designModule": {"phases": ["PHASE2"]},
                "conditionsModule": {"conditions": ["Non-Small Cell Lung Cancer", "EGFR mutation"]},
                "armsInterventionsModule": {
                    "interventions": [{"name": "Osimertinib", "type": "DRUG"}]
                },
                "eligibilityModule": {
                    "eligibilityCriteria": (
                        "Inclusion Criteria:\n"
                        "- EGFR exon 19 deletion or L858R mutation confirmed\n"
                        "- Age >= 18 years\n"
                        "- ECOG 0-2\n"
                        "- No prior EGFR-TKI therapy\n"
                        "Exclusion Criteria:\n"
                        "- T790M mutation present\n"
                        "- Active interstitial lung disease\n"
                    ),
                    "minimumAge": "18 Years",
                    "maximumAge": "N/A",
                    "sex": "ALL",
                },
            }
        },
        {
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT09000003",
                    "briefTitle": "CAR-T Cell Therapy for Relapsed B-Cell Lymphoma (Mock Trial C)",
                },
                "statusModule": {"overallStatus": "RECRUITING"},
                "designModule": {"phases": ["PHASE2"]},
                "conditionsModule": {"conditions": ["Diffuse Large B-Cell Lymphoma"]},
                "armsInterventionsModule": {
                    "interventions": [{"name": "Axicabtagene ciloleucel", "type": "BIOLOGICAL"}]
                },
                "eligibilityModule": {
                    "eligibilityCriteria": (
                        "Inclusion Criteria:\n"
                        "- Relapsed/refractory DLBCL after >= 2 prior lines\n"
                        "- Age 18-75\n"
                        "- ECOG 0-1\n"
                        "- Adequate organ function (liver, renal, cardiac)\n"
                        "Exclusion Criteria:\n"
                        "- Active CNS lymphoma\n"
                        "- Prior CAR-T therapy\n"
                        "- Pregnancy\n"
                    ),
                    "minimumAge": "18 Years",
                    "maximumAge": "75 Years",
                    "sex": "ALL",
                },
            }
        },
        {
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT09000004",
                    "briefTitle": "Durvalumab Maintenance After CRT in NSCLC (Mock Trial D)",
                },
                "statusModule": {"overallStatus": "RECRUITING"},
                "designModule": {"phases": ["PHASE3"]},
                "conditionsModule": {"conditions": ["Non-Small Cell Lung Cancer", "Stage III"]},
                "armsInterventionsModule": {
                    "interventions": [{"name": "Durvalumab", "type": "BIOLOGICAL"}]
                },
                "eligibilityModule": {
                    "eligibilityCriteria": (
                        "Inclusion Criteria:\n"
                        "- Unresectable Stage III NSCLC\n"
                        "- No disease progression after CRT\n"
                        "- Age >= 18\n"
                        "- ECOG 0-1\n"
                        "Exclusion Criteria:\n"
                        "- Prior immunotherapy\n"
                        "- Active autoimmune disease requiring systemic treatment\n"
                        "- Pregnancy\n"
                    ),
                    "minimumAge": "18 Years",
                    "maximumAge": "N/A",
                    "sex": "ALL",
                },
            }
        },
        {
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT09000005",
                    "briefTitle": "Pediatric NSCLC Targeted Therapy Study (Mock Trial E)",
                },
                "statusModule": {"overallStatus": "RECRUITING"},
                "designModule": {"phases": ["PHASE1"]},
                "conditionsModule": {"conditions": ["Non-Small Cell Lung Cancer"]},
                "armsInterventionsModule": {
                    "interventions": [{"name": "Crizotinib", "type": "DRUG"}]
                },
                "eligibilityModule": {
                    "eligibilityCriteria": (
                        "Inclusion Criteria:\n"
                        "- Age 1-17 years\n"
                        "- ALK or ROS1 rearrangement\n"
                        "Exclusion Criteria:\n"
                        "- Age >= 18\n"
                        "- Prior ALK inhibitor\n"
                    ),
                    "minimumAge": "1 Year",
                    "maximumAge": "17 Years",
                    "sex": "ALL",
                },
            }
        },
    ]


# ---------------------------------------------------------------------------
# Step 2 – Parse each trial into a structured object
# ---------------------------------------------------------------------------

def parse_trial(raw: dict) -> Optional[dict]:
    """Extract structured fields from a raw ClinicalTrials API response."""
    try:
        ps = raw.get("protocolSection", raw)
        id_mod = ps.get("identificationModule", {})
        status_mod = ps.get("statusModule", {})
        design_mod = ps.get("designModule", {})
        cond_mod = ps.get("conditionsModule", {})
        arms_mod = ps.get("armsInterventionsModule", {})
        elig_mod = ps.get("eligibilityModule", {})
        nct_id = id_mod.get("nctId", "UNKNOWN")
        title = id_mod.get("briefTitle", "Untitled")
        status = status_mod.get("overallStatus", "UNKNOWN")
        phases = design_mod.get("phases", ["N/A"])
        phase = phases[0] if phases else "N/A"
        conditions = cond_mod.get("conditions", [])
        interventions = [i.get("name", "") for i in arms_mod.get("interventions", [])]
        elig_text = elig_mod.get("eligibilityCriteria", "")
        min_age_str = elig_mod.get("minimumAge", "0 Years")
        max_age_str = elig_mod.get("maximumAge", "N/A")
        sex_req = elig_mod.get("sex", "ALL")
        return {
            "nct_id": nct_id,
            "title": title,
            "status": status,
            "phase": phase,
            "conditions": conditions,
            "interventions": interventions,
            "eligibility_text": elig_text,
            "min_age": _parse_age(min_age_str),
            "max_age": _parse_age(max_age_str),
            "sex_req": sex_req.upper(),
            "url": f"https://clinicaltrials.gov/study/{nct_id}",
        }
    except Exception:
        return None


def _parse_age(age_str: str) -> Optional[int]:
    """Convert '18 Years' to 18, 'N/A' to None."""
    if not age_str or age_str.upper() in ("N/A", ""):
        return None
    match = re.search(r"(\d+)", age_str)
    if match:
        value = int(match.group(1))
        if "month" in age_str.lower():
            return max(1, value // 12)
        return value
    return None


# ---------------------------------------------------------------------------
# Step 3 – Eligibility reasoning engine (the core agent loop)
# ---------------------------------------------------------------------------

EXCLUSION_SIGNALS = [
    ("brain_metastases", ["brain metastasis", "brain metastases", "cns metastasis", "active cns"]),
    ("pregnancy", ["pregnancy", "pregnant", "lactation", "breastfeeding"]),
    ("prior_immunotherapy", ["prior immunotherapy", "prior checkpoint", "prior anti-pd"]),
    ("prior_car_t", ["prior car-t", "prior cart", "chimeric antigen receptor"]),
    ("severe_organ_dysfunction", ["severe hepatic impairment", "renal failure", "severe organ"]),
    ("autoimmune", ["active autoimmune", "systemic autoimmune", "severe autoimmune"]),
]


def evaluate_eligibility(patient: PatientProfile, trial: dict) -> tuple[float, list[str], list[str]]:
    """Multi-step eligibility reasoning. Returns (score, match_reasons, disqualifiers)."""
    reasons: list[str] = []
    disqualifiers: list[str] = []

    elig_lower = trial["eligibility_text"].lower()

    if trial["min_age"] is not None and patient.age < trial["min_age"]:
        disqualifiers.append(f"Patient age {patient.age} < minimum {trial['min_age']}")
    if trial["max_age"] is not None and patient.age > trial["max_age"]:
        disqualifiers.append(f"Patient age {patient.age} > maximum {trial['max_age']}")

    sex_req = trial["sex_req"]
    if sex_req not in ("ALL", ""):
        patient_sex = patient.sex.upper()
        if patient_sex == "MALE" and sex_req == "FEMALE":
            disqualifiers.append("Trial enrolls females only")
        elif patient_sex == "FEMALE" and sex_req == "MALE":
            disqualifiers.append("Trial enrolls males only")

    if patient.has_brain_metastases:
        for sig in EXCLUSION_SIGNALS[0][1]:
            if sig in elig_lower:
                disqualifiers.append("Patient has brain metastases (excluded by trial)")
                break

    if patient.is_pregnant:
        for sig in EXCLUSION_SIGNALS[1][1]:
            if sig in elig_lower:
                disqualifiers.append("Patient is pregnant (excluded by trial)")
                break

    if not patient.organ_function_normal:
        for sig in EXCLUSION_SIGNALS[4][1]:
            if sig in elig_lower:
                disqualifiers.append("Abnormal organ function may disqualify patient")
                break

    ecog_match = re.search(r"ecog\s*(?:performance\s*status)?\s*(?:of\s*)?(\d)(?:\s*(?:or|-)\s*(\d))?", elig_lower)
    if ecog_match:
        max_ecog = int(ecog_match.group(2) or ecog_match.group(1))
        if patient.ecog_status > max_ecog:
            disqualifiers.append(f"Patient ECOG {patient.ecog_status} exceeds trial maximum {max_ecog}")

    if disqualifiers:
        return 0.0, reasons, disqualifiers

    score = 0.3
    trial_cond_lower = " ".join(c.lower() for c in trial["conditions"])
    condition_overlap = 0
    for cond in patient.conditions:
        for word in cond.lower().split():
            if len(word) > 4 and word in trial_cond_lower:
                condition_overlap += 1
                break
    if condition_overlap > 0:
        score += 0.3
        reasons.append(f"Condition overlap: {condition_overlap} matching condition(s)")

    text_hits = []
    for cond in patient.conditions:
        for word in cond.lower().split():
            if len(word) > 4 and word in elig_lower:
                text_hits.append(word)
                break
    if text_hits:
        score += 0.2
        reasons.append(f"Eligibility text mentions patient conditions: {', '.join(set(text_hits))}")

    for trt in patient.prior_treatments:
        if trt.lower() in elig_lower:
            reasons.append(f"Prior treatment '{trt}' mentioned in eligibility criteria")
            score += 0.1
            break

    if "PHASE3" in trial["phase"].upper() or "PHASE2" in trial["phase"].upper():
        reasons.append(f"Trial is {trial['phase']} (more developed)")
        score += 0.1

    score = min(score, 1.0)
    if not reasons:
        reasons.append("Passed all basic eligibility filters")

    return round(score, 2), reasons, disqualifiers


# ---------------------------------------------------------------------------
# Step 4 – Orchestrate the full agent loop
# ---------------------------------------------------------------------------

def run_matching_agent(patient: PatientProfile, max_trials: int = 20, top_n: int = 5) -> list[TrialMatch]:
    """Full agent loop: fetch, parse, evaluate, rank, return top N."""
    print(f"\n{'='*60}")
    print(f"  Clinical Trial Matcher Agent")
    print(f"  Patient: {patient.patient_id}  |  Age: {patient.age}  |  Sex: {patient.sex}")
    print(f"  Conditions: {', '.join(patient.conditions)}")
    print(f"{'='*60}")

    raw_trials = fetch_trials(patient, max_trials=max_trials)

    print(f"\n[Step 2] Parsing {len(raw_trials)} trial records ...")
    parsed = [t for r in raw_trials if (t := parse_trial(r)) is not None]
    print(f"  Successfully parsed {len(parsed)} trials.")

    print(f"\n[Step 3] Running eligibility reasoning on {len(parsed)} trials ...")
    matches: list[TrialMatch] = []
    for trial in parsed:
        score, reasons, disqualifiers = evaluate_eligibility(patient, trial)
        matches.append(TrialMatch(
            nct_id=trial["nct_id"],
            title=trial["title"],
            phase=trial["phase"],
            status=trial["status"],
            conditions=trial["conditions"],
            interventions=trial["interventions"],
            eligibility_summary=trial["eligibility_text"][:300].strip() + "...",
            match_score=score,
            match_reasons=reasons,
            disqualifiers=disqualifiers,
            url=trial["url"],
        ))

    print(f"\n[Step 4] Ranking trials by match score ...")
    qualified = sorted([m for m in matches if not m.disqualifiers], key=lambda x: x.match_score, reverse=True)
    disqualified = [m for m in matches if m.disqualifiers]
    print(f"  Qualified: {len(qualified)}  |  Disqualified: {len(disqualified)}")

    return qualified[:top_n]


# ---------------------------------------------------------------------------
# Step 5 – Report generation
# ---------------------------------------------------------------------------

def generate_report(patient: PatientProfile, matches: list[TrialMatch]) -> str:
    """Generate a structured physician-ready report."""
    lines = []
    lines.append("=" * 70)
    lines.append("  CLINICAL TRIAL MATCHING REPORT")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 70)

    lines.append(f"\nPATIENT PROFILE")
    lines.append(f"  ID:              {patient.patient_id}")
    lines.append(f"  Age / Sex:       {patient.age} / {patient.sex}")
    lines.append(f"  ECOG:            {patient.ecog_status}")
    lines.append(f"  Conditions:      {', '.join(patient.conditions)}")
    lines.append(f"  Medications:     {', '.join(patient.medications) or 'None listed'}")
    lines.append(f"  Prior Tx:        {', '.join(patient.prior_treatments) or 'None'}")
    lines.append(f"  Brain Mets:      {'Yes' if patient.has_brain_metastases else 'No'}")

    if not matches:
        lines.append("\n  No qualifying trials found. Consider broadening search criteria.")
        return "\n".join(lines)

    lines.append(f"\nTOP MATCHED TRIALS ({len(matches)} found)")
    lines.append("-" * 70)

    for rank, m in enumerate(matches, 1):
        stars = "★" * round(m.match_score * 5)
        lines.append(f"\n#{rank}  [{m.nct_id}]  Score: {m.match_score:.2f}  {stars}")
        lines.append(f"    Title:         {m.title}")
        lines.append(f"    Phase/Status:  {m.phase} / {m.status}")
        lines.append(f"    Conditions:    {', '.join(m.conditions[:3])}")
        lines.append(f"    Interventions: {', '.join(m.interventions[:3]) or 'N/A'}")
        lines.append(f"    Why matched:")
        for r in m.match_reasons:
            lines.append(f"      - {r}")
        lines.append(f"    URL:           {m.url}")

    lines.append("\n" + "=" * 70)
    lines.append("DISCLAIMER: This report is for investigational matching only.")
    lines.append("Final eligibility must be confirmed by the trial site coordinator.")
    lines.append("=" * 70)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

DEMO_PATIENTS = {
    "demo_nsclc": PatientProfile(
        patient_id="PT-2026-001", age=58, sex="male",
        conditions=["Non-Small Cell Lung Cancer", "NSCLC stage IIIB"],
        medications=["Carboplatin", "Paclitaxel"],
        prior_treatments=["Carboplatin", "Paclitaxel"],
        ecog_status=1, has_brain_metastases=False, is_pregnant=False,
        organ_function_normal=True,
        keywords=["NSCLC", "lung cancer", "immunotherapy"],
    ),
    "demo_lymphoma": PatientProfile(
        patient_id="PT-2026-002", age=42, sex="female",
        conditions=["Diffuse Large B-Cell Lymphoma", "DLBCL relapsed"],
        medications=["Rituximab"],
        prior_treatments=["R-CHOP", "R-ICE"],
        ecog_status=1, has_brain_metastases=False, is_pregnant=False,
        organ_function_normal=True,
        keywords=["DLBCL", "lymphoma", "CAR-T"],
    ),
}


def main():
    parser = argparse.ArgumentParser(description="Clinical Trial Matcher Agent")
    parser.add_argument("--demo", choices=list(DEMO_PATIENTS.keys()))
    parser.add_argument("--patient-id", default="PT-CUSTOM")
    parser.add_argument("--age", type=int, default=55)
    parser.add_argument("--sex", choices=["male", "female", "other"], default="male")
    parser.add_argument("--conditions", default="lung cancer")
    parser.add_argument("--medications", default="")
    parser.add_argument("--prior-treatments", default="")
    parser.add_argument("--ecog", type=int, default=1)
    parser.add_argument("--max-trials", type=int, default=20)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--output", help="Save report to file")
    args = parser.parse_args()

    if args.demo:
        patient = DEMO_PATIENTS[args.demo]
    else:
        patient = PatientProfile(
            patient_id=args.patient_id, age=args.age, sex=args.sex,
            conditions=[c.strip() for c in args.conditions.split(",") if c.strip()],
            medications=[m.strip() for m in args.medications.split(",") if m.strip()],
            prior_treatments=[t.strip() for t in args.prior_treatments.split(",") if t.strip()],
            ecog_status=args.ecog,
        )

    matches = run_matching_agent(patient, max_trials=args.max_trials, top_n=args.top_n)
    report = generate_report(patient, matches)

    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"\nReport saved to {args.output}")
    else:
        print("\n" + report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
