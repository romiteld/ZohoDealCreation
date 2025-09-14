#!/usr/bin/env python3
"""Test script for Calendly email extraction"""

import asyncio
import json
from app.langgraph_manager import EmailProcessingWorkflow

# Sample Calendly email content from the PDF
CALENDLY_EMAIL_CONTENT = """
Invitee: Roy Janse
Invitee Email: roy.janse@mariner.com
Event Date/Time: 11:30am - Thursday, September 11, 2025 (Central Time - US & Canada)
Description: Who We Are: The Well Recruiting Solutions—your partner in finding and hiring top-tier talent.
What We'll Do: Discuss your specific recruiting goals, share proven strategies, and map out a plan to build your ideal team.
Our Approach: A refreshing, personalized experience focused on understanding your unique needs and setting you up for long-term hiring success.
Next Steps: Book a time that works for you, and we'll tackle your recruiting challenges together.
Location: This is a Zoom web conference. Attendees can join this meeting from a computer, tablet or smartphone.
https://us02web.zoom.us/j/8065004359?omn=89172961675
One tap mobile:
+1 646 931 3860,,8065004359#
+1 301 715 8592,,8065004359#
They can also dial in using a phone.
US: +1 646 931 3860, +1 301 715 8592, +1 305 224 1968, +1 309 205 3325, +1 312 626 6799, +1 646 558 8656, +1 564 217 2000, +1 669 444 9171, +1 669 900 9128, +16892781000, +1 719 359 4580, +1 253 205 0468, +1 253 215 8782, +1 346 248 7799, +1 360 209 5623, +1 386 347 5053, +1 507 473 4847
Meeting ID: 806-500-4359
Invitee Time Zone: Eastern Time - US & Canada
Questions:
Phone +1 864-430-5074
What recruiting goals or ideas would you like to discuss?
Mid-career advisors to our Greenville team.
Your confirmation email might land in spam/junk. Got it- I'll check my spam/junk
View event in Calendly
Pro Tip!
Take Calendly anywhere you work Use Calendly anywhere on the web, without switching tabs!
Access your event types, share your Calendly link, and create meetings right from your Gmail or Outlook.
Get Calendly for Chrome, Firefox, or Outlook. See all apps
Sent from Calendly Report this event
"""

async def test_extraction():
    """Test the email extraction with Calendly content"""
    print("=" * 80)
    print("Testing Calendly Email Extraction")
    print("=" * 80)

    # Initialize the workflow
    workflow = EmailProcessingWorkflow()

    # Test with Calendly email
    sender_domain = "calendly.com"

    print("\n📧 Processing Calendly email...")
    print("-" * 40)

    try:
        # Process the email
        result = await workflow.process_email(
            email_body=CALENDLY_EMAIL_CONTENT,
            sender_domain=sender_domain
        )

        print("\n✅ Extraction Results:")
        print("-" * 40)

        # Display extracted fields
        fields_to_check = [
            ('candidate_name', 'Roy Janse'),
            ('email', 'roy.janse@mariner.com'),
            ('phone', '+1 864-430-5074'),
            ('job_title', None),
            ('location', 'Greenville'),
            ('company_name', 'Mariner'),
            ('notes', 'Mid-career advisors to our Greenville team')
        ]

        for field_name, expected in fields_to_check:
            actual = getattr(result, field_name, None)
            status = "✅" if actual else "❌"
            print(f"{status} {field_name}: {actual}")
            if expected and actual != expected:
                print(f"   ⚠️  Expected: {expected}")

        # Check for common issues
        print("\n🔍 Quality Checks:")
        print("-" * 40)

        # Check if email field contains only the email address
        if result.email and len(result.email) > 100:
            print("❌ Email field too long - may contain extra content")
        else:
            print("✅ Email field contains only email address")

        # Check if phone was extracted
        if result.phone:
            print(f"✅ Phone extracted: {result.phone}")
        else:
            print("❌ Phone number not extracted")

        # Check if notes contain recruiting goals
        if result.notes and "advisor" in result.notes.lower():
            print("✅ Recruiting goals captured in notes")
        else:
            print("❌ Recruiting goals not captured in notes")

        # Display full result for debugging
        print("\n📋 Full Extraction Result (JSON):")
        print("-" * 40)
        result_dict = {
            'candidate_name': result.candidate_name,
            'email': result.email,
            'phone': result.phone,
            'job_title': result.job_title,
            'location': result.location,
            'company_name': result.company_name,
            'referrer_name': result.referrer_name,
            'referrer_email': result.referrer_email,
            'notes': result.notes,
            'linkedin_url': result.linkedin_url,
            'website': result.website,
            'source': result.source,
            'source_detail': result.source_detail
        }
        print(json.dumps(result_dict, indent=2))

        # Test edge cases
        print("\n🧪 Testing Edge Cases:")
        print("-" * 40)

        # Test with the problematic format mentioned by user
        edge_case_email = """
        Roy Janse Invitee Email: roy.janse@mariner.com Event Date/Time: 11:30am - Thursday, September 11, 2025
        Phone +1 864-430-5074
        What recruiting goals or ideas would you like to discuss? Mid-career advisors to our Greenville team.
        """

        print("Testing with condensed format...")
        edge_result = await workflow.process_email(
            email_body=edge_case_email,
            sender_domain="calendly.com"
        )

        print(f"  Candidate: {edge_result.candidate_name}")
        print(f"  Email: {edge_result.email}")
        print(f"  Phone: {edge_result.phone}")
        print(f"  Notes: {edge_result.notes}")

    except Exception as e:
        print(f"\n❌ Error during extraction: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_extraction())