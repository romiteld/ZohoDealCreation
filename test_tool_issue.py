import os
from dotenv import load_dotenv
from app.crewai_manager import EmailProcessingCrew

load_dotenv('.env.local')

try:
    # Initialize the crew manager
    crew_manager = EmailProcessingCrew()
    
    # Check if the tool is created properly
    print(f"Web search tool: {crew_manager.web_search_tool}")
    print(f"Web search tool type: {type(crew_manager.web_search_tool)}")
    
    # Try to set up the crew
    crew = crew_manager.setup_crew()
    print("Crew setup successful")
    
    # Check the researcher tools
    researcher = crew.agents[1]  # researcher is the second agent
    print(f"Researcher tools: {researcher.tools}")
    print(f"Researcher tools type: {type(researcher.tools)}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()