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
class VarFile:
    """A template variable whose value is a file's contents.

    `path` is relative to the template's directory (e.g. 'codex.md' for
    templates/request-agent-review/codex.md).
    """
    path: str

@dataclasses.dataclass
class Skill:
    name: str
    refs: list[Ref]
    assets: list["Asset"] = dataclasses.field(default_factory=list)
    # When set, the skill is rendered from templates/<template>/SKILL.md instead
    # of skills/<name>/SKILL.md, with {{ var:X }} filled from `vars`. Lets
    # near-identical skills (one per agent CLI) share a single source.
    template: str | None = None
    vars: dict[str, "str | VarFile"] = dataclasses.field(default_factory=dict)

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

def herdr_refs(*ops: str) -> list[Ref]:
    """The named herdr operation guides. Omit `ops` for all of them.

    Skills should name only the operations they actually use — shipping a
    monitoring skill a spawn guide it never reads is the progressive-disclosure
    leak this whole decomposition exists to fix.
    """
    selected = list(ops) or HERDR_OPS
    unknown = [op for op in selected if op not in HERDR_OPS]
    if unknown:
        raise ValueError(f"unknown herdr op(s) {unknown}; valid ops: {HERDR_OPS}")
    return [ref(f"herdr/{op}.md") for op in selected]

def asset(src: str, dst: str) -> Asset:
    return Asset(src=src, dst=dst)

def var_file(path: str) -> VarFile:
    return VarFile(path=path)

def skill(name: str, refs: list[Ref] | None = None,
          assets: list[Asset] | None = None,
          template: str | None = None,
          vars: dict[str, "str | VarFile"] | None = None) -> Skill:
    return Skill(name=name, refs=refs or [], assets=assets or [],
                 template=template, vars=vars or {})

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
# Inline-code references (e.g. `references/herdr/spawn-worker.md`).
REF_CODE_PATTERN = re.compile(r"`references/([^`]+?\.md)`")
# Inline directive: {{ skill:<name> }} or {{ skill:<module>/<name> }}
SKILL_REF_PATTERN = re.compile(r"\{\{\s*skill:(.+?)\s*\}\}")
# Inline directive: {{ pd-version }} -> pd-vX.Y.Z tag from pd-components/package.json
PD_VERSION_PATTERN = re.compile(r"\{\{\s*pd-version\s*\}\}")
# Inline directive: {{ var:<name> }} -> a value from the skill's `vars` (templated skills only)
VAR_PATTERN = re.compile(r"\{\{\s*var:([A-Za-z_][\w-]*)\s*\}\}")
MAX_OUTPUT_CHARS = 15_000

# ---------------------------------------------------------------------------
# herdr operation guides
#
# The delegation skills drive background coding agents through herdr. The
# policy that does not depend on herdr's command grammar (eligibility rules,
# pool roles, what to dispatch) lives in the SKILL.md body; the command grammar
# itself lives in refs/herdr/<operation>.md.
#
# The filename set is the interface contract between the bodies and the guides:
# a body step that names an operation with no guide silently loses its
# mechanism, and a guide no body names is content nobody can reach.
# ---------------------------------------------------------------------------

HERDR_OPS = [
    "list-workers",
    "read-output",
    "scan-output",
    "spawn-worker",
    "verify-worker",
    "wait-for-ready",
    "send-prompt",
    "reset-worker",
    "reap-worker",
    "label-worker",
    "unblock-worker",
]


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


def _template_path(mod_dir: str, sk: Skill) -> str:
    if sk.template:
        return os.path.join(mod_dir, "templates", sk.template, "SKILL.md")
    return os.path.join(mod_dir, "skills", sk.name, "SKILL.md")


def _load_template(mod_dir: str, sk: Skill) -> tuple[str, list[str], list[str]]:
    """Read a skill's source and fill {{ var:X }}. Returns (text, errors, warnings).

    Var values may themselves contain {{ var:X }} (a per-agent fragment naming
    the agent), so substitution repeats until nothing is left to expand.
    """
    tag = f"[{os.path.basename(mod_dir)}/{sk.name}]"
    path = _template_path(mod_dir, sk)
    with open(path) as f:
        text = f.read()
    if not sk.template:
        if VAR_PATTERN.search(text):
            return text, [f"{tag} uses {{{{ var:X }}}} but is not declared with a template"], []
        return text, [], []

    errors: list[str] = []
    values: dict[str, str] = {}
    for key, value in sk.vars.items():
        if isinstance(value, VarFile):
            var_path = os.path.join(os.path.dirname(path), value.path)
            if not os.path.isfile(var_path):
                errors.append(f"{tag} var '{key}' file not found: {var_path}")
                continue
            with open(var_path) as f:
                values[key] = f.read().rstrip("\n")
        else:
            values[key] = value

    used: set[str] = set()
    def replace_var(m: re.Match) -> str:
        key = m.group(1)
        used.add(key)
        return values.get(key, m.group(0))
    for _ in range(5):
        expanded = VAR_PATTERN.sub(replace_var, text)
        if expanded == text:
            break
        text = expanded
    for key in sorted(set(VAR_PATTERN.findall(text))):
        errors.append(f"{tag} template uses {{{{ var:{key} }}}} but the skill declares no such var")

    warnings = [f"{tag} var '{k}' declared but never used" for k in sorted(set(sk.vars) - used)]
    fm = _parse_frontmatter(text)
    if fm and fm.get("name") != sk.name:
        errors.append(f"{tag} rendered frontmatter name '{fm.get('name')}' does not match skill name")
    return text, errors, warnings


def _parse_frontmatter(text: str) -> dict | None:
    """Extract top-level YAML frontmatter keys as a dict (no pyyaml dependency).

    Only unindented keys are captured. Nested blocks (e.g. `customize:`) declare
    their own `description:`/`default:` keys one level down; without the
    indentation guard those would flatten into the same dict and clobber the
    skill's real top-level values.
    """
    if not text.startswith("---"):
        return None
    end = text.index("---", 3)
    if end == -1:
        return None
    fm: dict[str, str] = {}
    for line in text[3:end].strip().splitlines():
        if line[:1].isspace() or line.lstrip().startswith("-"):
            continue  # nested key or list item, not a top-level field
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

        if not os.path.isdir(mod_dir):
            errors.append(f"Module directory not found: {mod_dir}")
            continue

        for sk in mod.skills:
            tag = f"[{mod.name}/{sk.name}]"
            template_path = _template_path(mod_dir, sk)

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

            # Read template (filling {{ var:X }} for templated skills)
            template, var_errors, var_warnings = _load_template(mod_dir, sk)
            errors.extend(var_errors)
            warnings.extend(var_warnings)

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
            used_refs |= set(m.strip() for m in REF_CODE_PATTERN.findall(template))

            # A ref may point at another ref (e.g. worker-pools.md sends the
            # reader to herdr/label-worker.md). That is real usage, so it must
            # suppress the orphan warning — but it must NOT force a declaration,
            # since refs also mention docs belonging to other skills entirely.
            # Hence two sets: the template drives errors, reachability drives warnings.
            reachable_refs: set[str] = set()
            for r in sk.refs:
                ref_path = os.path.join(refs_dir, r.filename)
                if not os.path.isfile(ref_path):
                    continue
                with open(ref_path) as f:
                    ref_body = f.read()
                reachable_refs |= (
                    set(m.strip() for m in REF_LINK_PATTERN.findall(ref_body))
                    | set(m.strip() for m in REF_CODE_PATTERN.findall(ref_body))
                )
            if INDEX_PATTERN.search(template):
                used_refs |= {r.filename for r in sk.refs if r.filename.startswith(CARD_PREFIX)}
            # Everything the template reaches directly, plus everything its refs
            # point onward to. Only used for the orphan warning below.
            reachable_refs |= used_refs
            declared_refs = {r.filename for r in sk.refs}

            for tag_name in used_refs - declared_refs:
                errors.append(f"{tag} Template uses {{{{ ref:{tag_name} }}}} but ref is not declared in DSL")

            for tag_name in declared_refs - reachable_refs:
                warnings.append(f"{tag} Ref '{tag_name}' declared but never used in template")

        # refs/herdr/ is an interface, not a folder: the filename set is what a
        # body is allowed to assume exists. A missing file silently drops that
        # step's mechanism; an extra file is content no body can reach.
        herdr_dir = os.path.join(refs_dir, "herdr")
        if os.path.isdir(herdr_dir):
            present = {f for f in os.listdir(herdr_dir) if f.endswith(".md")}
            expected = {f"{op}.md" for op in HERDR_OPS}
            for missing in sorted(expected - present):
                errors.append(f"[{mod.name}] refs/herdr/ is missing required operation '{missing}'")
            for extra in sorted(present - expected):
                errors.append(
                    f"[{mod.name}] refs/herdr/{extra} is not in the herdr operation set; "
                    f"add it to HERDR_OPS or remove it"
                )

    # Build global skill lookup: skill_name -> [module_names]
    skill_lookup: dict[str, list[str]] = {}
    for mod in modules:
        for sk in mod.skills:
            skill_lookup.setdefault(sk.name, []).append(mod.name)

    # Validate {{ skill:X }} references in templates and ref files
    for mod in modules:
        mod_dir = os.path.join(src_dir, mod.name)
        refs_dir = os.path.join(mod_dir, "refs")

        if not os.path.isdir(mod_dir):
            continue

        for sk in mod.skills:
            tag = f"[{mod.name}/{sk.name}]"
            template_path = _template_path(mod_dir, sk)

            # Collect all content to scan: template + ref files
            contents_to_scan: list[tuple[str, str]] = []  # (label, content)
            if os.path.isfile(template_path):
                contents_to_scan.append((f"{tag} template", _load_template(mod_dir, sk)[0]))
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

        for sk in mod.skills:
            tag = f"[{mod.name}/{sk.name}]"
            content = _load_template(mod_dir, sk)[0]

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

            # references/ is generated output: clear it so a ref that is no
            # longer declared cannot linger. Skills now declare per-skill subsets
            # (see herdr_refs), so dropping a ref is routine rather than rare,
            # and a stale copy would ship content the body never points at.
            refs_out = os.path.join(skill_out, "references")
            if os.path.isdir(refs_out):
                shutil.rmtree(refs_out)

            # Copy referenced files to references/ (substituting inline directives)
            if sk.refs:
                os.makedirs(refs_out, exist_ok=True)
                for r in sk.refs:
                    src_path = os.path.join(refs_dir, r.filename)
                    dst_path = os.path.join(refs_out, r.filename)
                    # Refs may be nested (e.g. 'ntm/spawn-worker.md'); only the
                    # references/ root is pre-created above.
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
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
TARGETS="claude,agents"

usage() {{
  cat <<EOF
Usage: ./install.sh [OPTIONS]

Install skills from {REPO} using \\`auto skill\\`.

Options:
  --module <name>    Install only skills from a specific module.
                     Available modules: {module_list}
  --target <styles>  Comma-separated output targets (default: claude,agents).
  -h, --help         Show this help message.

Examples:
  ./install.sh                              # Install all skills
  ./install.sh --module planning-workflow   # Install only planning skills
  ./install.sh --target claude              # Install to .claude/skills only

Requires the \\`auto\\` CLI: https://github.com/mistakenot/auto
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
    --target)
      TARGETS="$2"
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

if ! command -v auto >/dev/null 2>&1; then
  echo "error: 'auto' not found on PATH." >&2
  echo "Install it first: https://github.com/mistakenot/auto" >&2
  exit 1
fi

# auto resolves output targets from project config, not per-command flags, so
# the project must be initialised before adding anything.
if [[ ! -f .auto/skills/skills.yaml ]]; then
  auto skill init --project --target "$TARGETS" -y
fi

# Non-interactive shells (CI, curl | bash) can't answer the trust prompt.
TRUST=()
if [[ ! -t 0 ]]; then
  TRUST=(--trust-requested)
fi

if [[ -z "$MODULE" ]]; then
  auto skill add "$REPO" --skill \'*\' "${{TRUST[@]}}"
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
  ARGS=()
  for S in "${{SKILL_ARRAY[@]}}"; do
    ARGS+=(--skill "$S")
  done
  auto skill add "$REPO" "${{ARGS[@]}}" "${{TRUST[@]}}"
fi
'''

    install_path = os.path.join(repo_root, "install.sh")
    with open(install_path, "w") as f:
        f.write(script)
    os.chmod(install_path, os.stat(install_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Generated install.sh ({len(modules)} modules)")


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

    # every review skill: comment grammar (md + pd-thread) and where threads land by file type
    review_refs = [overview, ref("review-format.md"), ref("review-format-html.md"), ref("review-targets.md")]

    # the caller strips closed threads from regular (non-plan) docs after resolving
    strip_threads_script = asset("src/planning-workflow/scripts/strip-closed-threads.sh", "scripts/strip-closed-threads.sh")

    def request_review(agent: str, title: str, product: str) -> Skill:
        """request-<agent>-review: the shared template plus that agent's headless launch."""
        return skill(f"request-{agent}-review",
                     refs=[*review_refs, ref("review-scope.md")],
                     assets=[strip_threads_script],
                     template="request-agent-review",
                     vars={"agent": agent, "Agent": title, "product": product,
                           "invoke": var_file(f"{agent}.md")})

    herdr_worker_script = asset("src/planning-workflow/scripts/herdr-worker.sh", "scripts/herdr-worker.sh")
    # commit-task gates on a clean pd-lint of plan.html, so it carries its own
    # copy of the linter (skills can't reach into rich-doc's scripts dir).
    pd_lint_script = asset("pd-components/dist/pd-lint.mjs", "scripts/pd-lint.mjs")

    planning = module("planning-workflow",
        skill("new-epic",               refs=[overview, ref("epic-overview.md"), ref("epic-tabs.md")]),
        skill("new-task",               refs=[overview, ref("stage-requirements.md"), ref("tab-requirements.md")]),
        skill("new-solution",           refs=[overview, ref("stage-solution.md"), ref("tab-verification.md"), ref("tab-solution.md"), ref("template-context.md")]),
        skill("new-plan",               refs=[overview, ref("stage-plan.md"), ref("tab-plan.md")]),
        # runs all three stages unattended: links the same stage refs rather than
        # inlining them, so each is read only when that stage begins.
        skill("new-task-quick",         refs=[overview,
                                              ref("stage-requirements.md"), ref("stage-solution.md"), ref("stage-plan.md"),
                                              ref("tab-requirements.md"), ref("tab-verification.md"),
                                              ref("tab-solution.md"), ref("tab-plan.md"), ref("template-context.md")]),
        # composite: the root routes task mode vs file mode to review-plan / review-files
        skill("review-task",            refs=[*review_refs, ref("review-plan.md"), ref("review-files.md")]),
        # one template, one per-agent launch fragment (templates/request-agent-review/<agent>.md)
        request_review("codex",  "Codex",  "Codex"),
        request_review("claude", "Claude", "Claude Code"),
        request_review("grok",   "Grok",   "Grok CLI"),
        skill("request-council-review", refs=[*review_refs, ref("review-scope.md"), ref("headless-delegation.md")],
                                        assets=[strip_threads_script]),
        skill("resolve-comments",       refs=review_refs),
        skill("commit-task",            refs=[overview, ref("commit-conventions.md"), ref("task-status.md")],
                                        assets=[pd_lint_script]),
        skill("execute-task",           refs=[overview, ref("template-pr-body.md"), ref("worktree-conventions.md"), ref("commit-conventions.md"), ref("execute-task-full.md"), ref("task-status.md")]),
        # herdr ops per skill: dispatchers find/spawn/verify/send; the monitor
        # reads, verifies and reaps. label-worker is reached transitively, via
        # worker-pools.md.
        # The launch/verify/reap procedure is a bundled script; the herdr refs
        # remain as the manual procedure behind it and for the failure paths the
        # script reports but does not act on (interstitials, blocked workers).
        skill("delegate-task",          refs=[overview, ref("task-status.md"), ref("agent-conventions.md"), ref("worker-pools.md"),
                                              *herdr_refs("list-workers", "read-output", "scan-output", "spawn-worker",
                                                          "verify-worker", "wait-for-ready", "send-prompt",
                                                          "reset-worker", "label-worker", "unblock-worker")],
                                        assets=[herdr_worker_script]),
        skill("delegate",               refs=[ref("agent-conventions.md"), ref("worker-pools.md"),
                                              *herdr_refs("list-workers", "read-output", "scan-output", "spawn-worker",
                                                          "verify-worker", "wait-for-ready", "send-prompt",
                                                          "reset-worker", "reap-worker", "label-worker",
                                                          "unblock-worker")],
                                        assets=[herdr_worker_script]),
        skill("status-report",          refs=[overview, ref("agent-conventions.md"), ref("worker-pools.md"),
                                              *herdr_refs("list-workers", "read-output", "scan-output", "verify-worker",
                                                          "reap-worker", "reset-worker", "label-worker",
                                                          "unblock-worker")],
                                        assets=[herdr_worker_script]),
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

    council = module("consult-the-council",
        skill("consult-the-council", refs=[
            ref("strategies/blind-round.md"), ref("strategies/pre-mortem.md"),
            ref("strategies/red-team.md"), ref("strategies/dialectic.md"),
            ref("strategies/delphi.md"),
            ref("members/claude.md"), ref("members/codex.md"), ref("members/gemini.md"),
            ref("members/opencode.md"), ref("members/grok.md"),
            ref("prompts/neutral-framing.md"), ref("prompts/templates.md"),
            ref("synthesis.md"),
        ], assets=[
            asset("src/consult-the-council/scripts/council.py", "scripts/council.py"),
        ]),
        description="Consult a council of independent coding-agent models (claude, codex, gemini, opencode, grok) for diverse, unled opinions on a question; strategies, members and prompt framings compose like an SDK.",
        category="productivity",
        keywords=["council", "second-opinion", "multi-model", "diversity", "delphi"],
    )

    handoff = module("handoff",
        skill("handoff", assets=[
            asset("src/handoff/skills/handoff/scripts/handoff.py", "scripts/handoff.py"),
        ]),
        description="Machine-local handoff stack: push and pull short text notes between agent sessions using a JSONL store.",
        category="productivity",
        keywords=["handoff", "context", "jsonl", "agents"],
    )

    exploration = module("exploration",
        skill("tech-spike"),
        description="De-risk ideas before building: run exploratory tech spikes that validate assumptions and stress-test approaches.",
        category="development",
        keywords=["tech-spike", "prototyping", "research"],
    )

    rich_docs = module("rich-docs",
        skill("rich-doc", assets=[
            asset("pd-components/dist/pd-lint.mjs", "scripts/pd-lint.mjs"),
        ]),
        description="Author rich single-file HTML docs — designs, plans, proposals, reports — with tabs, mermaid diagrams, code, file trees, and inline comment threads.",
        category="productivity",
        keywords=["documentation", "html", "planning", "design-doc"],
    )

    reflect_overview = ref("reflection-overview.md")
    reflect_helper = asset("src/reflection/scripts/reflect.py", "scripts/reflect.py")
    reflection = module("reflection",
        skill("learning-diary"),
        skill("playbook-observe", refs=[reflect_overview], assets=[reflect_helper]),
        skill("playbook-refine",  refs=[reflect_overview], assets=[reflect_helper]),
        skill("playbook-search",  refs=[reflect_overview], assets=[reflect_helper]),
        description="Reflection loop: mine learnings into a diary, and observe→refine→search reusable task rules.",
        category="productivity",
        keywords=["learning", "reflection", "diary", "rules", "playbook"],
    )

    assurance = module("assurance",
        skill("assurance-strategist", refs=[ref("technique-unit-testing.md"), ref("technique-property-based-testing.md"), ref("technique-react-unit-testing.md"), ref("technique-model-based-testing.md"), ref("technique-differential-testing.md"), ref("technique-metamorphic-testing.md")]),
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

    domain_modelling = module("domain-modelling",
        skill("domain-modelling", refs=[
            ref("language-format.md"),
            ref("example-glossary.md"),
            ref("multi-context.md"),
            ref("interview-question-bank.md"),
            ref("ci-enforcement.md"),
        ], assets=[
            asset("src/domain-modelling/scripts/glossary.py", "scripts/glossary.py"),
        ]),
        description="Build and maintain a project's ubiquitous language: a DDD glossary of canonical domain terms, kept in sync with the code.",
        category="development",
        keywords=["domain-modelling", "ddd", "ubiquitous-language", "glossary", "terminology"],
    )

    grill = module("grill-me",
        skill("grill-me", refs=[
            ref("grilling-method.md"),
            ref("grilling-log-format.md"),
            ref("adr-format.md"),
        ]),
        description="Relentlessly interrogate a plan, design, or decision to surface assumptions and edge cases, recording the outcomes as numbered ADRs.",
        category="development",
        keywords=["grilling", "interrogation", "design-review", "adr", "decisions"],
    )

    eval_engineer = module("eval-engineer",
        skill("eval-engineer", refs=[
            ref("validating-the-eval.md"),
            ref("fixtures-from-history.md"),
            ref("harnesses.md"),
        ]),
        # the plan-quality improvement loop (generate, open/axial coding, iterate);
        # the tooling lives in src/plan-review/
        skill("plan-review", refs=[
            ref("plan-review-generate.md"),
            ref("plan-review-open-coding.md"),
            ref("plan-review-axial-coding.md"),
            ref("plan-review-iterate.md"),
        ]),
        description="Build, run, validate, and manage A/B evals for skills in this repo: replay real tasks, compare skill versions on cost and quality, and validate the eval before trusting it.",
        category="development",
        keywords=["eval", "evaluation", "benchmark", "ab-testing", "skill-quality"],
    )

    discovery = module("discovery",
        skill("extract-demand-from-customer-conversation", refs=[ref("pull-framework.md"), ref("urgency-signals.md")]),
        description="Customer discovery: mine real customer conversations for demand signals, jobs-to-be-done, and unmet needs.",
        category="productivity",
        keywords=["discovery", "customer-research", "jobs-to-be-done", "demand", "product"],
    )

    compile([planning, ideation, maintenance, council, handoff, exploration, rich_docs, reflection, assurance, research, domain_modelling, grill, eval_engineer, discovery])
