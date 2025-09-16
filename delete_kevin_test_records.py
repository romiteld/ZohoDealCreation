"""
Delete Kevin Sullivan test records created during API testing
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

# Test record IDs from the API call
TEST_RECORDS = {
    "deal_id": "6221978000101503150",
    "account_id": "6221978000101486215",
    "contact_id": "6221978000100019021"
}

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

async def delete_zoho_record(module, record_id, access_token):
    """Delete a record from Zoho CRM"""
    try:
        url = f"https://www.zohoapis.com/crm/v8/{module}/{record_id}"
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.delete(url, headers=headers)

            if response.status_code in [200, 204]:
                logger.info(f"✅ Successfully deleted {module} record: {record_id}")
                return True
            elif response.status_code == 404:
                logger.info(f"ℹ️ {module} record not found (already deleted?): {record_id}")
                return True
            else:
                logger.error(f"❌ Failed to delete {module} record {record_id}: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False

    except Exception as e:
        logger.error(f"Error deleting {module} record {record_id}: {e}")
        return False

async def main():
    """Main function to delete test records"""
    logger.info("🗑️ Starting deletion of Kevin Sullivan test records...")

    # Get access token
    access_token = await get_access_token()
    if not access_token:
        logger.error("Failed to get Zoho access token")
        return

    logger.info("✅ Got Zoho access token")

    # Delete records in reverse order of creation (Deal -> Contact -> Account)
    deletion_order = [
        ("Deals", TEST_RECORDS["deal_id"]),
        ("Contacts", TEST_RECORDS["contact_id"]),
        ("Accounts", TEST_RECORDS["account_id"])
    ]

    success_count = 0
    for module, record_id in deletion_order:
        if await delete_zoho_record(module, record_id, access_token):
            success_count += 1

    logger.info(f"\n🎯 Deletion complete: {success_count}/3 records processed")

    if success_count == 3:
        logger.info("✅ All Kevin Sullivan test records have been cleaned up!")
    else:
        logger.warning("⚠️ Some records may still exist. Please check manually if needed.")

if __name__ == "__main__":
    asyncio.run(main())