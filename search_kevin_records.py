"""
Search for any Kevin Sullivan test records in Zoho
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

async def search_records(module, search_criteria, access_token):
    """Search for records in Zoho CRM"""
    try:
        url = f"https://www.zohoapis.com/crm/v8/{module}/search"
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }
        params = {
            "criteria": search_criteria,
            "fields": "id,First_Name,Last_Name,Full_Name,Deal_Name,Account_Name,Email"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()
                records = data.get('data', [])
                if records:
                    logger.info(f"Found {len(records)} {module} record(s):")
                    for record in records:
                        logger.info(f"  - ID: {record.get('id')}, Name: {record.get('First_Name', record.get('Deal_Name', record.get('Account_Name', 'N/A')))}")
                    return records
                else:
                    logger.info(f"No {module} records found")
                    return []
            elif response.status_code == 204:
                logger.info(f"No {module} records found")
                return []
            else:
                logger.error(f"Search failed for {module}: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return []

    except Exception as e:
        logger.error(f"Error searching {module}: {e}")
        return []

async def main():
    """Main function to search for test records"""
    logger.info("🔍 Searching for Kevin Sullivan test records in Zoho...")

    # Get access token
    access_token = await get_access_token()
    if not access_token:
        logger.error("Failed to get Zoho access token")
        return

    logger.info("✅ Got Zoho access token")

    # Search for Kevin Sullivan records in different modules
    search_queries = [
        ("Contacts", "(First_Name:equals:Kevin)and(Last_Name:equals:Sullivan)"),
        ("Deals", "(Deal_Name:contains:Kevin Sullivan)"),
        ("Accounts", "(Account_Name:contains:NAMCOA)"),
        ("Accounts", "(Account_Name:contains:Well Partners Recruiting)")
    ]

    all_records = []
    for module, criteria in search_queries:
        logger.info(f"\n🔎 Searching {module} with: {criteria}")
        records = await search_records(module, criteria, access_token)
        if records:
            all_records.extend([(module, r) for r in records])

    if all_records:
        logger.info(f"\n⚠️ Found {len(all_records)} total test record(s) that may need cleanup")
        logger.info("\nRecord IDs for deletion:")
        for module, record in all_records:
            logger.info(f"  - {module}: {record.get('id')}")
    else:
        logger.info("\n✅ No Kevin Sullivan test records found in Zoho!")

if __name__ == "__main__":
    asyncio.run(main())