import os
from dotenv import load_dotenv
from app.crewai_manager import EmailProcessingCrew

load_dotenv('.env.local')

# Test email content
test_email = """
Subject: Financial Advisor opportunity - Fort Wayne area

Hi Brandon,

I wanted to reach out about Kevin Sullivan, a Senior Financial Advisor who's looking for new opportunities in the Fort Wayne area. 
He has 15+ years of experience managing high-net-worth portfolios and is particularly strong in retirement planning.

Kevin is actively interviewing and would be a great addition to your team at Northwestern Mutual.

Best regards,
Sarah Thompson
sarah@recruitmentfirm.com
"""

try:
    # Initialize the crew manager
    crew_manager = EmailProcessingCrew()
    
    # Extract the sender domain
    sender_domain = "recruitmentfirm.com"
    
    # Run the extraction
    print("Running extraction...")
    result = crew_manager.run(test_email, sender_domain)
    
    print(f"\nExtraction successful!")
    print(f"Result: {result}")
    print(f"Candidate Name: {result.candidate_name}")
    print(f"Job Title: {result.job_title}")
    print(f"Location: {result.location}")
    print(f"Company Name: {result.company_name}")
    print(f"Referrer Name: {result.referrer_name}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()