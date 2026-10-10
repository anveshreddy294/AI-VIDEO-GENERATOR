"""Verified account-only profile endpoints; client cannot choose an owner or role."""
from fastapi import APIRouter, Response
from .auth import CurrentUser, AccessToken, Runtime, AuthRoute
from ..core.supabase import SupabaseError
from ..services.security.auth import auth_http_error
from ..services.learning_profile import DOMAINS, LearningProfile, ProfileUpdate, read_profile, update_profile

router = APIRouter(prefix='/api/learning-profile', tags=['Learning profile'], route_class=AuthRoute)


@router.get('', response_model=LearningProfile)
def get_profile(user: CurrentUser, token: AccessToken, runtime: Runtime, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    try:
        return read_profile(user, token, runtime)
    except SupabaseError as error:
        raise auth_http_error(error) from None


@router.put('', response_model=LearningProfile)
def save_profile(body: ProfileUpdate, user: CurrentUser, token: AccessToken, runtime: Runtime, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    try:
        return update_profile(user, token, runtime, body)
    except SupabaseError as error:
        raise auth_http_error(error) from None


@router.get('/options')
def options():
    return {'interested_domains': DOMAINS, 'languages': ['English']}
