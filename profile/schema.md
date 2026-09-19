# profile.yaml and target.yaml

Two files, one job each. `profile.yaml` says what is true. A `target.yaml`
overlay says how it is framed for one offer. Every field below is optional
unless stated otherwise - a profile with three experiences and no projects is a
perfectly good profile.

Any text field can be written in one language:

```yaml
headline: "Backend Engineer"
```

or in several:

```yaml
headline: { en: "Backend Engineer", fr: "Ingenieur Backend" }
```

`pages: [en, fr]` in an overlay then produces one PDF with one page per
language.

A field written in *some* languages but not the one being printed is an error:
the renderer would quietly fall back to another language. Write the missing
text, or `fr: ""` to leave that field out of the French page on purpose. A
plain string is never flagged - it is language-neutral by intent, which is what
you want for a list of tools.

---

## profile.yaml

```yaml
identity:
  name: Alex Morand              # required
  headline: "..."                # default, an overlay usually replaces it
  summary: ["...", "..."]        # 1-2 lines under the headline

contact:
  location: "Lyon, France"
  nationality: "French citizen (EU)"
  email: "..."                   # an overlay can hide it: hide_contact: [email]
  phone: "..."
  photo: sources/photo.jpg       # optional, circle in the sidebar;
                                 # an overlay drops it with photo: false
  links:
    - label: "linkedin.com/in/example"
      url: "https://www.linkedin.com/in/example"

availability: "Available from March 2027"     # rendered as a green badge
badges:                                        # extra badges, sidebar
  - { text: "Work permit: EU", kind: blue }    # kind: green | blue | accent

employers:                       # only if you are a consultant / contractor
  - id: helmvale
    name: HELMVALE CONSULTING
    role: "Software Engineer (consultant)"     # the contract title
    period: "2023 - present"

experience:
  - id: northbay                 # required, referenced by overlays
    group: helmvale              # draws the employer band above this mission
    employer: HELMVALE CONSULTING
    employer_role: "Software Engineer (consultant)"
    client: NORTHBAY LOGISTICS   # omit for a salaried job or an internship
    role: "Backend Engineer - Fleet Tracking"   # mission framing, reframable
    city: "Lyon, France"
    period: "2025"
    tags: [Logistics, SaaS]      # small pills, for the recruiter's eye scan
    bullets:
      - id: nb-ingest            # required, this is what an overlay points to
        text: "Built the ingestion service ..."
    env: "Python, FastAPI, PostgreSQL"          # italic tooling line

education:
  - id: imi
    years: "2019-2023"
    school: "Institut Marbeau d'Ingenierie, Lyon"
    degree: "Engineering degree (MSc equiv.), Computer Science"
    detail: "Distributed systems, databases."   # one extra line, optional

certifications:
  - id: aws-cp
    text: "AWS Cloud Practitioner - exam scheduled, not yet passed"

skills:                          # default rows, an overlay usually replaces them
  - { label: Languages, value: "Python, SQL, Bash" }

languages:
  - { name: English, level: "C1", ratio: 0.85, note: "Daily working language." }

projects:
  - id: seedling
    name: Seedling
    period: "2024 - present"
    description: "..."
    stack: "Python, Click, PostgreSQL"
    links:
      - { label: "seedling.example.com", url: "https://seedling.example.com" }

interests: ["Bouldering", "Film photography"]

gaps:                            # what you do NOT master - see below
  - term: Kubernetes
    hedge: "ramp-up"
  - term: Assembly               # never goes on a CV, marked or not
    forbidden: true
```

An employer band carries the contract dates, so the missions under it usually
carry a shorter period ("2025") rather than repeating them.

### `gaps:` is the important one

Each term listed here may appear on a CV only in a sentence that also contains
a marker: *ramp-up*, *ramping up*, *open to*, *eager to*, *basics*, *notions*,
*academic*, *transferable*, *exposure*, *familiar*, *reading*, *learning*
(French equivalents are accepted too). Otherwise `python build.py` fails.

`forbidden: true` is the stronger form: the term may not appear at all, marked
or not. Use it for the skill you have simply never practised and that offers
keep asking for, and for the wording you must never use - "AWS Certified"
while the exam is not passed, for instance.

Write these down when you are calm, not when you are staring at a job ad that
asks for all of them. Matching is case-insensitive, so prefer distinctive terms
("Golang", not "Go").

---

## target.yaml

```yaml
meta:                            # documentation, not rendered
  company: Orbital Freight
  role: Backend Platform Engineer
  location: Remote (EU)
  source: applications/orbital-freight/offer.md
  applied: 2027-01-12
  fit: >
    Honest read of the fit, written before the CV. Reread it before the
    interview.

profile: profile/profile.yaml    # default: profile/profile.example.yaml
output: applications/orbital-freight/CV_Name_Company.pdf
letter: applications/orbital-freight/letter.md   # checked too; this is the default
pages: [en]                      # [en, fr] for a bilingual two-page PDF
header_height_mm: 30             # shrink the dark band to gain a few lines

headline: "..."                  # overrides the profile default
summary: ["...", "..."]
availability: "Available from March 2027"
badges: [{ text: "...", kind: blue }]
hide_contact: [phone]            # hide fields, never add them
photo: false                     # drop the photo for this application

layout:                          # section order, per column
  right: [experience, skills, education, certifications]
  left:  [photo, contact, badges, languages, projects, interests]

titles:                          # rename a section heading
  projects: "Built & shipped"

experience:
  include: [northbay, marlowe, vireo]        # order matters, omission is fine
  overrides:
    northbay:
      role: "Backend Engineer - Vehicle Telemetry"   # mission framing only
      tags: [Logistics, High volume]
      env: "..."
      bullets:
        - from: nb-ingest                    # profile wording
        - from: nb-api                       # reworded for this offer
          text: "..."

skills:                          # replaces the profile rows wholesale
  - { label: Backend, value: "..." }

education:
  include: [imi, saint-aubin]    # include or exclude only - never rewrite

projects:
  include: [seedling]
  overrides:
    seedling: { description: "..." }         # name and period stay locked

interests: ["...", "..."]
```

### What an overlay may never touch

`id`, `employer`, `employer_role`, `period`, `client`, `city` on an experience;
`name` and `period` on a project; anything at all on an education entry. The
loader raises a `RuleViolation` and the build stops.

The point is not to be strict for its own sake. It is that at 23:00, on the
fifth application of the week, "senior" slips into a title and nobody notices
until an interviewer asks about it.

---

## Theme

Both files accept a `theme:` block overriding any field of `cvkit/theme.py`:
palette, column width, margins, font sizes, and the two margin rules.

```yaml
theme:
  accent: "#2563EB"
  sidebar_w: 60
  size_body: 7.8                 # the whole type scale is adjustable
  leading: 1.22                  # line height, as a multiple of the font size
  bottom_margin_min: 15
  bottom_margin_max: 45
```

`leading` is the knob to reach for when a dense profile misses the one-page
rule by a few millimetres: line heights derive from it, so shrinking the type
scale really does free vertical space. Past a point, cut content instead.
