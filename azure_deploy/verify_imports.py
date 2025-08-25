#!/usr/bin/env python3
"""
Verify all required imports work correctly
"""

import sys
import traceback

# Override sqlite3 with pysqlite3 first
try:
    import pysqlite3
    sys.modules['sqlite3'] = pysqlite3
    sys.modules['sqlite3.dbapi2'] = pysqlite3.dbapi2
    print("✓ SQLite override successful")
except ImportError:
    print("⚠ SQLite override not available")

def verify_imports():
    """Test all critical imports"""
    
    imports_to_test = [
        # Core web framework
        ("fastapi", "FastAPI"),
        ("uvicorn", None),
        ("gunicorn", None),
        
        # Azure
        ("azure.storage.blob", "BlobServiceClient"),
        
        # Database
        ("asyncpg", None),
        ("psycopg2", None),
        ("pgvector", None),
        
        # AI/ML
        ("openai", None),
        ("langchain", None),
        ("langchain.chat_models", None),
        ("langchain_openai", "ChatOpenAI"),
        ("crewai", "Crew"),
        
        # Utilities
        ("pydantic", None),
        ("dotenv", "load_dotenv"),
        ("requests", None),
        ("tenacity", None),
        
        # Web research
        ("firecrawl", None),
    ]
    
    failed_imports = []
    
    for module_name, attr in imports_to_test:
        try:
            if '.' in module_name:
                parts = module_name.split('.')
                module = __import__(module_name, fromlist=[parts[-1]])
            else:
                module = __import__(module_name)
            
            if attr:
                getattr(module, attr)
            
            print(f"✓ {module_name}")
        except ImportError as e:
            failed_imports.append((module_name, str(e)))
            print(f"✗ {module_name}: {e}")
        except AttributeError as e:
            print(f"⚠ {module_name}: Module imported but {attr} not found")
        except Exception as e:
            failed_imports.append((module_name, str(e)))
            print(f"✗ {module_name}: Unexpected error - {e}")
    
    # Test CrewAI specifically
    try:
        from crewai import Crew, Agent, Task
        print("✓ CrewAI components available")
    except ImportError as e:
        print(f"✗ CrewAI components: {e}")
        failed_imports.append(("crewai components", str(e)))
    
    # Summary
    print("\n" + "="*50)
    if failed_imports:
        print(f"Failed imports: {len(failed_imports)}")
        for module, error in failed_imports:
            print(f"  - {module}")
        return False
    else:
        print("All imports successful!")
        return True

if __name__ == "__main__":
    success = verify_imports()
    sys.exit(0 if success else 1)
