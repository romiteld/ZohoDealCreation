import asyncio
import os
import httpx
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('.env.local')

async def publish_leads_to_vault():
    """Publish first 5 leads to vault"""
    
    # Zoho OAuth configuration
    client_id = os.getenv('ZOHO_CLIENT_ID')
    client_secret = os.getenv('ZOHO_CLIENT_SECRET')
    refresh_token = os.getenv('ZOHO_REFRESH_TOKEN')
    
    async with httpx.AsyncClient() as client:
        # Get access token
        token_url = "https://accounts.zoho.com/oauth/v2/token"
        token_data = {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token"
        }
        
        token_response = await client.post(token_url, data=token_data)
        access_token = token_response.json().get('access_token')
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }
        
        print("=" * 60)
        print("PUBLISHING LEADS TO VAULT")
        print("=" * 60)
        
        # Get first 5 leads
        leads_url = "https://www.zohoapis.com/crm/v8/Leads"
        params = {
            "fields": "id,First_Name,Last_Name,Email,Lead_Status,Publish_to_Vault,Date_Published_to_Vault",
            "per_page": 5
        }
        
        response = await client.get(leads_url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            leads = data.get('data', [])
            print(f"\nFound {len(leads)} leads to publish")
            
            # Prepare update data
            update_data = {
                "data": []
            }
            
            for lead in leads:
                print(f"  - {lead.get('First_Name', '')} {lead.get('Last_Name', '')} (ID: {lead['id']})")
                update_data["data"].append({
                    "id": lead['id'],
                    "Publish_to_Vault": True,  # Correct field name!
                    "Date_Published_to_Vault": datetime.now().strftime("%Y-%m-%d")
                })
            
            # Update the leads
            print("\nUpdating leads...")
            update_url = "https://www.zohoapis.com/crm/v8/Leads"
            update_response = await client.put(update_url, headers=headers, json=update_data)
            
            if update_response.status_code == 200:
                print("\n✅ Successfully published leads to vault!")
                result = update_response.json()
                for item in result.get('data', []):
                    if item.get('status') == 'success':
                        print(f"   ✓ Updated lead {item.get('details', {}).get('id')}")
            else:
                print(f"❌ Failed to update: {update_response.status_code}")
                print(update_response.text)
                
        else:
            print(f"Error: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    asyncio.run(publish_leads_to_vault())
