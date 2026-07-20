#!/usr/bin/env python3
"""Validate the ABP agent skills marketplace layout.

Checks:
- All four marketplace manifests parse, list the same plugins, and every
  `source` directory exists.
- Every plugin has both `plugin.json` and `.codex-plugin/plugin.json` with
  identical, valid content and a matching `version`.
- Every plugin listed in the manifests exists on disk, and vice versa.
- Every `SKILL.md` has front matter with `name` (matching its folder),
  `description`, and `license`; skill
  names are unique.

Exit code is non-zero if any check fails.
"""
import json
import os
import re
import sys
import glob

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only without the dependency
    print("validate.py: PyYAML is required (python3 -m pip install PyYAML)",
          file=sys.stderr)
    sys.exit(2)


class _NoDuplicateKeysLoader(yaml.SafeLoader):
    """SafeLoader that raises instead of silently keeping the last value when a
    mapping declares the same key twice (e.g. two `name:` in front matter)."""


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

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKETPLACES = [
    ".claude-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
    ".cursor-plugin/marketplace.json",
    ".github/plugin/marketplace.json",
]
ALLOWED_FRONTMATTER_FIELDS = {"name", "description", "license"}

# --- Static skill-safety / quality thresholds ---
# Static skill profiler for this markdown-skill repo.
#
# MAX_RENDERED_MENU_LEN: an agent renders a menu of <name>+<description> for
# every skill in a plugin under a hard character budget. SkillProfiler.cs pins
# this to the Copilot CLI's SKILL_CHAR_BUDGET of 15,000 chars (measured over the
# fully rendered <skill> blocks, not the raw descriptions). Skills past the
# cut-off collapse to a bare name with no description and stop being
# model-activated. We keep the same 15,000 ceiling and the same per-skill block
# rendering (RenderedSkillMenuCost) so "passes" means the plugin's whole menu
# stays model-invocable.
MAX_RENDERED_MENU_LEN = 15_000
# Early-warning threshold: warn (don't fail) once a plugin's rendered menu passes this,
# so a plugin approaching the hard cap is visible before an edit silently drops a
# description. A plugin sitting above this for long is a signal to split it.
MENU_WARN_LEN = 13_000
# agentskills.io spec #description-field: "Must be 1-1024 characters."
MAX_DESCRIPTION_LEN = 1024
# Warn before the hard cap so a description near the limit is flagged before one
# more routing target pushes it over.
DESCRIPTION_WARN_LEN = 950
# Hyphenated prose/template terms that appear in routing parentheticals but are
# NOT sibling-skill references — kept out of the dead-route check.
NON_SKILL_ROUTING_TERMS = {"per-stack", "app-nolayers", "build-time"}
# Progressive disclosure: split a SKILL.md into references/ once it grows past
# ~500 lines. Warn past 500, hard error past 2x.
SKILL_MD_WARN_LINES = 500
SKILL_MD_ERROR_LINES = 1000

ALLOWED_DOMAINS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "allowed-domains.txt")

errors = []
warnings = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def load_json(rel):
    path = os.path.join(ROOT, rel)
    with open(path) as f:
        return json.load(f)


class FrontmatterError(Exception):
    """Raised when a SKILL.md front matter block is absent or malformed."""


def parse_frontmatter(path):
    """Extract the leading YAML front matter block and parse it with
    yaml.safe_load. Returns the parsed mapping. Raises FrontmatterError when
    the block is missing, unterminated, not valid YAML, or not a mapping."""
    lines = open(path, encoding="utf-8").read().splitlines()
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError("missing front matter")
    try:
        end = lines[1:].index("---") + 1
    except ValueError:
        raise FrontmatterError("unterminated front matter block")
    block = "\n".join(lines[1:end])
    try:
        data = yaml.load(block, Loader=_NoDuplicateKeysLoader)
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"invalid YAML front matter ({exc})")
    if not isinstance(data, dict):
        raise FrontmatterError("front matter is not a mapping")
    return data


def check_relative_links(sk):
    """Flag internal markdown links that don't resolve to a file (or resolve
    to the repo root). Cross-references should use https:// URLs or valid paths."""
    import re
    d = os.path.dirname(sk)
    txt = open(sk, encoding="utf-8").read()
    for m in re.finditer(r"\]\((?!https?://|#|mailto:)([^)]+)\)", txt):
        target = m.group(1).split("#")[0].strip()
        if not target:
            continue
        resolved = os.path.normpath(os.path.join(d, target))
        rel = os.path.relpath(resolved, ROOT)
        if not os.path.exists(resolved) or rel in (".", ""):
            err(f"{sk}: broken/root-relative link -> {target}")


# --- Static skill-safety / quality helpers ---

_URL_RE = re.compile(r"https?://[^\s\)\]\"'<>;]+", re.I)
# curl ... | bash  or  wget ... | sh   (SkillProfiler/ReferenceScanner intent)
_PIPE_TO_SHELL_RE = re.compile(
    r"\b(?:curl|wget)\b[^|\n]*\|\s*(?:sudo\s+)?(?:ba)?sh\b", re.I)
# External <script src="http..."> tag (used for the SRI check)
_SCRIPT_TAG_RE = re.compile(
    r"<script\b[^>]*\bsrc\s*=\s*[\"'][^\"']*[\"'][^>]*>", re.I | re.S)
_SCRIPT_EXTERNAL_SRC_RE = re.compile(r"src\s*=\s*[\"']https?://", re.I)
_SCRIPT_SRC_URL_RE = re.compile(r"src\s*=\s*[\"']([^\"']+)[\"']", re.I)
_SRI_RE = re.compile(r"integrity\s*=", re.I)
_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
# Placeholder / template hosts — not real references (mirrors ReferenceScanner).
_PLACEHOLDER_HOST_RE = re.compile(
    r"(\{\{?[^}]+\}?\}|<[^>]+>|example\.(com|org|net)|contoso\.com|your[-_]?\w+)",
    re.I)


def _url_host(url):
    """Return the lowercased host of a URL (no scheme, port, path)."""
    h = re.sub(r"^https?://", "", url.lower())
    idx = len(h)
    for ch in "/:?#":
        p = h.find(ch)
        if p >= 0:
            idx = min(idx, p)
    return h[:idx]


def _is_local_host(host):
    """Loopback / bind-all / single-label internal service names are exempt from
    the https requirement and the domain allowlist. 0.0.0.0 is a Kestrel
    bind-all address; a dotless single-label host (e.g. a Dapr app-id or a
    docker service name) is not a routable public domain."""
    if host in ("localhost", "127.0.0.1", "0.0.0.0"):
        return True
    if host.startswith("localhost:") or host.startswith("127.0.0.1:"):
        return True
    if "." not in host:  # dotless internal name, not a public domain
        return True
    return False


def load_allowed_domains():
    """Load eng/allowed-domains.txt. One domain per line, '#' comments allowed.
    A URL host matches if it equals an entry or is a subdomain of it."""
    if not os.path.isfile(ALLOWED_DOMAINS_FILE):
        err(f"eng/allowed-domains.txt is missing (required for domain allowlist)")
        return []
    domains = []
    for raw in open(ALLOWED_DOMAINS_FILE, encoding="utf-8"):
        line = raw.strip()
        if line and not line.startswith("#"):
            domains.append(line.lower())
    return domains


def _domain_allowed(host, allowed):
    return any(host == d or host.endswith("." + d) for d in allowed)


def _line_of(text, index):
    return text.count("\n", 0, index) + 1


# Personal/absolute local paths leak a maintainer's machine into shipped content.
# Flag user-home and macOS temp paths (Unix + Windows); use neutral placeholders instead.
_PERSONAL_PATH_RE = re.compile(
    r"(?:/Users/|/home/)[A-Za-z][\w.-]*/"           # Unix / macOS user home
    r"|/var/folders/[\w./-]+"                        # macOS per-user temp
    r"|[A-Za-z]:[\\/]+Users[\\/]+[A-Za-z][\w.-]*"    # Windows user home (also JSON `C:\\Users\\`)
)


def scan_external_refs(sk, allowed):
    """Scan one SKILL.md for unsafe external references (errors):
      - plain http:// URL (require https) — localhost/127.0.0.1/0.0.0.0 exempt
      - curl|bash / wget|sh pipe-to-shell
      - external <script src="http..."> without an integrity= (SRI) attribute
    and for https domains not in the allowlist (error).
    http:// checks are skipped inside fenced code blocks (they legitimately
    show localhost/service examples), matching ReferenceScanner; domain checks
    still apply everywhere."""
    text = open(sk, encoding="utf-8").read()

    # External script tags without SRI (whole-file, multi-line).
    for m in _SCRIPT_TAG_RE.finditer(text):
        tag = m.group(0)
        if _SCRIPT_EXTERNAL_SRC_RE.search(tag) and not _SRI_RE.search(tag):
            src = _SCRIPT_SRC_URL_RE.search(tag)
            host = _url_host(src.group(1)) if src else ""
            if not _is_local_host(host):
                err(f"{sk}:{_line_of(text, m.start())}: external <script src> "
                    f"without integrity (SRI) attribute")

    in_fence = False
    for i, line in enumerate(text.splitlines(), start=1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue

        if _PIPE_TO_SHELL_RE.search(line):
            err(f"{sk}:{i}: pipe-to-shell pattern "
                f"(download piped straight into a shell): {line.strip()}")

        pm = _PERSONAL_PATH_RE.search(line)
        if pm:
            err(f"{sk}:{i}: personal/absolute local path '{pm.group(0)}' — "
                f"use a neutral placeholder (e.g. <path-to-abp-source>)")

        for um in _URL_RE.finditer(line):
            url = um.group(0).rstrip(".,;:)\"'")
            host = _url_host(url)
            if _is_local_host(host) or _PLACEHOLDER_HOST_RE.search(host):
                continue
            if url.lower().startswith("http://") and not in_fence:
                err(f"{sk}:{i}: insecure http:// URL (use https://): {url}")
            if not _domain_allowed(host, allowed):
                err(f"{sk}:{i}: domain '{host}' not in eng/allowed-domains.txt "
                    f"(add it if this reference is intentional): {url}")


def _render_menu_cost(name, desc):
    """Chars one skill contributes to the rendered <available_skills> menu.
    Mirrors SkillProfiler.RenderedSkillMenuCost: the full XML <skill> block
    (XML-escaped name + description + a location label) plus a newline."""
    def esc(s):
        return (s.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace('"', "&quot;")
                 .replace("'", "&apos;"))
    block = (f"<skill>\n  <name>{esc(name)}</name>\n"
             f"  <description>{esc(desc)}</description>\n"
             f"  <location>project</location>\n</skill>")
    return len(block) + 1


def description_errors(sk, description):
    """Problems with a non-empty skill frontmatter `description` (the empty-string
    case is handled by the caller). Pure function so it can be unit-tested."""
    problems = []
    for marker in ("USE FOR:", "DO NOT USE FOR:"):
        if marker not in description:
            problems.append(f"{sk}: description missing '{marker}' "
                            f"(3-part routing structure required)")
    # agentskills.io spec: description must be <= 1024 chars.
    if len(description) > MAX_DESCRIPTION_LEN:
        problems.append(f"{sk}: description is {len(description):,} chars "
                        f"(max {MAX_DESCRIPTION_LEN:,}) — shorten the frontmatter "
                        f"description")
    elif len(description) > DESCRIPTION_WARN_LEN:
        warn(f"{sk}: description is {len(description):,} chars "
             f"(warn > {DESCRIPTION_WARN_LEN:,}, hard cap {MAX_DESCRIPTION_LEN:,}) — "
             f"nearing the limit; trim before adding another routing target")
    # Codex skill-creator quick_validate rejects angle brackets in the description;
    # keep our gate at least as strict so a skill that passes here also passes the
    # canonical platform validator. Put exact C# generics in the body, not the
    # routing description.
    if "<" in description or ">" in description:
        problems.append(f"{sk}: description contains an angle bracket ('<' or '>') "
                        f"— the Codex skill validator rejects these. Reword without "
                        f"C# generics (e.g. 'generic IHybridCache'); keep exact "
                        f"signatures in the body")
    return problems


def routing_targets(description):
    """Sibling-skill names a description routes to (USE FOR / DO NOT USE FOR).

    Matches the two forms these descriptions use — a parenthetical `(name)` /
    `(use name)`, and an inline `use [the] name [skill]` — restricted to
    kebab-case tokens, minus known non-skill prose terms.
    """
    targets = set()
    for m in re.finditer(r"\((?:use )?([a-z][a-z0-9]*(?:-[a-z0-9]+)+)\)", description):
        targets.add(m.group(1))
    # `use A`, `use the A skill`, and slash lists like `use A / B / C`.
    for m in re.finditer(r"\buse (?:the )?([a-z0-9-]+(?:\s*/\s*[a-z0-9-]+)*)", description):
        for tok in re.split(r"\s*/\s*", m.group(1)):
            if re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+", tok.strip()):
                targets.add(tok.strip())
    return targets - NON_SKILL_ROUTING_TERMS


def main():
    # 1. marketplace manifests
    plugin_sets = []      # (manifest, set of names)
    plugin_entries = []   # (manifest, {name: (name, source, description)})
    for m in MARKETPLACES:
        try:
            d = load_json(m)
        except Exception as e:  # noqa: BLE001
            err(f"{m}: invalid JSON ({e})")
            continue
        # Vendor strict validators (e.g. `claude plugin validate --strict`) require a
        # top-level marketplace `description`; keep our gate at least as strict.
        mp_desc = d.get("description")
        if not isinstance(mp_desc, str) or not mp_desc.strip():
            err(f"{m}: missing top-level 'description' (required by vendor strict "
                f"marketplace validators)")
        plugins = d.get("plugins", [])
        malformed = False
        for i, p in enumerate(plugins):
            if not isinstance(p, dict) or "name" not in p or "source" not in p:
                err(f"{m}: plugin entry {i} missing 'name' or 'source'")
                malformed = True
        if malformed:
            # Skip cross-manifest comparison / source checks for this manifest;
            # its entries can't be keyed reliably.
            continue
        names = [p["name"] for p in plugins]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            err(f"{m}: duplicate plugin name(s): {sorted(dupes)}")
        entries = {
            p["name"]: (p.get("name"), p.get("source"), p.get("description"),
                        p.get("version"))
            for p in plugins
        }
        plugin_sets.append((m, set(names)))
        plugin_entries.append((m, entries))
        for p in plugins:
            src = p["source"].lstrip("./")
            if not os.path.isdir(os.path.join(ROOT, src)):
                err(f"{m}: source dir missing: {src}")

    if plugin_entries:
        base_name, base_entries = plugin_entries[0]
        for m, entries in plugin_entries[1:]:
            if entries != base_entries:
                err(f"marketplace entries differ: {base_name} vs {m} "
                    f"(name/source/description must match across all manifests)")

    # 2. plugins on disk
    disk_plugins = sorted(
        os.path.basename(os.path.dirname(p))
        for p in glob.glob(os.path.join(ROOT, "plugins", "*", "plugin.json"))
    )
    manifest_names = plugin_sets[0][1] if plugin_sets else set()
    if plugin_sets and set(disk_plugins) != manifest_names:
        err(f"disk plugins {set(disk_plugins)} != manifest plugins {manifest_names}")

    allowed_domains = load_allowed_domains()

    seen_skill_names = {}
    collected_descriptions = []  # (path, name, description) for the dead-route check
    plugin_versions = {}  # plugin name -> plugin.json version, for marketplace cross-check
    plugin_descriptions = {}  # plugin name -> plugin.json description, for marketplace cross-check
    for pd in sorted(glob.glob(os.path.join(ROOT, "plugins", "*"))):
        name = os.path.basename(pd)
        plugin_name = name  # stable: `name` is reassigned in the skill loop
        menu_cost = 0  # rendered <available_skills> footprint for this plugin
        pj = os.path.join(pd, "plugin.json")
        cj = os.path.join(pd, ".codex-plugin", "plugin.json")
        if not os.path.isfile(pj):
            err(f"{name}: missing plugin.json")
            continue
        if not os.path.isfile(cj):
            err(f"{name}: missing .codex-plugin/plugin.json")
            continue
        try:
            a, b = json.load(open(pj)), json.load(open(cj))
        except Exception as e:  # noqa: BLE001
            err(f"{name}: plugin.json parse error ({e})")
            continue
        # The two manifests must agree on the shared semantics (name, version,
        # description, skills), but each tool's manifest may carry tool-specific
        # metadata (e.g. Codex's `author` / `interface`), so don't require byte
        # equality — only that the common fields match.
        shared = ("name", "version", "description", "skills")
        for key in shared:
            if a.get(key) != b.get(key):
                err(f"{name}: plugin.json and .codex-plugin/plugin.json disagree on "
                    f"'{key}' ({a.get(key)!r} vs {b.get(key)!r})")

        if a.get("name") != name:
            err(f"{name}: plugin.json name {a.get('name')!r} != directory '{name}'")

        version = a.get("version")
        if not version:
            err(f"{name}: plugin.json missing version")
        elif not (isinstance(version, str) and SEMVER_RE.match(version)):
            err(f"{name}: plugin.json version {version!r} is not valid semver (X.Y.Z)")
        else:
            plugin_versions[name] = version
        if isinstance(a.get("description"), str):
            plugin_descriptions[name] = a["description"]

        skills_field = a.get("skills")
        if not isinstance(skills_field, list):
            err(f"{name}: plugin.json 'skills' must be a list")
        else:
            for entry in skills_field:
                if not isinstance(entry, str) or not entry.strip():
                    err(f"{name}: plugin.json 'skills' entry {entry!r} must be a string path")
                    continue
                resolved = os.path.normpath(os.path.join(pd, entry))
                plugin_root = os.path.normpath(pd)
                if resolved != plugin_root and not resolved.startswith(plugin_root + os.sep):
                    err(f"{name}: plugin.json 'skills' entry '{entry}' "
                        f"escapes the plugin directory")
                elif not os.path.isdir(resolved):
                    err(f"{name}: plugin.json 'skills' entry '{entry}' "
                        f"does not resolve to a directory under the plugin")

        skills = glob.glob(os.path.join(pd, "skills", "*", "SKILL.md"))
        if not skills:
            err(f"{name}: no skills")
        for sk in skills:
            folder = os.path.basename(os.path.dirname(sk))
            try:
                fm = parse_frontmatter(sk)
            except FrontmatterError as exc:
                err(f"{sk}: {exc}")
                continue

            extra = set(fm) - ALLOWED_FRONTMATTER_FIELDS
            if extra:
                err(f"{sk}: unknown front matter field(s): {sorted(extra)} "
                    f"(allowed: {sorted(ALLOWED_FRONTMATTER_FIELDS)})")
            missing = ALLOWED_FRONTMATTER_FIELDS - set(fm)
            if missing:
                err(f"{sk}: front matter missing required field(s): {sorted(missing)}")

            name = fm.get("name")
            if not isinstance(name, str) or not name.strip():
                err(f"{sk}: 'name' must be a non-empty string")
            elif name != folder:
                err(f"{sk}: name '{name}' != folder '{folder}'")

            license_ = fm.get("license")
            if license_ != "MIT":
                err(f"{sk}: license must be 'MIT' (got {license_!r})")

            description = fm.get("description")
            if not isinstance(description, str) or not description.strip():
                err(f"{sk}: 'description' must be a non-empty string")
            else:
                for problem in description_errors(sk, description):
                    err(problem)
                menu_cost += _render_menu_cost(
                    name if isinstance(name, str) else "", description)
                collected_descriptions.append((sk, name, description))

            # Progressive-disclosure line budget: warn past 500 lines, error
            # past 1000 (split an oversized SKILL.md into references/).
            n_lines = sum(1 for _ in open(sk, encoding="utf-8"))
            if n_lines > SKILL_MD_ERROR_LINES:
                err(f"{sk}: {n_lines} lines (hard cap {SKILL_MD_ERROR_LINES}) — "
                    f"split into references/ per progressive disclosure")
            elif n_lines > SKILL_MD_WARN_LINES:
                warn(f"{sk}: {n_lines} lines (>{SKILL_MD_WARN_LINES}) — consider "
                     f"splitting into references/ per progressive disclosure")

            # Unsafe external references + domain allowlist.
            scan_external_refs(sk, allowed_domains)

            if isinstance(name, str) and name.strip() and name == folder:
                if name in seen_skill_names:
                    err(f"duplicate skill name '{name}': "
                        f"{sk} & {seen_skill_names[name]}")
                seen_skill_names[name] = sk
            check_relative_links(sk)

        # Per-plugin skill-menu budget: an agent renders name+description for
        # every skill in the plugin under a hard char budget; once exceeded,
        # alphabetically-later skills lose their description and stop activating.
        if menu_cost > MAX_RENDERED_MENU_LEN:
            err(f"{plugin_name}: rendered skill-menu is {menu_cost:,} chars "
                f"(budget {MAX_RENDERED_MENU_LEN:,}) — trim skill descriptions "
                f"or split the plugin; later skills silently lose their "
                f"descriptions and stop activating")
        elif menu_cost > MENU_WARN_LEN:
            warn(f"{plugin_name}: rendered skill-menu is {menu_cost:,} chars "
                 f"(warn > {MENU_WARN_LEN:,}, hard cap {MAX_RENDERED_MENU_LEN:,}) — "
                 f"approaching the per-plugin menu budget; split the plugin or leave "
                 f"headroom before adding/growing skills")

    # Dead-route check: every skill a description routes to must exist. Runs after
    # the loop so the full skill-name set is known.
    for sk, _name, description in collected_descriptions:
        for target in sorted(routing_targets(description)):
            if target not in seen_skill_names:
                err(f"{sk}: description routes to '{target}', which is not an existing "
                    f"skill (dead route — fix the target name or add it to "
                    f"NON_SKILL_ROUTING_TERMS if it is prose)")

    # Marketplace entry versions must match each plugin's plugin.json version, so a
    # release tag can't drift from what a marketplace advertises. (All marketplaces
    # are already enforced identical, so checking the base one covers all four.)
    if plugin_entries:
        _, base_entries = plugin_entries[0]
        for pname, entry in base_entries.items():
            mp_version = entry[3]
            pj_version = plugin_versions.get(pname)
            if mp_version is None:
                err(f"marketplace entry '{pname}' is missing 'version'")
            elif pj_version is not None and mp_version != pj_version:
                err(f"version mismatch for '{pname}': marketplace entry {mp_version!r} "
                    f"!= plugin.json {pj_version!r}")
            mp_desc = entry[2]
            pj_desc = plugin_descriptions.get(pname)
            if pj_desc is not None and mp_desc != pj_desc:
                err(f"description mismatch for '{pname}': marketplace entry and "
                    f"plugin.json disagree (keep them identical)")

    # Repo-wide publication hygiene: no personal/absolute local paths in shipped files.
    # SKILL.md bodies are already covered by scan_external_refs; this catches docs,
    # manifests, experiment results, and C# fixtures. Workflow files are excluded
    # (CI runner paths like /home/runner are expected there).
    hygiene_globs = ["*.md", "eng/**/*.md", "plugins/**/*.json", ".claude-plugin/*.json",
                     ".agents/**/*.json", ".cursor-plugin/*.json", ".github/plugin/*.json",
                     "eng/compat/Skills/*.cs", "eng/experiment/*.json",
                     "eng/activation/*.json", "eng/**/*.yaml", "eng/**/*.yml",
                     "tests/**/*.yaml", "tests/**/*.yml", ".github/CODEOWNERS",
                     "scripts/*.sh", "scripts/*.ps1"]
    scanned = set()
    for g in hygiene_globs:
        for f in glob.glob(os.path.join(ROOT, g), recursive=True):
            if f in scanned or "/node_modules/" in f or "/bin/" in f or "/obj/" in f:
                continue
            scanned.add(f)
            try:
                content = open(f, encoding="utf-8", errors="replace").read()
            except Exception:  # noqa: BLE001
                continue
            for i, line in enumerate(content.splitlines(), start=1):
                pm = _PERSONAL_PATH_RE.search(line)
                if pm:
                    err(f"{os.path.relpath(f, ROOT)}:{i}: personal/absolute local path "
                        f"'{pm.group(0)}' — use a neutral placeholder")

    if warnings:
        print(f"validate.py: {len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings:
            print(f"  ! {w}", file=sys.stderr)
    if errors:
        print(f"validate.py: {len(errors)} problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    print(f"validate.py: OK ({len(disk_plugins)} plugins, "
          f"{len(seen_skill_names)} skills)")


if __name__ == "__main__":
    main()
