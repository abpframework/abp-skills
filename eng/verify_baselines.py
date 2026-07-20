#!/usr/bin/env python3
"""Enforce that eng/abp-baselines.yaml matches the ABP versions pinned everywhere else.

The stable and next ABP versions are duplicated across several files (compat package
props, runtime csproj, the TypeScript smoke, the README compatibility table, the CI
next-build step). Without a gate, abp-baselines.yaml is just a note and the copies
drift. This reads the YAML as the source of truth and fails if any copy disagrees.

Pure helpers take file *contents* so they can be unit-tested without a filesystem.
"""
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-.][0-9A-Za-z.]+)?$")


def props_abp_version(text):
    """<AbpVersion> from compat/Directory.Packages.props."""
    m = re.search(r"<AbpVersion>([^<]+)</AbpVersion>", text)
    return m.group(1).strip() if m else None


def ng_core_version(package_json_text):
    """@abp/ng.core version from compat-ts/package.json dependencies."""
    data = json.loads(package_json_text)
    for section in ("dependencies", "devDependencies"):
        deps = data.get(section, {})
        if "@abp/ng.core" in deps:
            return deps["@abp/ng.core"]
    return None


def readme_compile_tested_versions(text):
    """The last column of each compatibility-table row (compile-tested ABP)."""
    out = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) == 3 and VERSION_RE.match(cells[2]):
            out.append(cells[2])
    return out


def workflow_next_versions(text):
    """Every -p:AbpVersion=<x> passed on a build command (the next-ABP build step)."""
    return re.findall(r"-p:AbpVersion=(\S+)", text)


def baseline_errors(baselines, props, runtime_props, package_json, readme, workflows):
    """Return a list of human-readable mismatch strings (empty == consistent).

    workflows is a dict of {name: text}.
    """
    errors = []
    try:
        stable = baselines["stable_compile"]["nuget_version"]
        nxt = baselines["next_compile"]["nuget_version"]
    except (KeyError, TypeError):
        return ["abp-baselines.yaml: missing stable_compile/next_compile nuget_version"]

    pv = props_abp_version(props)
    if pv != stable:
        errors.append(
            f"compat/Directory.Packages.props AbpVersion={pv!r} != baseline stable {stable!r}"
        )

    rt = props_abp_version(runtime_props)
    if rt is None:
        errors.append("runtime/Directory.Packages.props: no <AbpVersion> found")
    elif rt != stable:
        errors.append(
            f"runtime/Directory.Packages.props AbpVersion={rt!r} != baseline stable {stable!r}"
        )

    nc = ng_core_version(package_json)
    if nc != stable:
        errors.append(
            f"compat-ts @abp/ng.core={nc!r} != baseline stable {stable!r}"
        )

    readme_versions = readme_compile_tested_versions(readme)
    if not readme_versions:
        errors.append("README: no compatibility-table rows found")
    for v in sorted(set(readme_versions)):
        if v != stable:
            errors.append(
                f"README compile-tested column {v!r} != baseline stable {stable!r}"
            )

    for name, text in workflows.items():
        nexts = workflow_next_versions(text)
        if not nexts:
            errors.append(f"{name}: no -p:AbpVersion=<next> build step found")
        for v in sorted(set(nexts)):
            if v != nxt:
                errors.append(
                    f"{name} -p:AbpVersion={v!r} != baseline next {nxt!r}"
                )

    return errors


def main():
    baselines = yaml.safe_load((ROOT / "eng/abp-baselines.yaml").read_text())
    errors = baseline_errors(
        baselines,
        (ROOT / "eng/compat/Directory.Packages.props").read_text(),
        (ROOT / "eng/runtime/Directory.Packages.props").read_text(),
        (ROOT / "eng/compat-ts/package.json").read_text(),
        (ROOT / "README.md").read_text(),
        {
            ".github/workflows/validate.yml": (ROOT / ".github/workflows/validate.yml").read_text(),
            ".github/workflows/release.yml": (ROOT / ".github/workflows/release.yml").read_text(),
        },
    )
    if errors:
        print("verify_baselines.py: FAIL")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    stable = baselines["stable_compile"]["nuget_version"]
    nxt = baselines["next_compile"]["nuget_version"]
    print(f"verify_baselines.py: OK (stable {stable}, next {nxt} consistent across props/runtime/ts/README/workflows)")


if __name__ == "__main__":
    main()
