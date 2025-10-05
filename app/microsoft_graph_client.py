"""
Microsoft Graph API Client for Real Email Integration
Connects to user's Outlook inbox and processes recruitment emails
"""

import os
import logging
import asyncio
import aiohttp
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import base64
import json

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class EmailData:
    """Email data structure for processing"""
    id: str
    from_address: str
    from_name: str
    subject: str
    body: str
    received_time: str
    has_attachments: bool
    attachments: List[Dict[str, Any]]
    importance: str
    is_read: bool
    categories: List[str]
    
    def to_dict(self):
        return asdict(self)

class MicrosoftGraphClient:
    """Client for Microsoft Graph API to access real emails"""
    
    def __init__(self, tenant_id: str = None, client_id: str = None, client_secret: str = None):
        self.tenant_id = tenant_id or os.getenv("AZURE_TENANT_ID")
        self.client_id = client_id or os.getenv("AZURE_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("AZURE_CLIENT_SECRET")
        
        # Graph API endpoints
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"
        
        # Access token cache
        self.access_token = None
        self.token_expires = None
        
        # Email filtering criteria for recruitment
        self.recruitment_keywords = [
            'resume', 'cv', 'application', 'position', 'job', 'candidate',
            'hiring', 'interview', 'employment', 'career', 'opportunity',
            'apply', 'interested', 'qualification', 'experience', 'skill'
        ]
        
        # Recruitment email domains (customize for your business)
        self.recruitment_domains = [
            'thewell.solutions',
            'emailthewell.com'
        ]
    
    async def get_access_token(self) -> str:
        """Get Microsoft Graph access token using client credentials"""
        try:
            # Check if current token is still valid
            if self.access_token and self.token_expires and datetime.now() < self.token_expires:
                return self.access_token
            
            token_endpoint = f"{self.authority}/oauth2/v2.0/token"
            
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'scope': 'https://graph.microsoft.com/.default'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(token_endpoint, data=data) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        self.access_token = token_data['access_token']
                        expires_in = token_data.get('expires_in', 3600)
                        self.token_expires = datetime.now() + timedelta(seconds=expires_in - 60)
                        logger.info("Successfully obtained Microsoft Graph access token")
                        return self.access_token
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to obtain access token: {response.status} - {error_text}")
                        raise Exception(f"Authentication failed: {response.status}")
        
        except Exception as e:
            logger.error(f"Error obtaining access token: {e}")
            raise

    async def get_users(self) -> List[Dict[str, Any]]:
        """Get list of users in the organization"""
        try:
            token = await self.get_access_token()
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.graph_endpoint}/users"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('value', [])
                    else:
                        logger.error(f"Failed to get users: {response.status}")
                        return []
        
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return []

    async def get_user_emails(self, user_email: str, 
                            filter_recruitment: bool = True,
                            hours_back: int = 24,
                            max_emails: int = 50) -> List[EmailData]:
        """Get emails from user's inbox with recruitment filtering"""
        try:
            token = await self.get_access_token()
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            # Build OData filter for recent emails
            since_time = (datetime.utcnow() - timedelta(hours=hours_back)).isoformat() + 'Z'
            odata_filter = f"receivedDateTime ge {since_time}"
            
            # Add recruitment filtering if enabled
            if filter_recruitment:
                # Filter for emails with recruitment keywords or from recruitment domains
                keyword_filters = []
                for keyword in self.recruitment_keywords[:5]:  # Limit to avoid URL length issues
                    keyword_filters.append(f"contains(subject, '{keyword}') or contains(body/content, '{keyword}')")
                
                domain_filters = []
                for domain in self.recruitment_domains:
                    domain_filters.append(f"contains(from/emailAddress/address, '{domain}')")
                
                recruitment_filter = f"({' or '.join(keyword_filters + domain_filters)})"
                odata_filter = f"({odata_filter}) and ({recruitment_filter})"
            
            url = f"{self.graph_endpoint}/users/{user_email}/messages"
            params = {
                '$filter': odata_filter,
                '$select': 'id,from,subject,body,receivedDateTime,hasAttachments,importance,isRead,categories',
                '$top': max_emails,
                '$orderby': 'receivedDateTime desc'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        emails = []
                        
                        for email_data in data.get('value', []):
                            try:
                                # Get attachments if any
                                attachments = []
                                if email_data.get('hasAttachments'):
                                    attachments = await self.get_email_attachments(user_email, email_data['id'])
                                
                                email = EmailData(
                                    id=email_data['id'],
                                    from_address=email_data['from']['emailAddress']['address'],
                                    from_name=email_data['from']['emailAddress'].get('name', ''),
                                    subject=email_data['subject'] or '',
                                    body=email_data['body']['content'] or '',
                                    received_time=email_data['receivedDateTime'],
                                    has_attachments=email_data.get('hasAttachments', False),
                                    attachments=attachments,
                                    importance=email_data.get('importance', 'normal'),
                                    is_read=email_data.get('isRead', False),
                                    categories=email_data.get('categories', [])
                                )
                                emails.append(email)
                            except Exception as e:
                                logger.warning(f"Error processing email {email_data.get('id', 'unknown')}: {e}")
                                continue
                        
                        logger.info(f"Retrieved {len(emails)} emails for user {user_email}")
                        return emails
                    
                    elif response.status == 404:
                        logger.warning(f"User {user_email} not found")
                        return []
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to get emails for {user_email}: {response.status} - {error_text}")
                        return []
        
        except Exception as e:
            logger.error(f"Error getting emails for {user_email}: {e}")
            return []

    async def get_email_attachments(self, user_email: str, message_id: str) -> List[Dict[str, Any]]:
        """Get attachments for a specific email"""
        try:
            token = await self.get_access_token()
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.graph_endpoint}/users/{user_email}/messages/{message_id}/attachments"
            params = {
                '$select': 'id,name,contentType,size,isInline'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        attachments = []
                        
                        for attachment in data.get('value', []):
                            attachments.append({
                                'id': attachment['id'],
                                'name': attachment.get('name', 'unknown'),
                                'contentType': attachment.get('contentType', ''),
                                'size': attachment.get('size', 0),
                                'isInline': attachment.get('isInline', False)
                            })
                        
                        return attachments
                    else:
                        logger.warning(f"Could not get attachments for email {message_id}")
                        return []
        
        except Exception as e:
            logger.error(f"Error getting attachments for email {message_id}: {e}")
            return []

    async def get_recruitment_emails_for_organization(self, 
                                                   hours_back: int = 24,
                                                   max_emails_per_user: int = 20) -> Dict[str, List[EmailData]]:
        """Get recruitment emails from all users in the organization"""
        try:
            # Get all users
            users = await self.get_users()
            
            # Filter for users with recruitment-related roles or in specific groups
            recruitment_users = []
            for user in users:
                email = user.get('mail') or user.get('userPrincipalName', '')
                display_name = user.get('displayName', '')
                job_title = user.get('jobTitle', '').lower()
                
                # Add logic to identify recruitment team members
                if any(keyword in job_title for keyword in ['recruiter', 'hr', 'hiring', 'talent']):
                    recruitment_users.append(email)
                elif any(domain in email for domain in self.recruitment_domains):
                    recruitment_users.append(email)
            
            # If no specific recruitment users found, use a default set
            if not recruitment_users:
                # Use a default recruitment email (configure for your organization)
                default_email = os.getenv("DEFAULT_RECRUITMENT_EMAIL", "daniel.romitelli@emailthewell.com")
                recruitment_users = [default_email]
            
            # Get emails for each recruitment user
            all_emails = {}
            tasks = []
            
            for user_email in recruitment_users[:5]:  # Limit to 5 users to avoid rate limits
                task = self.get_user_emails(
                    user_email=user_email,
                    filter_recruitment=True,
                    hours_back=hours_back,
                    max_emails=max_emails_per_user
                )
                tasks.append((user_email, task))
            
            # Execute all tasks concurrently
            for user_email, task in tasks:
                try:
                    emails = await task
                    if emails:
                        all_emails[user_email] = emails
                except Exception as e:
                    logger.error(f"Failed to get emails for {user_email}: {e}")
                    continue
            
            total_emails = sum(len(emails) for emails in all_emails.values())
            logger.info(f"Retrieved {total_emails} recruitment emails from {len(all_emails)} users")
            
            return all_emails
        
        except Exception as e:
            logger.error(f"Error getting recruitment emails for organization: {e}")
            return {}

    async def mark_email_as_processed(self, user_email: str, message_id: str):
        """Mark an email as processed by adding a category"""
        try:
            token = await self.get_access_token()
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.graph_endpoint}/users/{user_email}/messages/{message_id}"
            
            # Add "Processed by Zoho" category
            data = {
                'categories': ['Processed by Zoho', 'The Well Recruiting']
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.patch(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        logger.info(f"Marked email {message_id} as processed")
                        return True
                    else:
                        logger.warning(f"Could not mark email {message_id} as processed: {response.status}")
                        return False
        
        except Exception as e:
            logger.error(f"Error marking email {message_id} as processed: {e}")
            return False

    async def test_connection(self) -> bool:
        """Test the Microsoft Graph connection"""
        try:
            token = await self.get_access_token()
            if not token:
                return False
            
            # Test by getting organization info
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.graph_endpoint}/organization"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        org_name = data.get('value', [{}])[0].get('displayName', 'Unknown')
                        logger.info(f"Successfully connected to Microsoft Graph for organization: {org_name}")
                        return True
                    else:
                        logger.error(f"Microsoft Graph connection test failed: {response.status}")
                        return False
        
        except Exception as e:
            logger.error(f"Microsoft Graph connection test error: {e}")
            return False

# Convenience function for testing
async def test_graph_client():
    """Test function for Microsoft Graph client"""
    client = MicrosoftGraphClient()
    
    print("Testing Microsoft Graph connection...")
    is_connected = await client.test_connection()
    print(f"Connection status: {'✅ Connected' if is_connected else '❌ Failed'}")
    
    if is_connected:
        print("\nGetting recruitment emails...")
        emails = await client.get_recruitment_emails_for_organization(hours_back=168)  # Last week
        
        total_emails = sum(len(user_emails) for user_emails in emails.values())
        print(f"Found {total_emails} recruitment emails from {len(emails)} users")
        
        # Show sample emails
        for user_email, user_emails in list(emails.items())[:2]:
            print(f"\n📧 User: {user_email}")
            for email in user_emails[:3]:
                print(f"   • {email.subject[:50]}... from {email.from_name}")

if __name__ == "__main__":
    asyncio.run(test_graph_client())