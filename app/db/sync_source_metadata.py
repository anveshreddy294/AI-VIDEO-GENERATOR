"""Copy one authenticated user's metadata; never use a service-role credential."""
from getpass import getpass

from ..core import postgres
from ..core.supabase import get_supabase_runtime, SupabaseError
from ..services.repositories.source_repository import SupabaseSourceRepository


def main():
    runtime = get_supabase_runtime()
    try:
        postgres.readiness()
        token = getpass('Supabase user access token (hidden): ')
        user = runtime.verify_user(token)
        print(SupabaseSourceRepository(user, token, runtime).sync_metadata())
    except postgres.VideoDatabaseError as error:
        raise SystemExit(error.code) from None
    except SupabaseError:
        raise SystemExit('SOURCE_METADATA_SYNC_AUTH_OR_SOURCE_FAILED') from None
    finally:
        postgres.close_pool()
        runtime.close()


if __name__ == '__main__':
    main()
