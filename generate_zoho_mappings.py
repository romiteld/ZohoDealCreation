#!/usr/bin/env python3
"""
Generate comprehensive Zoho CRM field mappings.

Queries Zoho CRM API to fetch:
- All modules
- All fields for each module
- All custom views
- All picklist values

Creates canonical zoho_field_mappings.json as single source of truth.
"""
import requests
import json
from typing import Dict, List, Any
from datetime import datetime

# Get OAuth token
print("🔐 Getting OAuth token...")
response = requests.get("https://well-zoho-oauth-v2.azurewebsites.net/oauth/token")
if response.status_code != 200:
    print(f"❌ Failed to get token: {response.status_code}")
    print(response.text)
    exit(1)

token_data = response.json()
access_token = token_data['access_token']
api_domain = token_data.get('api_domain', 'https://www.zohoapis.com')

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

print(f"✅ Got token (cached: {token_data.get('cached', False)})")
print(f"📡 API Domain: {api_domain}")

# Comprehensive mapping structure
mappings = {
    "meta": {
        "description": "Canonical Zoho CRM field mappings for The Well Intake API",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "zoho_api_version": "v8",
        "api_domain": api_domain,
        "oauth_service": "https://well-zoho-oauth-v2.azurewebsites.net",
        "notes": "Auto-generated from Zoho CRM API - Single source of truth"
    },
    "modules": {},
    "field_mappings": {},
    "custom_views": {},
    "picklist_values": {}
}

# Step 1: Get all modules
print("\n📋 Fetching all modules...")
modules_url = f"{api_domain}/crm/v8/settings/modules"
response = requests.get(modules_url, headers=headers)

if response.status_code != 200:
    print(f"❌ Failed to get modules: {response.status_code}")
    print(response.text[:500])
    exit(1)

modules_data = response.json()
all_modules = modules_data.get('modules', [])
print(f"✅ Found {len(all_modules)} modules")

# Filter to API-accessible modules
api_modules = [m for m in all_modules if m.get('api_supported', False)]
print(f"📊 {len(api_modules)} modules are API-accessible")

# Step 2: For each module, get detailed field information
for module in api_modules:
    module_name = module.get('api_name')
    module_label = module.get('plural_label', module.get('singular_label', module_name))

    print(f"\n🔍 Processing module: {module_name} ({module_label})...")

    # Store module metadata
    mappings["modules"][module_name] = {
        "module_api_name": module_name,
        "singular_label": module.get('singular_label', ''),
        "plural_label": module.get('plural_label', ''),
        "api_endpoint": f"/crm/v8/{module_name}",
        "api_supported": module.get('api_supported', False),
        "creatable": module.get('creatable', False),
        "editable": module.get('editable', False),
        "deletable": module.get('deletable', False),
        "viewable": module.get('viewable', False),
        "quick_create": module.get('quick_create', False),
        "custom_module": module.get('custom_module', False),
        "id": module.get('id', ''),
        "fields": {}
    }

    # Get fields for this module
    fields_url = f"{api_domain}/crm/v8/settings/fields?module={module_name}"
    try:
        fields_response = requests.get(fields_url, headers=headers)

        if fields_response.status_code == 200:
            fields_data = fields_response.json()
            fields = fields_data.get('fields', [])

            print(f"  ✅ Found {len(fields)} fields")

            # Store field mappings
            for field in fields:
                field_api_name = field.get('api_name')

                field_mapping = {
                    "api_name": field_api_name,
                    "field_label": field.get('field_label', ''),
                    "data_type": field.get('data_type', ''),
                    "display_type": field.get('display_type', ''),
                    "length": field.get('length'),
                    "required": field.get('required', False),
                    "read_only": field.get('read_only', False),
                    "visible": field.get('visible', True),
                    "custom_field": field.get('custom_field', False),
                    "default_value": field.get('default_value'),
                    "field_read_only": field.get('field_read_only', False),
                    "businesscard_supported": field.get('businesscard_supported', False)
                }

                # Add picklist values if applicable
                if field.get('data_type') in ['picklist', 'multiselectpicklist']:
                    pick_list_values = field.get('pick_list_values', [])
                    field_mapping['picklist_values'] = [
                        {
                            "display_value": pv.get('display_value', ''),
                            "actual_value": pv.get('actual_value', ''),
                            "sequence_number": pv.get('sequence_number')
                        }
                        for pv in pick_list_values
                    ]

                # Add lookup details if applicable
                if field.get('data_type') == 'lookup':
                    lookup_module = field.get('lookup', {})
                    field_mapping['lookup_module'] = {
                        "module": lookup_module.get('module', {}).get('api_name', ''),
                        "id": lookup_module.get('id', '')
                    }

                # Add subform details if applicable
                if field.get('data_type') == 'subform':
                    subform_module = field.get('subform', {})
                    field_mapping['subform_module'] = subform_module.get('module', '')

                # Add formula details if applicable
                if field.get('data_type') == 'formula':
                    field_mapping['formula_return_type'] = field.get('formula', {}).get('return_type', '')

                mappings["modules"][module_name]["fields"][field_api_name] = field_mapping

        else:
            print(f"  ⚠️  Could not fetch fields: {fields_response.status_code}")

    except Exception as e:
        print(f"  ⚠️  Error fetching fields: {e}")

# Step 3: Get custom views for important modules
important_modules = ['Leads', 'Contacts', 'Deals', 'Accounts', 'Tasks', 'Calls', 'Meetings']
print("\n🔭 Fetching custom views for key modules...")

for module_name in important_modules:
    if module_name not in mappings["modules"]:
        continue

    print(f"  📌 {module_name} views...")
    views_url = f"{api_domain}/crm/v8/settings/custom_views?module={module_name}"

    try:
        views_response = requests.get(views_url, headers=headers)

        if views_response.status_code == 200:
            views_data = views_response.json()
            custom_views = views_data.get('custom_views', [])

            if module_name not in mappings["custom_views"]:
                mappings["custom_views"][module_name] = []

            for view in custom_views:
                mappings["custom_views"][module_name].append({
                    "id": view.get('id', ''),
                    "name": view.get('name', ''),
                    "display_value": view.get('display_value', ''),
                    "system_name": view.get('system_name', ''),
                    "system_defined": view.get('system_defined', False),
                    "default": view.get('default', False),
                    "favorite": view.get('favorite', False)
                })

            print(f"    ✅ Found {len(custom_views)} custom views")

    except Exception as e:
        print(f"    ⚠️  Error fetching custom views: {e}")

# Step 4: Create field_mappings organized by common use cases
print("\n📦 Creating organized field mappings for common use cases...")

# Vault Candidates (from Leads module with custom view)
if "Leads" in mappings["modules"]:
    vault_fields = {}
    leads_fields = mappings["modules"]["Leads"]["fields"]

    # Important vault candidate fields
    vault_field_names = [
        "Candidate_Locator", "Full_Name", "First_Name", "Last_Name",
        "Current_Location", "Date_Published_to_Vault", "Publish_to_Vault",
        "Pipeline_Stage", "Interview_Recording_Link", "Full_Interview_URL",
        "Designation", "Mobility_Details", "Is_Mobile", "Owner",
        "Created_Time", "Modified_Time", "Candidate_Type"
    ]

    for field_name in vault_field_names:
        if field_name in leads_fields:
            vault_fields[field_name] = leads_fields[field_name]

    mappings["field_mappings"]["vault_candidate_fields"] = vault_fields
    print(f"  ✅ Vault candidate fields: {len(vault_fields)}")

# Email Processing Fields (from Leads)
if "Leads" in mappings["modules"]:
    email_fields = {}
    leads_fields = mappings["modules"]["Leads"]["fields"]

    email_field_names = [
        "Full_Name", "First_Name", "Last_Name", "Email", "Phone",
        "Company", "Title", "Lead_Source", "Source", "Source_Detail",
        "Lead_Status", "Description", "Owner", "Created_Time"
    ]

    for field_name in email_field_names:
        if field_name in leads_fields:
            email_fields[field_name] = leads_fields[field_name]

    mappings["field_mappings"]["email_processing_fields"] = email_fields
    print(f"  ✅ Email processing fields: {len(email_fields)}")

# Write to file
print("\n💾 Writing mappings to zoho_field_mappings.json...")
output_file = "/home/romiteld/Development/Desktop_Apps/outlook/zoho_field_mappings.json"

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(mappings, f, indent=2, ensure_ascii=False)

print(f"✅ Successfully wrote {output_file}")

# Print summary
print("\n" + "="*60)
print("📊 SUMMARY")
print("="*60)
print(f"Total modules: {len(mappings['modules'])}")
print(f"Total fields across all modules: {sum(len(m['fields']) for m in mappings['modules'].values())}")
print(f"Modules with custom views: {len(mappings['custom_views'])}")
print(f"Custom field mapping groups: {len(mappings['field_mappings'])}")
print("\n✅ Complete! zoho_field_mappings.json is your canonical source of truth.")
