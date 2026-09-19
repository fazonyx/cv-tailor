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


def test_a_letter_claiming_a_gap_is_refused():
    letter = tmp_pdf("letter").with_suffix(".md")
    letter.write_text("Dear team,\n\nI run Kubernetes clusters in production.\n",
                      encoding="utf-8")
    findings = checks.check_letter(letter, PROFILE)
    assert [f for f in findings if f.level == "error"]


def test_a_letter_denying_a_gap_is_accepted():
    """Naming a gap in order to deny it is the honest move, not a claim."""
    letter = tmp_pdf("letter_honest").with_suffix(".md")
    letter.write_text(
        "Dear team,\n\nI have not run Kubernetes in production. I ship with "
        "Docker and CI, and would need a few weeks in a real cluster.\n",
        encoding="utf-8")
    assert not [f for f in checks.check_letter(letter, PROFILE) if f.level == "error"]


def test_a_missing_translation_on_a_printed_field_is_caught():
    profile = copy.deepcopy(PROFILE)
    for experience in profile["experience"]:
        if experience["id"] == "northbay":
            del experience["bullets"][0]["text"]["fr"]
    target = overlay()
    cv = build(profile, target, "fr")
    findings = checks.check_translations(profile, target, cv, "fr")
    assert any("nb-ingest" in finding.message or "nb-ingest" in str(finding)
               for finding in findings)


def test_a_missing_translation_outside_this_cv_stays_quiet():
    profile = copy.deepcopy(PROFILE)
    for experience in profile["experience"]:
        if experience["id"] == "marlowe":          # not in the overlay
            del experience["bullets"][0]["text"]["fr"]
    target = overlay()
    cv = build(profile, target, "fr")
    assert not checks.check_translations(profile, target, cv, "fr")


def test_an_intentionally_blank_translation_is_allowed():
    profile = copy.deepcopy(PROFILE)
    for experience in profile["experience"]:
        if experience["id"] == "northbay":
            experience["bullets"][0]["text"]["fr"] = ""
    target = overlay()
    cv = build(profile, target, "fr")
    assert not checks.check_translations(profile, target, cv, "fr")


def test_the_photo_is_drawn_when_the_profile_has_one():
    """The photo path is easy to break and invisible in a text diff."""
    from cvkit.render import render

    with_photo = overlay(layout={"left": ["photo", "contact"],
                                 "right": ["experience"]})
    without = overlay(layout={"left": ["contact"], "right": ["experience"]})
    assert Path(PROFILE["contact"]["photo"]).exists()
    photo_margin = render(PROFILE, with_photo, tmp_pdf("photo"))[0][1]
    plain_margin = render(PROFILE, without, tmp_pdf("no_photo"))[0][1]
    assert plain_margin > photo_margin + 25      # the circle takes ~30mm


def test_a_short_gap_term_can_be_matched_case_sensitively():
    """"Go" is a language and a verb; the check has to tell them apart."""
    profile = copy.deepcopy(PROFILE)
    profile["gaps"].append({"term": "Go", "case_sensitive": True, "hedge": "reading level"})
    claimed = overlay(skills=[{"label": "Languages", "value": "Python, Go, SQL"}])
    prose = overlay(skills=[{"label": "Delivery", "value": "Ready to go to production"}])
    assert [f for f in checks.check_gaps(build(profile, claimed), profile)]
    assert not checks.check_gaps(build(profile, prose), profile)


def test_an_open_question_in_the_profile_is_reported():
    draft = tmp_pdf("profile").with_suffix(".yaml")
    draft.write_text(
        '# Questions are marked "# ?" - this header is documentation, not one.\n'
        'availability: "Available in June"   # ? never stated anywhere\n',
        encoding="utf-8")
    findings = checks.check_open_questions(draft)
    assert len(findings) == 1 and findings[0].level == "warning"
    assert "availability" in findings[0].message


def test_a_salaried_job_shows_both_its_title_and_its_framing():
    """Without this, a `role:` override is dropped for anyone not a consultant."""
    from pypdf import PdfReader

    from cvkit.render import render

    profile = copy.deepcopy(PROFILE)
    profile["experience"] = [{
        "id": "solo", "employer": "ACME", "employer_role": "QA Engineer",
        "city": "Toulouse", "period": "2022 - present",
        "bullets": [{"id": "b1", "text": "Ran the release test suite."}],
    }]
    target = {"experience": {"include": ["solo"],
                             "overrides": {"solo": {"role": "Test infrastructure & CI",
                                                    "bullets": [{"from": "b1"}]}}}}
    output = tmp_pdf("salaried")
    render(profile, target, output)
    text = PdfReader(str(output)).pages[0].extract_text()
    assert "QA Engineer" in text          # the contract title, a fact
    assert "Test infrastructure" in text  # the framing for this offer
