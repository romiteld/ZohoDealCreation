#!/usr/bin/env python3
"""Test minimal langchain dependencies for CrewAI integration"""

import sys
import importlib.util

def test_import(module_name, component=None):
    """Test if a module/component can be imported"""
    try:
        if component:
            exec(f"from {module_name} import {component}")
            print(f"✓ {module_name}.{component} - SUCCESS")
            return True
        else:
            importlib.import_module(module_name)
            print(f"✓ {module_name} - SUCCESS")
            return True
    except ImportError as e:
        print(f"✗ {module_name}{f'.{component}' if component else ''} - FAILED: {e}")
        return False
    except Exception as e:
        print(f"✗ {module_name}{f'.{component}' if component else ''} - ERROR: {e}")
        return False

def main():
    print("Testing minimal dependencies for CrewAI email processing:\n")
    
    # Test core CrewAI imports
    print("=== CrewAI Core ===")
    crewai_ok = test_import("crewai")
    test_import("crewai", "Agent")
    test_import("crewai", "Task")
    test_import("crewai", "Crew")
    test_import("crewai", "Process")
    
    # Test langchain imports actually used
    print("\n=== LangChain Dependencies (Used in Code) ===")
    
    # Used in optimized version
    langchain_openai_ok = test_import("langchain_openai", "ChatOpenAI")
    
    # Used in non-optimized version only
    print("\n=== Additional in Non-Optimized Version ===")
    langchain_tools_ok = test_import("langchain.tools", "Tool")
    
    # Test CrewAI tools (optional)
    print("\n=== Optional CrewAI Tools ===")
    crewai_tools_ok = test_import("crewai_tools", "ScrapeWebsiteTool")
    
    # Test other essential imports
    print("\n=== Other Essential Dependencies ===")
    test_import("openai")
    test_import("pydantic")
    test_import("firecrawl")
    
    # Summary
    print("\n=== SUMMARY ===")
    if crewai_ok and langchain_openai_ok:
        print("✓ Minimal dependencies for OPTIMIZED version are satisfied")
        print("  Required: crewai, langchain-openai")
    else:
        print("✗ Missing essential dependencies")
    
    if langchain_tools_ok:
        print("✓ Additional dependencies for NON-OPTIMIZED version are satisfied")
        print("  Additional: langchain (for Tool class)")
    else:
        print("! Non-optimized version would need: langchain")
    
    # Test actual functionality
    print("\n=== Functional Test ===")
    try:
        from langchain_openai import ChatOpenAI
        import os
        
        # Don't actually call the API, just verify initialization
        llm = ChatOpenAI(
            model="gpt-5-mini",
            temperature=1,
            api_key=os.getenv("OPENAI_API_KEY", "dummy-key-for-test")
        )
        print("✓ ChatOpenAI initialization successful")
    except Exception as e:
        print(f"✗ ChatOpenAI initialization failed: {e}")

if __name__ == "__main__":
    main()