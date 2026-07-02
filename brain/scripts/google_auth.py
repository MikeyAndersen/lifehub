"""Run this ONCE on your own machine to mint the Google OAuth token.

1. Google Cloud Console -> create project -> enable "Google Calendar API".
2. OAuth consent screen: External, add yourself as test user.
3. Credentials -> OAuth client id -> Desktop app -> download client_secret.json here.
4. pip install google-auth-oauthlib google-api-python-client
5. python google_auth.py  -> browser opens -> approve -> token.json is written.
6. Copy token.json to the server:  lifehub/secrets/token.json
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0)
with open("token.json", "w") as f:
    f.write(creds.to_json())
print("token.json written — copy it to lifehub/secrets/token.json on the server.")
