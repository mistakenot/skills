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
MAX_OUTPUT_CHARS = 15_000


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
            declared_refs = {r.filename for r in sk.refs}

            for tag_name in used_refs - declared_refs:
                errors.append(f"{tag} Template uses {{{{ ref:{tag_name} }}}} but ref is not declared in DSL")

            for tag_name in declared_refs - used_refs:
                warnings.append(f"{tag} Ref '{tag_name}' declared but never used in template")

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

            # Copy referenced files to references/
            if sk.refs:
                refs_out = os.path.join(skill_out, "references")
                os.makedirs(refs_out, exist_ok=True)
                for r in sk.refs:
                    shutil.copy2(
                        os.path.join(refs_dir, r.filename),
                        os.path.join(refs_out, r.filename),
                    )

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
  npx skills add "$REPO" -s "$SKILLS" -a $AGENTS -y
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
        skill("v1-new-task",               refs=[overview, ref("template-requirements.md")]),
        skill("v1-new-solution",           refs=[overview, ref("template-solution.md"), ref("template-context.md"), ref("artifact-guidelines.md")]),
        skill("v1-new-plan",               refs=[overview, ref("template-context.md"), ref("template-plan.md"), ref("artifact-guidelines.md")]),
        skill("v1-review-task",            refs=[overview, ref("review-format.md")]),
        skill("v1-request-codex-review",   refs=[overview, ref("review-format.md")]),
        skill("v1-request-claude-review",  refs=[overview, ref("review-format.md")]),
        skill("v1-resolve-comments",       refs=[overview, ref("review-format.md")]),
        skill("v1-commit-task",            refs=[overview, ref("commit-conventions.md")]),
        skill("v1-execute-task",           refs=[overview, ref("template-pr-body.md"), ref("worktree-conventions.md"), ref("commit-conventions.md")]),
        skill("v1-delegate-task",          refs=[overview]),
        skill("v1-executor-status-check",  refs=[overview]),
        skill("v1-address-feedback",       refs=[overview]),
        skill("v1-complete-task",          refs=[overview, ref("template-feedback.md"), ref("commit-conventions.md")]),
        skill("v1-code-review",            refs=[overview]),
        skill("v1-task-feedback-analyser", refs=[overview, ref("template-rule.md")]),
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

    compile([planning, ideation, maintenance, exploration, rich_docs, reflection])
