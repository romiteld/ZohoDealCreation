import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv('.env.local')

async def list_zoho_modules():
    """List all available modules in Zoho CRM"""
    
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
        
        # Get all modules
        print("Available Zoho CRM Modules:")
        print("-" * 50)
        
        modules_url = "https://www.zohoapis.com/crm/v8/settings/modules"
        response = await client.get(modules_url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            modules = data.get('modules', [])
            
            # Filter for relevant modules
            for module in modules:
                api_name = module.get('api_name')
                display_name = module.get('plural_label')
                editable = module.get('editable', False)
                
                # Show all modules that might contain candidates/talent data
                if any(keyword in api_name.lower() for keyword in ['candidate', 'talent', 'contact', 'lead', 'custom']):
                    print(f"✓ {api_name:30} ({display_name}) - Editable: {editable}")
                elif editable:  # Show all editable modules
                    print(f"  {api_name:30} ({display_name})")
                    
            # Now check Contacts module specifically
            print("\n" + "=" * 50)
            print("Checking Contacts module for Published_to_Vault...")
            
            contacts_url = "https://www.zohoapis.com/crm/v8/Contacts"
            params = {"fields": "id,First_Name,Last_Name,Email,Published_to_Vault,Date_Published_to_Vault", "per_page": 5}
            
            response = await client.get(contacts_url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                contacts = data.get('data', [])
                print(f"Found {len(contacts)} contacts")
                
                if contacts:
                    first_contact = contacts[0]
                    print("\nFirst contact fields:", list(first_contact.keys())[:10])
                    print(f"Has Published_to_Vault: {'Published_to_Vault' in first_contact}")
                    
        else:
            print(f"Error: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    asyncio.run(list_zoho_modules())
