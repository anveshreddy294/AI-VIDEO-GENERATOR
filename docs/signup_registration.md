# Self-service registration

Signup uses public Supabase Auth, never the administrative user-creation API.
With email confirmation enabled, successful signup without a session displays:
"Account created. Check your email to verify your account before signing in."
Login verifies the JWT before automatically provisioning the caller's profile.
Supabase can obscure duplicate signup responses; a successful pending response
does not prove that a new account was created.

## Confirmation redirect configuration

In project hqszkkvuxwdedhegqbec, open Authentication > URL Configuration.
Set Site URL to the reachable VisualAI login URL and add the exact same URL to
Redirect URLs. Set SUPABASE_AUTH_REDIRECT_URL in the server environment to that
URL. For this machine's local development server it is
http://127.0.0.1:8000/login. Teammates need a reachable deployed HTTPS origin,
not localhost. Restart the application after changing its environment.
Use DATABASE_PROVIDER=supabase for verified identity and canonical persistence.

The dedicated acceptance account was confirmed remotely even though its email
redirect reached an unavailable localhost server. Its subsequent login and
automatic profile provisioning passed. No administrator confirmation was used.
Remote URL configuration was not changed automatically.

## Email delivery configuration

Recent Auth logs showed over_email_send_rate_limit. The application now retains
that error category and displays a safe message. Signup and the email provider
were enabled, and email confirmation was required at audit time.
If delivery restrictions recur, inspect Authentication > Emails > SMTP Settings
and configure a production SMTP provider with its sender, host, port, username,
and password. Review Authentication > Rate Limits against provider capacity.
SMTP configuration could not be inspected through the available MCP tools;
successful delivery in this run does not establish production delivery capacity.
Keep email confirmation and RLS enabled. Do not manually insert users or profiles.

References:
- https://supabase.com/docs/guides/auth/redirect-urls
- https://supabase.com/docs/guides/auth/auth-smtp

## Acceptance

One controlled new account passed signup, confirmation, login, profile creation,
verified identity and sources access. Cross-user access returned 404 and anonymous
sources access returned 401. The existing account still logged in and read its
own source. Mocked tests cover delivery failures, password errors, duplicate
responses, pending confirmation, immediate sessions, malformed responses,
profile-owner conflicts and unsafe redirects. Credentials remain in ignored
local configuration and are never included in this report.
