#!/usr/bin/env python3
"""
Migration script to switch to ultra-optimized CrewAI manager
This will update the main.py and main_optimized.py to use the new ultra-optimized version
"""

import os
import shutil
from datetime import datetime

def migrate_to_ultra_optimized():
    """Migrate to ultra-optimized CrewAI manager"""
    
    print("=" * 60)
    print("MIGRATING TO ULTRA-OPTIMIZED CREWAI MANAGER")
    print("=" * 60)
    
    # Files to update
    files_to_update = [
        'app/main.py',
        'app/main_optimized.py'
    ]
    
    # Backup directory
    backup_dir = f"backups/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    success_count = 0
    
    for file_path in files_to_update:
        if not os.path.exists(file_path):
            print(f"⚠️  File not found: {file_path}")
            continue
        
        try:
            # Create backup
            backup_path = os.path.join(backup_dir, os.path.basename(file_path))
            shutil.copy2(file_path, backup_path)
            print(f"✅ Backed up: {file_path} -> {backup_path}")
            
            # Read file content
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Replace import statement
            original_import = "from app.crewai_manager_optimized import EmailProcessingCrew"
            new_import = "from app.crewai_manager_ultra_optimized import EmailProcessingCrew"
            
            if original_import in content:
                content = content.replace(original_import, new_import)
                
                # Write updated content
                with open(file_path, 'w') as f:
                    f.write(content)
                
                print(f"✅ Updated: {file_path}")
                success_count += 1
            else:
                print(f"ℹ️  No changes needed: {file_path}")
                
        except Exception as e:
            print(f"❌ Error updating {file_path}: {e}")
    
    print("\n" + "=" * 60)
    
    if success_count > 0:
        print(f"✅ MIGRATION COMPLETE! Updated {success_count} file(s)")
        print(f"📁 Backups saved to: {backup_dir}")
        print("\n🚀 PERFORMANCE IMPROVEMENTS:")
        print("  • Intelligent caching for repeated emails")
        print("  • Circuit breaker prevents API overload")
        print("  • Enhanced fallback extraction patterns")
        print("  • Aggressive timeouts (5-10 seconds)")
        print("  • Optimized prompts for faster responses")
        print("  • Parallel processing support")
        print("\n⚡ EXPECTED PERFORMANCE:")
        print("  • CrewAI extraction: 5-10 seconds")
        print("  • Fallback extraction: <1 second")
        print("  • Cached results: instant")
    else:
        print("ℹ️  No files were updated. System may already be using ultra-optimized version.")
    
    print("\n💡 To test the new system:")
    print("  python test_api.py")
    print("  python test_dependencies.py")
    
    print("\n⚠️  To rollback if needed:")
    print(f"  cp {backup_dir}/* app/")
    
    return success_count > 0


def verify_ultra_optimized():
    """Verify ultra-optimized module is working"""
    print("\n🔍 Verifying ultra-optimized module...")
    
    try:
        # Test import
        from app.crewai_manager_ultra_optimized import EmailProcessingCrew, OptimizedEmailExtractor
        
        # Test instantiation
        crew = EmailProcessingCrew(firecrawl_api_key="test_key")
        extractor = OptimizedEmailExtractor()
        
        # Test fallback extraction
        test_email = """
        Hi,
        
        I'd like to introduce you to John Smith, a Senior Financial Advisor 
        based in Fort Wayne, IN. He's currently with Wealth Management Inc.
        
        Best regards,
        Jane Doe
        """
        
        result = extractor.extract(test_email, "jane.doe@wealthmgmt.com")
        
        print("✅ Module verification successful!")
        print(f"  • Candidate: {result.candidate_name}")
        print(f"  • Title: {result.job_title}")
        print(f"  • Location: {result.location}")
        print(f"  • Company: {result.company_name}")
        print(f"  • Referrer: {result.referrer_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Module verification failed: {e}")
        return False


if __name__ == "__main__":
    # Verify module first
    if verify_ultra_optimized():
        # Perform migration
        if migrate_to_ultra_optimized():
            print("\n✅ All systems ready! Ultra-optimized CrewAI is now active.")
        else:
            print("\n⚠️  Migration skipped or incomplete.")
    else:
        print("\n❌ Cannot proceed with migration. Please check the ultra-optimized module.")