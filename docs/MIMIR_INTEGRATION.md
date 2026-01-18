# Mimir Integration Guide

Complete guide to using Smart Autoscaler with Grafana Mimir for multi-tenant monitoring.

## Overview

[Grafana Mimir](https://grafana.com/oss/mimir/) is a horizontally scalable, highly available, multi-tenant TSDB for Prometheus. Smart Autoscaler supports Mimir with full multi-tenancy capabilities.

## Features

- ✅ **Multi-Tenant Support** - Isolate metrics by tenant
- ✅ **Authentication** - Basic Auth, Bearer Token, Custom Headers
- ✅ **Prometheus Compatibility** - Uses standard Prometheus API
- ✅ **Fallback Support** - Works with regular Prometheus too
- ✅ **Auto-Detection** - Automatically detects Mimir vs Prometheus

## Quick Start

### 1. Basic Mimir Setup

```yaml
# helm-values-mimir.yaml
config:
  prometheusUrl: "http://mimir-query-frontend.mimir:8080/prometheus"
  mimirTenantId: "tenant-1"
```

```bash
helm install smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system --create-namespace \
  -f helm-values-mimir.yaml
```

### 2. With Authentication

```yaml
config:
  prometheusUrl: "http://mimir-query-frontend.mimir:8080/prometheus"
  mimirTenantId: "tenant-1"
  prometheusUsername: "admin"
  prometheusPassword: "secret"
```

### 3. With Bearer Token

```yaml
config:
  prometheusUrl: "http://mimir-query-frontend.mimir:8080/prometheus"
  mimirTenantId: "tenant-1"
  prometheusBearerToken: "your-token-here"
```

---

## Configuration Options

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `PROMETHEUS_URL` | Mimir query frontend URL | `http://mimir-query-frontend.mimir:8080/prometheus` |
| `MIMIR_TENANT_ID` | Tenant ID for multi-tenancy | `tenant-1` |
| `PROMETHEUS_USERNAME` | Basic auth username | `admin` |
| `PROMETHEUS_PASSWORD` | Basic auth password | `secret` |
| `PROMETHEUS_BEARER_TOKEN` | Bearer token | `your-token-here` |
| `PROMETHEUS_CUSTOM_HEADERS` | Custom headers (JSON) | `{"X-Custom": "value"}` |

### Helm Values

```yaml
config:
  # Mimir URL (required)
  prometheusUrl: "http://mimir-query-frontend.mimir:8080/prometheus"
  
  # Multi-tenancy (optional)
  mimirTenantId: "tenant-1"
  
  # Authentication (optional)
  prometheusUsername: "admin"
  prometheusPassword: "secret"
  prometheusBearerToken: "your-token-here"
```

---

## Multi-Tenancy

### Tenant Isolation

Each tenant gets isolated metrics:

```yaml
# Tenant 1
config:
  mimirTenantId: "production"
  
# Tenant 2  
config:
  mimirTenantId: "staging"
```

### Per-Tenant Deployments

Deploy separate autoscaler instances per tenant:

```bash
# Production tenant
helm install smart-autoscaler-prod ./helm/smart-autoscaler \
  --namespace autoscaler-prod --create-namespace \
  --set config.mimirTenantId=production

# Staging tenant
helm install smart-autoscaler-staging ./helm/smart-autoscaler \
  --namespace autoscaler-staging --create-namespace \
  --set config.mimirTenantId=staging
```

---

## Authentication Methods

### 1. Basic Authentication

```yaml
config:
  prometheusUsername: "admin"
  prometheusPassword: "secret"
```

### 2. Bearer Token

```yaml
config:
  prometheusBearerToken: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 3. Custom Headers

```bash
# Environment variable
PROMETHEUS_CUSTOM_HEADERS='{"X-API-Key": "secret", "X-Tenant": "prod"}'
```

### 4. Using Kubernetes Secrets

```yaml
# Create secret
apiVersion: v1
kind: Secret
metadata:
  name: mimir-auth
type: Opaque
stringData:
  username: admin
  password: secret
  token: your-token-here
```

```yaml
# Reference in deployment
env:
  - name: PROMETHEUS_USERNAME
    valueFrom:
      secretKeyRef:
        name: mimir-auth
        key: username
  - name: PROMETHEUS_PASSWORD
    valueFrom:
      secretKeyRef:
        name: mimir-auth
        key: password
```

---

## Common Mimir URLs

| Setup | URL Pattern |
|-------|-------------|
| **Mimir Helm Chart** | `http://mimir-query-frontend.mimir:8080/prometheus` |
| **Mimir Operator** | `http://mimir-query-frontend.mimir-system:8080/prometheus` |
| **Grafana Cloud** | `https://prometheus-prod-XX-prod-XX.grafana.net/api/prom` |
| **Self-Hosted** | `https://mimir.company.com/prometheus` |

---

## Troubleshooting

### Connection Issues

**Error: "Failed to connect to Prometheus"**

1. Check Mimir URL:
   ```bash
   kubectl get svc -n mimir
   # Look for query-frontend service
   ```

2. Test connectivity:
   ```bash
   kubectl run test --rm -it --image=curlimages/curl -- \
     curl http://mimir-query-frontend.mimir:8080/prometheus/api/v1/query?query=up
   ```

### Authentication Issues

**Error: "401 Unauthorized"**

1. Verify credentials:
   ```bash
   kubectl logs -f deployment/smart-autoscaler -n autoscaler-system | grep -i auth
   ```

2. Test auth manually:
   ```bash
   curl -u admin:secret \
     http://mimir-query-frontend.mimir:8080/prometheus/api/v1/query?query=up
   ```

### Multi-Tenancy Issues

**Error: "No metrics found"**

1. Check tenant ID:
   ```bash
   kubectl logs -f deployment/smart-autoscaler -n autoscaler-system | grep -i tenant
   ```

2. Verify tenant has data:
   ```bash
   curl -H "X-Scope-OrgID: tenant-1" \
     http://mimir-query-frontend.mimir:8080/prometheus/api/v1/query?query=up
   ```

### Debug Mode

Enable debug logging:

```yaml
config:
  logLevel: DEBUG
```

Look for Mimir-specific logs:
```bash
kubectl logs -f deployment/smart-autoscaler -n autoscaler-system | grep -i mimir
```

---

## Example Configurations

### 1. Single Tenant (Simple)

```yaml
config:
  prometheusUrl: "http://mimir-query-frontend.mimir:8080/prometheus"
  mimirTenantId: "default"
  enableAutoDiscovery: true
```

### 2. Multi-Tenant with Auth

```yaml
config:
  prometheusUrl: "http://mimir-query-frontend.mimir:8080/prometheus"
  mimirTenantId: "production"
  prometheusUsername: "autoscaler"
  prometheusPassword: "secure-password"
  
  enablePredictive: true
  enablePrescale: true
  enableAutopilot: true
```

### 3. Grafana Cloud

```yaml
config:
  prometheusUrl: "https://prometheus-prod-XX-prod-XX.grafana.net/api/prom"
  prometheusUsername: "123456"  # Instance ID
  prometheusBearerToken: "glc_your-token-here"
```

### 4. Production Setup

```yaml
config:
  prometheusUrl: "https://mimir.company.com/prometheus"
  mimirTenantId: "k8s-autoscaler"
  prometheusBearerToken: "jwt-token-here"
  
  # Full features
  enableAutoDiscovery: true
  enablePredictive: true
  enablePrescale: true
  enableAutopilot: true
  autopilotLevel: autopilot
  autopilotEnableLearning: true

webhooks:
  slack: "https://hooks.slack.com/services/xxx/yyy/zzz"

resources:
  requests:
    cpu: 200m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 1Gi

persistence:
  enabled: true
  size: 20Gi
```

---

## Migration from Prometheus

### 1. Update URL

```yaml
# Before (Prometheus)
config:
  prometheusUrl: "http://prometheus-server.monitoring:9090"

# After (Mimir)
config:
  prometheusUrl: "http://mimir-query-frontend.mimir:8080/prometheus"
  mimirTenantId: "default"
```

### 2. Test Compatibility

```bash
# Deploy in test mode first
helm upgrade smart-autoscaler ./helm/smart-autoscaler \
  --set config.dryRun=true \
  --set config.prometheusUrl=http://mimir-query-frontend.mimir:8080/prometheus \
  --set config.mimirTenantId=default
```

### 3. Verify Metrics

Check dashboard shows same data as before migration.

---

## Best Practices

1. **Use Separate Tenants** - Isolate prod/staging/dev
2. **Secure Credentials** - Use Kubernetes secrets
3. **Monitor Performance** - Mimir adds slight latency
4. **Test First** - Use dry-run mode when migrating
5. **Backup Config** - Save working Prometheus config

---

## Next Steps

- [QUICKSTART.md](../QUICKSTART.md) - Basic setup
- [HELM_GUIDE.md](HELM_GUIDE.md) - Helm installation
- [examples/helm-values-mimir.yaml](../examples/helm-values-mimir.yaml) - Example config