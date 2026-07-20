import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET_PATH = os.path.join(PROJECT_ROOT, 'client_secret.json')
TOKEN_PICKLE_PATH = os.path.join(PROJECT_ROOT, 'token.pickle')

SCOPES = ['https://www.googleapis.com/auth/drive']

def get_token():
    creds = None
    
    if os.path.exists(TOKEN_PICKLE_PATH):
        print("✅ token.pickle already exists!")
        return
    
    print("🔐 Creating new OAuth token...")
    
    if not os.path.exists(CLIENT_SECRET_PATH):
        print(f"❌ client_secret.json not found at: {CLIENT_SECRET_PATH}")
        return
    
    # Web app client - use loopback
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRET_PATH, 
        SCOPES
    )
    
    print("\nBrowser will open automatically...")
    print("Please login and allow access.\n")
    
    # Opens browser + starts local server on port 8080
    creds = flow.run_local_server(port=8080)
    
    with open(TOKEN_PICKLE_PATH, 'wb') as token:
        pickle.dump(creds, token)
    
    print(f"\n✅ token.pickle created successfully!")
    print(f"📁 Saved to: {TOKEN_PICKLE_PATH}")

if __name__ == '__main__':
    get_token()