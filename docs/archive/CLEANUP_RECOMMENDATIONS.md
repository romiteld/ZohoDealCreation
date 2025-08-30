# File Cleanup Recommendations

## Security Concerns - Immediate Action Required

### 1. **test_container_deployment.py**
- **Issue**: Contains hardcoded API key on line 26
- **Action**: Update to use environment variables from `.env.local`
- **Fix**: Replace hardcoded key with `os.getenv('API_KEY')`

## Files to Keep (Still Useful)

### Core Deployment Files
- `deploy.sh` - Simple deployment script for quick deployments
- `deployment/deploy_with_security.sh` - Enterprise deployment with security/monitoring
- `deployment/container_apps_config.yaml` - Kubernetes configuration

### Utility Scripts
- `check_zoho_now.py` - Useful for debugging Zoho records
- `initialize_database.py` - Database setup script
- `update_manifest_version.py` - Manifest versioning utility
- `test_langgraph.py` - Core workflow testing

### Configuration Files
- `requirements.txt` - Python dependencies (updated with new packages)
- `Dockerfile` - Container configuration
- `.env.local.template` - Environment variable template (newly created)

### Documentation
- `README.md` - Main documentation
- `CLAUDE.md` - AI assistance guide
- `SECURITY_AND_MONITORING.md` - New security/monitoring guide (newly created)
- `DATABASE_ENHANCEMENTS.md` - Database documentation

## Files That Could Be Removed (Deprecated)

### Old Test Files
- `test_redis_cache.py` - If Redis caching is now handled by security_config.py
- `test_streaming.py` - If streaming is no longer used
- `test_database_enhancements.py` - If database tests are complete

### Log Files (Should be in .gitignore)
- `server.log`
- `server_minimal.log`

## Files to Review for Potential Removal

### OAuth Service Files
The `oauth_service/` directory contains multiple versions:
- `oauth_app.py` - Original OAuth implementation
- `oauth_app_with_proxy.py` - Proxy version
- `oauth_deploy.zip` - Deployment package
- `oauth_proxy_deploy.zip` - Proxy deployment package

**Recommendation**: Keep only the actively used version and document which one is in production.

## Recommended Actions

### 1. Update .gitignore
Add the following entries:
```
# Logs
*.log
server*.log

# Environment files
.env.local
.env.production

# Local encryption keys
.encryption_key

# Test outputs
test_results/
```

### 2. Security Updates Needed

#### Update test_container_deployment.py
```python
# Replace line 26
# OLD: self.api_key = "e49d2dbcfa4547f5bdc371c5c06aae2afd06914e16e680a7f31c5fc5384ba384"
# NEW:
import os
from dotenv import load_dotenv
load_dotenv('.env.local')
self.api_key = os.getenv('API_KEY')
```

### 3. File Organization
Consider creating subdirectories:
```
scripts/
  ├── deployment/
  ├── testing/
  └── utilities/
```

### 4. Documentation Updates
Update README.md to reference:
- New security features in `app/security_config.py`
- Monitoring capabilities in `app/monitoring.py`
- Enterprise deployment script `deployment/deploy_with_security.sh`

## Files Successfully Created/Updated

### New Files Created
1. ✅ `app/monitoring.py` - Application Insights integration and metrics
2. ✅ `app/security_config.py` - Key Vault, API keys, rate limiting
3. ✅ `deployment/container_apps_config.yaml` - Enterprise K8s configuration
4. ✅ `deployment/deploy_with_security.sh` - Zero-downtime deployment script
5. ✅ `.env.local.template` - Comprehensive environment template
6. ✅ `SECURITY_AND_MONITORING.md` - Complete documentation

### Files Updated
1. ✅ `requirements.txt` - Added security and monitoring dependencies

## Next Steps

1. **Immediate**: Fix hardcoded API key in `test_container_deployment.py`
2. **Short-term**: Remove deprecated test files after confirmation
3. **Medium-term**: Reorganize scripts into logical subdirectories
4. **Long-term**: Implement automated cleanup in CI/CD pipeline

## Validation Checklist

Before removing any files:
- [ ] Confirm file is not referenced in any import statements
- [ ] Check if file is mentioned in documentation
- [ ] Verify file is not used in deployment scripts
- [ ] Ensure functionality is covered elsewhere
- [ ] Create backup before deletion

## Summary

The new security and monitoring implementation is complete and production-ready. The main concern is the hardcoded API key in the test file, which should be addressed immediately. Other cleanup tasks are optional optimizations that can be done gradually.