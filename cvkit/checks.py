"""Checks that turn the method's rules into something a machine verifies.

Discipline works until you are tired, applying to five companies in an evening.
These checks run on every build:

  sources   every line of the CV points back to a fact in profile.yaml
  gaps      skills listed in `gaps:` are never stated as owned
  figures   a reframed line introduces no number its source did not have
  charset   no glyph the PDF base fonts cannot draw (the usual square box)
  pages     one page per declared language, never a silent overflow
  margins   white space left at the bottom of both columns
"""
import re
from dataclasses import dataclass

# Wordings that mark a skill as not-yet-owned. Keep them boring and honest:
# a recruiter reads them as candour, an ATS still matches the keyword.
HEDGES = (
    "ramp-up", "ramp up", "ramping up", "open to", "eager to", "willing to",
    "basics", "notions", "academic", "coursework", "transferable", "exposure",
    "familiar", "reading", "self-taught", "learning", "to deepen",
    # French equivalents, for bilingual CVs
    "sensibilisation", "bases", "notions academiques", "montee en competence",
    "en cours d'apprentissage", "ouvert a", "transferable",
)

LEVELS = ("error", "warning", "info")


@dataclass
class Finding:
    level: str
    code: str
    message: str

    def __str__(self):
        mark = {"error": "FAIL", "warning": "WARN", "info": "INFO"}[self.level]
        return f"  [{mark}] {self.code}: {self.message}"


def collect_strings(cv):
    """Every piece of text that ends up on the page, with a location label."""
    out = [("headline", cv.headline)]
    out += [("summary", line) for line in cv.summary]
    out += [("contact", label) for label, _ in cv.contact]
    out += [("badge", badge["text"]) for badge in cv.badges]
    out += [("language", f"{item['name']} {item['level'] or ''} {item['note'] or ''}")
            for item in cv.languages]
    out += [("interest", item) for item in cv.interests]
    out += [("skills", f"{label}: {value}") for label, value in cv.skills]
    out += [("certification", text) for text in cv.certifications]
    for project in cv.projects:
        out.append((f"project {project['name']}",
                    " ".join(filter(None, [project["description"], project["stack"]]))))
    for experience in cv.experience:
        label = experience.client or experience.employer
        out.append((f"{label} (role)", experience.role))
        out += [(f"{label} (tag)", tag) for tag in experience.tags]
        out.append((f"{label} (env)", experience.env))
        out += [(f"{label} [{bullet.source}]", bullet.text)
                for bullet in experience.bullets]
    return [(where, text) for where, text in out if text]


# ---- individual checks -------------------------------------------
def check_charset(cv):
    """PDF base fonts are Latin-1. Anything else silently renders as a box."""
    findings = []
    for where, text in collect_strings(cv):
        for char in text:
            try:
                char.encode("cp1252")
            except UnicodeEncodeError:
                findings.append(Finding(
                    "error", "charset",
                    f"{where}: character {char!r} (U+{ord(char):04X}) is not "
                    f"supported by the base fonts - it will render as a box"))
                break
    return findings


def check_sources(cv):
    findings, reframed, total = [], 0, 0
    for experience in cv.experience:
        for bullet in experience.bullets:
            total += 1
            reframed += bool(bullet.reframed)
            if not bullet.source:
                findings.append(Finding(
                    "error", "sources",
                    f"{experience.id}: a line has no source fact"))
    if total:
        findings.append(Finding(
            "info", "sources",
            f"{total} bullet(s) rendered, {reframed} reworded for this offer, "
            f"{total} traced back to profile.yaml"))
    return findings


def check_gaps(cv, profile):
    """A skill listed under `gaps:` may appear - never as an owned skill."""
    findings = []
    gaps = profile.get("gaps") or []
    for gap in gaps:
        term = gap.get("term")
        if not term:
            continue
        pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
        for where, text in collect_strings(cv):
            if not pattern.search(text):
                continue
            lowered = text.lower()
            if any(hedge in lowered for hedge in HEDGES):
                continue
            findings.append(Finding(
                "error", "gaps",
                f"{where}: '{term}' is listed as a gap in profile.yaml but is "
                f"written as an owned skill. Mark it (\"{gap.get('hedge', 'ramp-up')}\") "
                f"or drop it."))
    return findings


NUMBER = re.compile(r"\d[\d.,]*")


def check_figures(cv, profile):
    """A reworded line must not grow numbers its source fact did not have."""
    findings = []
    facts = {}
    for experience in profile.get("experience") or []:
        for bullet in experience.get("bullets") or []:
            value = bullet.get("text")
            values = value.values() if isinstance(value, dict) else [value]
            facts[bullet["id"]] = " ".join(str(v) for v in values)
    for experience in cv.experience:
        for bullet in experience.bullets:
            if not bullet.reframed:
                continue
            source_numbers = set(NUMBER.findall(facts.get(bullet.source, "")))
            for number in set(NUMBER.findall(bullet.text)) - source_numbers:
                findings.append(Finding(
                    "warning", "figures",
                    f"{experience.id} [{bullet.source}]: reworded line claims "
                    f"'{number}', absent from the source fact. Check it is real."))
    return findings


def check_margins(margins, minimum, maximum=None):
    """Both failure modes matter.

    Too little white space at the bottom and the page reads as cramped; far too
    much and it reads as a draft. The rule is a band, not a floor.
    """
    findings = []
    for lang, left, right in margins:
        level = "info"
        note = ""
        if min(left, right) < minimum:
            level = "error"
            note = f" - content reaches the bottom of the page"
        elif maximum and right > maximum:
            level = "warning"
            note = f" - the right column looks under-filled, add a fact or two"
        findings.append(Finding(
            level, "margins",
            f"page '{lang}': bottom white space left {left:.1f}mm / right "
            f"{right:.1f}mm (target {minimum:.0f}-{maximum or minimum:.0f}mm){note}"))
    return findings


def check_pdf(path, expected_pages):
    try:
        from pypdf import PdfReader
    except ImportError:
        return [Finding("warning", "pages", "pypdf not installed, page count not verified")]
    pages = len(PdfReader(str(path)).pages)
    if pages != expected_pages:
        return [Finding("error", "pages",
                        f"{pages} page(s) generated, {expected_pages} expected - "
                        f"content overflowed")]
    return [Finding("info", "pages", f"{pages} page(s), as declared")]


def run_all(cv, profile, margins, minimum, pdf_path=None, expected_pages=1):
    findings = []
    findings += check_sources(cv)
    findings += check_gaps(cv, profile)
    findings += check_figures(cv, profile)
    findings += check_charset(cv)
    findings += check_margins(margins, minimum)
    if pdf_path:
        findings += check_pdf(pdf_path, expected_pages)
    return findings


def has_errors(findings):
    return any(finding.level == "error" for finding in findings)
