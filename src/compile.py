"""
Skill compiler — renders templated skills with shared references.

Usage:
    python src/compile.py
"""

import dataclasses
import json
import os
import re
import shutil
import stat
import sys

# ---------------------------------------------------------------------------
# DSL types
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Ref:
    filename: str

@dataclasses.dataclass
class Asset:
    """A prebuilt file copied verbatim into the compiled skill.

    `src` is relative to the repo root (e.g. a pd-components build output);
    `dst` is relative to the skill's output dir (e.g. 'scripts/pd-lint.mjs').
    """
    src: str
    dst: str

@dataclasses.dataclass
class Skill:
    name: str
    refs: list[Ref]
    assets: list["Asset"] = dataclasses.field(default_factory=list)

@dataclasses.dataclass
class Module:
    name: str
    skills: list[Skill]
    description: str = ""
    category: str = ""
    keywords: list[str] = dataclasses.field(default_factory=list)
    display_name: str = ""


def ref(filename: str) -> Ref:
    return Ref(filename=filename)

def asset(src: str, dst: str) -> Asset:
    return Asset(src=src, dst=dst)

def skill(name: str, refs: list[Ref] | None = None,
          assets: list[Asset] | None = None) -> Skill:
    return Skill(name=name, refs=refs or [], assets=assets or [])

def module(name: str, *skills: Skill, description: str = "", category: str = "",
           keywords: list[str] | None = None, display_name: str = "") -> Module:
    return Module(name=name, skills=list(skills), description=description,
                  category=category, keywords=keywords or [], display_name=display_name)


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------

REF_PATTERN = re.compile(r"^\{\{\s*ref:(.+?)\s*\}\}$", re.MULTILINE)
# Also matches markdown links to references/ (e.g. [references/foo.md](references/foo.md))
REF_LINK_PATTERN = re.compile(r"\[references/(.+?)\]\(references/", re.MULTILINE)
# Inline directive: {{ skill:<name> }} or {{ skill:<module>/<name> }}
SKILL_REF_PATTERN = re.compile(r"\{\{\s*skill:(.+?)\s*\}\}")
# Inline directive: {{ pd-version }} -> pd-vX.Y.Z tag from pd-components/package.json
PD_VERSION_PATTERN = re.compile(r"\{\{\s*pd-version\s*\}\}")
MAX_OUTPUT_CHARS = 15_000


def _read_pd_version(src_dir: str) -> str:
    """Read pd-components version from package.json and return the git tag (e.g. 'pd-v0.4.0')."""
    pkg_path = os.path.join(os.path.dirname(src_dir), "pd-components", "package.json")
    with open(pkg_path) as f:
        return f"pd-v{json.load(f)['version']}"

INDEX_PATTERN = re.compile(r"^\{\{\s*index:techniques\s*\}\}$", re.MULTILINE)
CARD_PREFIX = "technique-"
REQUIRED_CARD_KEYS = ["name", "summary", "oracle", "archetypes", "criticality-min",
                      "volatility-fit", "harness", "pairs-with", "upgrade-looser",
                      "upgrade-stricter", "cost-author", "cost-maintain", "cost-run"]
REQUIRED_CARD_SECTIONS = [
    "What it is & what it catches/misses",
    "When to prescribe / when not",
    "Prerequisites",
    "Design decisions",
    "Derivation guidance",
    "Minimum viable instance vs full rigor",
    "Harness changes",
    "How to get to a walking skeleton",
    "Acceptance criteria to embed",
    "Composition",
    "Failure modes & retirement triggers",
    "Tool pointers",
]


def _replace_skill_ref(m: re.Match) -> str:
    """Replace {{ skill:X }} with the bare skill name (stripping module qualifier)."""
    raw = m.group(1).strip()
    if "/" in raw:
        _, skill_name = raw.split("/", 1)
    else:
        skill_name = raw
    return skill_name


def _parse_frontmatter(text: str) -> dict | None:
    """Extract YAML frontmatter as a simple key-value dict (no pyyaml dependency)."""
    if not text.startswith("---"):
        return None
    end = text.index("---", 3)
    if end == -1:
        return None
    fm: dict[str, str] = {}
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm


def _validate_card(path: str) -> list[str]:
    """Return a list of error strings for a malformed technique card."""
    with open(path) as f:
        text = f.read()

    errs: list[str] = []
    filename = os.path.basename(path)

    fm = _parse_frontmatter(text)
    if fm is None:
        errs.append(f"Card '{filename}' missing frontmatter")
        return errs

    for key in REQUIRED_CARD_KEYS:
        if not fm.get(key):
            errs.append(f"Card '{filename}' missing required key '{key}'")

    headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
    heading_set = set(headings)

    for title in REQUIRED_CARD_SECTIONS:
        if title not in heading_set:
            errs.append(f"Card '{filename}' missing required section '## {title}'")

    found_order = [h for h in headings if h in set(REQUIRED_CARD_SECTIONS)]
    canonical_order = [s for s in REQUIRED_CARD_SECTIONS if s in heading_set]
    if found_order != canonical_order:
        for actual, expected in zip(found_order, canonical_order):
            if actual != expected:
                errs.append(f"Card '{filename}' section '## {actual}' is out of order (expected '## {expected}')")
                break

    return errs


def render_techniques_index(sk: Skill, refs_dir: str) -> str:
    """Markdown table generated from each technique-*.md card's frontmatter."""
    cards = [r for r in sk.refs if r.filename.startswith(CARD_PREFIX)]

    rows: list[str] = []
    for card in cards:
        card_path = os.path.join(refs_dir, card.filename)
        with open(card_path) as f:
            fm = _parse_frontmatter(f.read())
        if fm is None:
            continue
        link = f"[{fm.get('name', card.filename)}](references/{card.filename})"
        rows.append(
            f"| {fm.get('name', '')} "
            f"| {fm.get('summary', '')} "
            f"| {fm.get('oracle', '')} "
            f"| {fm.get('archetypes', '')} "
            f"| {fm.get('criticality-min', '')} "
            f"| {fm.get('volatility-fit', '')} "
            f"| {link} |"
        )

    header = "| Technique | What it catches | Oracle | Archetypes | Crit | Volatility | Link |"
    sep = "| --- | --- | --- | --- | --- | --- | --- |"
    return "\n".join([header, sep] + rows)


def compile(modules: list[Module], src_dir: str | None = None, out_dir: str | None = None) -> None:
    if src_dir is None:
        src_dir = os.path.dirname(os.path.abspath(__file__))
    if out_dir is None:
        out_dir = os.path.join(os.path.dirname(src_dir), "skills")
    repo_root = os.path.dirname(src_dir)

    errors: list[str] = []
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # Phase 1: validate everything before writing any files
    # ------------------------------------------------------------------
    for mod in modules:
        mod_dir = os.path.join(src_dir, mod.name)
        refs_dir = os.path.join(mod_dir, "refs")
        skills_dir = os.path.join(mod_dir, "skills")

        if not os.path.isdir(mod_dir):
            errors.append(f"Module directory not found: {mod_dir}")
            continue

        for sk in mod.skills:
            tag = f"[{mod.name}/{sk.name}]"
            template_path = os.path.join(skills_dir, sk.name, "SKILL.md")

            # Template must exist
            if not os.path.isfile(template_path):
                errors.append(f"{tag} Template not found: {template_path}")
                continue

            # Declared refs must exist on disk
            for r in sk.refs:
                ref_path = os.path.join(refs_dir, r.filename)
                if not os.path.isfile(ref_path):
                    errors.append(f"{tag} Ref file not found: {ref_path}")
                elif r.filename.startswith(CARD_PREFIX):
                    for err in _validate_card(ref_path):
                        errors.append(f"{tag} {err}")

            # Declared assets must exist on disk (built before compile, e.g.
            # `make pd-components` produces the pd-lint.mjs bundle).
            for a in sk.assets:
                asset_path = os.path.join(repo_root, a.src)
                if not os.path.isfile(asset_path):
                    errors.append(f"{tag} Asset not found: {a.src} (build it before compiling)")

            # Read template
            with open(template_path) as f:
                template = f.read()

            # Frontmatter checks
            fm = _parse_frontmatter(template)
            if fm is None:
                errors.append(f"{tag} Missing YAML frontmatter")
            else:
                if not fm.get("name"):
                    errors.append(f"{tag} Missing 'name' in frontmatter")
                if not fm.get("description"):
                    errors.append(f"{tag} Missing 'description' in frontmatter")

            # Cross-check template tags vs DSL declarations
            used_refs = set(m.strip() for m in REF_PATTERN.findall(template))
            used_refs |= set(m.strip() for m in REF_LINK_PATTERN.findall(template))
            if INDEX_PATTERN.search(template):
                used_refs |= {r.filename for r in sk.refs if r.filename.startswith(CARD_PREFIX)}
            declared_refs = {r.filename for r in sk.refs}

            for tag_name in used_refs - declared_refs:
                errors.append(f"{tag} Template uses {{{{ ref:{tag_name} }}}} but ref is not declared in DSL")

            for tag_name in declared_refs - used_refs:
                warnings.append(f"{tag} Ref '{tag_name}' declared but never used in template")

    # Build global skill lookup: skill_name -> [module_names]
    skill_lookup: dict[str, list[str]] = {}
    for mod in modules:
        for sk in mod.skills:
            skill_lookup.setdefault(sk.name, []).append(mod.name)

    # Validate {{ skill:X }} references in templates and ref files
    for mod in modules:
        mod_dir = os.path.join(src_dir, mod.name)
        refs_dir = os.path.join(mod_dir, "refs")
        skills_dir = os.path.join(mod_dir, "skills")

        if not os.path.isdir(mod_dir):
            continue

        for sk in mod.skills:
            tag = f"[{mod.name}/{sk.name}]"
            template_path = os.path.join(skills_dir, sk.name, "SKILL.md")

            # Collect all content to scan: template + ref files
            contents_to_scan: list[tuple[str, str]] = []  # (label, content)
            if os.path.isfile(template_path):
                with open(template_path) as f:
                    contents_to_scan.append((f"{tag} template", f.read()))
            for r in sk.refs:
                ref_path = os.path.join(refs_dir, r.filename)
                if os.path.isfile(ref_path):
                    with open(ref_path) as f:
                        contents_to_scan.append((f"{tag} ref '{r.filename}'", f.read()))

            for label, content in contents_to_scan:
                for m in SKILL_REF_PATTERN.finditer(content):
                    raw = m.group(1).strip()
                    if "/" in raw:
                        mod_name, skill_name = raw.split("/", 1)
                        # Verify module exists
                        mod_names = {md.name for md in modules}
                        if mod_name not in mod_names:
                            errors.append(f"{label}: {{{{ skill:{raw} }}}} references unknown module '{mod_name}'")
                        elif skill_name not in {s.name for md in modules if md.name == mod_name for s in md.skills}:
                            errors.append(f"{label}: {{{{ skill:{raw} }}}} references unknown skill '{skill_name}' in module '{mod_name}'")
                    else:
                        matches = skill_lookup.get(raw, [])
                        if len(matches) == 0:
                            errors.append(f"{label}: {{{{ skill:{raw} }}}} references unknown skill '{raw}'")
                        elif len(matches) > 1:
                            errors.append(
                                f"{label}: {{{{ skill:{raw} }}}} is ambiguous — skill '{raw}' exists in modules: "
                                f"{', '.join(sorted(matches))}. Use qualified form {{{{ skill:<module>/{raw} }}}}"
                            )

    # Print warnings
    for w in warnings:
        print(f"  WARN: {w}", file=sys.stderr)

    if errors:
        print(f"\nValidation failed with {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Phase 2: render templates and write output
    # ------------------------------------------------------------------
    pd_version = _read_pd_version(src_dir)
    compiled = 0

    for mod in modules:
        mod_dir = os.path.join(src_dir, mod.name)
        refs_dir = os.path.join(mod_dir, "refs")
        skills_dir = os.path.join(mod_dir, "skills")

        for sk in mod.skills:
            tag = f"[{mod.name}/{sk.name}]"
            template_path = os.path.join(skills_dir, sk.name, "SKILL.md")

            with open(template_path) as f:
                content = f.read()

            # Expand {{ ref:X }} tags
            def replace_ref(m: re.Match) -> str:
                filename = m.group(1).strip()
                with open(os.path.join(refs_dir, filename)) as f:
                    return f.read().rstrip("\n")

            rendered = REF_PATTERN.sub(replace_ref, content)
            rendered = INDEX_PATTERN.sub(lambda m: render_techniques_index(sk, refs_dir), rendered)

            # Expand {{ skill:X }} and {{ pd-version }} tags
            rendered = SKILL_REF_PATTERN.sub(_replace_skill_ref, rendered)
            rendered = PD_VERSION_PATTERN.sub(pd_version, rendered)

            # Size check
            if len(rendered) > MAX_OUTPUT_CHARS:
                errors.append(
                    f"{tag} Rendered output is {len(rendered):,} chars (limit: {MAX_OUTPUT_CHARS:,})"
                )
                continue

            # Write compiled skill
            skill_out = os.path.join(out_dir, sk.name)
            os.makedirs(skill_out, exist_ok=True)

            with open(os.path.join(skill_out, "SKILL.md"), "w") as f:
                f.write(rendered)

            # Copy referenced files to references/ (substituting inline directives)
            if sk.refs:
                refs_out = os.path.join(skill_out, "references")
                os.makedirs(refs_out, exist_ok=True)
                for r in sk.refs:
                    src_path = os.path.join(refs_dir, r.filename)
                    dst_path = os.path.join(refs_out, r.filename)
                    with open(src_path) as f:
                        ref_content = f.read()
                    needs_render = SKILL_REF_PATTERN.search(ref_content) or PD_VERSION_PATTERN.search(ref_content)
                    if needs_render:
                        rendered_ref = SKILL_REF_PATTERN.sub(_replace_skill_ref, ref_content)
                        rendered_ref = PD_VERSION_PATTERN.sub(pd_version, rendered_ref)
                        with open(dst_path, "w") as f:
                            f.write(rendered_ref)
                    else:
                        shutil.copy2(src_path, dst_path)

            # Copy prebuilt assets (e.g. the pd-components CLI linter bundle)
            # verbatim into the skill output, preserving file mode.
            for a in sk.assets:
                asset_src = os.path.join(repo_root, a.src)
                asset_dst = os.path.join(skill_out, a.dst)
                os.makedirs(os.path.dirname(asset_dst), exist_ok=True)
                shutil.copy2(asset_src, asset_dst)

            compiled += 1
            print(f"  {sk.name} ({len(rendered):,} chars)")

    if errors:
        print(f"\nCompilation failed with {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nCompiled {compiled} skill(s) -> {out_dir}")

    # Generate install.sh
    _generate_install_script(modules, repo_root)

    # Generate the standalone `skills` CLI wrapper
    _generate_cli_script(modules, repo_root)

    # Generate Claude Code marketplace + per-module plugins
    _generate_plugins(modules, out_dir, repo_root)


# ---------------------------------------------------------------------------
# Install script generator
# ---------------------------------------------------------------------------

REPO = "mistakenot/skills"

def _generate_install_script(modules: list[Module], repo_root: str) -> None:
    """Generate install.sh at repo root with baked-in module→skill mappings."""

    # Build the case block for each module
    case_entries: list[str] = []
    module_names: list[str] = []
    for mod in modules:
        module_names.append(mod.name)
        skill_names = ",".join(sk.name for sk in mod.skills)
        case_entries.append(
            f"    {mod.name})\n"
            f"      SKILLS=\"{skill_names}\"\n"
            f"      ;;"
        )

    case_block = "\n".join(case_entries)
    module_list = ", ".join(module_names)

    script = f'''\
#!/usr/bin/env bash
# Auto-generated by src/compile.py — do not edit manually.
set -euo pipefail

REPO="{REPO}"
AGENTS="claude-code codex"

usage() {{
  cat <<EOF
Usage: ./install.sh [OPTIONS]

Install skills from {REPO}.

Options:
  --module <name>   Install only skills from a specific module.
                    Available modules: {module_list}
  --agent <agents>  Override target agents (default: claude-code codex).
                    Use '*' for all agents.
  -h, --help        Show this help message.

Examples:
  ./install.sh                              # Install all skills
  ./install.sh --module planning-workflow   # Install only planning skills
  ./install.sh --agent claude-code          # Install all skills to claude-code only
EOF
  exit 0
}}

MODULE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --module)
      MODULE="$2"
      shift 2
      ;;
    --agent)
      AGENTS="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      ;;
  esac
done

if [[ -z "$MODULE" ]]; then
  npx skills add "$REPO" -s \'*\' -a $AGENTS -y
else
  case "$MODULE" in
{case_block}
    *)
      echo "Unknown module: $MODULE" >&2
      echo "Available modules: {module_list}" >&2
      exit 1
      ;;
  esac
  IFS=',' read -ra SKILL_ARRAY <<< "$SKILLS"
  for S in "${{SKILL_ARRAY[@]}}"; do
    npx skills add "$REPO" -s "$S" -a $AGENTS -y
  done
fi
'''

    install_path = os.path.join(repo_root, "install.sh")
    with open(install_path, "w") as f:
        f.write(script)
    os.chmod(install_path, os.stat(install_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Generated install.sh ({len(modules)} modules)")


# ---------------------------------------------------------------------------
# Standalone `skills` CLI generator
# ---------------------------------------------------------------------------

# The generated CLI installs as `sk` (the bare `skills` name collides with the
# npm `skills` binary this wraps). Raw URL it fetches to self-update; tracks the
# default branch.
CLI_FILENAME = "sk.sh"
CLI_SELF_URL = f"https://raw.githubusercontent.com/{REPO}/main/{CLI_FILENAME}"

# Static body of the CLI. Dynamic parts are spliced in via __PLACEHOLDER__
# tokens (not f-string/format) so the bash `$` and `{}` need no escaping.
_CLI_TEMPLATE = r'''#!/usr/bin/env bash
# Auto-generated by src/compile.py — do not edit manually.
#
# A friendly wrapper around `npx skills@latest` for installing the skill
# packages (bundles of related skills) from __REPO__. Installed as `sk` because
# the bare `skills` name belongs to the npm CLI this delegates to.
#
#   sk ls                List available packages
#   sk add <package>     Install a package's skills ('all' for everything)
#   sk update            Update all installed skills
#
# Install:
#   curl -fsSL __SELF_URL__ -o ~/.local/bin/sk && chmod +x ~/.local/bin/sk
#
# On every run the script self-updates from GitHub; if a newer version is
# found it is written in place and you are asked to re-run your command.
set -euo pipefail

REPO="__REPO__"
SELF_URL="${SKILLS_SELF_URL:-__SELF_URL__}"
AGENTS="${SKILLS_AGENTS:-__AGENTS_DEFAULT__}"

PACKAGES="__PACKAGES__"

pkg_desc() {
  case "$1" in
__PKG_DESC_CASES__
    *) return 1 ;;
  esac
}

pkg_skills() {
  case "$1" in
__PKG_SKILLS_CASES__
    *) return 1 ;;
  esac
}

# Run a command, or just print it when SKILLS_DRY_RUN=1 (used by tests).
run() {
  if [[ "${SKILLS_DRY_RUN:-}" == "1" ]]; then
    echo "+ $*"
  else
    "$@"
  fi
}

# Absolute path to this script, resolving any symlinks.
_self_path() {
  local src="${BASH_SOURCE[0]}" dir
  while [ -h "$src" ]; do
    dir="$(cd -P "$(dirname "$src")" >/dev/null 2>&1 && pwd)"
    src="$(readlink "$src")"
    [[ "$src" != /* ]] && src="$dir/$src"
  done
  dir="$(cd -P "$(dirname "$src")" >/dev/null 2>&1 && pwd)"
  printf '%s/%s\n' "$dir" "$(basename "$src")"
}

# Fetch the latest version of this script. If it differs, overwrite self and
# exit so the user re-runs against the new version. Fails open: any problem
# (offline, no curl, not writable) silently skips the update.
self_update() {
  if [[ "${SKILLS_NO_SELFUPDATE:-}" == "1" || "${SKILLS_DRY_RUN:-}" == "1" ]]; then
    return 0
  fi
  command -v curl >/dev/null 2>&1 || return 0
  local self tmp
  self="$(_self_path)"
  [[ -w "$self" ]] || return 0
  tmp="$(mktemp)" || return 0
  if curl -fsSL "$SELF_URL" -o "$tmp" 2>/dev/null \
      && [[ -s "$tmp" ]] \
      && head -n1 "$tmp" | grep -q '^#!' \
      && ! cmp -s "$tmp" "$self"; then
    cat "$tmp" > "$self"
    rm -f "$tmp"
    echo "sk: self-updated to the latest version — please re-run your command." >&2
    exit 0
  fi
  rm -f "$tmp"
  return 0
}

usage() {
  cat <<EOF
sk — install reusable agent skill packages from $REPO

Usage:
  sk ls                 List available packages
  sk add <package>...    Install one or more packages ('all' for everything)
  sk update [args...]   Update all installed skills (default: project scope;
                        pass -g for global, -p for project, or skill names)
  sk help               Show this help

Each "package" is a bundle of related skills. Run 'sk ls' to see them.
Skills install to project-local .agents/ and .claude/ by default.
The script self-updates from GitHub on each run.

Environment:
  SKILLS_AGENTS         Target agents (default: "__AGENTS_DEFAULT__")
  SKILLS_NO_SELFUPDATE  Set to 1 to disable self-update
  SKILLS_SELF_URL       Override the URL self-update fetches from (e.g. a fork)
  SKILLS_DRY_RUN        Set to 1 to print commands instead of running them
EOF
}

cmd_ls() {
  echo "Available packages from $REPO:"
  echo
  local p
  for p in $PACKAGES; do
    printf '  %-18s %s\n' "$p" "$(pkg_desc "$p")"
  done
  echo
  echo "Install one with:  sk add <package>"
  echo "Install all with:  sk add all"
}

add_one() {
  local pkg="$1"
  if [[ "$pkg" == "all" ]]; then
    echo "==> Installing all skills from $REPO"
    run npx skills@latest add "$REPO" -s '*' -a $AGENTS -y
    return
  fi
  local list
  if ! list="$(pkg_skills "$pkg")"; then
    echo "sk add: unknown package '$pkg' (run 'sk ls')" >&2
    exit 1
  fi
  local count
  count="$(echo $list | wc -w | tr -d ' ')"
  echo "==> Installing package '$pkg' ($count skills) from $REPO"
  local s
  for s in $list; do
    run npx skills@latest add "$REPO" -s "$s" -a $AGENTS -y
  done
}

cmd_add() {
  if [[ $# -eq 0 ]]; then
    echo "sk add: missing package name (run 'sk ls')" >&2
    exit 1
  fi
  local pkg
  for pkg in "$@"; do
    add_one "$pkg"
  done
}

cmd_update() {
  # Forward extra args to `skills update`, e.g. `sk update -g` (global scope),
  # `sk update -p` (project scope), or specific skill names.
  echo "==> Updating all installed skills"
  run npx skills@latest update -y "$@"
}

main() {
  self_update

  local cmd="${1:-help}"
  if [[ $# -gt 0 ]]; then shift; fi

  case "$cmd" in
    ls|list)            cmd_ls "$@" ;;
    add|install)        cmd_add "$@" ;;
    update|upgrade)     cmd_update "$@" ;;
    help|-h|--help)     usage ;;
    *)
      echo "sk: unknown command '$cmd'" >&2
      echo >&2
      usage >&2
      exit 1
      ;;
  esac
}

main "$@"
'''


def _generate_cli_script(modules: list[Module], repo_root: str) -> None:
    """Generate the standalone `skills` CLI (skills.sh) at the repo root.

    Package→skill mappings and descriptions are baked in at compile time, so
    the CLI stays in sync with the DSL. Users curl it to ~/.local/bin/skills;
    it self-updates from GitHub on each run.
    """
    desc_cases: list[str] = []
    skills_cases: list[str] = []
    names: list[str] = []
    for mod in modules:
        names.append(mod.name)
        desc = mod.description.replace('"', r'\"')
        desc_cases.append(f'    {mod.name}) echo "{desc}" ;;')
        skill_names = " ".join(sk.name for sk in mod.skills)
        skills_cases.append(f'    {mod.name}) echo "{skill_names}" ;;')

    script = (
        _CLI_TEMPLATE
        .replace("__REPO__", REPO)
        .replace("__SELF_URL__", CLI_SELF_URL)
        .replace("__AGENTS_DEFAULT__", "claude-code codex")
        .replace("__PACKAGES__", " ".join(names))
        .replace("__PKG_DESC_CASES__", "\n".join(desc_cases))
        .replace("__PKG_SKILLS_CASES__", "\n".join(skills_cases))
    )

    cli_path = os.path.join(repo_root, CLI_FILENAME)
    with open(cli_path, "w") as f:
        f.write(script)
    os.chmod(cli_path, os.stat(cli_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Generated {CLI_FILENAME} ({len(modules)} packages)")


# ---------------------------------------------------------------------------
# Claude Code marketplace + plugin generator
# ---------------------------------------------------------------------------

MARKETPLACE_NAME = "mistakenot-skills"
MARKETPLACE_DESCRIPTION = (
    "Reusable agent skills for planning, executing, and shipping software with "
    "AI agents — installable as Claude Code plugins."
)
OWNER = {
    "name": "Charlie",
    "email": "github.5ef725@todevnull.work",
    "url": f"https://github.com/{REPO.split('/')[0]}",
}
PLUGIN_HOMEPAGE = f"https://github.com/{REPO}"
PLUGIN_MANIFEST_SCHEMA = "https://json.schemastore.org/claude-code-plugin-manifest.json"
MARKETPLACE_SCHEMA = "https://json.schemastore.org/claude-code-marketplace.json"


def _generate_plugins(modules: list[Module], out_dir: str, repo_root: str) -> None:
    """Generate a Claude Code marketplace and one plugin per module.

    Alongside the existing flat skills/ output this emits:
      .claude-plugin/marketplace.json          — lists every module as a plugin
      plugins/<module>/.claude-plugin/plugin.json
      plugins/<module>/skills/<skill>/...       — copied from compiled skills/

    The whole plugins/ tree and the marketplace manifest are regenerated from
    scratch each compile so they never drift from the DSL. The `version` field
    is intentionally omitted: Claude Code then versions each plugin by git commit
    SHA, so consumers pick up changes on every commit with no manual bump.
    """
    plugins_root = os.path.join(repo_root, "plugins")
    if os.path.isdir(plugins_root):
        shutil.rmtree(plugins_root)

    entries: list[dict] = []
    for mod in modules:
        plugin_dir = os.path.join(plugins_root, mod.name)
        meta_dir = os.path.join(plugin_dir, ".claude-plugin")
        skills_dir = os.path.join(plugin_dir, "skills")
        os.makedirs(meta_dir)
        os.makedirs(skills_dir)

        manifest: dict = {
            "$schema": PLUGIN_MANIFEST_SCHEMA,
            "name": mod.name,
            "description": mod.description,
            "author": {"name": OWNER["name"], "email": OWNER["email"]},
            "homepage": PLUGIN_HOMEPAGE,
            "repository": PLUGIN_HOMEPAGE,
            "license": "MIT",
        }
        if mod.display_name:
            manifest["displayName"] = mod.display_name
        if mod.keywords:
            manifest["keywords"] = mod.keywords
        with open(os.path.join(meta_dir, "plugin.json"), "w") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")

        # Copy each compiled skill (SKILL.md + references/) into the plugin
        for sk in mod.skills:
            shutil.copytree(
                os.path.join(out_dir, sk.name),
                os.path.join(skills_dir, sk.name),
            )

        entry: dict = {
            "name": mod.name,
            "source": f"./plugins/{mod.name}",
            "description": mod.description,
        }
        if mod.category:
            entry["category"] = mod.category
        entries.append(entry)

    marketplace = {
        "$schema": MARKETPLACE_SCHEMA,
        "name": MARKETPLACE_NAME,
        "description": MARKETPLACE_DESCRIPTION,
        "owner": OWNER,
        "plugins": entries,
    }
    mp_dir = os.path.join(repo_root, ".claude-plugin")
    os.makedirs(mp_dir, exist_ok=True)
    with open(os.path.join(mp_dir, "marketplace.json"), "w") as f:
        json.dump(marketplace, f, indent=2)
        f.write("\n")

    print(f"Generated marketplace '{MARKETPLACE_NAME}' + {len(modules)} plugin(s) -> plugins/")


# ---------------------------------------------------------------------------
# Module declarations
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # shared across all skills in this module
    overview = ref("workflow-overview.md")

    planning = module("planning-workflow",
        skill("new-epic",               refs=[overview, ref("epic-overview.md"), ref("epic-tabs.md")]),
        skill("new-task",               refs=[overview, ref("tab-requirements.md")]),
        skill("new-solution",           refs=[overview, ref("tab-verification.md"), ref("tab-solution.md"), ref("template-context.md")]),
        skill("new-plan",               refs=[overview, ref("tab-plan.md")]),
        skill("review-task",            refs=[overview, ref("review-format.md"), ref("review-format-html.md")]),
        skill("request-codex-review",   refs=[overview, ref("review-format.md"), ref("review-format-html.md")]),
        skill("request-claude-review",  refs=[overview, ref("review-format.md"), ref("review-format-html.md")]),
        skill("request-grok-review",    refs=[overview, ref("review-format.md"), ref("review-format-html.md")]),
        skill("resolve-comments",       refs=[overview, ref("review-format.md"), ref("review-format-html.md")]),
        skill("commit-task",            refs=[overview, ref("commit-conventions.md"), ref("task-status.md")]),
        skill("execute-task",           refs=[overview, ref("template-pr-body.md"), ref("worktree-conventions.md"), ref("commit-conventions.md"), ref("execute-task-full.md"), ref("task-status.md")]),
        skill("delegate-task",          refs=[overview, ref("task-status.md"), ref("delegating-to-agents.md")]),
        skill("delegate",               refs=[ref("delegating-to-agents.md")]),
        skill("status-report",          refs=[overview, ref("delegating-to-agents.md")]),
        skill("address-feedback",       refs=[overview]),
        skill("complete-task",          refs=[overview, ref("template-feedback.md"), ref("commit-conventions.md")]),
        skill("code-review",            refs=[overview]),
        skill("task-feedback-analyser", refs=[overview, ref("template-rule.md")]),
        description="End-to-end AI-agent task delivery: requirements, solution, plan, review, execute, and ship features through a structured plan-to-merge workflow.",
        category="productivity",
        keywords=["planning", "workflow", "code-review", "task-management"],
    )

    ideation = module("ideation",
        skill("generate-10-ideas"),
        skill("fan-out-user-simulation"),
        description="Structured ideation: generate high-impact feature ideas and run synthetic user-research simulations to decide what to build next.",
        category="productivity",
        keywords=["ideation", "brainstorming", "user-research"],
    )

    maintenance = module("maintenance",
        skill("revise-readme"),
        description="Documentation maintenance: keep READMEs and docs in sync with the current state of the code.",
        category="productivity",
        keywords=["documentation", "readme"],
    )

    exploration = module("exploration",
        skill("tech-spike"),
        description="De-risk ideas before building: run exploratory tech spikes that validate assumptions and stress-test approaches.",
        category="development",
        keywords=["tech-spike", "prototyping", "research"],
    )

    rich_docs = module("rich-docs",
        skill("planning-doc", assets=[
            asset("pd-components/dist/pd-lint.mjs", "scripts/pd-lint.mjs"),
        ]),
        description="Author rich single-file HTML planning docs with tabs, mermaid diagrams, file-change trees, and inline comment threads.",
        category="productivity",
        keywords=["planning", "documentation", "html"],
    )

    reflection = module("reflection",
        skill("learning-diary"),
        description="Mine git history, PRs, and session transcripts into a structured learning diary of techniques and breakthroughs.",
        category="productivity",
        keywords=["learning", "reflection", "diary"],
    )

    assurance = module("assurance",
        skill("assurance-strategist", refs=[ref("technique-unit-testing.md"), ref("technique-property-based-testing.md"), ref("technique-react-unit-testing.md")]),
        description="Design end-to-end assurance and testing strategies for autonomous agent-built software.",
        category="development",
        keywords=["testing", "assurance", "verification"],
    )

    research = module("research",
        skill("borrow-from-oss", refs=[ref("file-format.md")]),
        description="External-research skills: track open-source repos and mine their updates into a ranked backlog of ideas to borrow.",
        category="productivity",
        keywords=["research", "inspiration", "open-source", "competitive-analysis"],
    )

    compile([planning, ideation, maintenance, exploration, rich_docs, reflection, assurance, research])
