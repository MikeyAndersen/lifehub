"""Run this ONCE on your own machine to mint the Google OAuth token.

1. Google Cloud Console -> create project -> enable "Google Calendar API".
2. OAuth consent screen: External, add yourself as test user.
3. Credentials -> OAuth client id -> Desktop app -> download client_secret.json here.
4. pip install google-auth-oauthlib google-api-python-client
5. python google_auth.py  -> browser opens -> approve -> token.json is written.
6. Copy token.json to the server:  lifehub/secrets/token.json

Re-running after a scope change (e.g. adding gmail.readonly for Del 3):
back up the server token FIRST (`cp token.json token.json.bak`), run this
again, replace the server token and verify calendar still works. If refresh
then fails with invalid_grant, delete the token and run auth from scratch.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",  # Aula-indlæsning (Del 3)
]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0)
with open("token.json", "w") as f:
    f.write(creds.to_json())
print("token.json written — copy it to lifehub/secrets/token.json on the server.")
