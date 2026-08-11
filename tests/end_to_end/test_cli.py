from importlib import import_module
from pathlib import Path

from typer.testing import CliRunner

from graphabi.cli import app

runner = CliRunner()


def test_demo_cli_exit_codes_and_json(demo_result: object) -> None:
    del demo_result
    allowed = runner.invoke(app, ["--plain", "demo", "--allow-breaking"])
    assert allowed.exit_code == 0, allowed.output
    assert "Structural compatibility: PASS" in allowed.output
    assert "Semantic compatibility: FAIL" in allowed.output
    assert "researcher -> verifier" in allowed.output
    assert "candidate-003" in allowed.output
    assert "Observed contract coverage: 100.0%" in allowed.output
    assert "Coverage is not correctness." in allowed.output

    breaking = runner.invoke(app, ["demo"])
    assert breaking.exit_code == 2
    json_result = runner.invoke(app, ["--json-output", "demo", "--allow-breaking"])
    assert json_result.exit_code == 0
    assert '"first_breaking_edge": "researcher_to_verifier"' in json_result.output
    assert '"observed_contract_coverage_percent": 100.0' in json_result.output


def test_doctor_plain_and_json(demo_result: object) -> None:
    del demo_result
    plain = runner.invoke(app, ["--plain", "doctor"])
    assert plain.exit_code == 0, plain.output
    assert "PASS Python" in plain.output
    assert "PASS SQLite" in plain.output
    result = runner.invoke(app, ["--json-output", "doctor"])
    assert result.exit_code == 0
    assert '"check": "Architecture"' in result.output


def test_init_and_contract_check(tmp_path: Path) -> None:
    created = runner.invoke(app, ["init", str(tmp_path)])
    assert created.exit_code == 0
    contract = tmp_path / ".graphabi/contracts.yml"
    assert contract.is_file()
    duplicate = runner.invoke(app, ["init", str(tmp_path)])
    assert duplicate.exit_code == 1
    assert "--force" in duplicate.output
    assert runner.invoke(app, ["init", str(tmp_path), "--force"]).exit_code == 0
    checked = runner.invoke(app, ["--json-output", "check", str(contract)])
    assert checked.exit_code == 0
    assert '"status": "PASS"' in checked.output
    invalid = tmp_path / "invalid.yml"
    invalid.write_text("not: a-contract\n", encoding="utf-8")
    failed = runner.invoke(app, ["check", str(invalid)])
    assert failed.exit_code == 1
    assert "suggested correction" in failed.output


def test_record_infer_and_compare_commands(
    demo_result: object, repository_root: Path, tmp_path: Path
) -> None:
    del demo_result
    trace = repository_root / ".graphabi/demo/baseline.json"
    database = tmp_path / "traces.db"
    recorded = runner.invoke(app, ["record", str(trace), "--database", str(database)])
    assert recorded.exit_code == 0, recorded.output
    assert "3 edge observation" in recorded.output
    suggestions = tmp_path / "suggestions.yml"
    inferred = runner.invoke(
        app,
        ["infer", "--database", str(database), "--output", str(suggestions)],
    )
    assert inferred.exit_code == 0
    assert "none are enforced" in inferred.output
    assert "SUGGESTED: NOT ENFORCED" in suggestions.read_text(encoding="utf-8")

    demo_database = repository_root / ".graphabi/demo/traces.db"
    contract = repository_root / "examples/research_graph/contracts.yml"
    args = [
        "compare",
        "--baseline-run",
        "baseline-001",
        "--candidate-run",
        "candidate-003",
        "--contract",
        str(contract),
        "--database",
        str(demo_database),
    ]
    assert runner.invoke(app, args).exit_code == 2
    compared = runner.invoke(app, [*args, "--allow-breaking"])
    assert compared.exit_code == 0, compared.output
    assert "Semantic: FAIL" in compared.output
    assert "Graph edges: 3" in compared.output
    assert "Observed contract coverage: 100.0%" in compared.output


def test_report_paths_open_and_server(demo_result: object, monkeypatch: object) -> None:
    del demo_result
    module = import_module("graphabi.cli.app")
    located = runner.invoke(app, ["report"])
    assert located.exit_code == 0
    assert "index.html" in located.output
    monkeypatch.setattr(module.webbrowser, "open", lambda _: True)
    opened = runner.invoke(app, ["report", "--open"])
    assert opened.exit_code == 0
    called: dict[str, object] = {}

    def fake_run(application: object, **kwargs: object) -> None:
        called["application"] = application
        called.update(kwargs)

    monkeypatch.setattr(module.uvicorn, "run", fake_run)
    served = runner.invoke(app, ["report", "--serve", "--port", "9876"])
    assert served.exit_code == 0
    assert called["port"] == 9876


def test_actionable_cli_failures(tmp_path: Path, monkeypatch: object) -> None:
    missing = runner.invoke(app, ["record", str(tmp_path / "missing.json")])
    assert missing.exit_code == 1
    assert "could not record" in missing.output
    no_runs = runner.invoke(app, ["infer", "--database", str(tmp_path / "empty.db")])
    assert no_runs.exit_code == 1
    assert "no baseline runs" in no_runs.output

    module = import_module("graphabi.cli.app")
    monkeypatch.setattr(module, "_latest_report", lambda: tmp_path / "missing.html")
    doctor = runner.invoke(app, ["--plain", "doctor"])
    assert doctor.exit_code == 0
    assert "INFO Latest report" in doctor.output
    assert "FAIL Latest report" not in doctor.output
    no_report = runner.invoke(app, ["report"])
    assert no_report.exit_code == 1
    assert "does not exist" in no_report.output

    def broken_demo() -> None:
        raise RuntimeError("deliberate test failure")

    monkeypatch.setattr(module, "run_demo", broken_demo)
    failed_demo = runner.invoke(app, ["demo"])
    assert failed_demo.exit_code == 1
    assert "deliberate test failure" in failed_demo.output
