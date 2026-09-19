"""Checks that turn the method's rules into something a machine verifies.

Discipline works until you are tired, applying to five companies in an evening.
These checks run on every build:

  sources   every line of the CV points back to a fact in profile.yaml
  gaps      skills listed in `gaps:` are never stated as owned
  figures   a reframed line introduces no number its source did not have
  charset   no glyph the PDF base fonts cannot draw (the usual square box)
  pages     one page per declared language, never a silent overflow
  margins   white space left at the bottom of both columns
  letter    the cover letter is held to the same honesty rules as the CV
  i18n      no field silently printed in the wrong language
"""
import re
from dataclasses import dataclass
from pathlib import Path

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

# A cover letter is allowed to name a gap in order to deny it - that is the
# honest move, and it must not be reported as a claim.
NEGATIONS = (
    " not ", "n't ", "never", " no ", "without", "yet to",
    " pas ", "jamais", "aucun", "sans ",
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
    return scan_charset(collect_strings(cv))


def scan_charset(entries, code="charset"):
    findings = []
    for where, text in entries:
        for char in text:
            try:
                char.encode("cp1252")
            except UnicodeEncodeError:
                findings.append(Finding(
                    "error", code,
                    f"{where}: character {ascii(char)} (U+{ord(char):04X}) is not "
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
    """Two kinds of entry under `gaps:`.

    The default one may appear on a CV as long as it is marked ("ramp-up",
    "basics", "transferable"). One flagged `forbidden: true` may not appear at
    all, marked or not - for the skill you have simply never practised and that
    an offer keeps asking for, and for the wording you must never use ("AWS
    Certified" while the exam is not passed).
    """
    return scan_gaps(collect_strings(cv), profile, code="gaps")


def scan_gaps(entries, profile, code="gaps", allow_negation=False):
    """Run the gap terms over (location, text) pairs.

    `allow_negation` is for prose: a cover letter that says "I have not run
    Kubernetes in production" names the gap in order to deny it, which is the
    honest move and must not be reported as a claim.
    """
    findings = []
    for gap in profile.get("gaps") or []:
        term = gap.get("term")
        if not term:
            continue
        forbidden = bool(gap.get("forbidden"))
        # Short names ("Go", "R", "C") only work as gap terms when case
        # matters - otherwise every sentence containing "go" lights up, and
        # the usual workaround (writing "Golang") misses the word people
        # actually put on a CV.
        flags = 0 if gap.get("case_sensitive") else re.IGNORECASE
        pattern = re.compile(rf"\b{re.escape(term)}\b", flags)
        for where, text in entries:
            if not pattern.search(text):
                continue
            padded = f" {text.lower()} "
            if allow_negation and any(word in padded for word in NEGATIONS):
                continue
            if forbidden:
                findings.append(Finding(
                    "error", code,
                    f"{where}: '{term}' is marked forbidden in profile.yaml - it "
                    f"does not go on a CV, however an offer words its "
                    f"requirements."))
                continue
            if any(hedge in padded for hedge in HEDGES):
                continue
            findings.append(Finding(
                "error", code,
                f"{where}: '{term}' is listed as a gap in profile.yaml but is "
                f"written as an owned skill. Mark it (\"{gap.get('hedge', 'ramp-up')}\") "
                f"or drop it."))
    return findings


OPEN_QUESTION = re.compile(r"#\s*\?\s*(.*)")


def check_open_questions(path):
    """Keep the unverified fields of a profile visible until they are settled.

    Drafting a profile from old documents always leaves a few things unsure - a
    date nobody remembers, a title read off an outdated CV. Marking the line
    `# ? why` records that; without this check the mark is a comment nobody
    reads again, and the guess ships in a PDF.
    """
    path = Path(path)
    if not path.exists():
        return []
    findings = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = OPEN_QUESTION.search(line)
        if not match:
            continue
        field, _, _ = line.partition("#")
        if not field.strip():
            # A whole line of comment is documentation - including the header
            # explaining this very convention. Only a field carries a question.
            continue
        field = field.split(":")[0].strip().lstrip("- ") or "field"
        note = match.group(1).strip()
        findings.append(Finding(
            "warning", "profile",
            f"{path.name}:{number}: '{field}' is still an open question"
            f"{' - ' + note if note else ''}. Settle it or remove the field."))
    return findings


def check_letter(path, profile):
    """Hold the cover letter to the rules the CV is held to.

    The letter is free prose, written last and read by nobody before it is
    sent - which makes it exactly where an overclaim survives. Paragraph by
    paragraph, the same gap terms apply, and so does the Latin-1 limit, since
    the letter goes through the same PDF fonts.
    """
    path = Path(path)
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")

    paragraphs, buffer, start = [], [], 1
    for number, line in enumerate(text.splitlines() + [""], start=1):
        if line.strip():
            if not buffer:
                start = number
            buffer.append(line.strip())
        elif buffer:
            paragraphs.append((f"{path.name}:{start}", " ".join(buffer)))
            buffer = []

    findings = scan_gaps(paragraphs, profile, code="letter", allow_negation=True)
    findings += scan_charset(paragraphs, code="letter")
    findings.append(Finding("info", "letter",
                            f"{path.name}: {len(paragraphs)} paragraph(s) checked"))
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


LANG_KEY = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


def _is_translated_field(value):
    """A {en: ..., fr: ...} mapping, as opposed to a normal dict of data."""
    return (isinstance(value, dict) and value
            and all(isinstance(key, str) and LANG_KEY.match(key) for key in value)
            and all(isinstance(item, str) for item in value.values()))


def _walk_translations(node, lang, path, findings):
    if _is_translated_field(node):
        if lang not in node:
            available = ", ".join(sorted(node))
            findings.append(Finding(
                "error", "i18n",
                f"{path}: no '{lang}' text (has {available}). The '{available.split(', ')[0]}' "
                f"version would be printed on the '{lang}' page. Add it, or set "
                f"{lang}: \"\" to leave it out on purpose."))
        return
    if isinstance(node, dict):
        for key, value in node.items():
            _walk_translations(value, lang, f"{path}.{key}" if path else str(key), findings)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            # An id reads better than an index when you go fix the file.
            label = value.get("id") if isinstance(value, dict) else None
            _walk_translations(value, lang, f"{path}[{label or index}]", findings)


def check_translations(profile, target, cv, lang):
    """Catch a field translated into some languages but not the rendered one.

    The renderer falls back to another language rather than crashing, which is
    the right behaviour for a PDF - and the wrong behaviour for a silence. An
    English sentence in the middle of the French page is the kind of detail
    that costs an interview.

    Only what this application actually prints is checked: an untranslated
    bullet in a mission left out of this CV is not a problem today.
    """
    used_ids = {experience.id for experience in cv.experience}
    used_facts = {bullet.source for experience in cv.experience
                  for bullet in experience.bullets}
    used_groups = {experience.group for experience in cv.experience}

    pruned = {key: value for key, value in profile.items()
              if key not in ("experience", "employers", "gaps")}
    pruned["employers"] = [employer for employer in profile.get("employers") or []
                           if employer.get("id") in used_groups]
    pruned["experience"] = []
    for experience in profile.get("experience") or []:
        if experience.get("id") not in used_ids:
            continue
        copy = dict(experience)
        copy["bullets"] = [bullet for bullet in experience.get("bullets") or []
                           if bullet.get("id") in used_facts]
        pruned["experience"].append(copy)

    findings = []
    _walk_translations(pruned, lang, "profile", findings)
    _walk_translations({key: value for key, value in (target or {}).items()
                        if key != "meta"}, lang, "target", findings)
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
