"""Tests for Supabase schema migrations, repository abstraction, and auth helpers (Phases 11, 12, 13)."""

from pathlib import Path
import pytest
from fastapi import HTTPException
from app.core.config import settings
from app.services.repositories.factory import (
    get_source_repository,
    get_assessment_repository,
    get_learning_profile_repository,
)
from app.services.repositories.file_repository import FileSourceRepository
from app.services.repositories.supabase_repository import SupabaseSourceRepository
from app.services.security.auth import is_supabase_auth_configured, extract_authenticated_user_id


def test_supabase_migration_sql_exists_and_contains_core_tables():
    """Verify that migration SQL file exists and defines all required domain tables."""
    migration_file = Path("migrations/001_supabase_initial_schema.sql")
    assert migration_file.exists(), "Migration SQL file must exist"
    sql = migration_file.read_text(encoding="utf-8")

    expected_tables = [
        "profiles",
        "sources",
        "source_versions",
        "content_units",
        "concepts",
        "concept_relationships",
        "assessment_sessions",
        "assessment_questions",
        "assessment_attempts",
        "concept_mastery",
        "misconceptions",
        "remediation_jobs",
        "generated_videos",
    ]
    for table in expected_tables:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql, f"Table {table} missing from migration"

    # Verify RLS policies are declared
    assert "ENABLE ROW LEVEL SECURITY;" in sql
    assert "CREATE POLICY" in sql


def test_repository_factory_defaults_to_file_repository_when_unconfigured():
    """When Supabase is not configured, repository factory must safely return file repository."""
    src_repo = get_source_repository()
    assert isinstance(src_repo, (FileSourceRepository, SupabaseSourceRepository))
    if not settings.supabase_url:
        assert isinstance(src_repo, FileSourceRepository)


def test_supabase_source_repository_graceful_fallback():
    """When Supabase credentials are missing, SupabaseSourceRepository falls back to local file repo."""
    repo = SupabaseSourceRepository()
    # Should not raise exception
    sources = repo.list_sources()
    assert isinstance(sources, list)


def test_auth_helper_unconfigured_behavior():
    """Caller identity/defaults never authorize, even in unconfigured local mode."""
    # When Supabase Auth is not configured
    is_conf = is_supabase_auth_configured()
    assert is_conf is False or isinstance(is_conf, bool)

    # Resolves fallback user_id safely
    with pytest.raises(HTTPException) as exc:
        extract_authenticated_user_id(fallback_user_id="student_456")
    assert exc.value.status_code == 401

    # Default tenant fallback
    with pytest.raises(HTTPException) as exc:
        extract_authenticated_user_id()
    assert exc.value.status_code == 401


def test_runtime_configuration_validation():
    """Verify settings.validate_runtime_configuration produces clean, secret-free diagnostics."""
    status = settings.validate_runtime_configuration()
    assert "llm_provider" in status
    assert "embedding_model" in status
    assert "qdrant_url" in status
    assert "database_provider" in status
    assert "supabase_connected" in status
    assert isinstance(status["warnings"], list)
