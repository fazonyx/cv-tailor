"""Renderer: turns a ResolvedCV into a PDF page.

Section order is data, not code: `layout.left` and `layout.right` in the
overlay decide what appears where. That is how one profile produces a CV that
leads with shipped product for one offer, and with system validation for
another, without a second generator script.
"""
from pathlib import Path

from .layout import CVCanvas
from .model import build
from .theme import Theme


def _draw_left(page, cv):
    for block in cv.left:
        if block == "photo":
            if cv.photo and Path(cv.photo).exists():
                page.photo(cv.photo)
        elif block == "contact":
            page.section_left(cv.titles.get("contact", "Contact"))
            for label, url in cv.contact:
                page.contact_line(label, url)
            page.spacer("left", 2.5)
        elif block == "badges":
            for badge in cv.badges:
                page.badge(badge["text"], badge.get("kind", "blue"))
        elif block == "languages":
            if not cv.languages:
                continue
            page.section_left(cv.titles.get("languages", "Languages"))
            for language in cv.languages:
                page.language(language["name"], language["level"],
                              language["ratio"], language["note"])
            page.spacer("left", 1.5)
        elif block == "projects":
            if not cv.projects:
                continue
            page.section_left(cv.titles.get("projects", "Projects"))
            for project in cv.projects:
                page.project(project["name"], project["period"],
                             project["description"], project["stack"],
                             project["links"])
        elif block == "education":
            if not cv.education:
                continue
            page.section_left(cv.titles.get("education", "Education"))
            for entry in cv.education:
                page.sidebar_education(entry["years"], entry["school"], entry["degree"])
        elif block == "interests":
            if not cv.interests:
                continue
            page.section_left(cv.titles.get("interests", "Interests"))
            for interest in cv.interests:
                page.sidebar_item(interest)
        else:
            raise ValueError(f"unknown sidebar block '{block}'")


def _draw_experience(page, cv):
    page.section(cv.titles.get("experience", "Experience"))
    current_group = None
    for experience in cv.experience:
        group = cv.employers.get(experience.group) if experience.group else None
        if group and experience.group != current_group:
            page.employer_bar(group.get("name"), group.get("role"), group.get("period"))
            current_group = experience.group
        if not group:
            current_group = None

        title = experience.client or experience.employer
        if experience.client or group:
            # Consulting: the band above carries the contract title, so the
            # line below is free to describe the mission for this offer.
            parts = [experience.role, experience.city]
        else:
            # Salaried: the contract title is a fact and leads. An overlay's
            # framing follows it rather than being dropped - without this, a
            # `role:` override is silently ignored for anyone not a consultant.
            parts = [experience.employer_role, experience.city]
            if experience.role and experience.role != experience.employer_role:
                parts = [experience.employer_role, experience.role, experience.city]
        subtitle = " · ".join(part for part in parts if part)
        page.experience(
            title=title,
            subtitle=subtitle or None,
            period=experience.period,
            bullets=[bullet.text for bullet in experience.bullets],
            env=experience.env,
            tags=experience.tags,
        )


def _draw_right(page, cv):
    for block in cv.right:
        if block == "experience":
            _draw_experience(page, cv)
            page.spacer("right", 1.5)
        elif block == "skills":
            if not cv.skills:
                continue
            page.section(cv.titles.get("skills", "Skills"))
            for label, value in cv.skills:
                page.skill_row(label, value)
            page.spacer("right", 2.0)
        elif block == "education":
            if not cv.education:
                continue
            page.section(cv.titles.get("education", "Education"))
            for entry in cv.education:
                page.education(entry["years"], entry["school"],
                               entry["degree"], entry["detail"])
            page.spacer("right", 1.5)
        elif block == "certifications":
            if not cv.certifications:
                continue
            page.section(cv.titles.get("certifications", "Certifications"))
            for text in cv.certifications:
                page.note_line(text)
            page.spacer("right", 1.5)
        elif block == "projects":
            if not cv.projects:
                continue
            page.section(cv.titles.get("projects", "Projects"))
            for project in cv.projects:
                page.experience(
                    title=project["name"],
                    subtitle=project["stack"],
                    period=project["period"],
                    bullets=[project["description"]] if project["description"] else (),
                )
                if project["links"]:
                    page.links_line(project["links"])
            page.spacer("right", 1.5)
        else:
            raise ValueError(f"unknown section block '{block}'")


def draw_page(page, cv):
    page.header(cv.name, cv.headline, cv.summary, cv.header_h)
    page.sidebar_background()
    _draw_left(page, cv)
    _draw_right(page, cv)
    return page.margins_mm()


def render(profile, target, output):
    """Render one PDF. Returns [(lang, left_margin_mm, right_margin_mm), ...].

    A bilingual CV is one PDF with one page per language - recruiters pick the
    page they need, and each page must respect the one-page rule on its own.
    """
    languages = target.get("pages") or ["en"]
    theme = Theme.from_dict({**(profile.get("theme") or {}), **(target.get("theme") or {})})
    Path(output).parent.mkdir(parents=True, exist_ok=True)

    first = build(profile, target, languages[0])
    page = CVCanvas(str(output), theme=theme,
                    title=f"CV - {first.name}", author=first.name)
    margins = []
    for index, lang in enumerate(languages):
        cv = first if index == 0 else build(profile, target, lang)
        if index:
            page.end_page()
        left, right = draw_page(page, cv)
        margins.append((lang, left, right))
    page.save()
    return margins
