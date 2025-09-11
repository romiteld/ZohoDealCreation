import asyncio
import os
import httpx
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('.env.local')

async def test_zoho_api():
    """Test Zoho API directly with refresh token"""
    
    # Zoho OAuth configuration
    client_id = os.getenv('ZOHO_CLIENT_ID')
    client_secret = os.getenv('ZOHO_CLIENT_SECRET')
    refresh_token = os.getenv('ZOHO_REFRESH_TOKEN')
    
    if not all([client_id, client_secret, refresh_token]):
        print("Missing Zoho OAuth credentials in .env.local")
        return
    
    async with httpx.AsyncClient() as client:
        # 1. Get access token using refresh token
        print("1. Getting access token from Zoho...")
        token_url = "https://accounts.zoho.com/oauth/v2/token"
        token_data = {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token"
        }
        
        token_response = await client.post(token_url, data=token_data)
        if token_response.status_code != 200:
            print(f"Failed to get token: {token_response.text}")
            return
            
        access_token = token_response.json().get('access_token')
        print(f"✅ Got access token: {access_token[:20]}...")
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }
        
        # 2. Search for all candidates
        print("\n2. Searching for ALL candidates in Zoho CRM...")
        
        # First try without any criteria to see if module exists
        url = "https://www.zohoapis.com/crm/v8/Candidates"
        params = {
            "fields": "id,First_Name,Last_Name,Email,Candidate_Status,Published_to_Vault,Date_Published_to_Vault",
            "per_page": 10
        }
        
        response = await client.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            candidates = data.get('data', [])
            print(f"✅ Found {len(candidates)} total candidates in CRM")
            
            # Check for Published_to_Vault field
            if candidates:
                first_cand = candidates[0]
                has_published_field = 'Published_to_Vault' in first_cand
                has_date_field = 'Date_Published_to_Vault' in first_cand
                
                print(f"\n3. Field check:")
                print(f"   - Published_to_Vault field exists: {has_published_field}")
                print(f"   - Date_Published_to_Vault field exists: {has_date_field}")
                
                if not has_published_field:
                    print("\n⚠️  Published_to_Vault field NOT FOUND in Candidates module!")
                    print("   Available fields:", list(first_cand.keys()))
                    
                # Show first few candidates
                print(f"\n4. First {min(3, len(candidates))} candidates:")
                for idx, cand in enumerate(candidates[:3], 1):
                    print(f"\n   {idx}. {cand.get('First_Name', '')} {cand.get('Last_Name', '')}")
                    print(f"      ID: {cand.get('id')}")
                    print(f"      Status: {cand.get('Candidate_Status', 'N/A')}")
                    print(f"      Published: {cand.get('Published_to_Vault', 'FIELD MISSING')}")
                    print(f"      Date Published: {cand.get('Date_Published_to_Vault', 'FIELD MISSING')}")
                    
        elif response.status_code == 204:
            print("❌ No candidates found in Zoho CRM (module is empty)")
        elif response.status_code == 401:
            print("❌ Authentication failed - token might be invalid")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    asyncio.run(test_zoho_api())
