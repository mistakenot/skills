"""
Skill compiler — renders templated skills with shared references.

Usage:
    python src/compile.py
"""

import dataclasses
import os
import re
import shutil
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


# ---------------------------------------------------------------------------
# Module declarations
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # shared across all skills in this module
    overview = ref("workflow-overview.md")

    planning = module("planning-workflow",
        skill("new-task",               refs=[overview, ref("template-requirements.md")]),
        skill("new-solution",           refs=[overview, ref("template-solution.md"), ref("artifact-guidelines.md")]),
        skill("new-plan",               refs=[overview, ref("template-context.md"), ref("template-plan.md"), ref("artifact-guidelines.md")]),
        skill("review-task",            refs=[overview, ref("review-format.md")]),
        skill("request-codex-review",   refs=[overview, ref("review-format.md")]),
        skill("resolve-comments",       refs=[overview, ref("review-format.md")]),
        skill("commit-task",            refs=[overview, ref("commit-conventions.md")]),
        skill("execute-task",           refs=[overview, ref("template-pr-body.md"), ref("worktree-conventions.md"), ref("commit-conventions.md")]),
        skill("delegate-task",          refs=[overview]),
        skill("executor-status-check",  refs=[overview]),
        skill("address-feedback",       refs=[overview]),
        skill("complete-task",          refs=[overview, ref("template-feedback.md"), ref("commit-conventions.md")]),
        skill("code-review",            refs=[overview]),
        skill("task-feedback-analyser", refs=[overview, ref("template-rule.md")]),
    )

    compile([planning])
