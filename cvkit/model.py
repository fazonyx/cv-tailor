"""Content model: one profile of verified facts, one overlay per application.

`profile.yaml` is the single source of truth. It holds what is *true* about a
person: employers, contract titles, dates, schools, bullet-level facts, and an
explicit list of things they do NOT master.

An application overlay (`applications/<company>/target.yaml`) decides how those
facts are framed for one job offer: which experiences to keep, in which order,
with which wording, which skill rows, which headline.

The split is what makes the honesty rules enforceable. An overlay can reword a
fact, it cannot create one, and it cannot touch the fields that must stay
factual (employer, contract title, dates, schools).
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Fields an overlay may never redefine: doing so would rewrite history rather
# than reframe it. The contract title is locked; the client-mission framing
# ("role") is not, because that one is a description, not a title.
LOCKED_EXPERIENCE_FIELDS = ("id", "employer", "employer_role", "period", "client", "city")
LOCKED_EDUCATION = "education entries are facts: include or exclude them, never rewrite"


class RuleViolation(Exception):
    """Raised when an overlay breaks a structural rule of the method."""


# ---- loading -----------------------------------------------------
def load_yaml(path):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def tr(value, lang):
    """Resolve a translatable value.

    A field is either a plain string, or a mapping of language code to string:
        headline: "Backend Engineer"
        headline: {en: "Backend Engineer", fr: "Ingenieur Backend"}
    """
    if value is None:
        return None
    if isinstance(value, dict):
        if lang in value:
            return value[lang]
        # Fall back to the first declared language rather than crashing: a
        # missing translation should be visible in the PDF, not fatal.
        return next(iter(value.values()))
    return value


def tr_list(values, lang):
    return [tr(v, lang) for v in (values or [])]


# ---- resolved structures ----------------------------------------
@dataclass
class Bullet:
    text: str
    source: str          # id of the profile fact this line comes from
    reframed: bool = False


@dataclass
class Experience:
    id: str
    employer: str
    employer_role: str = None
    period: str = None
    client: str = None
    role: str = None
    city: str = None
    tags: list = field(default_factory=list)
    bullets: list = field(default_factory=list)
    env: str = None
    group: str = None     # experiences sharing a group sit under one employer bar


@dataclass
class ResolvedCV:
    lang: str
    name: str = ""
    headline: str = None
    summary: list = field(default_factory=list)
    photo: str = None
    contact: list = field(default_factory=list)
    badges: list = field(default_factory=list)
    languages: list = field(default_factory=list)
    projects: list = field(default_factory=list)
    interests: list = field(default_factory=list)
    experience: list = field(default_factory=list)
    employers: dict = field(default_factory=dict)
    skills: list = field(default_factory=list)
    education: list = field(default_factory=list)
    certifications: list = field(default_factory=list)
    left: list = field(default_factory=list)
    right: list = field(default_factory=list)
    header_h: float = None
    titles: dict = field(default_factory=dict)


DEFAULT_LEFT = ["photo", "contact", "badges", "languages", "projects", "interests"]
DEFAULT_RIGHT = ["experience", "skills", "education", "certifications"]

DEFAULT_TITLES = {
    "en": {"experience": "Experience", "skills": "Skills", "education": "Education",
           "certifications": "Certifications", "languages": "Languages",
           "projects": "Projects", "interests": "Interests", "contact": "Contact"},
    "fr": {"experience": "Experiences", "skills": "Competences", "education": "Formation",
           "certifications": "Certifications", "languages": "Langues",
           "projects": "Projets", "interests": "Centres d'interet", "contact": "Contact"},
}


def _index(items, key="id"):
    return {item[key]: item for item in items or [] if key in item}


def _resolve_bullets(exp_id, profile_bullets, overlay_bullets, lang):
    """Match every rendered line back to a fact in the profile.

    An overlay line is either `- from: fact-id` (use the profile wording) or
    `- {from: fact-id, text: "..."}` (reframe it). Anything else is refused:
    that is the mechanism behind "never invent".
    """
    known = _index(profile_bullets)
    if overlay_bullets is None:
        return [Bullet(tr(b.get("text"), lang), b["id"]) for b in profile_bullets or []]

    resolved = []
    for entry in overlay_bullets:
        if isinstance(entry, str):
            entry = {"from": entry}
        if "from" not in entry:
            raise RuleViolation(
                f"experience '{exp_id}': a bullet has no 'from:' field. Every line of "
                f"a CV must point to a fact in profile.yaml."
            )
        source = entry["from"]
        if source not in known:
            raise RuleViolation(
                f"experience '{exp_id}': bullet references unknown fact '{source}'. "
                f"Add the fact to profile.yaml first if it is true."
            )
        if "text" in entry:
            resolved.append(Bullet(tr(entry["text"], lang), source, reframed=True))
        else:
            resolved.append(Bullet(tr(known[source].get("text"), lang), source))
    return resolved


def _check_locked(exp_id, overrides):
    for locked in LOCKED_EXPERIENCE_FIELDS:
        if locked in overrides:
            raise RuleViolation(
                f"experience '{exp_id}': '{locked}' is locked. Employer, contract "
                f"title, dates and location are facts - reframe the mission role "
                f"and the bullets instead."
            )


def build(profile, target=None, lang="en"):
    """Merge a profile and an application overlay into something renderable."""
    target = target or {}
    cv = ResolvedCV(lang=lang)

    identity = profile.get("identity", {})
    cv.name = tr(identity.get("name"), lang) or ""
    cv.headline = tr(target.get("headline", identity.get("headline")), lang)
    cv.summary = tr_list(target.get("summary", identity.get("summary")), lang)
    cv.header_h = target.get("header_height_mm")
    cv.titles = dict(DEFAULT_TITLES.get(lang, DEFAULT_TITLES["en"]))
    cv.titles.update({k: tr(v, lang) for k, v in (target.get("titles") or {}).items()})

    # Contact block: the overlay may hide fields (international CVs often drop
    # phone and email), never invent them.
    contact = profile.get("contact", {}) or {}
    hidden = set(target.get("hide_contact") or [])
    for key in ("location", "nationality", "email", "phone"):
        if contact.get(key) and key not in hidden:
            cv.contact.append((tr(contact[key], lang), None))
    for link in contact.get("links") or []:
        if link.get("label") not in hidden:
            cv.contact.append((link.get("label"), link.get("url")))
    if contact.get("photo") and target.get("photo", True):
        cv.photo = contact["photo"]

    availability = tr(target.get("availability", profile.get("availability")), lang)
    badges = target.get("badges", profile.get("badges")) or []
    if availability:
        cv.badges.append({"text": availability, "kind": "green"})
    for badge in badges:
        cv.badges.append({"text": tr(badge.get("text"), lang),
                          "kind": badge.get("kind", "blue")})

    for language in profile.get("languages") or []:
        cv.languages.append({
            "name": tr(language.get("name"), lang),
            "level": tr(language.get("level"), lang),
            "ratio": language.get("ratio"),
            "note": tr(language.get("note"), lang),
        })

    # ---- experience ---------------------------------------------
    # Employer bands group several client missions under one contract. Their
    # content (name, contract title, dates) is locked by construction: it lives
    # in the profile and no overlay key reaches it.
    for employer in profile.get("employers") or []:
        cv.employers[employer["id"]] = {
            "name": employer.get("name"),
            "role": tr(employer.get("role"), lang),
            "period": tr(employer.get("period"), lang),
        }

    catalogue = _index(profile.get("experience"))
    section = target.get("experience") or {}
    include = section.get("include") or list(catalogue)
    overrides = section.get("overrides") or {}
    for exp_id in include:
        if exp_id not in catalogue:
            raise RuleViolation(f"unknown experience id '{exp_id}'")
        base = catalogue[exp_id]
        over = overrides.get(exp_id) or {}
        _check_locked(exp_id, over)
        cv.experience.append(Experience(
            id=exp_id,
            employer=base.get("employer"),
            employer_role=tr(base.get("employer_role"), lang),
            period=tr(base.get("period"), lang),
            client=base.get("client"),
            role=tr(over.get("role", base.get("role")), lang),
            city=base.get("city"),
            tags=over.get("tags", base.get("tags")) or [],
            bullets=_resolve_bullets(exp_id, base.get("bullets"),
                                     over.get("bullets"), lang),
            env=tr(over.get("env", base.get("env")), lang),
            group=base.get("group"),
        ))

    # ---- skills / education / projects --------------------------
    skills = target.get("skills", profile.get("skills")) or []
    cv.skills = [(tr(row.get("label"), lang), tr(row.get("value"), lang)) for row in skills]

    edu_catalogue = _index(profile.get("education"))
    edu_section = target.get("education") or {}
    if isinstance(edu_section, dict) and edu_section.get("overrides"):
        raise RuleViolation(LOCKED_EDUCATION)
    edu_include = (edu_section.get("include") if isinstance(edu_section, dict) else None)
    for edu_id in edu_include or list(edu_catalogue):
        if edu_id not in edu_catalogue:
            raise RuleViolation(f"unknown education id '{edu_id}'")
        entry = edu_catalogue[edu_id]
        cv.education.append({
            "years": tr(entry.get("years"), lang),
            "school": tr(entry.get("school"), lang),
            "degree": tr(entry.get("degree"), lang),
            "detail": tr(entry.get("detail"), lang),
        })

    cert_catalogue = _index(profile.get("certifications"))
    cert_section = target.get("certifications") or {}
    cert_include = cert_section.get("include") if isinstance(cert_section, dict) else None
    for cert_id in cert_include or list(cert_catalogue):
        cv.certifications.append(tr(cert_catalogue[cert_id].get("text"), lang))

    project_catalogue = _index(profile.get("projects"))
    project_section = target.get("projects") or {}
    project_include = project_section.get("include") or list(project_catalogue)
    project_over = project_section.get("overrides") or {}
    for project_id in project_include:
        if project_id not in project_catalogue:
            raise RuleViolation(f"unknown project id '{project_id}'")
        base = project_catalogue[project_id]
        over = project_over.get(project_id) or {}
        for locked in ("name", "period"):
            if locked in over:
                raise RuleViolation(f"project '{project_id}': '{locked}' is locked")
        cv.projects.append({
            "name": base.get("name"),
            "period": tr(base.get("period"), lang),
            "description": tr(over.get("description", base.get("description")), lang),
            "stack": tr(over.get("stack", base.get("stack")), lang),
            "links": [(link.get("label"), link.get("url"))
                      for link in base.get("links") or []],
        })

    cv.interests = tr_list(target.get("interests", profile.get("interests")), lang)

    layout = target.get("layout") or {}
    cv.left = layout.get("left") or DEFAULT_LEFT
    cv.right = layout.get("right") or DEFAULT_RIGHT
    return cv


def load_application(directory, profile_path="profile/profile.example.yaml"):
    """Load (profile, target) for one application directory."""
    directory = Path(directory)
    target = load_yaml(directory / "target.yaml")
    profile = load_yaml(target.get("profile", profile_path))
    return profile, target
