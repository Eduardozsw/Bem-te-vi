"""Run this script once locally to generate token.json for Gmail OAuth."""
from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("token.json", "w") as f:
    f.write(creds.to_json())

print("token.json created successfully.")
print("\nCopy the contents below to the GMAIL_TOKEN_JSON GitHub secret:\n")
print(creds.to_json())
