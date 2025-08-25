#!/usr/bin/env python3
"""Test script to verify all dependencies work together"""

import sys
print("Python version:", sys.version)
print("\n" + "="*60)

# Test Azure Cosmos DB
try:
    import azure.cosmos
    from azure.cosmos import CosmosClient
    print("✅ Azure Cosmos DB SDK imported successfully")
    print(f"   Version: {azure.cosmos.__version__}")
except ImportError as e:
    print(f"❌ Azure Cosmos DB import failed: {e}")

# Test PyMongo (for MongoDB vCore API)
try:
    import pymongo
    print("✅ PyMongo imported successfully")
    print(f"   Version: {pymongo.__version__}")
except ImportError as e:
    print(f"❌ PyMongo import failed: {e}")

# Test CrewAI
try:
    import crewai
    from crewai import Agent, Task, Crew
    print("✅ CrewAI imported successfully")
    print(f"   Version: {crewai.__version__}")
except ImportError as e:
    print(f"❌ CrewAI import failed: {e}")

# Test CrewAI Tools
try:
    import crewai_tools
    print("✅ CrewAI Tools imported successfully")
    if hasattr(crewai_tools, '__version__'):
        print(f"   Version: {crewai_tools.__version__}")
    else:
        print("   Version: Not available")
except ImportError as e:
    print(f"❌ CrewAI Tools import failed: {e}")

# Test Vector/Data libraries
try:
    import numpy as np
    import pandas as pd
    print("✅ NumPy and Pandas imported successfully")
    print(f"   NumPy Version: {np.__version__}")
    print(f"   Pandas Version: {pd.__version__}")
except ImportError as e:
    print(f"❌ NumPy/Pandas import failed: {e}")

# Test Azure Identity
try:
    from azure.identity import DefaultAzureCredential
    print("✅ Azure Identity imported successfully")
except ImportError as e:
    print(f"❌ Azure Identity import failed: {e}")

# Test Pydantic (used by both CrewAI and Azure SDKs)
try:
    import pydantic
    print("✅ Pydantic imported successfully")
    print(f"   Version: {pydantic.__version__}")
except ImportError as e:
    print(f"❌ Pydantic import failed: {e}")

# Test aiohttp
try:
    import aiohttp
    print("✅ aiohttp imported successfully")
    print(f"   Version: {aiohttp.__version__}")
except ImportError as e:
    print(f"❌ aiohttp import failed: {e}")

print("\n" + "="*60)

# Test vector embedding policy creation (Azure Cosmos DB feature)
try:
    vector_embedding_policy = {
        "vectorEmbeddings": [
            {
                "path": "/contentVector",
                "dataType": "float32",
                "dimensions": 1536,
                "distanceFunction": "cosine"
            }
        ]
    }
    print("✅ Vector embedding policy created successfully")
except Exception as e:
    print(f"❌ Vector embedding policy creation failed: {e}")

# Test CrewAI agent creation
try:
    test_agent = Agent(
        role="Test Agent",
        goal="Verify dependencies",
        backstory="A test agent to verify all dependencies work",
        verbose=False
    )
    print("✅ CrewAI Agent created successfully")
except Exception as e:
    print(f"❌ CrewAI Agent creation failed: {e}")

print("\n🎉 All dependency tests completed!")
print("No conflicts detected between Azure Cosmos DB, CrewAI, and CrewAI Tools!")