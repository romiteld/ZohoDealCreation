#!/usr/bin/env python3
"""
Migrate to Cosmos DB version - No more SQLite/Chroma issues!
This completely removes Chroma dependencies and uses Cosmos DB for vector storage
"""

import os
import shutil
import sys
from datetime import datetime

def create_backup(file_path):
    """Create backup of file before modification"""
    if os.path.exists(file_path):
        backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(file_path, backup_path)
        print(f"✅ Backed up {file_path} to {backup_path}")
        return backup_path
    return None

def migrate_to_cosmosdb():
    """Migrate to Cosmos DB-based solution"""
    print("\n🚀 Migrating to Cosmos DB for PostgreSQL with pgvector...")
    print("=" * 60)
    
    # Files to migrate
    migrations = [
        ("app/crewai_manager_cosmosdb.py", "app/crewai_manager_optimized.py"),
        ("app/main_cosmosdb.py", "app/main.py")
    ]
    
    # Perform migrations
    for source, target in migrations:
        if not os.path.exists(source):
            print(f"❌ Source file not found: {source}")
            continue
        
        # Create backup
        create_backup(target)
        
        # Copy new version
        shutil.copy2(source, target)
        print(f"✅ Migrated {source} -> {target}")
    
    print("\n📝 Updating startup script...")
    
    # Create new startup script
    startup_content = """#!/bin/bash
echo "=== Azure App Service Startup Script (Cosmos DB Mode) ==="
echo "=== No SQLite/Chroma dependencies! ==="

# Install base requirements
pip install --no-cache-dir -r requirements.txt

# No need for pysqlite3-binary or SQLite patches!
echo "=== Using Cosmos DB for PostgreSQL with pgvector ==="

echo "=== Starting application with Gunicorn ==="
exec gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 2 --worker-class uvicorn.workers.UvicornWorker app.main:app
"""
    
    with open("startup_cosmosdb.sh", "w") as f:
        f.write(startup_content)
    os.chmod("startup_cosmosdb.sh", 0o755)
    print("✅ Created startup_cosmosdb.sh")
    
    # Copy as main startup.sh
    create_backup("startup.sh")
    shutil.copy2("startup_cosmosdb.sh", "startup.sh")
    os.chmod("startup.sh", 0o755)
    print("✅ Updated startup.sh")
    
    print("\n✨ Migration complete!")
    print("\n📋 Next steps:")
    print("1. Deploy to Azure: az webapp deploy --resource-group TheWell-App-East --name well-intake-api --src-path deploy.zip --type zip")
    print("2. Restart app: az webapp restart --resource-group TheWell-App-East --name well-intake-api")
    print("3. Test endpoint: curl -X GET 'https://well-intake-api.azurewebsites.net/test/kevin-sullivan' -H 'X-API-Key: your-secure-api-key-here'")
    
    return True

if __name__ == "__main__":
    try:
        if migrate_to_cosmosdb():
            print("\n✅ Migration successful!")
            sys.exit(0)
        else:
            print("\n❌ Migration failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        sys.exit(1)