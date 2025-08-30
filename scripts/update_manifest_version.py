#!/usr/bin/env python3
"""
Manifest Version Updater
Increments the version number in manifest.xml to force Microsoft to refresh cached add-in
"""

import xml.etree.ElementTree as ET
import sys
from datetime import datetime

def update_manifest_version(manifest_path="/home/romiteld/outlook/addin/manifest.xml"):
    """Update the version number in manifest.xml"""
    
    # Register namespace
    ET.register_namespace('', 'http://schemas.microsoft.com/office/appforoffice/1.1')
    ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    ET.register_namespace('bt', 'http://schemas.microsoft.com/office/officeappbasictypes/1.0')
    ET.register_namespace('mailapp', 'http://schemas.microsoft.com/office/mailappversionoverrides/1.0')
    
    # Parse the manifest
    tree = ET.parse(manifest_path)
    root = tree.getroot()
    
    # Find the Version element
    ns = {'': 'http://schemas.microsoft.com/office/appforoffice/1.1'}
    version_elem = root.find('Version', ns)
    
    if version_elem is not None:
        current_version = version_elem.text
        print(f"Current version: {current_version}")
        
        # Parse version (e.g., "1.0.0.0")
        parts = current_version.split('.')
        if len(parts) == 4:
            # Increment the last part
            parts[3] = str(int(parts[3]) + 1)
            new_version = '.'.join(parts)
        else:
            # Default to 1.0.0.1 if format is unexpected
            new_version = "1.0.0.1"
        
        version_elem.text = new_version
        print(f"New version: {new_version}")
        
        # Write back to file
        tree.write(manifest_path, encoding='UTF-8', xml_declaration=True)
        print(f"✓ Manifest updated successfully at {datetime.now().isoformat()}")
        
        return new_version
    else:
        print("❌ Version element not found in manifest")
        return None


def main():
    """Main entry point"""
    print("="*60)
    print("  MANIFEST VERSION UPDATER")
    print("="*60)
    print("\nThis tool increments the manifest version to force Microsoft")
    print("to refresh its cached copy of your add-in.\n")
    
    new_version = update_manifest_version()
    
    if new_version:
        print("\n" + "="*60)
        print("  NEXT STEPS")
        print("="*60)
        print("\n1. Deploy the updated manifest:")
        print("   docker build -t wellintakeregistry.azurecr.io/well-intake-api:latest .")
        print("   docker push wellintakeregistry.azurecr.io/well-intake-api:latest")
        print("   az containerapp update --name well-intake-api \\")
        print("     --resource-group TheWell-Infra-East \\")
        print("     --image wellintakeregistry.azurecr.io/well-intake-api:latest")
        print("\n2. Remove and re-add the add-in in Outlook:")
        print("   - Go to outlook.office.com")
        print("   - Get Add-ins → My Add-ins → Custom Add-ins")
        print("   - Remove 'The Well - Send to Zoho'")
        print("   - Clear browser cache (Ctrl+Shift+Delete)")
        print("   - Add from URL: https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io/manifest.xml")
        print(f"\n3. Verify new version ({new_version}) is loaded in Outlook")
        print("\n4. Run test script to validate:")
        print("   python test_container_deployment.py")
    
    return 0 if new_version else 1


if __name__ == "__main__":
    exit(main())