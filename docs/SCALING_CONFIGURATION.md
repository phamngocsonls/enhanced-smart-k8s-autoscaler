# Scaling Configuration for Large Deployments

How to configure Smart Autoscaler when you have many deployments (10+, 100+, or more).

---

## The ConfigMap Limitation

Kubernetes ConfigMaps have a **1MB size limit**. If you configure deployments like this:

```yaml
DEPLOYMENT_0_NAMESPACE: "default"
DEPLOYMENT_0_NAME: "app1"
DEPLOYMENT_0_HPA_NAME: "app1-hpa"
DEPLOYMENT_0_STARTUP_FILTER: "2"
DEPLOYMENT_0_PRIORITY: "medium"

DEPLOYMENT_1_NAMESPACE: "default"
DEPLOYMENT_1_NAME: "app2"
...
# Repeat 100+ times
```

You'll hit the 1MB limit around **~200-300 deployments** (depending on name lengths).

---

## Solution 1: Helm Values (Recommended for 10-100 Deployments)

Use Helm's values.yaml which doesn't have size limits:

```yaml
# helm/smart-autoscaler/values.yaml
deployments:
  - namespace: default
    name: app1
    hpaName: app1-hpa
    startupFilterMinutes: 2
    priority: medium
  
  - namespace: default
    name: app2
    hpaName: app2-hpa
    startupFilterMinutes: 2
    priority: high
  
  # ... 100+ more deployments
```

**Pros:**
- ✅ No size limit
- ✅ Clean YAML structure
- ✅ Version controlled
- ✅ Easy to manage with GitOps

**Cons:**
- ❌ Requires Helm
- ❌ Need to redeploy to add deployments

**Install:**
```bash
helm install smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  --values my-deployments.yaml
```

---

## Solution 2: Label Selector (Recommended for 100+ Deployments)

**Coming in v0.0.23**: Auto-discover deployments by label!

Instead of listing every deployment, use a label selector:

```yaml
# ConfigMap
data:
  WATCH_LABEL_SELECTOR: "autoscale=smart"
  DEFAULT_STARTUP_FILTER: "2"
  DEFAULT_PRIORITY: "medium"
```

Then label your deployments:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  labels:
    autoscale: smart
  annotations:
    smart-autoscaler/startup-filter: "5"  # Override default
    smart-autoscaler/priority: "high"     # Override default
```

Smart Autoscaler will automatically discover and watch all deployments with the label!

**Pros:**
- ✅ No size limit
- ✅ Auto-discovery
- ✅ Per-deployment overrides via annotations
- ✅ Easy to add new deployments (just add label)

**Cons:**
- ❌ Not yet implemented (coming soon!)

---

## Solution 3: External Config File (For 1000+ Deployments)

Mount a config file from a Secret or external source:

```yaml
# deployments-config.yaml (stored in Secret)
deployments:
  - namespace: default
    name: app1
    hpa: app1-hpa
    startup_filter: 2
    priority: medium
  # ... 1000+ deployments
```

Mount as volume:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: smart-autoscaler
spec:
  template:
    spec:
      volumes:
      - name: config
        secret:
          secretName: deployments-config
      containers:
      - name: autoscaler
        volumeMounts:
        - name: config
          mountPath: /config
        env:
        - name: DEPLOYMENTS_CONFIG_FILE
          value: /config/deployments.yaml
```

**Pros:**
- ✅ No size limit (Secrets can be 1MB, but you can split into multiple)
- ✅ Can be generated programmatically
- ✅ Supports very large deployments

**Cons:**
- ❌ More complex setup
- ❌ Requires custom implementation

---

## Solution 4: Multiple ConfigMaps (Current Workaround)

Split deployments across multiple ConfigMaps:

```yaml
# configmap-deployments-1.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: smart-autoscaler-deployments-1
data:
  DEPLOYMENT_0_NAMESPACE: "default"
  DEPLOYMENT_0_NAME: "app1"
  # ... up to ~150 deployments

---
# configmap-deployments-2.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: smart-autoscaler-deployments-2
data:
  DEPLOYMENT_150_NAMESPACE: "default"
  DEPLOYMENT_150_NAME: "app151"
  # ... next 150 deployments
```

Mount both:

```yaml
spec:
  containers:
  - name: autoscaler
    envFrom:
    - configMapRef:
        name: smart-autoscaler-config
    - configMapRef:
        name: smart-autoscaler-deployments-1
    - configMapRef:
        name: smart-autoscaler-deployments-2
```

**Pros:**
- ✅ Works with current version
- ✅ Can scale to 500+ deployments

**Cons:**
- ❌ Messy to manage
- ❌ Still has limits

---

## Solution 5: Dynamic Discovery via Prometheus (Future)

Auto-discover deployments that have HPAs:

```yaml
data:
  AUTO_DISCOVER_HPAS: "true"
  NAMESPACE_FILTER: "production,staging"  # Optional filter
```

Smart Autoscaler queries Prometheus for all HPAs and automatically watches them.

**Pros:**
- ✅ Zero configuration
- ✅ Unlimited deployments
- ✅ Auto-adds new deployments

**Cons:**
- ❌ Not yet implemented
- ❌ Less control over per-deployment settings

---

## Recommendations by Scale

| Deployments | Recommended Solution |
|-------------|---------------------|
| 1-10 | ConfigMap (current approach) |
| 10-100 | Helm values.yaml |
| 100-500 | Multiple ConfigMaps or Helm |
| 500+ | Label Selector (v0.0.23) or External Config |
| 1000+ | External Config File + programmatic generation |

---

## Current Best Practice (Until v0.0.23)

For **10-100 deployments**, use Helm:

### 1. Create values file

```yaml
# my-deployments.yaml
deployments:
  - namespace: production
    name: api-gateway
    hpaName: api-gateway-hpa
    startupFilterMinutes: 2
    priority: critical
  
  - namespace: production
    name: auth-service
    hpaName: auth-service-hpa
    startupFilterMinutes: 3
    priority: critical
  
  - namespace: production
    name: payment-service
    hpaName: payment-service-hpa
    startupFilterMinutes: 5
    priority: critical
  
  # Add all your deployments here
```

### 2. Install with Helm

```bash
helm install smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  --create-namespace \
  --values my-deployments.yaml
```

### 3. Update deployments

```bash
# Edit my-deployments.yaml
vim my-deployments.yaml

# Upgrade
helm upgrade smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  --values my-deployments.yaml
```

---

## Programmatic Generation

For very large deployments, generate the config programmatically:

### Option 1: Use the provided script

```bash
# Auto-discover HPAs from your cluster
python3 scripts/generate-helm-values.py --auto-discover -o my-values.yaml

# Or from CSV file
python3 scripts/generate-helm-values.py --csv deployments.csv -o my-values.yaml

# Generate CSV template
python3 scripts/generate-helm-values.py --template > deployments.csv
```

CSV format:
```csv
namespace,deployment,hpa_name,startup_filter,priority
production,api-gateway,api-gateway-hpa,2,critical
production,auth-service,auth-service-hpa,3,critical
production,payment-service,payment-service-hpa,5,critical
```

Then install:
```bash
helm install smart-autoscaler ./helm/smart-autoscaler \
  --namespace autoscaler-system \
  --values my-values.yaml
```

### Option 2: Custom Python script

```python
#!/usr/bin/env python3
# generate-config.py

import yaml

# Your deployment list (from database, API, etc.)
deployments = [
    {"namespace": "prod", "name": f"app-{i}", "priority": "medium"}
    for i in range(1, 501)  # 500 deployments
]

# Generate Helm values
config = {
    "deployments": [
        {
            "namespace": d["namespace"],
            "name": d["name"],
            "hpaName": f"{d['name']}-hpa",
            "startupFilterMinutes": 2,
            "priority": d["priority"]
        }
        for d in deployments
    ]
}

# Write to file
with open("generated-deployments.yaml", "w") as f:
    yaml.dump(config, f, default_flow_style=False)

print(f"Generated config for {len(deployments)} deployments")
```

Run:
```bash
python3 generate-config.py
helm upgrade smart-autoscaler ./helm/smart-autoscaler \
  --values generated-deployments.yaml
```

---

## Future: Label Selector (v0.0.23)

We're working on label-based auto-discovery:

```yaml
# Just configure the label selector
data:
  WATCH_LABEL_SELECTOR: "autoscale=smart"
```

Then label your deployments:

```bash
# Label existing deployments
kubectl label deployment app1 autoscale=smart
kubectl label deployment app2 autoscale=smart

# Or in deployment manifest
metadata:
  labels:
    autoscale: smart
  annotations:
    smart-autoscaler/startup-filter: "5"
    smart-autoscaler/priority: "high"
```

Smart Autoscaler will automatically discover and watch them!

**Track progress**: [GitHub Issue #XX](https://github.com/phamngocsonls/enhanced-smart-k8s-autoscaler/issues/XX)

---

## Summary

- **ConfigMaps have 1MB limit** (~200-300 deployments max)
- **Use Helm values.yaml** for 10-100 deployments (recommended now)
- **Use multiple ConfigMaps** as workaround for 100-500 deployments
- **Label selector coming in v0.0.23** for unlimited deployments
- **Generate config programmatically** for very large scales

For most users (< 100 deployments), Helm is the best solution today!
