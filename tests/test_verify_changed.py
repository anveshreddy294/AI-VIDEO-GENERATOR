"""Selector contracts use simulated diffs and mocked execution, never live providers."""

from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
import pytest
from scripts import verify_changed as verifier


@pytest.mark.parametrize(
    ("files", "expected", "excluded"),
    [
        (["app/services/structurer.py"], {"STRUCTURING"}, {"WORKER", "FRONTEND"}),
        (
            ["cloudflare/visualai-inference-worker/src/visual.js"],
            {"WORKER"},
            {"STRUCTURING", "FRONTEND"},
        ),
        (["app/static/auth.js"], {"FRONTEND"}, {"WORKER", "STRUCTURING"}),
        (
            ["app/services/vision.py", "app/services/structurer.py"],
            {"VISION", "STRUCTURING"},
            {"WORKER", "FRONTEND"},
        ),
        (
            ["app/services/ingestion/knowledge_publication.py"],
            {"STRUCTURING", "SOURCE_INGESTION"},
            {"WORKER"},
        ),
        (["app/db/vector_store.py"], {"VECTOR"}, {"FRONTEND"}),
    ],
)
def test_subsystem_selection(
    files: list[str], expected: set[str], excluded: set[str]
) -> None:
    result = verifier.select_tests(files)
    assert expected <= set(result.groups)
    assert not excluded & set(result.groups)
    assert not any("e2e" in node for node in result.python_tests)
    assert len(result.python_tests) == len(set(result.python_tests))


@pytest.mark.parametrize(
    "file",
    [
        "migrations/new.sql",
        "app/services/security/source_scope.py",
        "app/services/schemas.py",
        "app/services/retrieval.py",
        "app/core/config.py",
        "app/services/repositories/source_repository.py",
    ],
)
def test_full_gate_is_reported(file: str) -> None:
    assert verifier.select_tests([file]).full_gate


@pytest.mark.parametrize(
    "file",
    [
        "app/services/structurer.py",
        "app/services/visual_router.py",
        "app/static/auth.js",
        "docs/readme.md",
    ],
)
def test_ordinary_changes_stay_fast(file: str) -> None:
    assert not verifier.select_tests([file]).full_gate


@pytest.mark.parametrize(
    "file",
    [
        "app/static/auth.js",
        "cloudflare/visualai-inference-worker/src/visual.js",
        "docs/readme.md",
    ],
)
def test_non_backend_has_no_python_or_core(file: str) -> None:
    result = verifier.select_tests([file])
    assert not result.core
    assert not result.python_tests


def test_unknown_backend_gets_contracts_and_core() -> None:
    result = verifier.select_tests(["app/services/new_service.py"])
    assert result.core and "BACKEND_CONTRACTS" in result.groups
    assert all(
        node in result.python_tests or node.split("::")[0] in result.python_tests
        for node in verifier.CORE
    )


def test_windows_paths_and_duplicates() -> None:
    result = verifier.select_tests(
        [r"app\services\structurer.py", "./app/services/structurer.py"]
    )
    assert result.changed == ("app/services/structurer.py",)


def test_git_staged_unstaged_and_untracked_union(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        commands.append(command)
        output = (
            b"app/services/structurer.py\0"
            if "diff" in command
            else b"tests/test_verify_changed.py\0"
        )
        return subprocess.CompletedProcess(command, 0, output, b"")

    monkeypatch.setattr(verifier.subprocess, "run", run)
    assert verifier.changed_files() == [
        "app/services/structurer.py",
        "tests/test_verify_changed.py",
    ]
    assert ["git", "diff", "--cached", "--name-only", "-z"] in commands
    assert ["git", "diff", "--name-only", "-z"] in commands


def test_gate_never_executes_full_suite(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(verifier, "changed_files", lambda: ["migrations/new.sql"])
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(verifier.subprocess, "run", run)
    assert verifier.main([]) == 0
    assert commands == [["git", "diff", "--check"]]
    assert "FULL_PHASE_GATE_REQUIRED: YES" in capsys.readouterr().out


def test_python_network_guard(tmp_path: Path) -> None:
    (tmp_path / "sitecustomize.py").write_text(verifier.PYTHON_GUARD, encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(tmp_path))
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import socket; socket.create_connection(('example.com',443))",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "FAST verification forbids network access" in result.stderr


def test_failures_propagate_and_credentials_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        verifier, "changed_files", lambda: ["app/services/structurer.py"]
    )
    monkeypatch.setenv("CLOUDFLARE_WORKER_SECRET", "private")

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        env = kwargs["env"]
        assert isinstance(env, dict)
        assert "CLOUDFLARE_WORKER_SECRET" not in env
        assert env["PYTHON_DOTENV_DISABLED"] == "1"
        if "pytest" in command:
            assert "tests/test_content_understanding.py" in command
            assert command[-1] != "tests"
            return subprocess.CompletedProcess(command, 1, "mocked failure", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(verifier.subprocess, "run", run)
    assert verifier.main([]) == 1


def test_live_and_database_tests_never_selected_directly() -> None:
    result = verifier.select_tests(
        ["tests/test_real_e2e_acceptance.py", "tests/test_knowledge_database.py"]
    )
    assert "tests/test_real_e2e_acceptance.py" not in result.python_tests
    assert "tests/test_knowledge_database.py" not in result.python_tests
    assert "BACKEND_CONTRACTS" in result.groups


def test_worker_missing_local_compiler_fails_without_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        verifier,
        "changed_files",
        lambda: ["cloudflare/visualai-inference-worker/src/visual.js"],
    )

    def missing() -> Path:
        raise RuntimeError("Local compiler missing")

    monkeypatch.setattr(verifier, "worker_tsc", missing)
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(verifier.subprocess, "run", run)
    assert verifier.main([]) == 1
    assert all("npx" not in command and "pytest" not in command for command in commands)


def test_node_network_guard(tmp_path: Path) -> None:
    guard = tmp_path / "offline.cjs"
    guard.write_text(verifier.NODE_GUARD, encoding="utf-8")
    result = subprocess.run(
        [
            "node",
            "--require",
            str(guard),
            "-e",
            "require('node:https').get('https://example.com')",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "FAST verification forbids network access" in result.stderr


def test_node_options_guard_works_with_space_in_path(tmp_path: Path) -> None:
    directory = tmp_path / "guard folder"
    directory.mkdir()
    guard = directory / "offline.cjs"
    guard.write_text(verifier.NODE_GUARD, encoding="utf-8")
    env = dict(os.environ, NODE_OPTIONS='--require "' + guard.as_posix() + '"')
    result = subprocess.run(
        ["node", "-e", "require('node:net').connect(443, 'example.com')"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "FAST verification forbids network access" in result.stderr


def test_offline_guard_allows_asyncio_private_ipc(tmp_path: Path) -> None:
    (tmp_path / "sitecustomize.py").write_text(verifier.PYTHON_GUARD, encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(tmp_path))
    result = subprocess.run(
        [sys.executable, "-c", "import asyncio; asyncio.run(asyncio.sleep(0))"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
