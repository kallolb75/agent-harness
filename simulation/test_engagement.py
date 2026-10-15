"""Tests for the simulated engagement. Fake mode only: no API key, no network."""

import re
from pathlib import Path

import pytest

from simulation import run_engagement as eng

REQUIREMENTS = Path(__file__).parent / "01-meeting" / "requirements.md"


@pytest.fixture(scope="module")
def runs():
    t, i, m = eng.run_triage(False), eng.run_intake(False), eng.run_mapping(False)
    return t, i, m, eng.check_requirements(t, i, m, eng.pii_reaches_model())


def test_every_requirement_from_the_meeting_is_checked(runs):
    in_meeting = set(re.findall(r"^\| (REQ-\d{3}) \|", REQUIREMENTS.read_text(), re.M))
    checked = {rid for rid, _, _ in runs[3]}
    assert in_meeting and in_meeting == checked


def test_no_raw_personal_data_reaches_the_model():
    assert eng.pii_reaches_model() == []


def test_mapping_was_refused_until_it_reconciled(runs):
    m = runs[2]
    assert m["refusals"] >= 1 and m["state"]["reconciled"] and m["state"]["submitted"]


def test_fake_run_meets_what_it_can_and_says_what_it_cannot(runs):
    status = {rid: s for rid, s, _ in runs[3]}
    assert all(status[f"REQ-00{n}"] == "MET" for n in range(1, 9))
    assert status["REQ-009"] == "PARTIAL"
    assert status["REQ-010"] == "READY, NOT APPLIED"
