---
description: Create an application folder from a job offer and build the first CV
argument-hint: <company-slug> [path to the offer]
---

Set up a new application for `$ARGUMENTS`, following the rules in CLAUDE.md.

1. Create `applications/<company-slug>/` and save the offer as `offer.md`
   (verbatim - do not summarise it).
2. Run the analysis from `/analyze-offer` on it and show me the verdict.
   **Stop there and wait for my go.** If the verdict is negative, say so and do
   not build anything.
3. Once I agree, write `target.yaml`:
   - `meta`, with your honest read of the fit under `meta.fit`;
   - the experiences to include and their order;
   - for each, the bullets by `from:` id, reworded only where the offer calls
     for a different emphasis;
   - skill rows aimed at this offer, with any gap marked ("ramp-up",
     "transferable", "basics");
   - headline, summary, availability, section order.
4. Run `python build.py <company-slug>` and fix everything it reports.
5. Show me the margins and tell me what you cut and why.

Never add a fact that is not in `profile/profile.yaml`. If a fact is missing
and true, tell me and I will add it to the profile myself.
