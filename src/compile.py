"""
Skill compiler — renders templated skills with shared references.

Usage:
    python src/compile.py
"""

import dataclasses
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
class Skill:
    name: str
    refs: list[Ref]

@dataclasses.dataclass
class Module:
    name: str
    skills: list[Skill]


def ref(filename: str) -> Ref:
    return Ref(filename=filename)

def skill(name: str, refs: list[Ref] | None = None) -> Skill:
    return Skill(name=name, refs=refs or [])

def module(name: str, *skills: Skill) -> Module:
    return Module(name=name, skills=list(skills))


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------

REF_PATTERN = re.compile(r"^\{\{\s*ref:(.+?)\s*\}\}$", re.MULTILINE)
# Also matches markdown links to references/ (e.g. [references/foo.md](references/foo.md))
REF_LINK_PATTERN = re.compile(r"\[references/(.+?)\]\(references/", re.MULTILINE)
# Inline directive: {{ skill:<name> }} or {{ skill:<module>/<name> }}
SKILL_REF_PATTERN = re.compile(r"\{\{\s*skill:(.+?)\s*\}\}")
MAX_OUTPUT_CHARS = 15_000

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

            # Expand {{ skill:X }} tags
            rendered = SKILL_REF_PATTERN.sub(_replace_skill_ref, rendered)

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

            # Copy referenced files to references/ (substituting {{ skill:X }} if present)
            if sk.refs:
                refs_out = os.path.join(skill_out, "references")
                os.makedirs(refs_out, exist_ok=True)
                for r in sk.refs:
                    src_path = os.path.join(refs_dir, r.filename)
                    dst_path = os.path.join(refs_out, r.filename)
                    with open(src_path) as f:
                        ref_content = f.read()
                    if SKILL_REF_PATTERN.search(ref_content):
                        rendered_ref = SKILL_REF_PATTERN.sub(_replace_skill_ref, ref_content)
                        with open(dst_path, "w") as f:
                            f.write(rendered_ref)
                    else:
                        shutil.copy2(src_path, dst_path)

            compiled += 1
            print(f"  {sk.name} ({len(rendered):,} chars)")

    if errors:
        print(f"\nCompilation failed with {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nCompiled {compiled} skill(s) -> {out_dir}")

    # Generate install.sh
    repo_root = os.path.dirname(src_dir)
    _generate_install_script(modules, repo_root)


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
# Module declarations
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # shared across all skills in this module
    overview = ref("workflow-overview.md")

    planning = module("planning-workflow",
        skill("new-task",               refs=[overview, ref("template-requirements.md")]),
        skill("new-solution",           refs=[overview, ref("template-solution.md"), ref("template-context.md"), ref("artifact-guidelines.md")]),
        skill("new-plan",               refs=[overview, ref("template-context.md"), ref("template-plan.md"), ref("artifact-guidelines.md")]),
        skill("review-task",            refs=[overview, ref("review-format.md")]),
        skill("request-codex-review",   refs=[overview, ref("review-format.md")]),
        skill("request-claude-review",  refs=[overview, ref("review-format.md")]),
        skill("resolve-comments",       refs=[overview, ref("review-format.md")]),
        skill("commit-task",            refs=[overview, ref("commit-conventions.md")]),
        skill("execute-task",           refs=[overview, ref("template-pr-body.md"), ref("worktree-conventions.md"), ref("commit-conventions.md"), ref("execute-task-full.md"), ref("execute-task-mini.md")]),
        skill("new-mini-task",          refs=[overview, ref("template-mini-plan.md")]),
        skill("delegate-task",          refs=[overview]),
        skill("status-report",          refs=[overview]),
        skill("address-feedback",       refs=[overview]),
        skill("complete-task",          refs=[overview, ref("template-feedback.md"), ref("commit-conventions.md")]),
        skill("code-review",            refs=[overview]),
        skill("task-feedback-analyser", refs=[overview, ref("template-rule.md")]),
    )

    ideation = module("ideation",
        skill("generate-10-ideas"),
        skill("fan-out-user-simulation"),
    )

    maintenance = module("maintenance",
        skill("revise-readme"),
    )

    exploration = module("exploration",
        skill("tech-spike"),
    )

    rich_docs = module("rich-docs",
        skill("planning-doc"),
    )

    reflection = module("reflection",
        skill("learning-diary"),
    )

    beta_planning = module("beta-planning",
        skill("beta-new-task",     refs=[ref("beta-workflow-overview.md"), ref("html-boilerplate.md"),
                                         ref("tab-requirements.md")]),
        skill("beta-new-solution", refs=[ref("beta-workflow-overview.md"), ref("tab-verification.md"),
                                         ref("tab-solution.md"), ref("template-context.md")]),
        skill("beta-new-plan",     refs=[ref("beta-workflow-overview.md"), ref("tab-plan.md")]),
    )

    compile([planning, ideation, maintenance, exploration, rich_docs, reflection, beta_planning])
