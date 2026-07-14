import requests
import json

# --- INPUT YOUR CREDENTIALS HERE ---
CODE_FROM_URL = "IKKADA_BROWSER_URL_LO_VACHINA_CODE_PASTE_CHEY"
CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID"
CLIENT_SECRET = "YOUR_GOOGLE_CLIENT_SECRET"
# ----------------------------------

# Make sure to strip any whitespaces or trailing character blocks
payload = {
    'code': CODE_FROM_URL.strip(),
    'client_id': CLIENT_ID.strip(),
    'client_secret': CLIENT_SECRET.strip(),
    'redirect_uri': 'http://localhost:8080/',
    'grant_type': 'authorization_code'
}

print("Fetching token from Google...")
response = requests.post('https://oauth2.googleapis.com/token', data=payload)

print("\n--- GOOGLE RESPONSE ---")
print(response.text)