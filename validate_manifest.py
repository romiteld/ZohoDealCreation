#!/usr/bin/env python3
"""
Validate the Outlook Add-in manifest.xml file
"""

import xml.etree.ElementTree as ET
import sys
import os
from urllib.parse import urlparse

def validate_manifest(manifest_path):
    """Validate the manifest.xml file for common issues"""
    
    issues = []
    warnings = []
    
    if not os.path.exists(manifest_path):
        print(f"❌ Manifest file not found at {manifest_path}")
        return False
    
    try:
        # Parse the XML
        tree = ET.parse(manifest_path)
        root = tree.getroot()
        
        # Define namespace (the default namespace for Office App)
        ns = {'': 'http://schemas.microsoft.com/office/appforoffice/1.1',
              'bt': 'http://schemas.microsoft.com/office/officeappbasictypes/1.0',
              'mailapp': 'http://schemas.microsoft.com/office/mailappversionoverrides/1.0'}
        
        # Register the default namespace
        for prefix, uri in ns.items():
            ET.register_namespace(prefix, uri)
        
        # Validate ID format (should be a GUID)
        id_elem = root.find('.//{http://schemas.microsoft.com/office/appforoffice/1.1}Id')
        
        if id_elem is not None:
            id_value = id_elem.text
            if not id_value or len(id_value) != 36:
                issues.append("ID should be a valid GUID (36 characters)")
        else:
            issues.append("Missing Id element")
        
        # Check version format
        version_elem = root.find('.//{http://schemas.microsoft.com/office/appforoffice/1.1}Version')
        if version_elem is None:
            version_elem = root.find('.//Version')
        
        if version_elem is not None:
            version = version_elem.text
            if not version or not all(part.isdigit() for part in version.split('.')):
                issues.append(f"Invalid version format: {version}")
        else:
            issues.append("Missing Version element")
        
        # Validate URLs
        url_elements = [
            ('IconUrl', False),
            ('HighResolutionIconUrl', False),
            ('SupportUrl', False),
            ('SourceLocation', True),
            ('FunctionFile.Url', True)
        ]
        
        for elem_name, is_critical in url_elements:
            if 'FunctionFile' in elem_name:
                # Handle bt:Url elements
                urls = root.findall('.//{http://schemas.microsoft.com/office/officeappbasictypes/1.0}Url[@id="FunctionFile.Url"]')
                for url_elem in urls:
                    url_value = url_elem.get('DefaultValue')
                    if url_value:
                        if not validate_url(url_value):
                            msg = f"{elem_name} has invalid URL: {url_value}"
                            if is_critical:
                                issues.append(msg)
                            else:
                                warnings.append(msg)
                        elif 'localhost' in url_value or 'your-' in url_value:
                            issues.append(f"{elem_name} contains placeholder URL: {url_value}")
            else:
                # Handle regular elements with namespace
                namespace_uri = 'http://schemas.microsoft.com/office/appforoffice/1.1'
                elems = root.findall(f'.//{{{namespace_uri}}}{elem_name}')
                for elem in elems:
                    url_value = elem.get('DefaultValue') or elem.text
                    if url_value:
                        if not validate_url(url_value):
                            msg = f"{elem_name} has invalid URL: {url_value}"
                            if is_critical:
                                issues.append(msg)
                            else:
                                warnings.append(msg)
                        elif 'localhost' in url_value or 'your-' in url_value or '~remoteAppUrl' in url_value:
                            issues.append(f"{elem_name} contains placeholder URL: {url_value}")
        
        # Check for FunctionFile reference in Action
        actions = root.findall('.//{http://schemas.microsoft.com/office/appforoffice/1.1}Action')
        for action in actions:
            if action.get('{http://www.w3.org/2001/XMLSchema-instance}type') == 'ExecuteFunction':
                function_file = action.find('.//{http://schemas.microsoft.com/office/appforoffice/1.1}FunctionFile')
                if function_file is None:
                    warnings.append("ExecuteFunction action missing FunctionFile reference")
        
        # Check permissions
        permissions = root.find('.//{http://schemas.microsoft.com/office/appforoffice/1.1}Permissions')
        if permissions is not None:
            perm_value = permissions.text
            valid_perms = ['Restricted', 'ReadItem', 'ReadWriteItem', 'ReadWriteMailbox']
            if perm_value not in valid_perms:
                warnings.append(f"Unusual permission level: {perm_value}")
        
        # Check for production URLs
        all_text = ET.tostring(root, encoding='unicode')
        if 'well-intake-api.azurewebsites.net' not in all_text:
            warnings.append("Manifest does not reference production URL (well-intake-api.azurewebsites.net)")
        
        # Display results
        print("\n" + "="*60)
        print("MANIFEST VALIDATION RESULTS")
        print("="*60)
        
        if not issues and not warnings:
            print("✅ Manifest validation passed with no issues!")
        else:
            if issues:
                print(f"\n❌ Critical Issues ({len(issues)}):")
                for issue in issues:
                    print(f"  • {issue}")
            
            if warnings:
                print(f"\n⚠️  Warnings ({len(warnings)}):")
                for warning in warnings:
                    print(f"  • {warning}")
        
        print("\n" + "="*60)
        print("MANIFEST SUMMARY")
        print("="*60)
        
        # Extract key information
        display_name = root.find('.//{http://schemas.microsoft.com/office/appforoffice/1.1}DisplayName')
        if display_name is not None:
            print(f"Add-in Name: {display_name.get('DefaultValue', 'Unknown')}")
        
        provider = root.find('.//{http://schemas.microsoft.com/office/appforoffice/1.1}ProviderName')
        if provider is not None:
            print(f"Provider: {provider.text}")
        
        description = root.find('.//{http://schemas.microsoft.com/office/appforoffice/1.1}Description')
        if description is not None:
            print(f"Description: {description.get('DefaultValue', 'No description')}")
        
        print("\n" + "="*60)
        
        return len(issues) == 0
        
    except ET.ParseError as e:
        print(f"❌ XML Parse Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Validation Error: {e}")
        return False

def validate_url(url):
    """Check if a URL is valid"""
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except:
        return False

if __name__ == "__main__":
    manifest_path = os.path.join(os.path.dirname(__file__), 'addin', 'manifest.xml')
    
    if len(sys.argv) > 1:
        manifest_path = sys.argv[1]
    
    print(f"Validating manifest at: {manifest_path}")
    
    if validate_manifest(manifest_path):
        sys.exit(0)
    else:
        sys.exit(1)