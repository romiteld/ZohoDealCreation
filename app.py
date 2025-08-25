from flask import Flask, request, redirect
import requests
import os
from datetime import datetime

app = Flask(__name__)

# Configuration
CLIENT_ID = os.getenv("ZOHO_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET", "")
ZOHO_DC = os.getenv("ZOHO_DC", "com")
REDIRECT_URI = os.getenv("ZOHO_REDIRECT_URI", "https://well-zoho-oauth.azurewebsites.net/callback")

# Validate required envs at runtime (basic guard)
if not CLIENT_ID or not CLIENT_SECRET:
    raise RuntimeError("ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET must be set in environment variables")

@app.route('/')
def home():
    auth_url = (
        f"https://accounts.zoho.{ZOHO_DC}/oauth/v2/auth"
        "?scope=ZohoCRM.modules.ALL,ZohoCRM.settings.ALL,ZohoCRM.users.ALL"
        f"&client_id={CLIENT_ID}"
        "&response_type=code"
        "&access_type=offline"
        f"&redirect_uri={REDIRECT_URI}"
        "&prompt=consent"
    )
    
    return f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial; padding: 40px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
            .btn {{ display: inline-block; padding: 15px 40px; background: #0066cc; color: white; text-decoration: none; border-radius: 5px; font-size: 18px; }}
            .warning {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Zoho OAuth - The Well Recruiting</h1>
            <div class="warning">
                <strong>⏱️ URGENT:</strong> You have 10 minutes from updating Zoho app!
            </div>
            <p><a href="{auth_url}" class="btn">Click Here to Authorize with Zoho</a></p>
            <p>Time: {datetime.now()}</p>
        </div>
    </body>
    </html>
    """

@app.route('/callback')
def callback():
    code = request.args.get('code')
    
    if not code:
        return "Error: No authorization code received", 400
    
    token_url = f"https://accounts.zoho.{ZOHO_DC}/oauth/v2/token"
    data = {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': REDIRECT_URI,
        'code': code
    }
    
    response = requests.post(token_url, data=data)
    tokens = response.json()
    
    if 'refresh_token' in tokens:
        refresh_token = tokens['refresh_token']
        access_token = tokens.get('access_token', '')
        
        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: monospace; padding: 40px; background: #f5f5f5; }}
                .success {{ color: green; }}
                .token-box {{ background: #f0f0f0; padding: 15px; border: 2px solid green; border-radius: 5px; margin: 20px 0; }}
                textarea {{ width: 100%; height: 100px; font-size: 14px; font-family: monospace; }}
            </style>
        </head>
        <body>
            <h1 class="success">✅ SUCCESS - REFRESH TOKEN RETRIEVED!</h1>
            <div class="token-box">
                <h2>COPY THIS REFRESH TOKEN NOW:</h2>
                <textarea readonly onclick="this.select()">{refresh_token}</textarea>
                
                <h2>Access Token:</h2>
                <textarea readonly onclick="this.select()">{access_token}</textarea>
                
                <h2>Add to .env.local:</h2>
                <textarea readonly onclick="this.select()">ZOHO_REFRESH_TOKEN={refresh_token}</textarea>
            </div>
            <p>Retrieved at: {datetime.now()}</p>
            <p style="color: red; font-size: 18px;">⚠️ SAVE THESE TOKENS IMMEDIATELY!</p>
        </body>
        </html>
        """
    else:
        return f"""
        <html>
        <body>
            <h1 style="color: red;">Error getting tokens</h1>
            <pre>{tokens}</pre>
        </body>
        </html>
        """

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)