#!/usr/bin/env python3
"""Cross-check version-specific API annotations in SKILL.md prose against a registry.

The C# compile-smoke (compat/) is pinned to a single stable ABP baseline, so an API
a skill documents as available only from a *newer* version is not exercised by that
gate — a wrong signature could ship undetected. To keep those claims explicit and
reviewable, every version annotation in prose (e.g. "ABP 10.6+", "10.6-only",
"available from ABP 10.6") must be registered in eng/version-annotations.yaml.

Reports (and exits non-zero on):
- unregistered annotation: a SKILL.md carries a version annotation but its skill has
  no entry in the registry (an accidental version-specific leak, or an unreviewed one).
- stale registry entry: a registry entry names a skill that no longer carries any
  version annotation (the annotation was removed but the entry wasn't).
- a registry entry pointing at a skill folder that does not exist.

Doc-link refs (github.com/abpframework/abp/blob/rel-x.y/...) are NOT annotations and
are ignored.
"""
import glob
import os
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    print("check_version_annotations.py: PyYAML is required (python3 -m pip install PyYAML)",
          file=sys.stderr)
    sys.exit(2)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "eng", "version-annotations.yaml")

# A version annotation is a claim that an ABP API is tied to a specific ABP version:
#   "ABP 10.6+", "ABP 11.0-only", "available in/from ABP 10.6", "requires ABP 12.1",
#   "since ABP 10.6". Any major.minor is matched (not a hardcoded major). "ABP" must be
#   adjacent so unrelated version tokens (".NET 8.0+", "C# 12+", package literals like
#   "10.5.0") are not flagged. Release-branch doc links (blob/rel-10.5/...) are excluded.
_ANNOTATION_RE = re.compile(
    r"\bABP\s+\**\s*\d+\.\d+\s*\+"                       # ABP 10.6+
    r"|\bABP\s+\**\s*\d+\.\d+\s*-\s*only"                # ABP 10.6-only
    r"|\b(?:available|introduced|added|new)\s+(?:in|from)\s+\**\s*ABP\s+\d+\.\d+"
    r"|\b(?:requires|since)\s+\**\s*ABP\s+\d+\.\d+",
    re.IGNORECASE,
)

errors = []


def err(msg):
    errors.append(msg)


def skill_key(path):
    """plugins/<plugin>/skills/<skill>/SKILL.md -> '<plugin>/<skill>'."""
    skill = os.path.basename(os.path.dirname(path))
    plugin = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
    return f"{plugin}/{skill}"


def is_doc_link(line):
    return "blob/rel-" in line or "/rel-" in line and "github.com" in line


def annotated_skills():
    """Return {skill_key: [(lineno, text), ...]} for skills whose prose carries a
    version annotation."""
    found = {}
    for sk in glob.glob(os.path.join(ROOT, "plugins", "*", "skills", "*", "SKILL.md")):
        key = skill_key(sk)
        for i, line in enumerate(open(sk, encoding="utf-8"), start=1):
            if is_doc_link(line):
                continue
            if _ANNOTATION_RE.search(line):
                found.setdefault(key, []).append((i, line.strip()))
    return found


def abp_next_regions(source):
    """Return the concatenated text found strictly INSIDE `#if ABP_NEXT ... #endif`
    regions of a C# source, so a member outside the guard (with an empty guard
    elsewhere) is not mistaken for being compiled next-only. Handles nested #if."""
    regions = []
    in_next = False
    depth = 0
    buf = []
    for line in source.splitlines():
        s = line.strip()
        if not in_next:
            if re.match(r"#\s*if\b.*\bABP_NEXT\b", s):
                in_next, depth, buf = True, 0, []
            continue
        if re.match(r"#\s*if\b", s):
            depth += 1
            buf.append(line)
        elif re.match(r"#\s*endif\b", s):
            if depth == 0:
                in_next = False
                regions.append("\n".join(buf))
            else:
                depth -= 1
                buf.append(line)
        else:
            buf.append(line)
    return "\n".join(regions)


def skill_text(skill):
    """Return the SKILL.md text for a 'plugin/skill' key, or None if it doesn't exist."""
    plugin, _, skname = skill.partition("/")
    path = os.path.join(ROOT, "plugins", plugin, "skills", skname, "SKILL.md")
    return open(path, encoding="utf-8").read() if os.path.isfile(path) else None


def load_registry():
    if not os.path.isfile(REGISTRY):
        err(f"{os.path.relpath(REGISTRY, ROOT)}: file missing")
        return {}
    try:
        data = yaml.safe_load(open(REGISTRY, encoding="utf-8"))
    except yaml.YAMLError as exc:
        err(f"{os.path.relpath(REGISTRY, ROOT)}: invalid YAML ({exc})")
        return {}
    if not isinstance(data, dict) or not isinstance(data.get("annotations"), list):
        err(f"{os.path.relpath(REGISTRY, ROOT)}: expected a top-level 'annotations' list")
        return {}
    reg = {}
    for idx, entry in enumerate(data["annotations"]):
        if not isinstance(entry, dict):
            err(f"annotations[{idx}]: must be a mapping")
            continue
        skill = entry.get("skill")
        if not isinstance(skill, str) or not skill.strip():
            err(f"annotations[{idx}]: 'skill' must be a non-empty string")
            continue
        if not isinstance(entry.get("since"), str) or not entry["since"].strip():
            err(f"annotations[{idx}] ({skill}): 'since' must be a non-empty string")
        if not isinstance(entry.get("symbols"), list) or not entry["symbols"]:
            err(f"annotations[{idx}] ({skill}): 'symbols' must be a non-empty list")
        if skill in reg:
            err(f"annotations[{idx}]: duplicate entry for '{skill}'")
        reg[skill] = entry
    return reg


def main():
    registry = load_registry()
    annotated = annotated_skills()

    for skill in registry:
        plugin, _, skname = skill.partition("/")
        if not os.path.isfile(os.path.join(ROOT, "plugins", plugin, "skills", skname, "SKILL.md")):
            err(f"registry entry '{skill}' does not correspond to a real skill")

    # Unregistered annotations.
    for skill, hits in sorted(annotated.items()):
        if skill not in registry:
            first = hits[0]
            err(f"unregistered version annotation: '{skill}' SKILL.md:{first[0]} "
                f"carries a version annotation ({first[1]!r}) but has no entry in "
                f"eng/version-annotations.yaml")

    # Stale registry entries.
    for skill in sorted(registry):
        if skill not in annotated:
            err(f"stale registry entry: '{skill}' is registered in "
                f"eng/version-annotations.yaml but its SKILL.md carries no version annotation")

    # Registered symbols must actually appear in the skill's prose (catches a typo'd
    # or removed symbol name in the registry — the whole point is to track a real API).
    for skill in sorted(registry):
        text = skill_text(skill)
        if text is None:
            continue  # non-existent skill already reported above
        for symbol in registry[skill].get("symbols") or []:
            if not isinstance(symbol, str):
                continue
            member = symbol.split(".")[-1]
            if symbol not in text and member not in text:
                err(f"registry symbol not in prose: '{skill}' registers '{symbol}' "
                    f"but neither it nor '{member}' appears in its SKILL.md")

    # Each registered symbol must also be *compiled* in the next-ABP build: it has to
    # appear in the entry's compat_source inside an `#if ABP_NEXT` region. This turns a
    # prose-only version claim into a real type-check against the newer package.
    for skill in sorted(registry):
        entry = registry[skill]
        compat_source = entry.get("compat_source")
        if not compat_source or not isinstance(compat_source, str):
            err(f"missing compat_source: '{skill}' registers version-specific symbols "
                f"but has no 'compat_source' next-only compile-smoke file")
            continue
        path = os.path.join(ROOT, compat_source)
        if not os.path.isfile(path):
            err(f"compat_source missing: '{skill}' -> '{compat_source}' does not exist")
            continue
        source = open(path, encoding="utf-8").read()
        next_region = abp_next_regions(source)
        if not next_region.strip():
            err(f"compat_source not guarded: '{compat_source}' ({skill}) has no non-empty "
                f"'#if ABP_NEXT' region — version-specific symbols must be compiled only "
                f"in the next-ABP build")
        for symbol in entry.get("symbols") or []:
            if not isinstance(symbol, str):
                continue
            member = symbol.split(".")[-1]
            # The member must appear INSIDE an #if ABP_NEXT region, not just anywhere in
            # the file, so it is genuinely type-checked only by the next-ABP build.
            if member not in next_region:
                err(f"symbol not compiled next-only: '{skill}' registers '{symbol}' but "
                    f"its member '{member}' does not appear inside an '#if ABP_NEXT' region "
                    f"in {compat_source}")

    if errors:
        print(f"check_version_annotations.py: {len(errors)} problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    print(f"check_version_annotations.py: OK "
          f"({len(annotated)} skill(s) with version annotations, all registered)")


if __name__ == "__main__":
    main()
