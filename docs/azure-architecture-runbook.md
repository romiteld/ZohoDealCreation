# Well Intake – Azure Architecture & Ops Runbook

## Overview

This system processes Outlook emails into Zoho CRM using a FastAPI backend (Azure Container Apps) protected by a Flask OAuth reverse proxy (Azure App Service). Azure Front Door provides global edge. Data services include Blob Storage, Redis Cache, Service Bus, and optional Azure Cognitive Search. CI/CD builds Docker images to ACR and updates the Container App.

## Architecture Diagram (Logical)

```
┌──────────────────────────────────────────────────────────────────┐
│                         Client (Outlook Add-in)                   │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Azure Front Door (CDN)                         │
│                  well-intake-frontdoor profile                    │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│              Azure App Service (Flask Proxy)                      │
│                  well-zoho-oauth-v2                               │
│                                                                   │
│  Routes:                                                          │
│  • /health → Local health check                                   │
│  • /api/* → Backend /api/*                                        │
│  • /cdn/* → Backend /api/cdn/*                                    │
│  • /manifest.xml → Backend manifest                               │
│                                                                   │
│  Security:                                                        │
│  • Rate limiting (100 req/min)                                    │
│  • Circuit breaker pattern                                        │
│  • API key injection                                              │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│            Azure Container Apps (FastAPI Backend)                 │
│                  well-intake-api                                  │
│                                                                   │
│  • LangGraph workflow (Extract → Research → Validate)             │
│  • GPT-5-mini integration                                         │
│  • CDN management endpoints                                       │
└────────┬──────────┬──────────┬──────────┬──────────┬────────────┘
         │          │          │          │          │
    ┌────▼───┐ ┌───▼────┐ ┌──▼───┐ ┌────▼────┐ ┌──▼─────┐
    │ Blob   │ │ Redis  │ │Service│ │Cosmos DB│ │Cognitive│
    │Storage │ │ Cache  │ │ Bus   │ │PostgreSQL│ │ Search │
    └────────┘ └────────┘ └──────┘ └─────────┘ └────────┘
```

## Resource Inventory (TheWell-Infra-East)

- Container App: `well-intake-api`
  - FQDN: `well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io`
  - Scale: min 2, max 10
- App Service (Proxy): `well-zoho-oauth-v2`
  - Host: `well-zoho-oauth-v2.azurewebsites.net`
- Azure Front Door (Profile): `well-intake-frontdoor`
  - Endpoint: `well-intake-api-dnajdub4azhjcgc3.z03.azurefd.net`
  - Origin group: `well-intake-origins`
  - Origin host: `well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io`
- Container Registry: `wellintakeacr0903.azurecr.io`
- Storage Accounts: `wellattachments0903`, `wellcontent0903`, `wellintakefunc0903`, `wellintakestorage0903`, `wellintakewebui78196327`
- Redis: `wellintakecache0903.redis.cache.windows.net:6380` (Basic)
- Service Bus: `wellintakebus0903` (queue: `email-processing`)
- Cognitive Search: `wellintakesearch0903` (optional integration)
- Container Apps Env: `well-intake-env`
- App Insights: `wellintakeinsights0903`

## Endpoints

- Proxy root: `https://well-zoho-oauth-v2.azurewebsites.net/`
  - Health: `/health`
  - Manifest: `/manifest.xml`
  - API proxy: `/api/*` (forwards to Container App)
- Backend (Container App): `https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io`
  - Health: `/health`
  - Intake API: `/api/intake/email`
  - CDN mgmt: `/api/cdn/status`, `/api/cdn/purge`

Note: If `/api/cdn/*` returns 404 via proxy, see “Proxy Rewrite Fix”.

## Operations

### Deploy (Backend)

1) Build and push image

```
docker build -t wellintakeacr0903.azurecr.io/well-intake-api:<tag> .
az acr login --name wellintakeacr0903
docker push wellintakeacr0903.azurecr.io/well-intake-api:<tag>
```

2) Update Container App

```
az containerapp update \
  -g TheWell-Infra-East \
  -n well-intake-api \
  --image wellintakeacr0903.azurecr.io/well-intake-api:<tag>
```

### Deploy (Proxy)

Zip deploy (if needed for oauth service updates):

```
az webapp deployment source config-zip \
  -g TheWell-Infra-East \
  -n well-zoho-oauth-v2 \
  --src oauth_service/oauth_proxy_deploy.zip
```

### Rollback

- Container Apps: activate a previous revision or redeploy a previous image tag.

```
az containerapp revision list -g TheWell-Infra-East -n well-intake-api -o table
az containerapp revision activate -g TheWell-Infra-East -n well-intake-api --revision <name>
```

- App Service:

```
az webapp deployment rollback -g TheWell-Infra-East -n well-zoho-oauth-v2
```

### Logs & Health

- Proxy logs (stream 15s sample):

```
az webapp log tail -g TheWell-Infra-East -n well-zoho-oauth-v2
```

- Container App logs (last lines):

```
az containerapp logs show -g TheWell-Infra-East -n well-intake-api --tail 200
```

- Health checks:

```
curl -s https://well-zoho-oauth-v2.azurewebsites.net/health | jq
curl -s https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health | jq
```

### CDN (Front Door) Purge

- App-level purge (direct to backend):

```
curl -s https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/cdn/status | jq
curl -s -X POST \
  https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/cdn/purge \
  -H 'Content-Type: application/json' \
  -d '{"paths":["/manifest.xml"],"provider":"front_door"}' | jq
```

- Azure Front Door routing verification:

```
az afd endpoint show -g TheWell-Infra-East --profile-name well-intake-frontdoor -n well-intake-api -o jsonc
az afd origin-group list -g TheWell-Infra-East --profile-name well-intake-frontdoor -o table
az afd origin list -g TheWell-Infra-East --profile-name well-intake-frontdoor --origin-group-name well-intake-origins -o table
az afd route list -g TheWell-Infra-East --profile-name well-intake-frontdoor --endpoint-name well-intake-api -o table
```

## Known Issue – Proxy Rewrite Fix

`oauth_service/web.config` currently rewrites `^api/(.*)` to the backend as `/{R:1}` (dropping the `/api` prefix), and still targets an old Container Apps domain. This causes `/api/cdn/*` (and other nested routes) to 404 via proxy.

Suggested fix:

1) Update the backend host to the current FQDN:
   `well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io`

2) Preserve `/api` prefix in the rewrite action, e.g.:

```
<match url="^api/(.*)" />
<action type="Rewrite" 
  url="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/{R:1}{QUERY_STRING}"
  appendQueryString="false" />
```

This ensures `/api/cdn/status` via proxy maps to `/api/cdn/status` on the backend.

## Verification Checklist

- Proxy `/health` → HTTP 200, reports `proxy_status: healthy`
- Backend `/health` → HTTP 200, shows services operational
- Manifest accessible via proxy and Front Door
- CDN purge returns success (paths or version)
- Container App logs clean (no repeated errors)

## Quick Commands

```
az account show -o table
az resource list -g TheWell-Infra-East -o table | head -n 50
```

