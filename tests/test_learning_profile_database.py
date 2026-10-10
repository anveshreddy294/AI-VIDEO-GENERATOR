"""Real disposable Postgres coverage of preferences, account RLS and privilege isolation."""
from pathlib import Path
import json
import pytest
from tests.test_knowledge_database import Database, database, OWNER, OTHER, literal

MIGRATION=Path(__file__).resolve().parents[1]/'migrations/20261010190948_learning_preferences.sql'


@pytest.fixture(scope='module')
def profiles(database:Database):
    database.sql(MIGRATION.read_text(),role='postgres',owner=None)
    return database


def test_preferences_persist_and_owner_isolation(profiles):
    preferences={'education_level':'Secondary','interested_domains':['Sports'],'custom_interest':'',
        'preferred_language':'English','learning_goal':'','personalization_enabled':True}
    encoded=literal(json.dumps(preferences))+'::jsonb'
    profiles.sql(f'UPDATE public.profiles SET learning_preferences={encoded} WHERE id={literal(OWNER)}')
    assert json.loads(profiles.sql(f'SELECT learning_preferences FROM public.profiles WHERE id={literal(OWNER)}'))==preferences
    assert profiles.sql(f'SELECT count(*) FROM public.profiles WHERE id={literal(OWNER)}',owner=OTHER)=='0'
    profiles.sql(f'UPDATE public.profiles SET learning_preferences={encoded} WHERE id={literal(OWNER)}',owner=OTHER)
    profiles.sql(f"UPDATE public.profiles SET role='admin' WHERE id={literal(OWNER)}",succeeds=False)
    assert 'permission denied' in profiles.sql('SELECT learning_preferences FROM public.profiles',role='anon',owner=None,succeeds=False)


def test_empty_interests_cannot_be_complete(profiles):
    value={'education_level':'Primary','interested_domains':[],'custom_interest':'','preferred_language':'English','learning_goal':'','personalization_enabled':True}
    assert 'check constraint' in profiles.sql(f'UPDATE public.profiles SET learning_preferences={literal(json.dumps(value))}::jsonb WHERE id={literal(OWNER)}',succeeds=False)
