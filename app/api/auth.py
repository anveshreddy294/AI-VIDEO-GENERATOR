"""Backend Auth APIs; legacy HTML login/dashboard is not an authorization layer."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, TypedDict
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, JsonValue, SecretStr, ValidationError, field_validator

from ..core.supabase import AuthenticatedUser, Profile, SupabaseError, SupabaseRuntime, SupabaseResponseError, AuthServerUser
from ..services.security.auth import auth_http_error, get_current_user, get_runtime, require_access_token

class ValidationIssue(TypedDict):
    loc: list[str | int]
    msg: str
    type: str


class AuthRoute(APIRoute):
    """Remove credential inputs from validation errors before returning them."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[object, object, Response]]:
        handler = super().get_route_handler()

        async def safe_handler(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError as error:
                issues: list[ValidationIssue] = [
                    {'loc': list(issue['loc']), 'msg': issue['msg'], 'type': issue['type']}
                    for issue in error.errors()
                ]
                return JSONResponse(status_code=422, content={'detail': issues}, headers={'Cache-Control': 'no-store'})
        return safe_handler


router = APIRouter(prefix='/api/auth', tags=['authentication'], route_class=AuthRoute)
Runtime = Annotated[SupabaseRuntime, Depends(get_runtime)]
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
AccessToken = Annotated[str, Depends(require_access_token)]


class Credentials(BaseModel):
    """Bound request sizes without rejecting existing Supabase password lengths."""
    model_config = ConfigDict(extra='forbid')
    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=1, max_length=1024)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip()
        if email.count('@') != 1 or any(char.isspace() for char in email) or not all(email.split('@')):
            raise ValueError('A valid email address is required')
        return email


class SignupCredentials(Credentials):
    """New accounts use an explicit eight-character local minimum policy."""
    password: SecretStr = Field(min_length=8, max_length=1024)
    full_name: str | None = Field(default=None, max_length=200)


class RefreshCredentials(BaseModel):
    model_config = ConfigDict(extra='forbid')
    refresh_token: SecretStr


class AuthSession(BaseModel):
    access_token: str = Field(repr=False)
    refresh_token: str = Field(repr=False)
    token_type: str
    expires_in: int


class AuthResult(BaseModel):
    confirmation_required: bool
    session: AuthSession | None = None
    user_id: UUID | None = None
    profile: Profile | None = None


class CurrentIdentity(BaseModel):
    user_id: UUID
    email: str | None
    profile: Profile


def session_result(runtime: SupabaseRuntime, payload: JsonValue, *, allow_confirmation: bool = False) -> AuthResult:
    if allow_confirmation and isinstance(payload, dict) and not payload.get('access_token'):
        try:
            AuthServerUser.model_validate(payload)
        except ValidationError:
            raise SupabaseResponseError('Invalid Supabase signup response') from None
        return AuthResult(confirmation_required=True)
    try:
        session = AuthSession.model_validate(payload)
    except ValidationError:
        raise SupabaseResponseError('Invalid Supabase session response') from None
    user = runtime.verify_user(session.access_token)
    profile = runtime.ensure_profile(user, session.access_token)
    return AuthResult(confirmation_required=False, session=session, user_id=user.user_id, profile=profile)


@router.post('/signup', response_model=AuthResult)
def signup(body: SignupCredentials, runtime: Runtime, response: Response) -> AuthResult:
    response.headers['Cache-Control'] = 'no-store'
    try:
        return session_result(runtime, runtime.signup(body.email, body.password.get_secret_value(), body.full_name),
                              allow_confirmation=True)
    except SupabaseError as error:
        raise auth_http_error(error) from None


@router.post('/login', response_model=AuthResult)
def login(body: Credentials, runtime: Runtime, response: Response) -> AuthResult:
    response.headers['Cache-Control'] = 'no-store'
    try:
        return session_result(runtime, runtime.login(body.email, body.password.get_secret_value()))
    except SupabaseError as error:
        raise auth_http_error(error) from None


@router.post('/refresh', response_model=AuthResult)
def refresh(body: RefreshCredentials, runtime: Runtime, response: Response) -> AuthResult:
    response.headers['Cache-Control'] = 'no-store'
    try:
        return session_result(runtime, runtime.refresh(body.refresh_token.get_secret_value()))
    except SupabaseError as error:
        raise auth_http_error(error) from None


@router.get('/me', response_model=CurrentIdentity)
def me(user: CurrentUser, token: AccessToken, runtime: Runtime, response: Response) -> CurrentIdentity:
    response.headers['Cache-Control'] = 'no-store'
    try:
        return CurrentIdentity(user_id=user.user_id, email=user.email, profile=runtime.ensure_profile(user, token))
    except SupabaseError as error:
        raise auth_http_error(error) from None


@router.post('/logout', status_code=204)
def logout(user: CurrentUser, token: AccessToken, runtime: Runtime) -> Response:
    try:
        runtime.logout(token)
    except SupabaseError as error:
        raise auth_http_error(error) from None
    return Response(status_code=204, headers={'Cache-Control': 'no-store'})
