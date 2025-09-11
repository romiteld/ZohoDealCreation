#!/usr/bin/env python3
"""
Test fixtures for Outlook email payloads.
Contains realistic Outlook message data for testing email intake.
"""

from datetime import datetime, timezone
import base64


class OutlookPayloadFixtures:
    """Test fixtures for Outlook email processing."""
    
    # Standard recruitment email
    RECRUITMENT_EMAIL = {
        "sender_email": "recruiter@talentfirm.com",
        "sender_name": "Jennifer Recruiter",
        "subject": "Senior Financial Advisor - Chicago Opportunity",
        "body": """<html>
<body>
<p>Dear Hiring Manager,</p>

<p>I hope this email finds you well. I am reaching out regarding an exceptional 
candidate for your Senior Financial Advisor position in Chicago.</p>

<p><strong>Candidate Profile:</strong><br>
Name: Michael Thompson<br>
Current Position: VP Wealth Management at Morgan Stanley<br>
Experience: 15 years in financial services<br>
AUM: $180M<br>
Location: Chicago, IL<br>
Education: MBA Finance, Northwestern Kellogg</p>

<p>Michael has consistently exceeded his targets and is seeking a new opportunity 
with a growing firm. He has expressed strong interest in your organization and 
would be available for an interview next week.</p>

<p>His key strengths include:<br>
• High-net-worth client relationship management<br>
• Portfolio construction and risk management<br>
• Business development and client acquisition<br>
• Team leadership and mentoring</p>

<p>Please let me know if you would like to review his resume and schedule a call.</p>

<p>Best regards,<br>
Jennifer Recruiter<br>
Senior Executive Recruiter<br>
TalentFirm Executive Search<br>
jennifer@talentfirm.com<br>
(312) 555-0123</p>
</body>
</html>""",
        "message_id": "AAMkAGQ2YjBmNzM0LWRkMjUtNDEzYS05NjY4LTE4ZTMwOWU0ZjkwNgBGAAAAAA@outlook.com",
        "attachments": [],
        "received_datetime": "2025-01-15T10:30:00Z",
        "conversation_id": "AAQkAGQ2YjBmNzM0LWRkMjUtNDEzYS05NjY4LTE4ZTMwOWU0ZjkwNgAQAL4kVxjSFFhBsEcX4HGKrSo="
    }
    
    # Referral email from internal source
    REFERRAL_EMAIL = {
        "sender_email": "partner@wellpartners.com",
        "sender_name": "Steve Perry",
        "subject": "Referral: Portfolio Manager - Sarah Kim",
        "body": """Hi Team,

I wanted to personally refer Sarah Kim for our Portfolio Manager opening. 
She comes highly recommended from our Chicago network.

Background:
- Currently at UBS Private Wealth Management
- 12 years experience managing high-net-worth portfolios
- CFA charterholder
- Strong performance track record (top 10% in her division)
- Looking to join a smaller, more entrepreneurial firm

I've known Sarah through industry events and she's exactly the type of 
talent we want to attract. She's professional, client-focused, and 
has the kind of integrity that fits our culture.

Please prioritize this referral and reach out to her directly:
Sarah Kim
sarah.kim@email.com
(773) 555-0156

I've already told her someone from our team will be in touch this week.

Best,
Steve

Steve Perry
Managing Partner
The Well Partners""",
        "message_id": "AAMkAGQ2YjBmNzM0LWRkMjUtNDEzYS05NjY4LTE4ZTMwOWU0ZjkwNgBGAAAAB@outlook.com",
        "attachments": [],
        "received_datetime": "2025-01-16T14:22:00Z",
        "conversation_id": "AAQkAGQ2YjBmNzM0LWRkMjUtNDEzYS05NjY4LTE4ZTMwOWU0ZjkwNgAQAM3nVxjSFFhBsEcX4HGKrSp="
    }
    
    # Direct candidate application
    CANDIDATE_APPLICATION = {
        "sender_email": "david.rodriguez@gmail.com",
        "sender_name": "David Rodriguez",
        "subject": "Application for Wealth Manager Position",
        "body": """Dear The Well Partners Hiring Team,

I am writing to express my strong interest in the Wealth Manager position 
I saw posted on your website. With over 10 years of experience in wealth 
management and a track record of building long-term client relationships, 
I believe I would be a valuable addition to your team.

My background includes:
• 10+ years at Edward Jones as Senior Financial Advisor
• $85M in assets under management
• Consistent top performer (President's Club 5 years)
• Series 7, 66, and insurance licenses
• Bachelor's in Finance from University of Illinois Chicago

What attracts me to The Well Partners is your focus on fiduciary responsibility 
and comprehensive financial planning. I share these values and believe in 
putting clients' interests first in all decisions.

I would welcome the opportunity to discuss how my experience and client-first 
approach would benefit your team. I am available at your convenience and 
can provide references upon request.

Thank you for your consideration.

Sincerely,
David Rodriguez
(312) 555-9876
david.rodriguez@gmail.com

P.S. I am currently licensed in Illinois and Wisconsin, and would be happy 
to obtain additional state licenses as needed.""",
        "message_id": "AAMkAGQ2YjBmNzM0LWRkMjUtNDEzYS05NjY4LTE4ZTMwOWU0ZjkwNgBGAAAAC@outlook.com",
        "attachments": [
            {
                "filename": "David_Rodriguez_Resume.pdf",
                "content_type": "application/pdf",
                "size": 245760,
                "content_base64": base64.b64encode(b"Mock PDF resume content").decode()
            }
        ],
        "received_datetime": "2025-01-17T09:15:00Z",
        "conversation_id": "AAQkAGQ2YjBmNzM0LWRkMjUtNDEzYS05NjY4LTE4ZTMwOWU0ZjkwNgAQAP8mVxjSFFhBsEcX4HGKrSq="
    }
    
    # Headhunter pitch with multiple candidates
    HEADHUNTER_PITCH = {
        "sender_email": "lisa@executivesearch.com",
        "sender_name": "Lisa Chen",
        "subject": "3 Premium Candidates - Investment Advisory Roles",
        "body": """Good morning,

I have three exceptional candidates who would be perfect fits for your 
investment advisory openings. All are currently employed and confidentially 
exploring opportunities.

CANDIDATE #1: Senior Investment Advisor
• Name: Robert Martinez
• Current: Goldman Sachs Private Wealth
• Experience: 18 years
• AUM: $350M
• Location: New York (willing to relocate to Chicago)
• Compensation: $650K+ total
• Education: Wharton MBA

CANDIDATE #2: Portfolio Manager
• Name: Emily Chen
• Current: JPMorgan Private Bank
• Experience: 14 years
• AUM: $220M
• Location: Chicago
• Compensation: $425K base + bonus
• Education: CFA, University of Chicago

CANDIDATE #3: Wealth Manager
• Name: James Wilson
• Current: Merrill Lynch Private Client
• Experience: 11 years
• AUM: $165M
• Location: Milwaukee (open to Chicago)
• Compensation: $380K total
• Education: CFP, Marquette University

All three candidates have pristine compliance records, strong client retention 
rates, and are motivated by the opportunity to join a growing independent firm.

I can arrange confidential interviews for any or all of these candidates 
within the next two weeks. My fee structure is 25% of first-year compensation, 
payable upon successful placement with 90-day guarantee.

Please let me know which candidates interest you most and I'll coordinate 
the next steps.

Best regards,
Lisa Chen
Executive Search Consultant
Elite Financial Recruiting
lisa@executivesearch.com
(773) 555-EXEC""",
        "message_id": "AAMkAGQ2YjBmNzM0LWRkMjUtNDEzYS05NjY4LTE4ZTMwOWU0ZjkwNgBGAAAAD@outlook.com",
        "attachments": [],
        "received_datetime": "2025-01-18T11:45:00Z",
        "conversation_id": "AAQkAGQ2YjBmNzM0LWRkMjUtNDEzYS05NjY4LTE4ZTMwOWU0ZjkwNgAQAB7pVxjSFFhBsEcX4HGKrSq="
    }
    
    # Forwarded email with nested candidate info
    FORWARDED_EMAIL = {
        "sender_email": "steve.perry@thewell.com",
        "sender_name": "Steve Perry",
        "subject": "FW: Outstanding Wealth Manager Referral",
        "body": """Team,

Please see the referral below from our contact at First National Bank. 
This sounds like exactly the type of candidate we're looking for.

Steve

-----Original Message-----
From: contact@firstnational.com
Sent: Thursday, January 18, 2025 3:30 PM
To: steve.perry@thewell.com
Subject: Outstanding Wealth Manager Referral

Hi Steve,

I hope you're doing well. I wanted to reach out about Jessica Wong, 
who is currently on my team but is looking to transition to the 
independent advisor space.

Jessica has been with us for 9 years and has built an impressive 
book of business:
- $125M AUM
- 180 high-net-worth clients
- Average account size: $695K
- Client retention rate: 97%

She's professional, detail-oriented, and has the entrepreneurial 
spirit that would thrive in your environment. Jessica is particularly 
strong with retirement planning and estate planning strategies.

She's expressed interest in firms like yours that offer more 
independence and growth opportunities. Would you have time for 
a brief call to discuss?

Her direct contact:
Jessica Wong
jessica.wong@email.com
(312) 555-7890

Thanks for considering this referral.

Best,
Tom Anderson
VP Private Banking
First National Bank""",
        "message_id": "AAMkAGQ2YjBmNzM0LWRkMjUtNDEzYS05NjY4LTE4ZTMwOWU0ZjkwNgBGAAAAE@outlook.com",
        "attachments": [],
        "received_datetime": "2025-01-18T15:45:00Z",
        "conversation_id": "AAQkAGQ2YjBmNzM0LWRkMjUtNDEzYS05NjY4LTE4ZTMwOWU0ZjkwNgAQAC8qVxjSFFhBsEcX4HGKrSq="
    }
    
    # Bulk recruiter email (lower quality lead)
    BULK_RECRUITER_EMAIL = {
        "sender_email": "noreply@massrecruiting.com",
        "sender_name": "TalentBot Recruiting",
        "subject": "Multiple Financial Advisor Opportunities Available",
        "body": """Dear Financial Professional,

Are you ready to take your career to the next level? We have multiple 
opportunities available for experienced financial advisors in the 
Chicago area.

Current Openings:
- Senior Financial Advisor ($75K-$150K)
- Investment Consultant ($85K-$200K) 
- Wealth Management Advisor ($100K-$250K)
- Portfolio Manager ($120K-$300K)

Requirements:
- 3+ years experience in financial services
- Series 7 and 66 licenses required
- Bachelor's degree preferred
- Strong communication skills
- Clean compliance record

Benefits:
- Competitive compensation packages
- Full benefits including health, dental, vision
- 401(k) with company match
- Flexible work arrangements available
- Professional development opportunities

To apply, please reply to this email with:
1. Current resume
2. Summary of your experience
3. Salary expectations
4. Preferred location

We will review all applications and contact qualified candidates 
within 5 business days.

Thank you,
TalentBot Recruiting Team
jobs@massrecruiting.com
1-800-RECRUIT

This is an automated message. Please do not reply directly to this email.""",
        "message_id": "AAMkAGQ2YjBmNzM0LWRkMjUtNDEzYS05NjY4LTE4ZTMwOWU0ZjkwNgBGAAAAF@outlook.com",
        "attachments": [],
        "received_datetime": "2025-01-19T08:30:00Z",
        "conversation_id": "AAQkAGQ2YjBmNzM0LWRkMjUtNDEzYS05NjY4LTE4ZTMwOWU0ZjkwNgAQAD9rVxjSFFhBsEcX4HGKrSq="
    }
    
    # Email with attachment handling
    EMAIL_WITH_RESUME = {
        "sender_email": "candidate@domain.com",
        "sender_name": "Amanda Foster",
        "subject": "Senior Advisor Position - Resume Attached", 
        "body": """Dear Hiring Manager,

Please find my resume attached for your review. I am very interested 
in the Senior Financial Advisor position at The Well Partners.

I have 8 years of experience at Northwestern Mutual and am looking 
for an opportunity to grow with an independent firm.

Key qualifications:
- $65M AUM across 95 clients
- Consistent top 15% performance ranking
- Series 7, 66, Life & Health licenses
- CFP certification in progress

I would welcome the opportunity to discuss my background further.

Thank you for your consideration.

Best regards,
Amanda Foster
amanda.foster@domain.com
(847) 555-4321""",
        "message_id": "AAMkAGQ2YjBmNzM0LWRkMjUtNDEzYS05NjY4LTE4ZTMwOWU0ZjkwNgBGAAAAG@outlook.com",
        "attachments": [
            {
                "filename": "Amanda_Foster_Resume_2025.pdf",
                "content_type": "application/pdf", 
                "size": 187392,
                "content_base64": base64.b64encode(b"Mock PDF resume content for Amanda Foster").decode()
            },
            {
                "filename": "References.docx",
                "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "size": 45672,
                "content_base64": base64.b64encode(b"Mock Word document with references").decode()
            }
        ],
        "received_datetime": "2025-01-20T13:15:00Z",
        "conversation_id": "AAQkAGQ2YjBmNzM0LWRkMjUtNDEzYS05NjY4LTE4ZTMwOWU0ZjkwNgAQAE5sVxjSFFhBsEcX4HGKrSq="
    }
    
    # Email with special characters and encoding issues
    ENCODING_TEST_EMAIL = {
        "sender_email": "josé@consultora.mx",
        "sender_name": "José María García",
        "subject": "Asesor Financiero - Candidato Bilingüe",
        "body": """Estimados Señores,

Me permito presentarles a María González, una excelente candidata 
para posiciones de asesoría financiera bilingüe.

Perfil:
• Nombre: María José González Rodríguez
• Experiencia: 12 años en banca privada
• Idiomas: Español nativo, Inglés fluido
• Ubicación: Chicago, IL
• Especialización: Clientes hispanos de alto patrimonio

María tiene una sólida formación académica (MBA - ITESM) y experiencia 
comprobada manejando carteras de más de $150M USD.

Estaría disponible para una entrevista la próxima semana.

Saludos cordiales,
José María García
Director Ejecutivo
Consultora Financiera México-USA
josé@consultora.mx
+1 (312) 555-MÉXICO""",
        "message_id": "AAMkAGQ2YjBmNzM0LWRkMjUtNDEzYS05NjY4LTE4ZTMwOWU0ZjkwNgBGAAAAH@outlook.com",
        "attachments": [],
        "received_datetime": "2025-01-21T16:20:00Z",
        "conversation_id": "AAQkAGQ2YjBmNzM0LWRkMjUtNDEzYS05NjY4LTE4ZTMwOWU0ZjkwNgAQAF7tVxjSFFhBsEcX4HGKrSq="
    }
    
    # Malformed/corrupted email for error handling
    MALFORMED_EMAIL = {
        "sender_email": "broken\x00@example.com",
        "sender_name": "Test\x01User\x0c",
        "subject": "Subject\x00with\x08control\x1fchars",
        "body": """This email contains\x00null bytes and\x01control\x08characters
        that\x0cshould\x1fbe\x7fsanitized\x9f by the system.
        
        It also has some unicode issues: \ud800\udc00 and emoji: 🎉📊
        
        The system should handle this gracefully.""",
        "message_id": "corrupted\x00message@outlook.com",
        "attachments": [],
        "received_datetime": "2025-01-22T10:00:00Z",
        "conversation_id": "corrupted-conversation-id"
    }
    
    # Very long email for size testing
    OVERSIZED_EMAIL = {
        "sender_email": "longform@writer.com",
        "sender_name": "Verbose Writer",
        "subject": "Extremely Detailed Candidate Profile",
        "body": "This is a test email with excessive content. " * 5000,  # ~200KB body
        "message_id": "oversized-email@outlook.com",
        "attachments": [],
        "received_datetime": "2025-01-23T11:30:00Z",
        "conversation_id": "oversized-conversation-id"
    }
    
    @classmethod
    def get_all_fixtures(cls):
        """Get all email fixtures as a list."""
        return [
            cls.RECRUITMENT_EMAIL,
            cls.REFERRAL_EMAIL,
            cls.CANDIDATE_APPLICATION,
            cls.HEADHUNTER_PITCH,
            cls.FORWARDED_EMAIL,
            cls.BULK_RECRUITER_EMAIL,
            cls.EMAIL_WITH_RESUME,
            cls.ENCODING_TEST_EMAIL,
            cls.MALFORMED_EMAIL,
            cls.OVERSIZED_EMAIL,
        ]
    
    @classmethod
    def get_fixture_by_type(cls, email_type: str):
        """Get specific fixture by type."""
        fixtures = {
            "recruitment": cls.RECRUITMENT_EMAIL,
            "referral": cls.REFERRAL_EMAIL,
            "candidate": cls.CANDIDATE_APPLICATION,
            "headhunter": cls.HEADHUNTER_PITCH,
            "forwarded": cls.FORWARDED_EMAIL,
            "bulk": cls.BULK_RECRUITER_EMAIL,
            "with_resume": cls.EMAIL_WITH_RESUME,
            "encoding_test": cls.ENCODING_TEST_EMAIL,
            "malformed": cls.MALFORMED_EMAIL,
            "oversized": cls.OVERSIZED_EMAIL,
        }
        return fixtures.get(email_type)
    
    @classmethod
    def create_graph_api_payload(cls, email_fixture: dict):
        """Convert email fixture to Microsoft Graph API format."""
        return {
            "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('user')/messages/$entity",
            "id": email_fixture["message_id"],
            "subject": email_fixture["subject"],
            "bodyPreview": email_fixture["body"][:255] + "...",
            "body": {
                "contentType": "HTML" if "<html>" in email_fixture["body"] else "Text",
                "content": email_fixture["body"]
            },
            "from": {
                "emailAddress": {
                    "address": email_fixture["sender_email"],
                    "name": email_fixture["sender_name"]
                }
            },
            "toRecipients": [{
                "emailAddress": {
                    "address": "intake@thewell.com",
                    "name": "The Well Partners"
                }
            }],
            "receivedDateTime": email_fixture["received_datetime"],
            "conversationId": email_fixture["conversation_id"],
            "hasAttachments": len(email_fixture.get("attachments", [])) > 0,
            "attachments": [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "id": f"attachment-{i}",
                    "name": att["filename"],
                    "contentType": att["content_type"],
                    "size": att["size"],
                    "contentBytes": att["content_base64"]
                }
                for i, att in enumerate(email_fixture.get("attachments", []))
            ]
        }


if __name__ == "__main__":
    # Example usage
    fixtures = OutlookPayloadFixtures()
    
    # Print sample fixture
    print("Sample recruitment email:")
    print(f"From: {fixtures.RECRUITMENT_EMAIL['sender_name']} <{fixtures.RECRUITMENT_EMAIL['sender_email']}>")
    print(f"Subject: {fixtures.RECRUITMENT_EMAIL['subject']}")
    print(f"Body preview: {fixtures.RECRUITMENT_EMAIL['body'][:200]}...")
    print(f"Message ID: {fixtures.RECRUITMENT_EMAIL['message_id']}")
    
    # Show Graph API format
    print("\nGraph API format:")
    graph_payload = fixtures.create_graph_api_payload(fixtures.RECRUITMENT_EMAIL)
    print(f"ID: {graph_payload['id']}")
    print(f"HasAttachments: {graph_payload['hasAttachments']}")
    print(f"Body type: {graph_payload['body']['contentType']}")