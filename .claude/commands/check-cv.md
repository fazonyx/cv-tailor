---
description: Rebuild every application and report what needs fixing
argument-hint: [company-slug]
---

Run `python build.py $ARGUMENTS` and read the output.

For each finding, in order of severity:

- say what the check is complaining about in plain words;
- propose a concrete fix that removes or rewords content, never one that
  weakens the check or shrinks the font;
- for a margin failure, name the exact bullet or section you would cut, and
  what is lost by cutting it.

Then check consistency across the set: if a fact was reworded in one
application, grep the others for the old wording and tell me which ones drifted.

Do not apply anything until I say so.
