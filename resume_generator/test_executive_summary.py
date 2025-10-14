import asyncio
import os
from app.services.openai_service import OpenAIService

async def test():
    os.environ['AZURE_OPENAI_ENDPOINT'] = 'https://eastus2.api.cognitive.microsoft.com/'
    os.environ['AZURE_OPENAI_KEY'] = 'a3dfd2487f074dd7aa46d61489a9b300'
    os.environ['AZURE_OPENAI_DEPLOYMENT'] = 'gpt-5-mini'
    os.environ['AZURE_OPENAI_API_VERSION'] = '2024-08-01-preview'
    
    service = OpenAIService()
    
    test_context = """
Recent Experience: Senior Vice President, Transitions & Onboarding at Osaic: Directed onboarding of 350+ advisors representing over $20B in AUM Launched digital Transition Dashboard to improve real-time tracking and recruiting efficiency | Vice President, Advisor Experience at National Planning Holdings (NPH): Founded and led Advisor Experience department (33 employees, 6 locations); centralized training for 3,000+ advisors Oversaw $7M event budget and managed 17 national conferences with 2,500+ attendees
Key Skills: Advisor transitions, Onboarding strategy, Wealth management operations, Enterprise training & development, Cross-functional leadership, Project management, Digital product launches, AUM migration & integration
"""
    
    summary = await service.generate_executive_summary(
        interview_notes=test_context,
        candidate_name="Kirsten Bosch",
        target_role="leadership position"
    )
    
    print(f"Summary length: {len(summary)}")
    print(f"Summary: {summary}")

asyncio.run(test())
