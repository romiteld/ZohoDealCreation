# Security and Monitoring Implementation Guide

## Overview

This document describes the enterprise-grade security and monitoring enhancements implemented for the Well Intake API. These features ensure production-ready security, comprehensive observability, and cost optimization.

## Architecture Components

### 1. Security Configuration (`app/security_config.py`)

#### Key Features
- **Azure Key Vault Integration**: Centralized secret management with automatic rotation
- **API Key Management**: Secure generation, validation, and revocation of API keys
- **Rate Limiting**: Distributed rate limiting using Redis
- **Encryption**: Data encryption at rest and in transit
- **Security Headers**: Comprehensive security headers for all responses

#### Key Vault Setup
```bash
# Create Key Vault
az keyvault create \
  --name well-intake-kv \
  --resource-group TheWell-Infra-East \
  --location eastus

# Enable Managed Identity access
az keyvault set-policy \
  --name well-intake-kv \
  --object-id <managed-identity-object-id> \
  --secret-permissions get list set delete
```

#### API Key Management

##### Creating API Keys
```python
from app.security_config import create_api_key

# Create a new API key
api_key = await create_api_key({
    "owner": "daniel.romitelli@emailthewell.com",
    "permissions": ["read", "write"],
    "description": "Production API key for Outlook integration"
})
```

##### Validating API Keys
```python
from app.security_config import validate_api_key

# Validate an API key
result = await validate_api_key("wia_your-api-key")
if result["valid"]:
    metadata = result["metadata"]
    # Process request
```

#### Rate Limiting Configuration

The system implements tiered rate limiting:
- **Default**: 100 requests per 60 seconds
- **Burst**: Allows short bursts up to 150% of limit
- **Per-API-Key**: Individual limits can be configured

Example FastAPI integration:
```python
from app.security_config import verify_api_key, get_rate_limiter

app = FastAPI()
limiter = get_rate_limiter()

@app.post("/intake/email")
@limiter.limit("100/minute")
async def process_email(
    request: Request,
    api_key_data: dict = Depends(verify_api_key)
):
    # Process email
    pass
```

### 2. Monitoring Service (`app/monitoring.py`)

#### Application Insights Integration

##### Metrics Tracked
- **Email Processing**:
  - Total emails processed
  - Processing duration (P50, P95, P99)
  - Success/error rates
  
- **GPT-5-mini Performance**:
  - Request count
  - Token usage (input/output)
  - Latency metrics
  - Cost calculation

- **Zoho Integration**:
  - API call count
  - Error rates
  - Response times

- **System Metrics**:
  - Memory usage
  - CPU utilization
  - Active connections

##### Cost Monitoring

The system automatically tracks GPT-5-mini usage and calculates costs:

```python
from app.monitoring import record_gpt_usage

# Record GPT usage after each call
cost_info = record_gpt_usage(
    input_text=prompt,
    output_text=response,
    operation="email_extraction"
)
# cost_info contains token counts and USD costs
```

##### Custom Metrics

```python
from app.monitoring import monitoring

# Track custom metrics
monitoring.email_processing_counter.add(1, {"status": "success"})
monitoring.processing_duration.record(2.5)  # seconds
monitoring.duplicate_detection_counter.add(1, {"type": "account"})
```

#### Alert Definitions

Alerts are automatically configured for:

| Alert Name | Condition | Severity | Action |
|------------|-----------|----------|--------|
| High Error Rate | Error rate > 5% | Critical | Page on-call |
| High GPT Latency | P95 > 5 seconds | Warning | Notify team |
| Excessive GPT Cost | Daily > $100 | Warning | Notify finance |
| Zoho API Failures | Error rate > 10% | Critical | Page on-call |
| High Memory Usage | > 1GB | Warning | Scale or restart |

### 3. Container Apps Configuration (`deployment/container_apps_config.yaml`)

#### Zero-Downtime Deployment

The configuration implements:
- **Rolling Updates**: MaxSurge=1, MaxUnavailable=0
- **Health Checks**: Liveness, Readiness, and Startup probes
- **Canary Deployments**: Gradual traffic shifting
- **Auto-scaling**: Based on CPU, memory, and custom metrics

#### Scaling Rules

```yaml
metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        averageUtilization: 70
  - type: External
    external:
      metric:
        name: email_processing_duration_seconds
      target:
        averageValue: "5"  # Scale if avg > 5s
```

## Deployment Process

### Using the Enhanced Deployment Script

```bash
# Deploy with security and monitoring
./deployment/deploy_with_security.sh [image-tag]

# Example: Deploy specific version
./deployment/deploy_with_security.sh v2.0.0
```

The script handles:
1. Key Vault setup and secret migration
2. Application Insights configuration
3. Redis cache provisioning
4. Docker image building and pushing
5. Zero-downtime Container Apps deployment
6. Alert configuration
7. Health check validation

### Environment Variables

Required variables in `.env.local` (see `.env.local.template`):

```bash
# Key Vault
KEY_VAULT_URL=https://well-intake-kv.vault.azure.net/
USE_MANAGED_IDENTITY=true  # Production only

# Application Insights
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...
LOG_ANALYTICS_WORKSPACE_ID=...

# Redis Cache
REDIS_CONNECTION_STRING=...

# Security Settings
API_KEY_ROTATION_DAYS=30
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60
```

## Usage Examples

### 1. Monitoring Dashboard Queries

```python
from app.monitoring import query_performance_metrics, query_cost_metrics

# Get performance metrics for last 24 hours
perf_metrics = await query_performance_metrics(hours=24)

# Get cost metrics for last 7 days
cost_metrics = await query_cost_metrics(days=7)
```

### 2. Secret Rotation

```python
from app.security_config import rotate_secret

# Rotate API keys
success, new_key = await rotate_secret("openai-api-key")

# Rotate with custom generator
def generate_complex_password():
    return secrets.token_urlsafe(64)

success, new_password = await rotate_secret(
    "database-password",
    generator_func=generate_complex_password
)
```

### 3. Audit Logging

```python
from app.security_config import audit_log

# Log security events
await audit_log("api_key_created", {
    "owner": "user@example.com",
    "permissions": ["read", "write"],
    "ip_address": request.client.host
})
```

## Monitoring Endpoints

### Health Checks

```bash
# Basic health check
GET /health

# Detailed health with monitoring status
GET /health/detailed

# Readiness check
GET /health/ready

# Startup check
GET /health/startup
```

### Metrics Endpoints

```bash
# Performance metrics
GET /metrics/performance?hours=24

# Cost analysis
GET /metrics/costs?days=7

# System metrics
GET /metrics/system
```

## Security Best Practices

### 1. API Key Rotation

- Rotate API keys every 30 days (configurable)
- Automated rotation via Azure Functions (optional)
- Grace period for old keys during rotation

### 2. Rate Limiting Strategies

- **Per-IP**: Default 100 req/min
- **Per-API-Key**: Configurable limits
- **Burst Handling**: Short-term allowance for spikes
- **Distributed**: Redis-backed for multi-instance

### 3. Secret Management

- **Never hardcode secrets** in code
- Use Key Vault references in Container Apps
- Enable secret versioning and audit logs
- Implement least-privilege access

### 4. Monitoring Alerts

Configure alerts for:
- Unusual traffic patterns
- Failed authentication attempts
- High error rates
- Cost anomalies
- Performance degradation

## Cost Optimization

### GPT-5-mini Token Tracking

The system tracks token usage and costs:
- Input tokens: $0.15 per 1M tokens
- Output tokens: $0.60 per 1M tokens

### Cost Reduction Strategies

1. **Caching**: Redis caching for repeated patterns
2. **Batch Processing**: Group similar requests
3. **Prompt Optimization**: Minimize token usage
4. **Rate Limiting**: Prevent abuse and overuse

## Troubleshooting

### Common Issues

#### 1. Key Vault Access Denied
```bash
# Grant access to managed identity
az keyvault set-policy \
  --name well-intake-kv \
  --object-id <identity-id> \
  --secret-permissions get list
```

#### 2. Rate Limit Exceeded
Check headers in response:
- `X-RateLimit-Limit`: Total allowed
- `X-RateLimit-Remaining`: Requests left
- `X-RateLimit-Reset`: Reset timestamp

#### 3. High Memory Usage
```bash
# Check memory metrics
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --query "memory_usage_mb"
```

### Monitoring Commands

```bash
# View Application Insights logs
az monitor app-insights query \
  --app well-intake-insights \
  --analytics-query "traces | where timestamp > ago(1h)"

# Check alert status
az monitor metrics alert list \
  --resource-group TheWell-Infra-East

# View Redis cache metrics
az redis show \
  --name well-intake-redis \
  --resource-group TheWell-Infra-East \
  --query "sku"
```

## Maintenance Tasks

### Daily
- Review cost metrics
- Check error rates
- Monitor response times

### Weekly
- Review security audit logs
- Check for unused API keys
- Analyze traffic patterns

### Monthly
- Rotate API keys
- Review and update rate limits
- Cost optimization analysis
- Security assessment

## Integration with Existing Code

### Updating Main Application

```python
# app/main.py
from app.monitoring import track_email_processing, track_gpt_request
from app.security_config import verify_api_key, apply_security_headers

@app.post("/intake/email")
@track_email_processing
async def process_email(
    request: Request,
    email_data: EmailData,
    api_key_data: dict = Depends(verify_api_key)
):
    async with track_gpt_request("email_extraction"):
        # Process with GPT-5-mini
        result = await extract_information(email_data)
    
    return apply_security_headers(response)
```

### Updating LangGraph Manager

```python
# app/langgraph_manager.py
from app.monitoring import record_gpt_usage

async def extract_information(state):
    # Existing extraction logic
    response = await openai_client.chat.completions.create(...)
    
    # Record usage for cost tracking
    record_gpt_usage(
        input_text=prompt,
        output_text=response.choices[0].message.content,
        operation="langgraph_extraction"
    )
    
    return state
```

## Compliance and Regulations

### Data Protection
- Encryption at rest (Azure Storage, Key Vault)
- Encryption in transit (TLS 1.2+)
- PII handling compliance
- Audit trail for all operations

### Access Control
- Role-based access (RBAC)
- Managed identities for service-to-service
- API key scoping and permissions
- Regular access reviews

## Support and Escalation

### Monitoring Alerts
- **Critical**: Page on-call engineer
- **Warning**: Notify team via Teams/Slack
- **Info**: Log for review

### Escalation Path
1. On-call engineer (Critical alerts)
2. Team lead (Persistent issues)
3. Security team (Security incidents)
4. Finance team (Cost overruns)

## Future Enhancements

### Planned Features
1. **Advanced Threat Detection**: ML-based anomaly detection
2. **Cost Prediction**: Forecast monthly costs
3. **Auto-scaling Optimization**: ML-driven scaling decisions
4. **Compliance Reporting**: Automated compliance checks
5. **Performance Insights**: AI-powered optimization suggestions

### Integration Roadmap
- Sentinel integration for SIEM
- Cost Management APIs for budgeting
- Azure Policy for compliance
- GitHub Actions for CI/CD security scanning

## Conclusion

This security and monitoring implementation provides enterprise-grade protection and observability for the Well Intake API. Regular review and updates of these configurations ensure continued security and optimal performance.