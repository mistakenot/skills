"""
Tests for the skill compiler's technique-card features.

Covers:
  AC-2: Index regenerates when card frontmatter changes (no SKILL.md source edit).
  AC-3: Malformed cards (missing key / missing section) fail the build with
        an error naming the card and the missing element.
  AC-1 backstop: Real assurance module compiles (skip if Phase C not merged).
"""

import os
import sys
import textwrap

import pytest

# Add the src/ directory to sys.path so we can import the compiler module.
_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.abspath(_SRC_DIR))

import compile  # noqa: E402 — must follow sys.path manipulation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A minimal SKILL.md template with the {{ index:techniques }} directive.
_SKILL_TEMPLATE = textwrap.dedent("""\
    ---
    name: test-skill
    description: "A test skill for compiler tests."
    ---

    # Test Skill

    {{ index:techniques }}
""")


def _card_body() -> str:
    """Return the 12 required sections with minimal content."""
    sections = [
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
    return "\n\n".join(f"## {title}\n\nContent for {title}." for title in sections)


def _card_frontmatter(*, summary: str = "Catches regressions in pure logic") -> str:
    """Return valid technique-card frontmatter with all 13 required keys."""
    return textwrap.dedent(f"""\
        ---
        name: Foo Testing
        summary: {summary}
        oracle: exact
        archetypes: algorithmic-core, crud-surface
        criticality-min: C1
        volatility-fit: both
        harness: ci
        pairs-with: differential-testing, mutation-testing
        upgrade-looser: none
        upgrade-stricter: none
        cost-author: low
        cost-maintain: low
        cost-run: fast
        ---
    """)


def _full_card(*, summary: str = "Catches regressions in pure logic") -> str:
    """Return a complete, valid technique card (frontmatter + body)."""
    return _card_frontmatter(summary=summary) + "\n" + _card_body()


def _build_module(tmp_path, *, card_content: str | None = None):
    """
    Scaffold a throwaway module in a nested temp layout and return
    (modules_list, src_dir, out_dir) ready for compile.compile().

    Layout:
        tmp_path/repo/src/testmod/skills/test-skill/SKILL.md
        tmp_path/repo/src/testmod/refs/technique-foo.md
        tmp_path/repo/skills/   (output dir)

    The nested layout ensures install.sh lands in tmp_path/repo/ —
    a throwaway dir, never the real repo root.
    """
    src_dir = tmp_path / "repo" / "src"
    out_dir = tmp_path / "repo" / "skills"
    out_dir.mkdir(parents=True, exist_ok=True)

    mod_dir = src_dir / "testmod"
    skill_dir = mod_dir / "skills" / "test-skill"
    refs_dir = mod_dir / "refs"

    skill_dir.mkdir(parents=True, exist_ok=True)
    refs_dir.mkdir(parents=True, exist_ok=True)

    # Write the SKILL.md template
    (skill_dir / "SKILL.md").write_text(_SKILL_TEMPLATE)

    # Write the technique card
    if card_content is None:
        card_content = _full_card()
    (refs_dir / "technique-foo.md").write_text(card_content)

    # Build the DSL objects
    modules = [
        compile.module(
            "testmod",
            compile.skill("test-skill", refs=[compile.ref("technique-foo.md")]),
        )
    ]
    return modules, str(src_dir), str(out_dir)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIndexRegenerates:
    """AC-2: editing card frontmatter + recompiling changes the index row."""

    def test_index_regenerates(self, tmp_path):
        modules, src_dir, out_dir = _build_module(tmp_path)

        # --- First compile ---
        compile.compile(modules, src_dir=src_dir, out_dir=out_dir)

        compiled_skill = os.path.join(out_dir, "test-skill", "SKILL.md")
        first_output = open(compiled_skill).read()

        # The index row should contain the original summary
        assert "Catches regressions in pure logic" in first_output

        # --- Rewrite the card's summary ---
        card_path = os.path.join(src_dir, "testmod", "refs", "technique-foo.md")
        original_card = open(card_path).read()
        updated_card = original_card.replace(
            "summary: Catches regressions in pure logic",
            "summary: Detects broken arithmetic fast",
        )
        with open(card_path, "w") as f:
            f.write(updated_card)

        # --- Recompile ---
        compile.compile(modules, src_dir=src_dir, out_dir=out_dir)

        second_output = open(compiled_skill).read()

        # The index row should now reflect the new summary
        assert "Detects broken arithmetic fast" in second_output
        assert "Catches regressions in pure logic" not in second_output

        # --- Source template must NEVER have been edited ---
        template_path = os.path.join(
            src_dir, "testmod", "skills", "test-skill", "SKILL.md"
        )
        template_content = open(template_path).read()
        assert "{{ index:techniques }}" in template_content


class TestMalformedCard:
    """AC-3: malformed cards fail the build with descriptive errors."""

    def test_malformed_card_missing_key(self, tmp_path, capsys):
        """A card missing a required frontmatter key fails the build."""
        # Build a card without the 'oracle' key
        bad_fm = textwrap.dedent("""\
            ---
            name: Foo Testing
            summary: Catches regressions in pure logic
            archetypes: algorithmic-core, crud-surface
            criticality-min: C1
            volatility-fit: both
            harness: ci
            pairs-with: differential-testing, mutation-testing
            upgrade-looser: none
            upgrade-stricter: none
            cost-author: low
            cost-maintain: low
            cost-run: fast
            ---
        """)
        bad_card = bad_fm + "\n" + _card_body()

        modules, src_dir, out_dir = _build_module(tmp_path, card_content=bad_card)

        with pytest.raises(SystemExit) as exc_info:
            compile.compile(modules, src_dir=src_dir, out_dir=out_dir)

        assert exc_info.value.code != 0

        captured = capsys.readouterr()
        # Error should name the card file and the missing key
        assert "technique-foo.md" in captured.err
        assert "oracle" in captured.err

    def test_malformed_card_missing_section(self, tmp_path, capsys):
        """A card missing a required body section fails the build."""
        # Build a card with valid frontmatter but missing "## Prerequisites"
        sections_minus_prereqs = [
            "What it is & what it catches/misses",
            "When to prescribe / when not",
            # "Prerequisites" intentionally omitted
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
        body = "\n\n".join(
            f"## {title}\n\nContent for {title}." for title in sections_minus_prereqs
        )
        bad_card = _card_frontmatter() + "\n" + body

        modules, src_dir, out_dir = _build_module(tmp_path, card_content=bad_card)

        with pytest.raises(SystemExit) as exc_info:
            compile.compile(modules, src_dir=src_dir, out_dir=out_dir)

        assert exc_info.value.code != 0

        captured = capsys.readouterr()
        # Error should name the card file and the missing section
        assert "technique-foo.md" in captured.err
        assert "Prerequisites" in captured.err


# Path to the real assurance module's SKILL.md template (Phase C artifact).
_REAL_SKILL_TEMPLATE = os.path.join(
    os.path.dirname(__file__), "..", "skills", "assurance-strategist", "SKILL.md"
)
_REAL_CARD = os.path.join(
    os.path.dirname(__file__), "..", "refs", "technique-unit-testing.md"
)


@pytest.mark.skipif(
    not os.path.isfile(_REAL_CARD),
    reason="Phase C not yet merged — technique-unit-testing.md does not exist",
)
class TestRealModuleCompiles:
    """AC-1 backstop: the real assurance module compiles without error."""

    def test_real_module_compiles(self, tmp_path):
        """Compile the real assurance module into a temp output dir."""
        # Use the real src/ directory but redirect output to tmp_path
        real_src_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        out_dir = str(tmp_path / "repo" / "skills")
        os.makedirs(out_dir, exist_ok=True)

        modules = [
            compile.module(
                "assurance",
                compile.skill(
                    "assurance-strategist",
                    refs=[compile.ref("technique-unit-testing.md")],
                ),
            )
        ]

        # Should not raise
        compile.compile(modules, src_dir=real_src_dir, out_dir=out_dir)

        # The compiled SKILL.md should exist and contain a generated table row
        compiled = os.path.join(out_dir, "assurance-strategist", "SKILL.md")
        assert os.path.isfile(compiled)

        content = open(compiled).read()
        # The directive should have been replaced (no longer present)
        assert "{{ index:techniques }}" not in content
        # The index table header should be present
        assert "| Technique |" in content
        # The card should be linked, not inlined — check the card's section
        # titles are NOT in the compiled SKILL.md
        assert "## What it is & what it catches/misses" not in content
        # The references file should be copied
        ref_copy = os.path.join(
            out_dir, "assurance-strategist", "references", "technique-unit-testing.md"
        )
        assert os.path.isfile(ref_copy)
