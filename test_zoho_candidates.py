import asyncio
import os
import httpx
import urllib.parse
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('.env.local')

async def check_and_publish_candidates():
    """Check Zoho CRM for candidates and publish some to vault"""
    
    # Get OAuth token from our OAuth service
    oauth_service_url = os.getenv('ZOHO_OAUTH_SERVICE_URL', 'https://well-zoho-oauth.azurewebsites.net')
    
    async with httpx.AsyncClient() as client:
        # Get access token
        print("Getting Zoho access token...")
        token_response = await client.get(f"{oauth_service_url}/get-token")
        if token_response.status_code != 200:
            print(f"Failed to get token: {token_response.text}")
            return
        
        access_token = token_response.json().get('access_token')
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }
        
        # 1. First, search for candidates NOT published to vault
        print("\n1. Searching for candidates NOT published to vault...")
        
        # Search for candidates where Published_to_Vault is false or null
        search_criteria = "((Candidate_Status:not_equals:Placed)and(Candidate_Status:not_equals:Hired))"
        
        url = "https://www.zohoapis.com/crm/v8/Candidates/search"
        params = {
            "criteria": search_criteria,
            "fields": "id,First_Name,Last_Name,Email,Candidate_Status,Published_to_Vault,Date_Published_to_Vault,Owner",
            "per_page": 20
        }
        
        response = await client.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            candidates = data.get('data', [])
            print(f"Found {len(candidates)} candidates (not placed/hired)")
            
            # Find unpublished candidates
            unpublished = []
            for cand in candidates:
                published = cand.get('Published_to_Vault', False)
                if not published:
                    unpublished.append(cand)
                    
            print(f"Found {len(unpublished)} unpublished candidates")
            
            if len(unpublished) > 0:
                # 2. Publish the first 5 candidates
                print("\n2. Publishing first 5 candidates to vault...")
                
                to_publish = unpublished[:5]
                update_data = {
                    "data": []
                }
                
                for cand in to_publish:
                    print(f"   - {cand.get('First_Name', '')} {cand.get('Last_Name', '')} (ID: {cand['id']})")
                    update_data["data"].append({
                        "id": cand['id'],
                        "Published_to_Vault": True,
                        "Date_Published_to_Vault": datetime.now().strftime("%Y-%m-%d")
                    })
                
                # Update the candidates
                update_url = "https://www.zohoapis.com/crm/v8/Candidates"
                update_response = await client.put(update_url, headers=headers, json=update_data)
                
                if update_response.status_code == 200:
                    print(f"\n✅ Successfully published {len(to_publish)} candidates to vault!")
                    result = update_response.json()
                    for item in result.get('data', []):
                        if item.get('status') == 'success':
                            print(f"   ✓ Updated candidate {item.get('details', {}).get('id')}")
                else:
                    print(f"❌ Failed to update: {update_response.status_code}")
                    print(update_response.text)
                    
            else:
                print("\n⚠️  All candidates are already published to vault!")
                
        elif response.status_code == 204:
            print("\n⚠️  No candidates found in Zoho CRM (module might be empty)")
        else:
            print(f"Error searching: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    asyncio.run(check_and_publish_candidates())
