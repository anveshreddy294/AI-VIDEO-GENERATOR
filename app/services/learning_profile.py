"""Minimal account preferences, separate from source-specific mastery evidence."""
from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from ..core.supabase import AuthenticatedUser, SupabaseRuntime, SupabaseResponseError

DOMAINS = ('Sports', 'Dance', 'Music', 'Gaming', 'Technology', 'Science',
           'Nature and Animals', 'Art and Design', 'Movies and Animation',
           'Business and Entrepreneurship', 'Fitness', 'Other')


class LearningPreferences(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    education_level: Literal['Primary', 'Secondary', 'Undergraduate', 'Other']
    interested_domains: list[str] = Field(min_length=1, max_length=len(DOMAINS))
    custom_interest: str = Field(default='', max_length=80)
    preferred_language: Literal['English'] = 'English'
    learning_goal: Literal['', 'Exam preparation', 'Concept understanding', 'Revision', 'Skill development'] = ''
    personalization_enabled: bool = True

    @field_validator('interested_domains')
    @classmethod
    def domains(cls, values: list[str]) -> list[str]:
        if any(v not in DOMAINS for v in values) or len(values) != len(set(values)):
            raise ValueError('Select valid, distinct interested domains')
        return values

    @field_validator('custom_interest')
    @classmethod
    def custom(cls, value: str) -> str:
        value = ' '.join(value.split())
        if value and not re.fullmatch(r"[\w .,'&()+/-]+", value, re.UNICODE):
            raise ValueError('Use a short interest name without markup')
        return value

    @model_validator(mode='after')
    def custom_required(self) -> LearningPreferences:
        if ('Other' in self.interested_domains) != bool(self.custom_interest):
            raise ValueError('Provide a custom interest only when Other is selected')
        return self


class ProfileUpdate(LearningPreferences):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator('display_name')
    @classmethod
    def name(cls, value: str | None) -> str | None:
        if value is not None:
            value = ' '.join(value.split())
            if not value or any(c in value for c in '<>'):
                raise ValueError('Enter a display name without markup')
        return value


class LearningProfile(BaseModel):
    user_id: UUID
    display_name: str | None
    preferences: LearningPreferences | None = None
    complete: bool = False


def read_profile(user: AuthenticatedUser, token: str, runtime: SupabaseRuntime) -> LearningProfile:
    # Explicit owner filter as well as caller-token RLS. No client IDs or admin keys.
    rows = runtime.user_request('GET', '/rest/v1/profiles', token=token,
        params={'id': 'eq.' + str(user.user_id), 'select': 'id,full_name,learning_preferences'})
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict) or rows[0].get('id') != str(user.user_id):
        raise SupabaseResponseError('Learning profile unavailable')
    data = rows[0]
    preferences = None
    if data.get('learning_preferences'):
        try:
            preferences = LearningPreferences.model_validate(data['learning_preferences'])
        except ValueError:
            pass  # Old/partial preferences must go through setup; never mark them complete.
    name = data.get('full_name')
    return LearningProfile(user_id=user.user_id, display_name=name if isinstance(name, str) else None,
        preferences=preferences, complete=preferences is not None)


def update_profile(user: AuthenticatedUser, token: str, runtime: SupabaseRuntime, body: ProfileUpdate) -> LearningProfile:
    preferences = LearningPreferences.model_validate(body.model_dump(exclude={'display_name'}))
    payload = {'learning_preferences': preferences.model_dump(mode='json')}
    if body.display_name is not None:
        payload['full_name'] = body.display_name
    runtime.user_request('PATCH', '/rest/v1/profiles', token=token,
        params={'id': 'eq.' + str(user.user_id)}, body=payload)
    return read_profile(user, token, runtime)


def repository_preferences(repository) -> LearningPreferences | None:
    """Request-local lazy load; no cross-user cache or local fallback."""
    if not hasattr(repository, '_learning_preferences'):
        from .repositories.learning_storage import LearningStorage
        runtime = getattr(repository, 'runtime', None)
        auth_runtime = runtime.auth if isinstance(runtime, LearningStorage) else runtime
        if not isinstance(getattr(repository, '_token', None), str) or not isinstance(auth_runtime, SupabaseRuntime):
            return None  # Local/legacy contexts have no authenticated account preferences.
        from ..core.supabase import SupabaseError
        try:
            profile = read_profile(repository.user, repository._token, repository.runtime)
            repository._learning_preferences = profile.preferences
        except SupabaseError:
            # Presentation preferences cannot break the established learning pipeline.
            repository._learning_preferences = None
    return repository._learning_preferences
