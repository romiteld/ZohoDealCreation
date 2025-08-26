import os
from dotenv import load_dotenv
from app.custom_llm import ChatOpenAIWithoutStop
from crewai import Agent, Task, Crew, Process

load_dotenv('.env.local')

# Test the LLM first
print("Testing LLM...")
llm = ChatOpenAIWithoutStop(
    model_name="gpt-5",
    temperature=1,  # GPT-5 only supports temperature=1
    streaming=False,  # Explicitly disable streaming
    api_key=os.getenv("OPENAI_API_KEY")
)

try:
    response = llm.invoke("Hello, this is a test")
    print(f"LLM Response: {response.content}")
except Exception as e:
    print(f"LLM Error: {e}")

# Test with a simple crew
print("\nTesting CrewAI...")
agent = Agent(
    role="Test Agent",
    goal="Test the system",
    backstory="You are a test agent",
    verbose=True,
    allow_delegation=False,
    llm=llm
)

task = Task(
    description="Say hello and confirm you're working",
    expected_output="A greeting message",
    agent=agent
)

crew = Crew(
    agents=[agent],
    tasks=[task],
    process=Process.sequential
)

try:
    result = crew.kickoff()
    print(f"Crew Result: {result}")
except Exception as e:
    print(f"Crew Error: {e}")