---
description: Build profile.yaml from the documents in sources/
---

Read everything in `sources/` except `sources/README.md`, which is part of the
template (CV, competency file, old applications, notes)
and draft `profile/profile.yaml` from it, using
`profile/profile.example.yaml` and `profile/schema.md` as the reference.

Rules:

- Transcribe, do not embellish. If a bullet on the old CV says "participated
  in", it stays "participated in".
- Give every experience and every bullet a short stable id: overlays point to
  them by id and renaming one silently breaks an application.
- Keep contract titles exactly as written. For consulting work, put the
  employer and contract title in `employers:` and the client mission in
  `experience:`.
- Write down only what a source states. If the sources are vague or silent
  about a date, a title, a number or an availability, leave the field out, or
  write it with a trailing `# ? why` - the build reports those until they are
  settled. Do not guess, not even for something as harmless-looking as a
  notice period.
- When two sources disagree, take the more conservative version and flag it.
  An old CV saying "owner of the CI pipeline" against a review saying "jointly
  with a platform engineer" resolves to the review, every time.
- Fill `gaps:` with the things the sources show as weak, partial or absent, and
  ask me what else belongs there.
- If a source names a client or a programme that may be confidential, flag it
  and propose a generic wording.

When you are done, list what you were unsure about. I will correct the file
before we use it - everything downstream depends on it being true.
