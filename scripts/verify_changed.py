"""Explicit offline change selection; full regression gates are reported, never run."""

from __future__ import annotations
import argparse
from dataclasses import dataclass
from fnmatch import fnmatchcase
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence

ROOT = Path(__file__).resolve().parents[1]
GROUPS: dict[str, tuple[str, ...]] = {
    "MASTERY": ("test_session_mastery", "test_step_5a_mastery", "test_session_mastery_database"),
    "ASSESSMENT": ("test_canonical_assessment", "test_canonical_assessment_database"),
    "NOTES": ("test_grounded_notes", "test_canonical_retrieval"),
    "TOOLING": ("test_verify_changed",),
    "PROVIDERS": ("test_reasoning_provider", "test_embedding_configuration"),
    "VISION": (
        "test_visual_model_router",
        "test_vision_structured_output",
        "test_vision_timeout_runtime",
        "test_multimodal_canonical",
        "test_extraction_quality_regression",
        "test_visual_structure_ground_truth",
    ),
    "STRUCTURING": (
        "test_content_understanding",
        "test_visual_knowledge_preparation",
        "test_evidence_anchors",
    ),
    "RETRIEVAL_RAG": (
        "test_session_grounded_qa",
        "test_canonical_retrieval",
        "test_secure_rag_qa",
        "test_rag_semantics_and_recovery",
    ),
    "SOURCE_INGESTION": (
        "test_source_supabase",
        "test_ingestion_runtime_repair",
        "test_supabase_repository",
    ),
    "AUTH_SECURITY": (
        "test_supabase_runtime",
        "test_signup_registration",
        "test_phase6a1_security",
        "test_hardening_security_grounding",
    ),
    "VECTOR": (
        "test_vector_reindex",
        "test_embedding_configuration",
        "test_canonical_retrieval",
        "test_sec002_qdrant_exposure",
    ),
    "BACKEND_CONTRACTS": (
        "test_phase6a1_security",
        "test_canonical_retrieval",
        "test_learning_session_service",
        "test_knowledge_repository",
    ),
}
RULES: dict[str, tuple[str, ...]] = {
    "MASTERY": ("app/services/mastery/*", "migrations/*session_mastery.sql"),
    "ASSESSMENT": ("app/services/assessment/*", "app/services/repositories/supabase_repository.py",
                   "app/services/repositories/factory.py", "migrations/*session_assessments.sql"),
    "NOTES": ("app/services/grounded_notes.py", "app/api/learning_sessions.py"),
    "TOOLING": ("scripts/verify_changed.py",),
    "PROVIDERS": ("app/core/reasoning.py", "app/core/config.py"),
    "BACKEND_CONTRACTS": ("tests/conftest.py",),
    "VISION": (
        "app/services/vision.py",
        "app/services/visual_*",
        "app/services/extractor.py",
        "scripts/benchmark_visual*",
        "scripts/visual_structure*",
        "tests/fixtures/multimodal/*",
    ),
    "STRUCTURING": (
        "app/services/content_understanding.py",
        "app/services/structurer.py",
        "app/services/evidence_anchors.py",
        "app/services/ingestion/knowledge_publication.py",
    ),
    "RETRIEVAL_RAG": (
        "app/services/retrieval.py",
        "app/services/qa/*",
        "app/api/qa.py",
        "app/services/learning_session.py",
    ),
    "SOURCE_INGESTION": (
        "app/services/ingestion/*",
        "app/services/repositories/source_repository.py",
        "app/api/pipeline.py",
        "app/api/source_jobs.py",
        "app/api/sources.py",
        "app/services/dispatcher.py",
    ),
    "AUTH_SECURITY": (
        "app/services/security/*",
        "app/core/supabase.py",
        "app/core/config.py",
        "app/api/auth.py",
        ".env.example",
    ),
    "VECTOR": ("app/db/*", "*qdrant*", "app/services/embedding*"),
    "WORKER": ("cloudflare/visualai-inference-worker/*",),
    "FRONTEND": (
        "app/static/*",
        "app/templates/*",
        "tests/test_frontend_auth.js",
        "tests/test_learning_frontend.js",
        "tests/test_notes_frontend.js",
    ),
}
GATE_PATTERNS = (
    "migrations/*",
    "supabase/migrations/*",
    "app/services/security/auth.py",
    "app/services/security/source_scope.py",
    "app/services/security/legacy_boundary.py",
    "app/core/supabase.py",
    "app/core/config.py",
    ".env.example",
    "app/services/schemas.py",
    "app/services/*models.py",
    "app/services/*contracts.py",
    "app/services/retrieval.py",
    "app/services/repositories/source_repository.py",
    "app/services/repositories/knowledge_repository.py",
    "app/services/knowledge_service.py",
    "app/services/snapshot_validation.py",
)
CORE = (
    "tests/test_source_supabase.py::test_payload_identity_cannot_override_auth_dependency",
    "tests/test_source_supabase.py::test_commit_before_qdrant_and_no_source_json",
    "tests/test_phase6a1_security.py::test_version_mapper_roundtrip_and_scope_immutability",
    "tests/test_multimodal_canonical.py::test_no_filename_or_plaintext_fallback",
    "tests/test_multimodal_canonical.py::test_visual_central_retrieval_and_grounded_citation",
    "tests/test_learning_session_service.py::test_foreign_and_anonymous_sessions_uniform_denial",
)


@dataclass(frozen=True)
class Selection:
    changed: tuple[str, ...]
    groups: tuple[str, ...]
    python_tests: tuple[str, ...]
    core: bool
    full_gate: bool


def select_tests(files: Sequence[str]) -> Selection:
    """Conservatively select contract coverage for unmapped backend changes."""
    changed = tuple(sorted({f.replace("\\", "/").removeprefix("./") for f in files}))
    groups: set[str] = set()
    tests: set[str] = set()
    for file in changed:
        matched = {
            g
            for g, patterns in RULES.items()
            if any(fnmatchcase(file, p) for p in patterns)
        }
        groups.update(matched)
        if file.startswith("app/") and file.endswith(".py") and not matched:
            groups.add("BACKEND_CONTRACTS")
        if file.startswith("tests/test_") and file.endswith(".py"):
            if "e2e" in file or "database" in file:
                groups.add("BACKEND_CONTRACTS")
            else:
                tests.add(file)
    for group in groups:
        tests.update("tests/" + name + ".py" for name in GROUPS.get(group, ()))
    core = any(f.startswith("app/") and f.endswith(".py") for f in changed)
    if core:
        tests.update(node for node in CORE if node.split("::")[0] not in tests)
    gate = any(fnmatchcase(f, pattern) for f in changed for pattern in GATE_PATTERNS)
    return Selection(changed, tuple(sorted(groups)), tuple(sorted(tests)), core, gate)


def changed_files() -> list[str]:
    """Include both requested diffs and untracked files so new code is not missed."""
    files: set[str] = set()
    for args in (
        ("diff", "--name-only", "-z"),
        ("diff", "--cached", "--name-only", "-z"),
        ("ls-files", "--others", "--exclude-standard", "-z"),
    ):
        result = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, check=True
        )
        files.update(os.fsdecode(name) for name in result.stdout.split(b"\0") if name)
    return sorted(files)


PYTHON_GUARD = """import socket, threading
_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex
_original_socketpair = socket.socketpair
_ipc = threading.local()
def blocked_connect(self, *args, **kwargs):
    if getattr(_ipc, 'creating_socketpair', False):
        return _original_connect(self, *args, **kwargs)
    raise RuntimeError('FAST verification forbids network access')
def blocked_connect_ex(self, *args, **kwargs):
    if getattr(_ipc, 'creating_socketpair', False):
        return _original_connect_ex(self, *args, **kwargs)
    raise RuntimeError('FAST verification forbids network access')
def private_socketpair(*args, **kwargs):
    _ipc.creating_socketpair = True
    try:
        return _original_socketpair(*args, **kwargs)
    finally:
        _ipc.creating_socketpair = False
def blocked(*args, **kwargs):
    raise RuntimeError('FAST verification forbids network access')
socket.socketpair = private_socketpair
socket.socket.connect = blocked_connect
socket.socket.connect_ex = blocked_connect_ex
socket.create_connection = blocked
socket.socket.sendto = blocked
"""

NODE_GUARD = """const blocked=()=>{throw new Error('FAST verification forbids network access')};
require('node:net').Socket.prototype.connect=blocked;
require('node:http').request=blocked;require('node:http').get=blocked;
require('node:https').request=blocked;require('node:https').get=blocked;globalThis.fetch=blocked;
"""


def worker_tsc() -> Path:
    """Use installed TypeScript only; never invoke a package downloader."""
    override = os.environ.get("VISUALAI_TSC_PATH")
    candidates = [Path(override)] if override else []
    candidates.append(
        ROOT / "cloudflare/visualai-inference-worker/node_modules/typescript/bin/tsc"
    )
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.extend(
            sorted(
                (Path(local) / "npm-cache/_npx").glob(
                    "*/node_modules/typescript/bin/tsc"
                )
            )
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        "Local TypeScript compiler missing; install it separately or set VISUALAI_TSC_PATH. No downloads attempted."
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan", action="store_true", help="Show selection without running tests"
    )
    args = parser.parse_args(argv)
    started = time.perf_counter()
    selection = select_tests(changed_files())
    for label, value in (
        ("CHANGED_FILES", selection.changed),
        ("AFFECTED_SUBSYSTEMS", selection.groups),
        ("TEST_GROUPS", selection.groups),
    ):
        print(label + ": " + (", ".join(value) or "NONE"), flush=True)
    print("CORE_CONTRACT_SMOKE: " + ("YES" if selection.core else "NO"))
    print(
        "VERIFICATION_LEVEL_REQUIRED: "
        + ("FULL_PHASE_GATE" if selection.full_gate else "FAST")
    )
    print(
        "FULL_PHASE_GATE_REQUIRED: " + ("YES" if selection.full_gate else "NO"),
        flush=True,
    )
    if args.plan:
        print("TESTS_RUN: NONE (plan only)")
        print("SELECTED_PYTHON_TESTS: " + ", ".join(selection.python_tests))
        return 0
    passed: list[str] = []
    failed: list[str] = []
    with tempfile.TemporaryDirectory(prefix="visualai-fast-") as directory:
        guard = Path(directory)
        (guard / "sitecustomize.py").write_text(PYTHON_GUARD, encoding="utf-8")
        (guard / "offline.cjs").write_text(NODE_GUARD, encoding="utf-8")
        env = dict(os.environ)
        for key in tuple(env):
            if key.startswith(("SUPABASE_", "CLOUDFLARE_", "VISUALAI_AUTH_TEST_")):
                del env[key]
        env.update(
            PYTHON_DOTENV_DISABLED="1",
            LLM_PROVIDER="mock",
            EMBEDDING_PROVIDER="mock",
            DATABASE_PROVIDER="file",
            QDRANT_URL="",
        )
        env["PYTHONPATH"] = str(guard) + os.pathsep + str(ROOT)
        env["NODE_OPTIONS"] = '--require "' + (guard / "offline.cjs").as_posix() + '"'
        commands: list[tuple[str, list[str], Path]] = []
        if selection.python_tests:
            commands.append(
                (
                    "Python selected contracts",
                    [sys.executable, "-m", "pytest", "-q", *selection.python_tests],
                    ROOT,
                )
            )
        if "FRONTEND" in selection.groups:
            commands.append(
                (
                    "Frontend",
                    [
                        "node",
                        "--test",
                        "tests/test_frontend_auth.js",
                        "tests/test_learning_frontend.js",
                        "tests/test_notes_frontend.js",
                    ],
                    ROOT,
                )
            )
        if "WORKER" in selection.groups:
            worker = ROOT / "cloudflare/visualai-inference-worker"
            commands.append(
                (
                    "Worker",
                    [
                        "node",
                        "--test",
                        *[str(p) for p in sorted((worker / "tests").glob("*.test.js"))],
                    ],
                    worker,
                )
            )
            try:
                tsc = worker_tsc()
                commands.append(
                    (
                        "Worker strict JS",
                        [
                            "node",
                            str(tsc),
                            "--allowJs",
                            "--checkJs",
                            "--noEmit",
                            "--strict",
                            "--target",
                            "ES2022",
                            "--module",
                            "ESNext",
                            "--moduleResolution",
                            "bundler",
                            "--lib",
                            "ES2022,DOM",
                            *[str(p) for p in sorted((worker / "src").glob("*.js"))],
                        ],
                        worker,
                    )
                )
            except RuntimeError as error:
                print(str(error))
                failed.append("Worker strict JS setup")
        commands.append(("Diff whitespace", ["git", "diff", "--check"], ROOT))
        for label, command, cwd in commands:
            try:
                result = subprocess.run(
                    command,
                    cwd=cwd,
                    env=env,
                    capture_output=True,
                    text=True,
                    errors="replace",
                    check=False,
                )
                (passed if result.returncode == 0 else failed).append(label)
                print(
                    label + ": " + ("PASS" if result.returncode == 0 else "FAIL"),
                    flush=True,
                )
                # Keep success compact; retain failure evidence for diagnosis.
                if result.returncode:
                    print(result.stdout[-6000:] + result.stderr[-2000:])
            except OSError as error:
                failed.append(label)
                print(label + ": " + str(error))
    print("TESTS_RUN: " + ", ".join(passed + failed))
    print("PASSED: " + (", ".join(passed) or "NONE"))
    print("FAILED: " + (", ".join(failed) or "NONE"))
    print(f"DURATION: {time.perf_counter() - started:.2f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
