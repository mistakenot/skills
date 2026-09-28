"""
Tests for the skill compiler's shared templates: skill(template=..., vars=...).

Several skills can render from one templates/<name>/SKILL.md, each filling
{{ var:X }} with its own values — plain strings or var_file() fragments that sit
beside the template and may themselves contain {{ var:X }}.
"""

import os
import sys
import textwrap

import pytest

_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.abspath(_SRC_DIR))

import compile  # noqa: E402 — must follow sys.path manipulation

_TEMPLATE = textwrap.dedent("""\
    ---
    name: greet-{{ var:who }}
    description: "Greets {{ var:who }}."
    ---

    # Greet {{ var:Who }}

    {{ var:body }}
""")


def _layout(tmp_path, template: str = _TEMPLATE):
    repo = tmp_path / "repo"
    (repo / "pd-components").mkdir(parents=True)
    (repo / "pd-components" / "package.json").write_text('{"version": "0.0.0-test"}\n')
    tdir = repo / "src" / "testmod" / "templates" / "greet"
    tdir.mkdir(parents=True)
    (tdir / "SKILL.md").write_text(template)
    (tdir / "alice.md").write_text("Say hi to {{ var:Who }}.\n")
    (tdir / "bob.md").write_text("Wave at {{ var:Who }}.\n")
    (repo / "skills").mkdir()
    return str(repo / "src"), str(repo / "skills")


def _greet(who: str, **extra):
    vars = {"who": who, "Who": who.title(), "body": compile.var_file(f"{who}.md"), **extra}
    return compile.skill(f"greet-{who}", template="greet", vars=vars)


def test_one_template_renders_each_skill(tmp_path):
    src, out = _layout(tmp_path)
    compile.compile([compile.module("testmod", _greet("alice"), _greet("bob"))], src_dir=src, out_dir=out)

    alice = open(os.path.join(out, "greet-alice", "SKILL.md")).read()
    bob = open(os.path.join(out, "greet-bob", "SKILL.md")).read()
    assert "name: greet-alice" in alice and "# Greet Alice" in alice
    assert "Say hi to Alice." in alice  # fragment's own {{ var:Who }} expanded
    assert "Wave at Bob." in bob
    assert "{{" not in alice + bob


def test_undeclared_var_fails(tmp_path, capsys):
    src, out = _layout(tmp_path, _TEMPLATE + "\n{{ var:missing }}\n")
    with pytest.raises(SystemExit):
        compile.compile([compile.module("testmod", _greet("alice"))], src_dir=src, out_dir=out)
    assert "var:missing" in capsys.readouterr().err


def test_missing_var_file_fails(tmp_path, capsys):
    src, out = _layout(tmp_path)
    sk = _greet("alice", body=compile.var_file("nobody.md"))
    with pytest.raises(SystemExit):
        compile.compile([compile.module("testmod", sk)], src_dir=src, out_dir=out)
    assert "nobody.md" in capsys.readouterr().err


def test_rendered_name_must_match_skill(tmp_path, capsys):
    src, out = _layout(tmp_path)
    sk = compile.skill("greet-carol", template="greet",
                       vars={"who": "alice", "Who": "Alice", "body": "x"})
    with pytest.raises(SystemExit):
        compile.compile([compile.module("testmod", sk)], src_dir=src, out_dir=out)
    assert "does not match skill name" in capsys.readouterr().err


def test_unused_var_warns(tmp_path, capsys):
    src, out = _layout(tmp_path)
    compile.compile([compile.module("testmod", _greet("alice", spare="x"))], src_dir=src, out_dir=out)
    assert "var 'spare' declared but never used" in capsys.readouterr().err
