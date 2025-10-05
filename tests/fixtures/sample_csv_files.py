#!/usr/bin/env python3
"""
Test data fixtures for TalentWell CSV import system.
Contains sample CSV files with edge cases for comprehensive testing.
"""

import os
from pathlib import Path
from datetime import datetime, timedelta


class CSVFixtures:
    """Test CSV data fixtures with various edge cases."""
    
    # Valid CSV with proper structure
    VALID_DEALS_CSV = """Deal Id,Deal Name,Deal Owner,Job Title,Account Name,Location,Stage,Created Time,Closing Date,Modified Time
123,John Doe - Senior Advisor,Steve Perry,Senior Financial Advisor,Morgan Stanley,Chicago IL,Qualification,2025-01-15 10:30:00,2025-02-15,2025-01-20 14:22:00
124,Jane Smith - VP Wealth,Steve Perry,VP Wealth Management,Independent Firm,New York NY,Negotiation,2025-03-10,2025-04-10,2025-03-15
125,Mike Johnson - Portfolio Manager,Steve Perry,Portfolio Manager,Wells Fargo,Boston MA,Closed Won,2025-02-01,2025-03-01,2025-02-15
126,Sarah Wilson - Analyst,Steve Perry,Investment Analyst,Charles Schwab,Dallas TX,Proposal,2025-04-10,2025-05-10,2025-04-15"""
    
    # CSV with various date formats
    MIXED_DATE_FORMATS_CSV = """Deal Id,Deal Name,Deal Owner,Created Time,Closing Date
127,Format Test 1,Steve Perry,2025-01-15 10:30:00,2025-02-15
128,Format Test 2,Steve Perry,01/15/2025,02/15/2025
129,Format Test 3,Steve Perry,01/15/2025 10:30 AM,02/15/2025 2:30 PM
130,Format Test 4,Steve Perry,15-Jan-2025,15-Feb-2025
131,Format Test 5,Steve Perry,01-15-2025,02-15-2025
132,Format Test 6,Steve Perry,2025/01/15,2025/02/15
133,Format Test 7,Steve Perry,01/15/25,02/15/25"""
    
    # CSV with encoding issues and special characters
    ENCODING_TEST_CSV = """Deal Id,Deal Name,Deal Owner,Job Title,Account Name,Location
134,José García - Advisor,Steve Perry,Financial Advisor,Banco Español,São Paulo
135,François Müller - Manager,Steve Perry,Portfolio Manager,Credit Suisse,Zürich
136,李明 - Analyst,Steve Perry,Investment Analyst,中国银行,北京
137,محمد أحمد - Consultant,Steve Perry,Financial Consultant,البنك العربي,دبي
138,Åse Nordström - Director,Steve Perry,Investment Director,Nordea Bank,Stockholm"""
    
    # CSV with column aliases
    COLUMN_ALIASES_CSV = """DealId,Name,Owner,Title,Company,City,Status,CreatedDate,CloseDate
139,Test User 1,Steve Perry,Financial Advisor,LPL Financial,Chicago,Active,2025-01-20,2025-02-20
140,Test User 2,Steve Perry,Wealth Manager,Independent Firm,New York,Pending,2025-01-21,2025-02-21
141,Test User 3,Steve Perry,Portfolio Manager,Morgan Stanley,Boston,Closed,2025-01-22,2025-02-22"""
    
    # Malformed CSV with parsing challenges
    MALFORMED_CSV = """Deal Id,Deal Name,Deal Owner,Job Title
"142","Broken Quote - Test,Steve Perry,"Senior Advisor"
143,Normal Row,Steve Perry,Financial Advisor
144,"Missing Quote,Steve Perry,Wealth Manager
145,Extra Comma,Steve Perry,Portfolio Manager,
146,	Tab	Separated,Steve Perry,Investment Analyst"""
    
    # CSV with missing columns
    MISSING_COLUMNS_CSV = """Deal Name,Deal Owner,Created Time
Missing Columns Test 1,Steve Perry,2025-01-15
Missing Columns Test 2,Steve Perry,2025-01-16"""
    
    # CSV with extra columns
    EXTRA_COLUMNS_CSV = """Deal Id,Deal Name,Deal Owner,Extra Col 1,Job Title,Extra Col 2,Account Name,Random Data
147,Extra Columns Test,Steve Perry,Extra1,Financial Advisor,Extra2,Test Firm,Random
148,Another Test,Steve Perry,More Extra,Wealth Manager,Even More,Another Firm,More Random"""
    
    # Empty CSV
    EMPTY_CSV = ""
    
    # Header only CSV
    HEADER_ONLY_CSV = "Deal Id,Deal Name,Deal Owner,Job Title,Account Name"
    
    # CSV with different owners (filtering test)
    MULTIPLE_OWNERS_CSV = """Deal Id,Deal Name,Deal Owner,Job Title,Created Time
149,Steve Deal 1,Steve Perry,Financial Advisor,2025-01-15
150,John Deal 1,John Smith,Wealth Manager,2025-01-15
151,Steve Deal 2,Steve Perry,Portfolio Manager,2025-01-16
152,Jane Deal 1,Jane Doe,Investment Analyst,2025-01-16
153,Steve Deal 3,Steve Perry,Senior Advisor,2025-01-17"""
    
    # CSV with date range filtering test
    DATE_RANGE_TEST_CSV = """Deal Id,Deal Name,Deal Owner,Created Time
154,Too Early,Steve Perry,2024-12-31
155,Just Right,Steve Perry,2025-01-15
156,Also Right,Steve Perry,2025-05-10
157,Too Late,Steve Perry,2025-10-01
158,Edge Case Early,Steve Perry,2025-01-01 00:00:00
159,Edge Case Late,Steve Perry,2025-09-08 23:59:59"""
    
    # Large CSV for performance testing
    def generate_large_csv(self, num_rows: int = 10000) -> str:
        """Generate large CSV for performance testing."""
        header = "Deal Id,Deal Name,Deal Owner,Job Title,Account Name,Location,Stage,Created Time"
        rows = [header]
        
        for i in range(1, num_rows + 1):
            row = f"{i},Deal {i},Steve Perry,Financial Advisor,Firm {i},City {i},New,2025-01-{(i % 28) + 1:02d}"
            rows.append(row)
        
        return "\n".join(rows)
    
    # CSV with various data quality issues
    DATA_QUALITY_ISSUES_CSV = """Deal Id,Deal Name,Deal Owner,Job Title,Account Name,Location,Contact Email,Phone
160,Quality Test 1,Steve Perry,,Missing Title Inc,,valid@email.com,555-123-4567
161,,Steve Perry,Financial Advisor,No Name Firm,Chicago,invalid-email,not-a-phone
162,Quality Test 3,Steve Perry,Wealth Manager,Special Chars <>&"',New York,test@domain,123
163,Quality Test 4,Steve Perry,Very Long Job Title That Exceeds Normal Limits And Should Be Truncated,Normal Firm,Boston,normal@email.com,555-987-6543
164,Quality Test 5,Steve Perry,Financial Advisor,   Whitespace Firm   ,  Chicago  ,  spaced@email.com  ,  555-111-2222  """
    
    # CSV with various stage values
    STAGE_VARIETY_CSV = """Deal Id,Deal Name,Deal Owner,Stage,Created Time
165,New Stage,Steve Perry,New,2025-01-15
166,Qualification Stage,Steve Perry,Qualification,2025-01-15
167,Proposal Stage,Steve Perry,Proposal,2025-01-15
168,Negotiation Stage,Steve Perry,Negotiation,2025-01-15
169,Closed Won Stage,Steve Perry,Closed Won,2025-01-15
170,Closed Lost Stage,Steve Perry,Closed Lost,2025-01-15
171,On Hold Stage,Steve Perry,On Hold,2025-01-15
172,Custom Stage,Steve Perry,Custom Stage Name,2025-01-15"""
    
    # CSV with location variety
    LOCATION_VARIETY_CSV = """Deal Id,Deal Name,Deal Owner,Location,Created Time
173,Chicago Test,Steve Perry,Chicago IL,2025-01-15
174,New York Test,Steve Perry,New York NY,2025-01-15
175,Los Angeles Test,Steve Perry,Los Angeles CA,2025-01-15
176,Remote Test,Steve Perry,Remote,2025-01-15
177,International Test,Steve Perry,London UK,2025-01-15
178,State Only Test,Steve Perry,Texas,2025-01-15
179,City Only Test,Steve Perry,Miami,2025-01-15
180,Full Address Test,Steve Perry,"123 Main St, Chicago, IL 60601",2025-01-15"""
    
    # CSV with firm variety for employer classification
    FIRM_VARIETY_CSV = """Deal Id,Deal Name,Deal Owner,Account Name,Created Time
181,LPL Test,Steve Perry,LPL Financial,2025-01-15
182,Raymond James Test,Steve Perry,Raymond James & Associates,2025-01-15
183,Morgan Stanley Test,Steve Perry,Morgan Stanley Smith Barney,2025-01-15
184,Merrill Test,Steve Perry,Merrill Lynch Pierce Fenner & Smith,2025-01-15
185,Wells Fargo Test,Steve Perry,Wells Fargo Advisors,2025-01-15
186,Independent Test 1,Steve Perry,Independent Wealth Advisors,2025-01-15
187,Independent Test 2,Steve Perry,Smith Family Financial,2025-01-15
188,Regional Test,Steve Perry,Midwest Financial Group,2025-01-15"""
    
    @classmethod
    def write_fixture_files(cls, output_dir: Path):
        """Write all fixture CSV files to disk for testing."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        fixtures = {
            'valid_deals.csv': cls.VALID_DEALS_CSV,
            'mixed_dates.csv': cls.MIXED_DATE_FORMATS_CSV,
            'encoding_test.csv': cls.ENCODING_TEST_CSV,
            'column_aliases.csv': cls.COLUMN_ALIASES_CSV,
            'malformed.csv': cls.MALFORMED_CSV,
            'missing_columns.csv': cls.MISSING_COLUMNS_CSV,
            'extra_columns.csv': cls.EXTRA_COLUMNS_CSV,
            'empty.csv': cls.EMPTY_CSV,
            'header_only.csv': cls.HEADER_ONLY_CSV,
            'multiple_owners.csv': cls.MULTIPLE_OWNERS_CSV,
            'date_range_test.csv': cls.DATE_RANGE_TEST_CSV,
            'data_quality_issues.csv': cls.DATA_QUALITY_ISSUES_CSV,
            'stage_variety.csv': cls.STAGE_VARIETY_CSV,
            'location_variety.csv': cls.LOCATION_VARIETY_CSV,
            'firm_variety.csv': cls.FIRM_VARIETY_CSV,
        }
        
        for filename, content in fixtures.items():
            file_path = output_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        # Generate large file separately
        instance = cls()
        large_content = instance.generate_large_csv(10000)
        with open(output_dir / 'large_10k.csv', 'w', encoding='utf-8') as f:
            f.write(large_content)
        
        # Generate oversized file for limit testing
        oversized_content = instance.generate_large_csv(100001)
        with open(output_dir / 'oversized_100k.csv', 'w', encoding='utf-8') as f:
            f.write(oversized_content)
    
    @classmethod
    def get_csv_as_bytes(cls, csv_content: str, encoding: str = 'utf-8') -> bytes:
        """Convert CSV content to bytes with specified encoding."""
        return csv_content.encode(encoding)
    
    @classmethod
    def create_multipart_chunks(cls, csv_content: str, chunk_size: int = 1024) -> list:
        """Split CSV content into chunks for multipart upload testing."""
        content_bytes = csv_content.encode('utf-8')
        chunks = []
        
        for i in range(0, len(content_bytes), chunk_size):
            chunks.append(content_bytes[i:i + chunk_size])
        
        return chunks


# Additional utility functions for test data generation
def generate_test_email_data(count: int = 5) -> list:
    """Generate test email data for intake testing."""
    emails = []
    
    templates = [
        {
            "sender_email": "recruiter1@example.com",
            "sender_name": "John Recruiter",
            "subject": "Great candidate for Senior Advisor role",
            "body": """Hi Team,
            
I'd like to introduce Sarah Johnson for the Senior Financial Advisor 
position in Chicago. She has 12 years of experience at Morgan Stanley 
and is looking for new opportunities.

Contact: sarah@example.com
Phone: 555-123-4567

Best regards,
John Recruiter""",
            "message_id": "recruiter-email-1@outlook.com"
        },
        {
            "sender_email": "referrer@wellpartners.com",
            "sender_name": "Jane Referrer", 
            "subject": "Referral - Michael Chen",
            "body": """Hello,

I'm referring Michael Chen for the Wealth Manager position. 
He's currently at UBS with 8 years of experience and excellent 
client relationships.

Please reach out to michael.chen@email.com

Thanks,
Jane""",
            "message_id": "referral-email-1@outlook.com"
        },
        {
            "sender_email": "candidate@gmail.com",
            "sender_name": "David Smith",
            "subject": "Interest in Financial Advisor Position",
            "body": """Dear Hiring Manager,

I am writing to express my interest in financial advisor opportunities. 
I have 10 years of experience at Raymond James and am looking for 
new challenges.

Resume attached.

Best regards,
David Smith
david.smith@gmail.com
555-987-6543""",
            "message_id": "candidate-email-1@outlook.com"
        },
        {
            "sender_email": "partner@headhunter.com",
            "sender_name": "Lisa Hunter",
            "subject": "VP Wealth Management - Premium Candidate",
            "body": """Good morning,

I have an exceptional candidate for VP-level wealth management roles:

Name: Robert Taylor
Current: Goldman Sachs (12 years)
AUM: $2.8B
Location: New York (open to Chicago)

Compensation expectations: $400K base + bonus
Available for interview next week.

Call me at 555-HUNTER to discuss.

Lisa Hunter
Executive Search""",
            "message_id": "headhunter-email-1@outlook.com"
        },
        {
            "sender_email": "internal@thewell.com",
            "sender_name": "Steve Perry",
            "subject": "FW: Portfolio Manager Referral",
            "body": """Team,

Please see below referral from our Chicago contact:

------- Forwarded Message -------
From: chicago-contact@advisor.com
Subject: Portfolio Manager Referral

Hi Steve,

I wanted to refer Jessica Wang for portfolio management roles. 
She's at Schwab currently with strong performance metrics 
and is looking to join a growing firm.

Best,
Chicago Contact
------- End Forward -------

Please follow up on this.

Steve""",
            "message_id": "internal-email-1@outlook.com"
        }
    ]
    
    # Generate requested number of emails, cycling through templates
    for i in range(count):
        template = templates[i % len(templates)]
        email = template.copy()
        
        # Modify IDs to make unique
        email["message_id"] = f"{email['message_id']}-{i}"
        
        # Add some variation
        if i > 0:
            email["subject"] += f" (Batch {i})"
            
        emails.append(email)
    
    return emails


def generate_zoho_mock_responses():
    """Generate mock Zoho API responses for testing."""
    return {
        "success_lead": {
            "data": [{
                "code": "SUCCESS",
                "details": {
                    "id": "123456789",
                    "created_time": "2025-01-15T10:30:00-05:00"
                },
                "message": "Lead created successfully"
            }]
        },
        "success_deal": {
            "data": [{
                "code": "SUCCESS", 
                "details": {
                    "id": "987654321",
                    "created_time": "2025-01-15T10:30:00-05:00"
                },
                "message": "Deal created successfully"
            }]
        },
        "duplicate_error": {
            "data": [{
                "code": "DUPLICATE_DATA",
                "details": {
                    "id": "123456789"
                },
                "message": "Duplicate record found"
            }]
        },
        "validation_error": {
            "data": [{
                "code": "INVALID_DATA",
                "details": {
                    "api_name": "Email",
                    "message": "Invalid email format"
                },
                "message": "Validation failed"
            }]
        },
        "rate_limit_error": {
            "code": "RATE_LIMIT_EXCEEDED",
            "message": "API rate limit exceeded. Try again later.",
            "details": {
                "retry_after": 60
            }
        },
        "server_error": {
            "code": "INTERNAL_ERROR",
            "message": "Internal server error occurred",
            "details": {}
        }
    }


if __name__ == "__main__":
    # Create fixture files for manual testing
    fixtures_dir = Path(__file__).parent
    CSVFixtures.write_fixture_files(fixtures_dir)
    print(f"Fixture files written to {fixtures_dir}")