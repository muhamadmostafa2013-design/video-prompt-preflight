"""CLI error and remote privacy opt-in regression tests."""
from argparse import Namespace

import pytest

from vpp.cli import build_parser, cmd_jev_review, cmd_import_prompt, cmd_lint_prompt, main


def test_jev_refuses_remote_prompt_transfer_without_explicit_opt_in(capsys):
    args=build_parser().parse_args(["jev-review","not-a-file.txt","--engine","openai","--model","model"])
    assert args.allow_remote_judge is False
    assert cmd_jev_review(args)==2
    assert "opt-in" in capsys.readouterr().err.lower()


def test_lint_prompt_unknown_total_duration_requires_review(tmp_path):
    source=tmp_path/"prompt.txt"
    source.write_text("Show a beautiful sunset.",encoding="utf-8")
    args=Namespace(file=str(source),json=True)
    assert cmd_lint_prompt(args)==3


def test_import_prompt_unknown_total_duration_requires_review(tmp_path):
    source=tmp_path/"prompt.txt"
    out=tmp_path/"scene.yaml"
    source.write_text("Show a beautiful sunset.",encoding="utf-8")
    args=Namespace(file=str(source),output=str(out))
    assert cmd_import_prompt(args)==3
    assert out.exists()


def test_nonexistent_input_returns_clean_exit_code(monkeypatch,capsys):
    monkeypatch.setattr("sys.argv",["vpp","lint","/nonexistent_vpp_test.yaml"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code==2
    stderr=capsys.readouterr().err
    assert "VPP input error" in stderr
    assert "Traceback" not in stderr


def test_bad_yaml_returns_clean_exit_code(tmp_path,monkeypatch,capsys):
    p=tmp_path/"bad.yaml"
    p.write_text("timeline: [this: invalid : YAML",encoding="utf-8")
    monkeypatch.setattr("sys.argv",["vpp","lint",str(p)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code==2
    assert "VPP input error" in capsys.readouterr().err
