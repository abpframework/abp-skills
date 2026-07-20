#!/usr/bin/env python3
"""Verify every skill has a real C# compile-coverage chain or an explicit exemption.

Contract:
- Each skill is a `plugins/<plugin>/skills/<skill>/SKILL.md`.
- A skill is "compiled" when the FULL chain below exists and is consistent:
  1. snippet `compat/Skills/<PascalCase>.cs` exists, where the kebab-case skill
     folder maps to PascalCase (e.g. `handle-dates-and-time` ->
     `HandleDatesAndTime.cs`). Existing file names are matched case-insensitively
     so intentional casing (e.g. `OpenIddict`) resolves.
  2. a project `compat/Projects/<Pascal>/<Pascal>.csproj` exists AND it has a
     `<Compile Include="../../Skills/<Pascal>.cs" />` pointing at the skill's own
     snippet.
  3. that project is listed in `compat/AbpSkillsCompat.slnx`.
- A skill is "exempt" when it appears in `compat/coverage-exemptions.yaml`
  under `exempt:` with a non-empty `reason`.

Reports (and exits non-zero on):
- coverage hole: a skill with NEITHER a compiled chain nor an exemption.
- broken chain: snippet present but the .csproj is missing / doesn't compile it
  / isn't in the solution.
- orphan snippet: a `compat/Skills/*.cs` that maps to no skill.
- orphan project: a `compat/Projects/*` project with no matching snippet.
- stem collision: two different skill dirs mapping to the same PascalCase stem.
- stale exemption: an exemption that doesn't correspond to a real skill.
- contradiction: a skill that has BOTH a compiled chain and an exemption.

Exit code is non-zero if any problem is found.
"""
import glob
import os
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only without the dependency
    print("verify_compat_coverage.py: PyYAML is required (python3 -m pip install PyYAML)",
          file=sys.stderr)
    sys.exit(2)


class _NoDuplicateKeysLoader(yaml.SafeLoader):
    """SafeLoader that raises instead of silently keeping the last value when a
    mapping declares the same key twice (mirrors eng/validate.py)."""


def _no_duplicate_keys(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping", node.start_mark,
                f"found duplicate key {key!r}", key_node.start_mark)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_NoDuplicateKeysLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_CS_DIR = os.path.join(ROOT, "eng", "compat", "Skills")
PROJECTS_DIR = os.path.join(ROOT, "eng", "compat", "Projects")
SLN = os.path.join(ROOT, "eng", "compat", "AbpSkillsCompat.slnx")
EXEMPTIONS = os.path.join(ROOT, "eng", "compat", "coverage-exemptions.yaml")

errors = []


def err(msg):
    errors.append(msg)


def pascal_case(kebab):
    """Map a kebab-case skill folder to its PascalCase compile-smoke stem."""
    return "".join(part.capitalize() for part in kebab.split("-"))


def load_exemptions():
    if not os.path.isfile(EXEMPTIONS):
        err(f"{os.path.relpath(EXEMPTIONS, ROOT)}: file missing")
        return {}
    try:
        data = yaml.load(open(EXEMPTIONS, encoding="utf-8"), Loader=_NoDuplicateKeysLoader)
    except (OSError, yaml.YAMLError) as exc:
        err(f"{os.path.relpath(EXEMPTIONS, ROOT)}: invalid YAML ({exc})")
        return {}
    if not isinstance(data, dict) or not isinstance(data.get("exempt"), list):
        err(f"{os.path.relpath(EXEMPTIONS, ROOT)}: expected a top-level 'exempt' list")
        return {}

    exemptions = {}
    for index, entry in enumerate(data["exempt"]):
        loc = f"exempt[{index}]"
        if not isinstance(entry, dict):
            err(f"{loc}: must be a mapping with 'skill' and 'reason'")
            continue
        skill = entry.get("skill")
        reason = entry.get("reason")
        if not isinstance(skill, str) or not skill.strip():
            err(f"{loc}: 'skill' must be a non-empty string")
            continue
        if not isinstance(reason, str) or not reason.strip():
            err(f"{loc} ({skill}): 'reason' must be a non-empty string")
        if skill in exemptions:
            err(f"{loc}: duplicate exemption for '{skill}'")
        exemptions[skill] = reason
    return exemptions


def load_sln_projects():
    """Return the set of csproj paths (repo-relative, forward slashes) listed in
    the solution file."""
    projects = set()
    if not os.path.isfile(SLN):
        err(f"{os.path.relpath(SLN, ROOT)}: file missing")
        return projects
    text = open(SLN, encoding="utf-8").read()
    for match in re.finditer(r'"([^"]+\.csproj)"', text):
        projects.add(match.group(1).replace("\\", "/"))
    return projects


def csproj_compiles(csproj_path, expected_include):
    """Return True when the csproj text has a <Compile Include=...> referencing
    the skill's own snippet (`../../Skills/<Pascal>.cs`)."""
    text = open(csproj_path, encoding="utf-8").read()
    for match in re.finditer(r'<Compile\s+Include\s*=\s*"([^"]+)"', text):
        if match.group(1).replace("\\", "/") == expected_include:
            return True
    return False


def check_chain(key, stem):
    """Verify the full snippet -> csproj -> Compile -> sln chain for a skill whose
    snippet stem is `stem`. Records an error and returns False on any break."""
    ok = True
    project_dir = os.path.join(PROJECTS_DIR, stem)
    csproj = os.path.join(project_dir, f"{stem}.csproj")
    if not os.path.isfile(csproj):
        err(f"broken chain: '{key}' has compat/Skills/{stem}.cs but no "
            f"compat/Projects/{stem}/{stem}.csproj")
        return False

    expected_include = f"../../Skills/{stem}.cs"
    if not csproj_compiles(csproj, expected_include):
        err(f"broken chain: '{key}' project {stem}.csproj does not "
            f"<Compile Include=\"{expected_include}\">")
        ok = False

    sln_rel = f"Projects/{stem}/{stem}.csproj"
    if sln_rel not in SLN_PROJECTS:
        err(f"broken chain: '{key}' project {sln_rel} is not listed in "
            f"compat/AbpSkillsCompat.slnx")
        ok = False
    return ok


def main():
    global SLN_PROJECTS
    existing_lower = {}
    for f in glob.glob(os.path.join(SKILLS_CS_DIR, "*.cs")):
        stem = os.path.basename(f)[:-3]
        existing_lower[stem.lower()] = stem

    SLN_PROJECTS = load_sln_projects()
    exemptions = load_exemptions()

    # Map skill -> (folder, expected PascalCase, resolved snippet stem or None).
    # Detect two skill dirs colliding to the same PascalCase stem.
    skills = {}          # "plugin/skill" -> resolved snippet stem or None
    stem_owner = {}      # lower(PascalCase) -> "plugin/skill"
    matched_snippets = set()
    matched_projects = set()
    for sk in sorted(glob.glob(os.path.join(ROOT, "plugins", "*", "skills", "*", "SKILL.md"))):
        skill_folder = os.path.basename(os.path.dirname(sk))
        plugin = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(sk))))
        key = f"{plugin}/{skill_folder}"
        stem_key = pascal_case(skill_folder).lower()
        if stem_key in stem_owner:
            err(f"stem collision: '{key}' and '{stem_owner[stem_key]}' both map "
                f"to PascalCase stem '{pascal_case(skill_folder)}'")
        else:
            stem_owner[stem_key] = key
        resolved = existing_lower.get(stem_key)
        skills[key] = resolved
        if resolved is not None:
            matched_snippets.add(resolved)
            matched_projects.add(resolved)

    compiled = 0
    exempt = 0
    for key, stem in sorted(skills.items()):
        has_cs = stem is not None
        is_exempt = key in exemptions
        if has_cs and is_exempt:
            err(f"contradiction: '{key}' has both compat/Skills/{stem}.cs "
                f"and a coverage exemption")
        elif has_cs:
            if check_chain(key, stem):
                compiled += 1
        elif is_exempt:
            exempt += 1
        else:
            expected = pascal_case(os.path.basename(key))
            err(f"coverage hole: '{key}' has no compat/Skills/{expected}.cs "
                f"and no entry in coverage-exemptions.yaml")

    # Orphan snippets: a .cs mapping to no skill.
    for stem in sorted(existing_lower.values()):
        if stem not in matched_snippets:
            err(f"orphan snippet: compat/Skills/{stem}.cs maps to no skill")

    # Orphan projects: a project dir with a .csproj but no matching snippet.
    for project_dir in sorted(glob.glob(os.path.join(PROJECTS_DIR, "*"))):
        if not os.path.isdir(project_dir):
            continue
        stem = os.path.basename(project_dir)
        csproj = os.path.join(project_dir, f"{stem}.csproj")
        if os.path.isfile(csproj) and stem not in matched_projects:
            err(f"orphan project: compat/Projects/{stem}/{stem}.csproj has no "
                f"matching compat/Skills/{stem}.cs / skill")

    for skill in sorted(exemptions):
        if skill not in skills:
            err(f"stale exemption: '{skill}' does not correspond to a real skill")

    if errors:
        print(f"verify_compat_coverage.py: {len(errors)} problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    print(f"verify_compat_coverage.py: OK ({len(skills)} skills: "
          f"{compiled} compiled, {exempt} exempt)")


if __name__ == "__main__":
    main()
