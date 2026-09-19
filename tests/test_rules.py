"""The guardrails are the product, so they get the tests.

    pip install pytest && python -m pytest tests -q
"""
import copy
import tempfile
from pathlib import Path

import pytest

from cvkit import checks
from cvkit.model import RuleViolation, build, load_yaml

PROFILE = load_yaml("profile/profile.example.yaml")


def tmp_pdf(name):
    return Path(tempfile.gettempdir()) / f"cv_tailor_{name}.pdf"


def overlay(**extra):
    base = {
        "experience": {
            "include": ["northbay"],
            "overrides": {"northbay": {"bullets": [{"from": "nb-ingest"}]}},
        }
    }
    base.update(extra)
    return base


def test_a_bullet_must_point_to_a_fact():
    target = overlay()
    target["experience"]["overrides"]["northbay"]["bullets"] = [
        {"text": "Led a team of twelve engineers."}
    ]
    with pytest.raises(RuleViolation, match="no 'from:' field"):
        build(PROFILE, target)


def test_a_bullet_cannot_invent_a_source():
    target = overlay()
    target["experience"]["overrides"]["northbay"]["bullets"] = [{"from": "nb-nonexistent"}]
    with pytest.raises(RuleViolation, match="unknown fact"):
        build(PROFILE, target)


@pytest.mark.parametrize("field", ["employer", "employer_role", "period", "client", "city"])
def test_an_overlay_cannot_rewrite_a_fact(field):
    target = overlay()
    target["experience"]["overrides"]["northbay"][field] = "Senior Staff Engineer"
    with pytest.raises(RuleViolation, match="locked"):
        build(PROFILE, target)


def test_education_cannot_be_rewritten():
    with pytest.raises(RuleViolation):
        build(PROFILE, overlay(education={"overrides": {"imi": {"degree": "PhD"}}}))


def test_a_mission_role_can_be_reframed():
    """The mission description is framing, not a title: this one is allowed."""
    target = overlay()
    target["experience"]["overrides"]["northbay"]["role"] = "Backend Engineer - Telemetry"
    cv = build(PROFILE, target)
    assert cv.experience[0].role == "Backend Engineer - Telemetry"
    assert cv.experience[0].employer_role == "Software Engineer (consultant)"


def test_a_gap_stated_as_owned_fails():
    target = overlay(skills=[{"label": "Infra", "value": "Docker, Kubernetes, GitLab CI"}])
    findings = checks.check_gaps(build(PROFILE, target), PROFILE)
    assert [f for f in findings if f.level == "error"]


def test_a_gap_with_a_marker_passes():
    target = overlay(skills=[{"label": "Infra", "value": "Docker (Kubernetes: ramp-up)"}])
    assert not checks.check_gaps(build(PROFILE, target), PROFILE)


def test_a_reworded_line_growing_a_number_is_flagged():
    target = overlay()
    target["experience"]["overrides"]["northbay"]["bullets"] = [
        {"from": "nb-ingest", "text": "Built the ingestion service for 40,000 vehicles."}
    ]
    findings = checks.check_figures(build(PROFILE, target), PROFILE)
    assert any("40,000" in finding.message for finding in findings)


def test_an_undrawable_character_is_caught():
    profile = copy.deepcopy(PROFILE)
    profile["identity"]["headline"] = {"en": "Backend Engineer ▶ APIs"}
    findings = checks.check_charset(build(profile, overlay()))
    assert [f for f in findings if f.level == "error"]


def test_margins_flag_both_a_full_page_and_an_empty_one():
    cramped = checks.check_margins([("en", 40.0, 9.0)], 15, 45)
    empty = checks.check_margins([("en", 40.0, 80.0)], 15, 45)
    assert cramped[0].level == "error"
    assert empty[0].level == "warning"


def test_a_forbidden_term_is_refused_even_when_marked():
    profile = copy.deepcopy(PROFILE)
    profile["gaps"].append({"term": "Assembly", "forbidden": True})
    target = overlay(skills=[{"label": "Languages", "value": "C, Assembly: basics"}])
    findings = checks.check_gaps(build(profile, target), profile)
    assert any("forbidden" in finding.message for finding in findings)


def test_the_type_scale_drives_vertical_space():
    """Shrinking the type must actually free room, or the knob is a lie."""
    from cvkit.render import render

    target = overlay(output="", pages=["en"])
    tight = dict(target, theme={"size_body": 6.5, "leading": 1.15})
    roomy_margin = render(PROFILE, target, tmp_pdf("roomy"))[0][2]
    tight_margin = render(PROFILE, tight, tmp_pdf("tight"))[0][2]
    assert tight_margin > roomy_margin + 2
