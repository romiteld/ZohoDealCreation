# GitHub Webhook Setup for Automatic Cache Invalidation

This document explains how to set up GitHub webhooks to automatically invalidate Redis cache when manifest-related files change.

## Overview

The webhook handler automatically triggers Redis cache invalidation when changes are made to Outlook Add-in files, ensuring users always get the latest version without manual cache clearing.

## Features

- **Secure Signature Verification**: Uses HMAC-SHA256 to verify webhook authenticity
- **Intelligent File Detection**: Only processes changes to manifest-related files
- **Automatic Cache Invalidation**: Clears relevant Redis cache patterns
- **Comprehensive Logging**: Integrates with Application Insights for monitoring
- **Error Handling & Retry Logic**: Robust error handling with retry mechanisms
- **Statistics Tracking**: Monitors webhook processing metrics

## Monitored Files

The webhook monitors changes to these file patterns:

```
addin/manifest.xml
addin/*.html
addin/*.js
addin/*.css
addin/config.js
addin/commands.js
addin/commands.html
addin/taskpane.js
addin/taskpane.html
static/icons/*.png
```

## Cache Invalidation Patterns

When changes are detected, the following Redis cache patterns are invalidated:

| File Type | Cache Pattern | Description |
|-----------|---------------|-------------|
| Manifest | `well:manifest:*` | Manifest XML cache |
| JavaScript | `well:js:*` | JavaScript file cache |
| HTML | `well:html:*` | HTML file cache |
| Config | `well:config:*` | Configuration cache |
| Icons | `well:icons:*` | Icon file cache |
| Add-in Assets | `well:addin:*` | General add-in asset cache |

## Setup Instructions

### 1. Configure Environment Variables

Add these variables to your `.env.local` file:

```bash
# GitHub Webhook Configuration
GITHUB_WEBHOOK_SECRET=your-secure-webhook-secret-here
GITHUB_REPOSITORY=romiteld/outlook
```

Generate a secure webhook secret:
```bash
# Linux/Mac
openssl rand -hex 20

# Or use Python
python -c "import secrets; print(secrets.token_hex(20))"
```

### 2. Configure GitHub Webhook

1. Go to your GitHub repository settings
2. Navigate to **Settings** → **Webhooks** → **Add webhook**
3. Configure the webhook:

```
Payload URL: https://your-api-domain.azurecontainerapps.io/api/webhook/github
Content type: application/json
Secret: [your-webhook-secret-from-env]
Which events: Just the push event
Active: ✅ Checked
```

### 3. Test the Webhook

Test the webhook setup using the API endpoint:

```bash
# Test webhook functionality
curl -X POST "https://your-api-domain/api/webhook/github/test" \
  -H "X-API-Key: your-api-key"

# Check webhook status
curl -X GET "https://your-api-domain/api/webhook/github/status" \
  -H "X-API-Key: your-api-key"
```

## API Endpoints

### Webhook Endpoint
```
POST /api/webhook/github
```
- **Purpose**: Receives GitHub webhook events
- **Authentication**: GitHub signature verification
- **Payload**: GitHub push event JSON

### Status Endpoint
```
GET /api/webhook/github/status
```
- **Purpose**: Get webhook handler statistics
- **Authentication**: API key required
- **Returns**: Handler stats and configuration

### Test Endpoint
```
GET /api/webhook/github/test
```
- **Purpose**: Manually trigger cache invalidation test
- **Authentication**: API key required
- **Returns**: Simulated webhook processing results

## Monitoring & Logging

### Application Insights Integration

The webhook handler integrates with Azure Application Insights to provide:

- **Custom Traces**: Detailed webhook processing events
- **Performance Metrics**: Processing duration and success rates
- **Error Tracking**: Failed webhook attempts and reasons
- **Cache Metrics**: Number of cache entries invalidated

### Log Messages

Monitor these log messages in Application Insights:

```
INFO: Received GitHub webhook: push
INFO: Cache invalidation completed: X entries deleted
WARNING: GitHub webhook signature verification failed
ERROR: Webhook processing error: [error details]
```

## Security Features

### Signature Verification

- Uses HMAC-SHA256 with your webhook secret
- Timing-safe comparison prevents timing attacks
- Rejects requests with invalid signatures

### Rate Limiting

- Built-in protection against webhook spam
- Graceful handling of malformed requests
- Comprehensive error logging

### Input Validation

- Validates required GitHub headers
- Sanitizes webhook payload data
- Prevents processing of malicious payloads

## Troubleshooting

### Common Issues

1. **403 Signature Verification Failed**
   ```
   Solution: Verify GITHUB_WEBHOOK_SECRET matches GitHub configuration
   ```

2. **Cache Not Invalidating**
   ```
   Check: Redis connection status
   Verify: File changes match monitored patterns
   ```

3. **Webhook Not Triggering**
   ```
   Verify: GitHub webhook URL is correct
   Check: Webhook is active in GitHub settings
   ```

### Debug Mode

Enable debug logging to see detailed webhook processing:

```bash
# In .env.local
LOG_LEVEL=DEBUG
```

### Manual Cache Invalidation

If webhooks fail, manually clear cache:

```bash
curl -X POST "https://your-api-domain/cache/invalidate" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"pattern": "well:addin:*"}'
```

## Architecture

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   GitHub    │───▶│  Webhook Handler │───▶│  Redis Cache    │
│   Push      │    │                  │    │  Invalidation   │
│   Event     │    │  - Signature     │    │                 │
└─────────────┘    │    Verification  │    │  - Pattern      │
                   │  - File Analysis │    │    Matching     │
                   │  - Event Logging │    │  - Bulk Delete  │
                   └──────────────────┘    └─────────────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │ Application      │
                   │ Insights         │
                   │ Monitoring       │
                   └──────────────────┘
```

## Performance Impact

- **Processing Time**: ~50-200ms per webhook
- **Cache Operations**: Bulk operations minimize Redis load  
- **Memory Usage**: Minimal - processes events asynchronously
- **Network Impact**: Only invalidates when manifest files change

## Best Practices

1. **Monitor Webhook Health**: Check status endpoint regularly
2. **Review Logs**: Monitor Application Insights for errors
3. **Test After Deployment**: Use test endpoint after infrastructure changes
4. **Secure Secrets**: Rotate webhook secrets periodically
5. **Branch Strategy**: Only processes main/master branch changes

## Integration with CI/CD

The webhook automatically handles cache invalidation during deployments:

1. Developer pushes manifest changes to main branch
2. GitHub triggers webhook to Azure Container Apps
3. Webhook handler analyzes changed files
4. Cache patterns are automatically invalidated
5. Next user request gets fresh content

No manual intervention required! ✅

---

**Next Steps**: Test the webhook by making a small change to `addin/manifest.xml` and pushing to the main branch. Check the logs to verify automatic cache invalidation.