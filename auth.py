import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/gmail.compose"
]

def get_creds():
    creds = None
    
    # 1. Load from Environment Variable (for Render)
    env_token = os.environ.get("GOOGLE_TOKEN_JSON")
    if env_token:
        creds = Credentials.from_authorized_user_info(json.loads(env_token), SCOPES)
    # 2. Fallback to local file
    elif os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    is_deployed = bool(
        os.environ.get("RENDER")
        or os.environ.get("RAILWAY_ENVIRONMENT")
        or os.environ.get("IS_DEPLOYED")
    )

    # 3. Refresh or Fail (No interactive login in cloud)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if is_deployed:
                raise Exception("Missing GOOGLE_TOKEN_JSON env var or token is totally invalid.")

            # Local flow
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the refreshed token locally only when not running in a deployed env
        if not is_deployed:
            with open("token.json", "w") as token:
                token.write(creds.to_json())
                
    return creds