import httpx
from app.config import settings
from app.models.candidate import CandidateResponse

class ZohoService:
    def __init__(self):
        # Use Zoho APIs directly instead of OAuth proxy
        # The OAuth proxy doesn't support /crm/ endpoints
        self.base_url = "https://www.zohoapis.com/crm/v8"
        self.oauth_service_url = settings.ZOHO_OAUTH_SERVICE_URL
        self.access_token = None

    async def get_access_token(self) -> str:
        """Get Zoho OAuth access token from OAuth service."""
        if self.access_token:
            return self.access_token

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.oauth_service_url}/oauth/token",
                timeout=10.0
            )
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            return self.access_token

    async def fetch_candidate(self, candidate_id: str) -> CandidateResponse:
        """
        Fetch candidate data from Zoho CRM.
        Uses OAuth token from OAuth proxy service.

        Note: Candidates are stored in the Leads module, not Contacts.
        """
        token = await self.get_access_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/Leads/{candidate_id}",
                headers={"Authorization": f"Zoho-oauthtoken {token}"},
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

            # Extract relevant fields
            candidate_data = data.get("data", [{}])[0]

            # Try multiple field name formats for Interview Notes
            # Zoho might use different naming conventions
            interview_notes = (
                candidate_data.get("Interviewer_Notes") or
                candidate_data.get("Interview_Notes") or
                candidate_data.get("The_Well_Assessment", {}).get("Interviewer_Notes") or
                ""
            )

            # Try multiple field name formats for Current Location
            current_location = (
                candidate_data.get("Current_Location") or
                candidate_data.get("Current Location") or
                ""
            )

            return CandidateResponse(
                full_name=candidate_data.get("Full_Name", ""),
                email=candidate_data.get("Email", ""),
                phone=candidate_data.get("Phone", ""),
                city=candidate_data.get("City", ""),
                state=candidate_data.get("State", ""),
                current_location=current_location,
                linkedin_url=candidate_data.get("LinkedIn_Profile") or candidate_data.get("LinkedIn_URL", ""),
                interview_notes=interview_notes,
                target_role=candidate_data.get("Title") or candidate_data.get("Target_Role", "")
            )

    async def get_all_attachments(self, candidate_id: str) -> list:
        """
        Get list of all attachments for a candidate.
        Returns list of attachment metadata.
        """
        token = await self.get_access_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/Leads/{candidate_id}/Attachments",
                headers={"Authorization": f"Zoho-oauthtoken {token}"},
                params={"fields": "File_Name,Size,id"},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("data", [])

    async def get_resume_attachment(self, candidate_id: str) -> bytes:
        """
        Download candidate's resume PDF attachment from Zoho.
        Looks for resume, CV, or general PDF files (NOT LinkedIn profile).

        Priority order:
        1. Files with "resume" or "CV" in name
        2. Files with candidate name in filename
        3. First PDF that's not LinkedIn

        Note: Candidates are stored in the Leads module, not Contacts.
        """
        token = await self.get_access_token()

        async with httpx.AsyncClient() as client:
            attachments = await self.get_all_attachments(candidate_id)

            # Filter out LinkedIn profiles
            non_linkedin_pdfs = [
                att for att in attachments
                if att.get("File_Name", "").lower().endswith(".pdf")
                and "linkedin" not in att.get("File_Name", "").lower()
            ]

            # Priority 1: Look for "resume" or "CV" in filename
            resume_attachment = None
            for attachment in non_linkedin_pdfs:
                filename = attachment.get("File_Name", "").lower()
                if "resume" in filename or "cv" in filename:
                    resume_attachment = attachment
                    break

            # Priority 2: If no resume-specific file, get first non-LinkedIn PDF
            if not resume_attachment and non_linkedin_pdfs:
                resume_attachment = non_linkedin_pdfs[0]

            if not resume_attachment:
                raise ValueError("No resume PDF attachment found (only LinkedIn profiles available)")

            # Download the attachment
            attachment_id = resume_attachment.get("id")
            download_response = await client.get(
                f"{self.base_url}/Leads/{candidate_id}/Attachments/{attachment_id}",
                headers={"Authorization": f"Zoho-oauthtoken {token}"},
                timeout=60.0
            )
            download_response.raise_for_status()

            return download_response.content

    async def get_linkedin_attachment(self, candidate_id: str) -> bytes:
        """
        Download LinkedIn PDF attachment from Zoho.
        Brandon's requirement: LinkedIn profile is attached to candidate record.

        Note: Candidates are stored in the Leads module, not Contacts.
        """
        token = await self.get_access_token()

        async with httpx.AsyncClient() as client:
            attachments = await self.get_all_attachments(candidate_id)

            # Find LinkedIn PDF (look for "LinkedIn" or "profile" in filename)
            linkedin_attachment = None
            for attachment in attachments:
                filename = attachment.get("File_Name", "").lower()
                if "linkedin" in filename or "profile" in filename:
                    linkedin_attachment = attachment
                    break

            if not linkedin_attachment:
                # If no LinkedIn-specific attachment, get first PDF
                for attachment in attachments:
                    if attachment.get("File_Name", "").lower().endswith(".pdf"):
                        linkedin_attachment = attachment
                        break

            if not linkedin_attachment:
                raise ValueError("No LinkedIn PDF attachment found")

            # Download the attachment
            attachment_id = linkedin_attachment.get("id")
            download_response = await client.get(
                f"{self.base_url}/Leads/{candidate_id}/Attachments/{attachment_id}",
                headers={"Authorization": f"Zoho-oauthtoken {token}"},
                timeout=60.0
            )
            download_response.raise_for_status()

            return download_response.content

    async def upload_attachment(
        self,
        candidate_id: str,
        pdf_data: bytes,
        filename: str
    ) -> dict:
        """
        Upload generated PDF to Zoho CRM attachments.

        Note: Candidates are stored in the Leads module, not Contacts.
        """
        token = await self.get_access_token()

        async with httpx.AsyncClient() as client:
            files = {"file": (filename, pdf_data, "application/pdf")}

            response = await client.post(
                f"{self.base_url}/Leads/{candidate_id}/Attachments",
                headers={"Authorization": f"Zoho-oauthtoken {token}"},
                files=files,
                timeout=60.0
            )
            response.raise_for_status()
            result = response.json()

            return {
                "success": True,
                "attachment_id": result.get("data", [{}])[0].get("details", {}).get("id")
            }

    async def download_linkedin_pdf(self, candidate_id: str) -> bytes:
        """Alias for get_linkedin_attachment for consistency."""
        return await self.get_linkedin_attachment(candidate_id)

    async def upload_resume_pdf(
        self,
        candidate_id: str,
        pdf_bytes: bytes,
        filename: str
    ) -> str:
        """
        Upload resume PDF and return attachment ID.
        Alias for upload_attachment for consistency.
        """
        result = await self.upload_attachment(candidate_id, pdf_bytes, filename)
        return result.get("attachment_id")
