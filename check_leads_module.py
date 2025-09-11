import asyncio
import os
import httpx
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('.env.local')

async def check_leads_module():
    """Check Leads module (which is actually Candidates in Zoho)"""
    
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
        print("ZOHO CRM: LEADS MODULE (aka Candidates)")
        print("=" * 60)
        
        # 1. Get Leads (which are Candidates)
        print("\n1. Fetching Leads/Candidates from Zoho CRM...")
        
        leads_url = "https://www.zohoapis.com/crm/v8/Leads"
        params = {
            "fields": "id,First_Name,Last_Name,Email,Lead_Status,Published_to_Vault,Date_Published_to_Vault,Owner",
            "per_page": 10
        }
        
        response = await client.get(leads_url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            leads = data.get('data', [])
            print(f"✅ Found {len(leads)} Leads/Candidates")
            
            # Check if fields exist
            if leads:
                first_lead = leads[0]
                available_fields = list(first_lead.keys())
                
                print(f"\n2. Available fields in Leads module:")
                for field in available_fields:
                    print(f"   - {field}: {first_lead.get(field, '')}")
                
                has_published = 'Published_to_Vault' in first_lead
                has_date_published = 'Date_Published_to_Vault' in first_lead
                
                print(f"\n3. Field Status:")
                print(f"   ✓ Published_to_Vault exists: {has_published}")
                print(f"   ✓ Date_Published_to_Vault exists: {has_date_published}")
                
                if not has_published or not has_date_published:
                    print("\n⚠️  MISSING REQUIRED FIELDS!")
                    print("   The backend expects these fields but they don't exist.")
                    print("   Options:")
                    print("   1. Add these fields via Zoho CRM UI (Setup > Modules > Leads > Fields)")
                    print("   2. Update backend to use existing Lead_Status field")
                    
                # Show unpublished leads
                print(f"\n4. Lead/Candidate Summary:")
                unpublished = []
                for lead in leads:
                    published = lead.get('Published_to_Vault', False)
                    if not published:
                        unpublished.append(lead)
                        
                print(f"   - Total: {len(leads)}")
                print(f"   - Unpublished: {len(unpublished)}")
                print(f"   - Published: {len(leads) - len(unpublished)}")
                
                if unpublished:
                    print(f"\n5. First 3 unpublished Leads/Candidates:")
                    for idx, lead in enumerate(unpublished[:3], 1):
                        print(f"\n   {idx}. {lead.get('First_Name', '')} {lead.get('Last_Name', '')}")
                        print(f"      ID: {lead.get('id')}")
                        print(f"      Email: {lead.get('Email', 'N/A')}")
                        print(f"      Status: {lead.get('Lead_Status', 'N/A')}")
                        print(f"      Owner: {lead.get('Owner', {}).get('name', 'Unknown')}")
                    
        elif response.status_code == 204:
            print("❌ No Leads found in Zoho CRM")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
        # Check field metadata
        print("\n" + "=" * 60)
        print("6. Checking field definitions in Leads module...")
        
        fields_url = "https://www.zohoapis.com/crm/v8/settings/fields?module=Leads"
        response = await client.get(fields_url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            fields = data.get('fields', [])
            
            # Look for our specific fields
            vault_fields = []
            for field in fields:
                api_name = field.get('api_name', '')
                if 'vault' in api_name.lower() or 'published' in api_name.lower():
                    vault_fields.append(field)
                    
            if vault_fields:
                print("\n✅ Found vault-related fields:")
                for field in vault_fields:
                    print(f"   - {field.get('api_name')}: {field.get('display_label')} ({field.get('data_type')})")
            else:
                print("\n❌ No vault-related fields found in Leads module")
                print("   Need to add Published_to_Vault and Date_Published_to_Vault fields")

if __name__ == "__main__":
    asyncio.run(check_leads_module())
