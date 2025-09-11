"""
Integration script to add the Import v2 router to the main FastAPI app
"""

import os
import sys
from pathlib import Path

def add_import_router():
    """Add the import v2 router to main.py"""
    
    main_py_path = Path("app/main.py")
    
    if not main_py_path.exists():
        print("❌ app/main.py not found")
        return False
    
    # Read the current content
    with open(main_py_path, 'r') as f:
        content = f.read()
    
    # Check if already added
    if 'import_exports_v2' in content:
        print("✅ Import v2 router already added to main.py")
        return True
    
    # Find the location to add the router
    # Look for the admin policies router line
    policies_router_line = "app.include_router(policies_router)"
    
    if policies_router_line not in content:
        print("❌ Could not find policies_router inclusion in main.py")
        return False
    
    # Add the import statement
    import_section = "# Import Admin routes\nfrom app.admin import policies_router"
    new_import_section = """# Import Admin routes
from app.admin import policies_router
from app.admin.import_exports_v2 import router as import_v2_router"""
    
    content = content.replace(import_section, new_import_section)
    
    # Add the router inclusion
    router_section = "# Include Admin policies router\napp.include_router(policies_router)"
    new_router_section = """# Include Admin policies router
app.include_router(policies_router)

# Include Admin import v2 router
app.include_router(import_v2_router)"""
    
    content = content.replace(router_section, new_router_section)
    
    # Write the updated content
    with open(main_py_path, 'w') as f:
        f.write(content)
    
    print("✅ Added import v2 router to main.py")
    print("   - Added import statement")
    print("   - Added router inclusion")
    return True

def verify_integration():
    """Verify the integration was successful"""
    
    try:
        # Try to import the module
        sys.path.append(str(Path.cwd()))
        
        # Set a dummy database URL for testing
        if not os.getenv('DATABASE_URL'):
            os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost:5432/test'
        
        from app.admin.import_exports_v2 import router as import_v2_router
        print("✅ Import v2 router imports successfully")
        
        # Check router configuration
        print(f"   - Router prefix: {import_v2_router.prefix}")
        print(f"   - Router tags: {import_v2_router.tags}")
        
        # List routes
        routes = [route.path for route in import_v2_router.routes]
        print(f"   - Routes: {routes}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import router: {e}")
        return False
    except Exception as e:
        print(f"❌ Error verifying integration: {e}")
        return False

def main():
    """Main integration function"""
    
    print("🚀 Integrating Import v2 Router with FastAPI App")
    print("=" * 50)
    
    # Step 1: Add router to main.py
    if not add_import_router():
        print("❌ Failed to add router to main.py")
        return False
    
    # Step 2: Verify integration
    if not verify_integration():
        print("❌ Failed to verify integration")
        return False
    
    print("\n✅ Integration completed successfully!")
    print("\nNext steps:")
    print("1. Run database migration: python app/admin/migrate_import_tables.py")
    print("2. Test the endpoints: python test_import_v2.py")
    print("3. Start your FastAPI app and check: http://localhost:8000/docs")
    print("4. Look for endpoints under 'admin' tag")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)