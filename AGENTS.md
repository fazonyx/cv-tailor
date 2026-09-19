# Agent instructions

The working rules for this repository live in [CLAUDE.md](CLAUDE.md). They are
tool-agnostic: read that file and follow it, whichever assistant you are.

Short version, if you only read this file:

- `profile/profile.yaml` holds the facts. An application overlay in
  `applications/<company>/target.yaml` decides how they are framed for one job
  offer. The overlay may reorder, drop and reword. It may not add.
- Every CV line must carry `- from: <fact-id>`. No source, no line.
- Never invent a job title, a skill, a tool or a certification. Gaps are stated
  with a marker ("ramp-up", "transferable", "basics") or left out entirely.
- One page per language, with white space left at the bottom.
- Run `python build.py` after every change and fix what it reports.
- Never commit anything under `sources/`, and never commit a real
  `profile/profile.yaml`.
