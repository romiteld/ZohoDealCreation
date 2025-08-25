# Azure Infrastructure Overview - The Well Recruiting Solutions

## Account Information

### Subscription Details
- **Subscription Name**: Azure subscription 1
- **Subscription ID**: `0837ddfd-9119-4378-af40-65c20eeeee0f`
- **State**: Enabled (Default)
- **Cloud Environment**: AzureCloud

### Tenant Information
- **Organization**: The Well Recruiting Solutions
- **Tenant ID**: `29ee1479-b5f7-48c5-b665-7de9a8a9033e`
- **Tenant Domain**: emailthewell.com
- **Administrator**: daniel.romitelli@emailthewell.com

## Resource Groups

| Name | Location | Status |
|------|----------|--------|
| TheWell-Infra-East | East US | Succeeded |
| TheWell-App-East | East US | Succeeded |
| NetworkWatcherRG | East US | Succeeded |

## Infrastructure Components

### 1. Web Application: Zoho OAuth Service

**Resource**: `well-zoho-oauth`

#### Configuration
- **Type**: Linux App Service
- **Location**: Canada Central
- **URL**: https://well-zoho-oauth.azurewebsites.net
- **App Service Plan**: `daniel.romitelli_asp_3999`
- **State**: Running

#### Purpose
OAuth integration service for Zoho CRM/Suite that:
- Manages OAuth authentication flow with Zoho APIs
- Handles token refresh and API authentication
- Provides secure integration between The Well's systems and Zoho

#### Environment Variables
- `ZOHO_CLIENT_ID`: 1000.L49UYM6D8YHCSFNUF18X5QR8T1MBSX
- `ZOHO_CLIENT_SECRET`: [Configured]
- `REDIRECT_URI`: https://well-zoho-oauth.azurewebsites.net/callback
- `SCM_DO_BUILD_DURING_DEPLOYMENT`: True
- `WEBSITE_HTTPLOGGING_RETENTION_DAYS`: 3

### 2. Storage: Email Attachments Repository

**Resource**: `wellintakeattachments`

#### Configuration
- **Type**: StorageV2 (General Purpose v2)
- **Location**: East US
- **Access Tier**: Hot
- **Security**: HTTPS Traffic Only
- **Public Blob Access**: Disabled
- **Minimum TLS Version**: TLS1_0
- **Created**: August 20, 2025

#### Storage Containers
| Container Name | Purpose | Created |
|----------------|---------|---------|
| email-attachments | Stores attachments from incoming emails | 2025-08-20 |

#### Purpose
Document and file storage system for email intake workflow:
- Stores email attachments from recruitment/intake processes
- Hot tier indicates frequent access patterns
- Integrated with email processing pipeline

### 3. Database: PostgreSQL Cluster

**Resource**: `well-intake-db`

#### Configuration
- **Type**: Azure Cosmos DB for PostgreSQL (Citus)
- **PostgreSQL Version**: 15
- **Citus Version**: 12.1
- **Location**: East US
- **State**: Ready

#### Server Details
- **Server Name**: well-intake-db-c
- **Role**: Coordinator
- **Edition**: GeneralPurpose
- **vCores**: 2
- **Storage**: 128 GB
- **Public IP Access**: Enabled
- **High Availability**: Disabled
- **Administrator Login**: citus
- **FQDN**: c-well-intake-db.kaj3v6jxajtw66.postgres.cosmos.azure.com

#### Purpose
Backend database for intake and lead management:
- Stores intake forms and lead information
- Manages recruitment pipeline data
- Processes data from email/web submissions
- Supports distributed PostgreSQL workloads via Citus

### 4. Monitoring: Log Analytics

**Resource**: `workspace-heellnfraastTQf8`

#### Configuration
- **Type**: Log Analytics Workspace
- **Location**: East US
- **SKU**: PerGB2018 (Pay-per-GB)
- **Retention Period**: 30 days
- **Daily Quota**: Unlimited (-1.0 GB)
- **Last Updated**: August 20, 2025

#### Purpose
Centralized monitoring and logging:
- Collects logs from all Azure resources
- Provides troubleshooting capabilities
- Enables performance analytics
- Stores diagnostic data for 30-day retention

### 5. Networking Infrastructure

#### Virtual Network
- **Resource**: `vnet-1`
- **Location**: East US
- **Purpose**: Private network isolation for resources

#### Network Security Group
- **Resource**: `nsg-1`
- **Location**: East US
- **Purpose**: Network access control and security rules

#### Network Watcher
- **Resource**: `NetworkWatcher_eastus`
- **Location**: East US
- **Purpose**: Network monitoring and diagnostics

## System Architecture Summary

The infrastructure represents an **Email/Lead Intake System** for The Well Recruiting Solutions with the following workflow:

### Data Flow
1. **Email Reception**: Emails with attachments arrive at the system
2. **Attachment Storage**: Files are stored in Azure Blob Storage (`email-attachments` container)
3. **Data Processing**: Intake information is processed and stored in PostgreSQL database
4. **CRM Integration**: Data syncs with Zoho CRM via OAuth integration
5. **Monitoring**: All operations are logged to Log Analytics for tracking and troubleshooting

### Key Features
- **Scalable Storage**: Hot-tier blob storage for quick access to attachments
- **Distributed Database**: Citus-enabled PostgreSQL for scalable data operations
- **Secure Integration**: OAuth-based Zoho CRM integration
- **Comprehensive Monitoring**: 30-day log retention with analytics capabilities
- **Network Security**: VNet isolation with NSG rules

### Security Considerations
- HTTPS-only traffic for storage account
- OAuth authentication for Zoho integration
- Network security groups for access control
- Public IP access enabled on database (consider restricting)
- TLS 1.0 minimum on storage (consider upgrading to TLS 1.2)

## Recommendations

1. **Security Enhancements**
   - Upgrade minimum TLS version to 1.2 for storage account
   - Consider restricting database public IP access
   - Implement Private Endpoints for enhanced security

2. **Monitoring Improvements**
   - Configure diagnostic settings for web app
   - Set up alerts for critical metrics
   - Enable Application Insights for detailed telemetry

3. **Backup Strategy**
   - Implement automated backups for PostgreSQL
   - Configure geo-redundant storage for critical data
   - Document disaster recovery procedures

4. **Cost Optimization**
   - Review storage access patterns for potential tier optimization
   - Consider reserved capacity for predictable workloads
   - Monitor Log Analytics data ingestion costs

## Last Updated
Generated on: 2025-08-22