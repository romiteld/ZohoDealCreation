"""
Delete all Kevin Sullivan contact records from Zoho
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
import httpx

# Load environment variables
load_dotenv('.env.local')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Zoho OAuth service URL
ZOHO_OAUTH_SERVICE_URL = os.getenv('ZOHO_OAUTH_SERVICE_URL', 'https://well-zoho-oauth.azurewebsites.net')

# Contact IDs to delete
KEVIN_CONTACT_IDS = [
    "6221978000101505125",
    "6221978000099974044",
    "6221978000098251018"
]

async def get_access_token():
    """Get Zoho access token from OAuth service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ZOHO_OAUTH_SERVICE_URL}/oauth/token")
            if response.status_code == 200:
                data = response.json()
                return data.get('access_token')
            else:
                logger.error(f"Failed to get token: {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"Error getting access token: {e}")
        return None

async def delete_contact(contact_id, access_token):
    """Delete a contact from Zoho CRM"""
    try:
        url = f"https://www.zohoapis.com/crm/v8/Contacts/{contact_id}"
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.delete(url, headers=headers)

            if response.status_code in [200, 204]:
                logger.info(f"✅ Successfully deleted Contact: {contact_id}")
                return True
            elif response.status_code == 404:
                logger.info(f"ℹ️ Contact not found (already deleted?): {contact_id}")
                return True
            else:
                logger.error(f"❌ Failed to delete Contact {contact_id}: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False

    except Exception as e:
        logger.error(f"Error deleting Contact {contact_id}: {e}")
        return False

async def main():
    """Main function to delete all Kevin Sullivan contacts"""
    logger.info("🗑️ Cleaning up all Kevin Sullivan contact records...")

    # Get access token
    access_token = await get_access_token()
    if not access_token:
        logger.error("Failed to get Zoho access token")
        return

    logger.info("✅ Got Zoho access token")

    # Delete all contacts
    success_count = 0
    for contact_id in KEVIN_CONTACT_IDS:
        if await delete_contact(contact_id, access_token):
            success_count += 1

    logger.info(f"\n🎯 Cleanup complete: {success_count}/{len(KEVIN_CONTACT_IDS)} contacts deleted")

    if success_count == len(KEVIN_CONTACT_IDS):
        logger.info("✅ All Kevin Sullivan test records have been removed from Zoho!")
    else:
        logger.warning("⚠️ Some contacts may still exist. Please check manually if needed.")

if __name__ == "__main__":
    asyncio.run(main())