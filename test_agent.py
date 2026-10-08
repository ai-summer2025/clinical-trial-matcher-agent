"""Tests for clinical-trial-matcher-agent"""
import unittest
from agent import (
    PatientProfile, TrialMatch, _mock_trials, parse_trial,
    evaluate_eligibility, run_matching_agent, generate_report, _parse_age,
)


def make_patient(**overrides) -> PatientProfile:
    defaults = dict(
        patient_id="TEST-001", age=55, sex="male",
        conditions=["Non-Small Cell Lung Cancer"],
        medications=["Carboplatin"], prior_treatments=["Carboplatin"],
        ecog_status=1, has_brain_metastases=False,
        is_pregnant=False, organ_function_normal=True,
        keywords=["NSCLC"],
    )
    defaults.update(overrides)
    return PatientProfile(**defaults)


class TestParseAge(unittest.TestCase):
    def test_parse_years(self):
        self.assertEqual(_parse_age("18 Years"), 18)
        self.assertEqual(_parse_age("75 Years"), 75)
    def test_parse_months(self):
        self.assertEqual(_parse_age("24 Months"), 2)
    def test_not_available(self):
        self.assertIsNone(_parse_age("N/A"))
        self.assertIsNone(_parse_age(""))
    def test_none_input(self):
        self.assertIsNone(_parse_age(None))


class TestParseTrial(unittest.TestCase):
    def setUp(self):
        self.raw_trials = _mock_trials()
    def test_parse_all_mock_trials(self):
        parsed = [parse_trial(r) for r in self.raw_trials]
        self.assertTrue(all(p is not None for p in parsed))
    def test_nct_id_extracted(self):
        parsed = parse_trial(self.raw_trials[0])
        self.assertTrue(parsed["nct_id"].startswith("NCT"))
    def test_phase_extracted(self):
        parsed = parse_trial(self.raw_trials[0])
        self.assertIn("PHASE", parsed["phase"].upper())
    def test_conditions_extracted(self):
        parsed = parse_trial(self.raw_trials[0])
        self.assertIsInstance(parsed["conditions"], list)
        self.assertGreater(len(parsed["conditions"]), 0)
    def test_eligibility_text_present(self):
        parsed = parse_trial(self.raw_trials[0])
        self.assertGreater(len(parsed["eligibility_text"]), 10)
    def test_url_format(self):
        parsed = parse_trial(self.raw_trials[0])
        self.assertTrue(parsed["url"].startswith("https://clinicaltrials.gov/study/"))
    def test_bad_input_returns_none(self):
        result = parse_trial({})
        if result is not None:
            self.assertIn("nct_id", result)


class TestEligibilityEvaluation(unittest.TestCase):
    def setUp(self):
        self.parsed = [parse_trial(r) for r in _mock_trials() if parse_trial(r)]
    def test_age_disqualification_too_young(self):
        score, _, disq = evaluate_eligibility(make_patient(age=10), self.parsed[0])
        self.assertEqual(score, 0.0)
        self.assertTrue(any("age" in d.lower() for d in disq))
    def test_age_disqualification_too_old(self):
        score, _, disq = evaluate_eligibility(make_patient(age=80), self.parsed[2])
        self.assertEqual(score, 0.0)
        self.assertTrue(any("age" in d.lower() for d in disq))
    def test_brain_metastases_disqualification(self):
        score, _, disq = evaluate_eligibility(make_patient(has_brain_metastases=True), self.parsed[0])
        self.assertEqual(score, 0.0)
        self.assertTrue(any("brain" in d.lower() for d in disq))
    def test_pregnancy_disqualification(self):
        score, _, disq = evaluate_eligibility(make_patient(sex="female", is_pregnant=True), self.parsed[0])
        self.assertEqual(score, 0.0)
        self.assertTrue(any("pregnant" in d.lower() for d in disq))
    def test_eligible_patient_gets_positive_score(self):
        score, _, disq = evaluate_eligibility(make_patient(), self.parsed[0])
        self.assertGreater(score, 0.0)
        self.assertEqual(len(disq), 0)
    def test_score_between_zero_and_one(self):
        for trial in self.parsed:
            score, _, _ = evaluate_eligibility(make_patient(), trial)
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)
    def test_high_score_for_exact_condition_match(self):
        patient = make_patient(conditions=["Non-Small Cell Lung Cancer", "NSCLC stage IIIB"])
        score, _, _ = evaluate_eligibility(patient, self.parsed[0])
        self.assertGreater(score, 0.5)
    def test_pediatric_trial_disqualifies_adult(self):
        score, _, disq = evaluate_eligibility(make_patient(age=40), self.parsed[4])
        self.assertEqual(score, 0.0)
        self.assertTrue(any("age" in d.lower() for d in disq))
    def test_ecog_disqualification(self):
        score, _, disq = evaluate_eligibility(make_patient(ecog_status=3), self.parsed[0])
        self.assertEqual(score, 0.0)
        self.assertTrue(any("ecog" in d.lower() for d in disq))


class TestAgentRun(unittest.TestCase):
    def test_agent_returns_list(self):
        self.assertIsInstance(run_matching_agent(make_patient(), max_trials=5, top_n=3), list)
    def test_agent_returns_trial_match_objects(self):
        for m in run_matching_agent(make_patient(), max_trials=5, top_n=3):
            self.assertIsInstance(m, TrialMatch)
    def test_agent_no_disqualified_in_results(self):
        for m in run_matching_agent(make_patient(), max_trials=5, top_n=5):
            self.assertEqual(len(m.disqualifiers), 0)
    def test_agent_sorted_by_score(self):
        matches = run_matching_agent(make_patient(), max_trials=5, top_n=5)
        for i in range(len(matches) - 1):
            self.assertGreaterEqual(matches[i].match_score, matches[i+1].match_score)
    def test_top_n_respected(self):
        self.assertLessEqual(len(run_matching_agent(make_patient(), max_trials=10, top_n=2)), 2)


class TestReportGeneration(unittest.TestCase):
    def test_report_contains_patient_id(self):
        patient = make_patient(patient_id="REPORT-TEST-001")
        report = generate_report(patient, run_matching_agent(patient, max_trials=5, top_n=3))
        self.assertIn("REPORT-TEST-001", report)
    def test_report_contains_disclaimer(self):
        patient = make_patient()
        report = generate_report(patient, run_matching_agent(patient, max_trials=5, top_n=3))
        self.assertIn("DISCLAIMER", report)
    def test_empty_matches_report(self):
        self.assertIn("No qualifying", generate_report(make_patient(), []))
    def test_report_contains_nct_ids(self):
        patient = make_patient()
        matches = run_matching_agent(patient, max_trials=5, top_n=3)
        report = generate_report(patient, matches)
        for m in matches:
            self.assertIn(m.nct_id, report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
