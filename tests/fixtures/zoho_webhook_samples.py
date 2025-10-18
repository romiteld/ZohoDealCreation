"""
Real Zoho CRM Webhook Payload Fixtures

Based on Zoho's actual webhook format documented at:
https://www.zoho.com/crm/developer/docs/api/v2/notifications/webhooks.html

Webhook Structure:
{
    "data": [{ <record fields> }],
    "operation": "Leads.edit",
    "user": { "id": "...", "name": "...", "email": "..." },
    "source": "web",
    "timestamp": 1697545800000
}
"""

from datetime import datetime

# =============================================================================
# LEAD WEBHOOKS
# =============================================================================

LEAD_CREATE_WEBHOOK = {
    "data": [{
        "id": "6221978000123456789",
        "Full_Name": "John Anderson",
        "Company": "Anderson Financial Group",
        "Email": "john.anderson@afg.com",
        "Phone": "(555) 123-4567",
        "Mobile": "+1-555-987-6543",
        "Lead_Source": "Email Campaign",
        "Lead_Status": "New",
        "Industry": "Financial Services",
        "State": "California",
        "City": "San Francisco",
        "Created_Time": "2025-10-17T10:30:00-07:00",
        "Modified_Time": "2025-10-17T10:30:00-07:00",
        "Owner": {
            "id": "6221978000001234567",
            "name": "Steve Perry",
            "email": "steve.perry@emailthewell.com"
        }
    }],
    "operation": "Leads.create",
    "user": {
        "id": "6221978000001234567",
        "name": "Steve Perry",
        "email": "steve.perry@emailthewell.com"
    },
    "source": "web",
    "timestamp": 1697545800000
}

LEAD_UPDATE_WEBHOOK = {
    "data": [{
        "id": "6221978000123456789",
        "Full_Name": "John Anderson",
        "Company": "Anderson Wealth Advisors",  # Changed
        "Email": "john.anderson@afg.com",
        "Phone": "+15551234567",  # Normalized format
        "Mobile": "+15559876543",
        "Lead_Source": "Email Campaign",
        "Lead_Status": "Contacted",  # Changed
        "Industry": "Financial Services",
        "State": "California",
        "City": "San Francisco",
        "Created_Time": "2025-10-17T10:30:00-07:00",
        "Modified_Time": "2025-10-17T14:30:00-07:00",  # Later timestamp
        "Owner": {
            "id": "6221978000001234567",
            "name": "Steve Perry",
            "email": "steve.perry@emailthewell.com"
        }
    }],
    "operation": "Leads.edit",
    "user": {
        "id": "6221978000001234567",
        "name": "Steve Perry",
        "email": "steve.perry@emailthewell.com"
    },
    "source": "api",
    "timestamp": 1697545800000
}

LEAD_DELETE_WEBHOOK = {
    "data": [{
        "id": "6221978000123456789",
        "Modified_Time": "2025-10-17T15:00:00-07:00"
    }],
    "operation": "Leads.delete",
    "user": {
        "id": "6221978000001234567",
        "name": "Steve Perry",
        "email": "steve.perry@emailthewell.com"
    },
    "source": "web",
    "timestamp": 1697549400000
}

# =============================================================================
# DEAL WEBHOOKS
# =============================================================================

DEAL_CREATE_WEBHOOK = {
    "data": [{
        "id": "6221978000987654321",
        "Deal_Name": "Anderson Financial - Wealth Management",
        "Stage": "Qualification",
        "Amount": 150000.00,
        "Closing_Date": "2025-11-15",
        "Probability": 25,
        "Pipeline": "Sales Pipeline",
        "Account_Name": {
            "id": "6221978000111222333",
            "name": "Anderson Financial Group"
        },
        "Contact_Name": {
            "id": "6221978000444555666",
            "name": "John Anderson"
        },
        "Lead_Source": "Email Campaign",
        "Source": "Email",
        "Source_Detail": "steve.perry@emailthewell.com",
        "Created_Time": "2025-10-17T11:00:00-07:00",
        "Modified_Time": "2025-10-17T11:00:00-07:00",
        "Owner": {
            "id": "6221978000001234567",
            "name": "Steve Perry",
            "email": "steve.perry@emailthewell.com"
        }
    }],
    "operation": "Deals.create",
    "user": {
        "id": "6221978000001234567",
        "name": "Steve Perry",
        "email": "steve.perry@emailthewell.com"
    },
    "source": "workflow",
    "timestamp": 1697547600000
}

DEAL_UPDATE_STAGE_WEBHOOK = {
    "data": [{
        "id": "6221978000987654321",
        "Deal_Name": "Anderson Financial - Wealth Management",
        "Stage": "Proposal/Price Quote",  # Changed from Qualification
        "Amount": 175000.00,  # Increased
        "Closing_Date": "2025-11-10",  # Moved up
        "Probability": 50,  # Increased
        "Pipeline": "Sales Pipeline",
        "Account_Name": {
            "id": "6221978000111222333",
            "name": "Anderson Financial Group"
        },
        "Contact_Name": {
            "id": "6221978000444555666",
            "name": "John Anderson"
        },
        "Lead_Source": "Email Campaign",
        "Source": "Email",
        "Source_Detail": "steve.perry@emailthewell.com",
        "Created_Time": "2025-10-17T11:00:00-07:00",
        "Modified_Time": "2025-10-18T09:30:00-07:00",  # Next day
        "Owner": {
            "id": "6221978000001234567",
            "name": "Steve Perry",
            "email": "steve.perry@emailthewell.com"
        }
    }],
    "operation": "Deals.edit",
    "user": {
        "id": "6221978000001234567",
        "name": "Steve Perry",
        "email": "steve.perry@emailthewell.com"
    },
    "source": "web",
    "timestamp": 1697629800000
}

# =============================================================================
# CONTACT WEBHOOKS
# =============================================================================

CONTACT_CREATE_WEBHOOK = {
    "data": [{
        "id": "6221978000444555666",
        "First_Name": "John",
        "Last_Name": "Anderson",
        "Full_Name": "John Anderson",
        "Email": "john.anderson@afg.com",
        "Phone": "+15551234567",
        "Mobile": "+15559876543",
        "Title": "Managing Partner",
        "Department": "Wealth Management",
        "Account_Name": {
            "id": "6221978000111222333",
            "name": "Anderson Financial Group"
        },
        "Mailing_City": "San Francisco",
        "Mailing_State": "California",
        "Mailing_Zip": "94102",
        "Created_Time": "2025-10-17T10:45:00-07:00",
        "Modified_Time": "2025-10-17T10:45:00-07:00",
        "Owner": {
            "id": "6221978000001234567",
            "name": "Steve Perry",
            "email": "steve.perry@emailthewell.com"
        }
    }],
    "operation": "Contacts.create",
    "user": {
        "id": "6221978000001234567",
        "name": "Steve Perry",
        "email": "steve.perry@emailthewell.com"
    },
    "source": "api",
    "timestamp": 1697546700000
}

# =============================================================================
# ACCOUNT WEBHOOKS
# =============================================================================

ACCOUNT_CREATE_WEBHOOK = {
    "data": [{
        "id": "6221978000111222333",
        "Account_Name": "Anderson Financial Group",
        "Website": "https://andersonfinancial.com",
        "Phone": "+15551234567",
        "Industry": "Financial Services",
        "Type": "Prospect",
        "Billing_City": "San Francisco",
        "Billing_State": "California",
        "Billing_Country": "United States",
        "Billing_Code": "94102",
        "Annual_Revenue": 5000000.00,
        "Employees": 25,
        "Created_Time": "2025-10-17T10:40:00-07:00",
        "Modified_Time": "2025-10-17T10:40:00-07:00",
        "Owner": {
            "id": "6221978000001234567",
            "name": "Steve Perry",
            "email": "steve.perry@emailthewell.com"
        }
    }],
    "operation": "Accounts.create",
    "user": {
        "id": "6221978000001234567",
        "name": "Steve Perry",
        "email": "steve.perry@emailthewell.com"
    },
    "source": "web",
    "timestamp": 1697546400000
}

# =============================================================================
# EDGE CASES
# =============================================================================

# Webhook with multiselectpicklist field
LEAD_WITH_PICKLIST_WEBHOOK = {
    "data": [{
        "id": "6221978000777888999",
        "Full_Name": "Sarah Martinez",
        "Company": "Martinez & Associates",
        "Email": "sarah@martinez.com",
        "Licenses_and_Exams": '["Series 7", "Series 66", "CFP"]',  # JSON string
        "Professional_Designations": "CFP, CFA, CIMA",  # Comma-separated
        "Lead_Source": "Referral",
        "Lead_Status": "New",
        "Created_Time": "2025-10-17T12:00:00-07:00",
        "Modified_Time": "2025-10-17T12:00:00-07:00",
        "Owner": {
            "id": "6221978000001234567",
            "name": "Steve Perry",
            "email": "steve.perry@emailthewell.com"
        }
    }],
    "operation": "Leads.create",
    "user": {
        "id": "6221978000001234567",
        "name": "Steve Perry",
        "email": "steve.perry@emailthewell.com"
    },
    "source": "web",
    "timestamp": 1697551200000
}

# Stale update (conflict scenario)
LEAD_STALE_UPDATE_WEBHOOK = {
    "data": [{
        "id": "6221978000123456789",
        "Full_Name": "John Anderson (Old Update)",
        "Company": "Anderson Financial Group",
        "Email": "john.anderson@afg.com",
        "Lead_Status": "New",  # Outdated status
        "Created_Time": "2025-10-17T10:30:00-07:00",
        "Modified_Time": "2025-10-17T12:00:00-07:00",  # Earlier than UPDATE_WEBHOOK
        "Owner": {
            "id": "6221978000001234567",
            "name": "Steve Perry",
            "email": "steve.perry@emailthewell.com"
        }
    }],
    "operation": "Leads.edit",
    "user": {
        "id": "6221978000009999999",
        "name": "System User",
        "email": "system@zoho.com"
    },
    "source": "api",
    "timestamp": 1697549400000
}

# Missing owner (should use default)
LEAD_NO_OWNER_WEBHOOK = {
    "data": [{
        "id": "6221978000555666777",
        "Full_Name": "Test Lead Without Owner",
        "Company": "Test Company",
        "Email": "test@example.com",
        "Lead_Source": "Web Form",
        "Lead_Status": "New",
        "Created_Time": "2025-10-17T13:00:00-07:00",
        "Modified_Time": "2025-10-17T13:00:00-07:00"
        # No Owner field
    }],
    "operation": "Leads.create",
    "user": {
        "id": "6221978000001234567",
        "name": "Steve Perry",
        "email": "steve.perry@emailthewell.com"
    },
    "source": "web",
    "timestamp": 1697554800000
}
