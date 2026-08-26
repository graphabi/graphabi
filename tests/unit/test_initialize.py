from pathlib import Path

import pytest
import yaml

from graphabi.cli.initialize import InitError, detect_project_context, initialize_project


def test_detect_project_context_uses_supported_manifest_dependencies(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """[project]
name = "sample-agent"
dependencies = ["LangGraph>=1.0,<1.3"]

[project.optional-dependencies]
agents = ["openai_agents>=0.20,<0.21"]

[dependency-groups]
dev = ["pytest>=9"]
""",
        encoding="utf-8",
    )

    detection = detect_project_context(tmp_path)

    assert detection.project_name == "sample-agent"
    assert [hint.adapter for hint in detection.adapters] == ["langgraph", "openai-agents"]
    assert detection.evidence == (
        "pyproject.toml project.dependencies declares 'langgraph'",
        "pyproject.toml project.optional-dependencies.agents declares 'openai-agents'",
    )
    assert detection.warnings == ()


def test_detect_project_context_supports_requirements_and_poetry(tmp_path: Path) -> None:
    (tmp_path / "requirements-dev.txt").write_text(
        "# test requirements\nopenai_agents==0.20.0\n-r requirements.txt\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        """[tool.poetry]
name = "poetry-agent"

[tool.poetry.dependencies]
python = ">=3.12,<3.14"
langgraph = "^1.2"

[tool.poetry.group.dev.dependencies]
pytest = "^9"
""",
        encoding="utf-8",
    )

    detection = detect_project_context(tmp_path)

    assert detection.project_name == "poetry-agent"
    assert [hint.adapter for hint in detection.adapters] == ["langgraph", "openai-agents"]
    assert "requirements-dev.txt declares 'openai-agents'" in detection.evidence
    assert "pyproject.toml tool.poetry.dependencies declares 'langgraph'" in detection.evidence


def test_detection_warning_does_not_hide_valid_requirements_context(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("langgraph>=1.0\n", encoding="utf-8")

    detection = detect_project_context(tmp_path)

    assert [hint.adapter for hint in detection.adapters] == ["langgraph"]
    assert detection.warnings
    assert detection.warnings[0].startswith("pyproject.toml could not be read:")


def test_detection_warns_for_non_utf8_manifests(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_bytes(b"\xff\xfe")
    (tmp_path / "requirements.txt").write_bytes(b"\xff\xfe")

    detection = detect_project_context(tmp_path)

    assert detection.adapters == ()
    assert len(detection.warnings) == 2
    assert detection.warnings[0].startswith("pyproject.toml could not be read:")
    assert detection.warnings[1].startswith("requirements.txt could not be read:")


def test_initialize_project_creates_explicit_unenforced_starters(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "starter"\ndependencies = ["langgraph>=1"]\n',
        encoding="utf-8",
    )

    result = initialize_project(tmp_path)

    assert result.replaced == ()
    assert set(result.created) == {
        ".graphabi/.gitignore",
        ".graphabi/README.md",
        ".graphabi/config.yml",
        ".graphabi/contracts.yml",
    }
    config = yaml.safe_load((tmp_path / ".graphabi/config.yml").read_text(encoding="utf-8"))
    assert config["version"] == "0.1"
    assert config["project"]["detected_adapters"] == ["langgraph"]
    assert config["graph"]["discovery"] == "NOT_ATTEMPTED"
    assert config["contract_policy"] == {
        "starter_status": "EXAMPLE_NOT_ENFORCED",
        "inference_status": "SUGGESTED_NOT_ENFORCED",
        "auto_enforce_inferred_contracts": False,
    }
    contract = (tmp_path / ".graphabi/contracts.yml").read_text(encoding="utf-8")
    assert "not inferred" in contract
    assert "Field guide" in contract
    readme = (tmp_path / ".graphabi/README.md").read_text(encoding="utf-8")
    assert "LangGraphRecorder" in readme
    assert "graphabi record" in readme
    assert "graphabi doctor" in readme
    assert "UNKNOWN" in readme


def test_initialize_project_requires_force_and_preserves_unmanaged_files(tmp_path: Path) -> None:
    initialize_project(tmp_path)
    unmanaged = tmp_path / ".graphabi/keep.txt"
    unmanaged.write_text("keep", encoding="utf-8")
    contract = tmp_path / ".graphabi/contracts.yml"
    contract.write_text("custom", encoding="utf-8")

    with pytest.raises(InitError, match=r"starter file\(s\) already exist:.*--force"):
        initialize_project(tmp_path)

    result = initialize_project(tmp_path, force=True)

    assert set(result.replaced) == {
        ".graphabi/.gitignore",
        ".graphabi/README.md",
        ".graphabi/config.yml",
        ".graphabi/contracts.yml",
    }
    assert unmanaged.read_text(encoding="utf-8") == "keep"
    assert "replace_with_graph_id" in contract.read_text(encoding="utf-8")


def test_initialize_project_rejects_missing_or_non_directory_targets(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(InitError, match="does not exist; create it first"):
        initialize_project(missing)

    file_path = tmp_path / "project.txt"
    file_path.write_text("not a directory", encoding="utf-8")
    with pytest.raises(InitError, match="is not a directory"):
        initialize_project(file_path)


def test_initialize_project_rejects_symlinked_generated_paths(tmp_path: Path) -> None:
    outside = tmp_path / "outside.yml"
    outside.write_text("preserve", encoding="utf-8")
    state = tmp_path / ".graphabi"
    state.mkdir()
    (state / "contracts.yml").symlink_to(outside)

    with pytest.raises(InitError, match=r"contracts\.yml is a symbolic link"):
        initialize_project(tmp_path, force=True)

    assert outside.read_text(encoding="utf-8") == "preserve"
