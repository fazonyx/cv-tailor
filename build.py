#!/usr/bin/env python3
"""Build every application in `applications/`, then check the result.

    python build.py                 # build and check everything
    python build.py northwind       # build one application
    python build.py --strict        # treat warnings as failures
    python build.py --list          # show what would be built

Exit code is non-zero when a check fails, so CI can gate on it.
"""
import argparse
import sys
from pathlib import Path

from cvkit import checks
from cvkit.model import RuleViolation, build as build_model, load_yaml
from cvkit.render import render
from cvkit.theme import Theme

ROOT = Path(__file__).resolve().parent
APPLICATIONS = ROOT / "applications"
DEFAULT_PROFILE = "profile/profile.example.yaml"


def discover(names):
    found = sorted(path.parent for path in APPLICATIONS.glob("*/target.yaml"))
    if not names:
        return found
    selected = [path for path in found if path.name in names]
    missing = set(names) - {path.name for path in selected}
    if missing:
        sys.exit(f"unknown application(s): {', '.join(sorted(missing))}")
    return selected


def build_one(directory, strict=False):
    target = load_yaml(directory / "target.yaml")
    profile_path = ROOT / target.get("profile", DEFAULT_PROFILE)
    profile = load_yaml(profile_path)

    output = ROOT / target.get("output", f"applications/{directory.name}/cv.pdf")
    languages = target.get("pages") or ["en"]

    meta = target.get("meta") or {}
    heading = meta.get("company") or directory.name
    role = meta.get("role")
    print(f"\n{heading}{' - ' + role if role else ''}")
    print(f"  profile: {profile_path.relative_to(ROOT)}")

    margins = render(profile, target, output)
    theme = Theme.from_dict(
        {**(profile.get("theme") or {}), **(target.get("theme") or {})})

    findings = checks.check_margins(margins, theme.bottom_margin_min,
                                    theme.bottom_margin_max)
    findings += checks.check_pdf(output, len(languages))
    for lang in languages:
        cv = build_model(profile, target, lang)
        findings += checks.check_sources(cv)
        findings += checks.check_gaps(cv, profile)
        findings += checks.check_figures(cv, profile)
        findings += checks.check_charset(cv)

    print(f"  output:  {output.relative_to(ROOT)}")
    for finding in findings:
        print(finding)

    failed = checks.has_errors(findings)
    if strict:
        failed = failed or any(finding.level == "warning" for finding in findings)
    return failed


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("applications", nargs="*", help="application folder names")
    parser.add_argument("--strict", action="store_true", help="warnings fail the build")
    parser.add_argument("--list", action="store_true", help="list applications and exit")
    args = parser.parse_args()

    directories = discover(args.applications)
    if args.list:
        for directory in directories:
            print(directory.relative_to(ROOT))
        return 0
    if not directories:
        print("no application found in applications/")
        return 0

    failures = []
    for directory in directories:
        try:
            if build_one(directory, args.strict):
                failures.append(directory.name)
        except RuleViolation as error:
            print(f"\n{directory.name}")
            print(f"  [FAIL] rule: {error}")
            failures.append(directory.name)

    print()
    if failures:
        print(f"FAILED: {', '.join(failures)}")
        return 1
    print(f"OK - {len(directories)} application(s) built and checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
