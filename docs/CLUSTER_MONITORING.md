# Cluster Monitoring Guide

## Overview

Smart Autoscaler v0.0.11+ includes a comprehensive cluster monitoring dashboard that provides real-time visibility into your Kubernetes cluster's resource utilization, node health, and capacity planning metrics.

## Features

### 🖥️ Cluster Monitoring Dashboard

The cluster monitoring tab provides:

1. **Cluster Summary**
   - Total node count
   - Total pod count across watched deployments
   - Overall cluster health status

2. **CPU Resources Dashboard**
   - Total CPU capacity (cores)
   - Total CPU allocatable (cores available for scheduling)
   - Total CPU requests (sum of all pod requests)
   - Total CPU usage (actual usage across all pods)
   - Request % and usage % of allocatable
   - Visual progress bar with color coding
   - 24-hour historical trend chart

3. **Memory Resources Dashboard**
   - Total memory capacity (GB)
   - Total memory allocatable (GB available for scheduling)
   - Total memory requests (sum of all pod requests)
   - Total memory usage (actual usage across all pods)
   - Request % and usage % of allocatable
   - Visual progress bar with color coding
   - 24-hour historical trend chart

4. **Nodes Detail Table**
   - Per-node breakdown of all metrics
   - CPU capacity, usage, and percentage
   - Memory capacity, usage, and percentage
   - Health status per node
   - Visual progress bars

5. **Namespace Filter**
   - Filter deployments by namespace
   - Applies across all dashboard tabs
   - Dynamically populated from watched deployments

## Accessing the Dashboard

### Port Forward (Development)
```bash
kubectl port-forward -n autoscaler-system svc/smart-autoscaler 5000:5000
```

Then open: http://localhost:5000

### Production Access
```bash
# If using LoadBalancer
kubectl get svc -n autoscaler-system smart-autoscaler

# If using Ingress
kubectl get ingress -n autoscaler-system
```

## Understanding the Metrics

### CPU Metrics

#### Capacity
- **Definition**: Total CPU cores physically available on all nodes
- **Source**: `kube_node_status_capacity{resource="cpu"}`
- **Example**: 12.0 cores (3 nodes × 4 cores each)

#### Allocatable
- **Definition**: CPU cores available for pod scheduling (after system reservations)
- **Source**: `kube_node_status_allocatable{resource="cpu"}`
- **Example**: 11.4 cores (95% of capacity, 5% reserved for system)
- **Note**: Always less than capacity due to system daemons (kubelet, kube-proxy, etc.)

#### Requests
- **Definition**: Sum of all CPU requests from all pods
- **Source**: `sum(kube_pod_container_resource_requests{resource="cpu"})`
- **Example**: 6.5 cores
- **Meaning**: Pods have requested 6.5 cores total
- **Impact**: Scheduler uses this for placement decisions

#### Usage
- **Definition**: Actual CPU usage across all pods
- **Source**: `sum(rate(container_cpu_usage_seconds_total[5m]))`
- **Example**: 4.8 cores
- **Meaning**: Pods are actually using 4.8 cores
- **Note**: Can be less than requests (over-provisioned) or more (bursting)

#### Request %
- **Calculation**: (Requests / Allocatable) × 100
- **Example**: 57.0% (6.5 / 11.4 × 100)
- **Meaning**: 57% of schedulable CPU is requested
- **Threshold**: >80% = Warning, >90% = Critical

#### Usage %
- **Calculation**: (Usage / Allocatable) × 100
- **Example**: 42.1% (4.8 / 11.4 × 100)
- **Meaning**: 42% of schedulable CPU is actually used
- **Threshold**: >70% = Warning, >85% = Critical

### Memory Metrics

#### Capacity
- **Definition**: Total memory (GB) physically available on all nodes
- **Source**: `kube_node_status_capacity{resource="memory"}`
- **Example**: 48.0 GB (3 nodes × 16 GB each)

#### Allocatable
- **Definition**: Memory available for pod scheduling (after system reservations)
- **Source**: `kube_node_status_allocatable{resource="memory"}`
- **Example**: 43.5 GB (90% of capacity, 10% reserved for system)

#### Requests
- **Definition**: Sum of all memory requests from all pods
- **Source**: `sum(kube_pod_container_resource_requests{resource="memory"})`
- **Example**: 24.0 GB
- **Meaning**: Pods have requested 24 GB total

#### Usage
- **Definition**: Actual memory usage across all pods
- **Source**: `sum(container_memory_working_set_bytes)`
- **Example**: 18.5 GB
- **Meaning**: Pods are actually using 18.5 GB
- **Note**: Memory cannot burst like CPU (hard limit)

#### Request %
- **Calculation**: (Requests / Allocatable) × 100
- **Example**: 55.2% (24.0 / 43.5 × 100)
- **Threshold**: >80% = Warning, >90% = Critical

#### Usage %
- **Calculation**: (Usage / Allocatable) × 100
- **Example**: 42.5% (18.5 / 43.5 × 100)
- **Threshold**: >70% = Warning, >85% = Critical

## Health Status Indicators

### Color Coding

| Color | Status | Threshold | Action |
|-------|--------|-----------|--------|
| 🟢 Green | Healthy | < 70% | Normal operation |
| 🟡 Yellow | Warning | 70-85% | Monitor closely, consider scaling |
| 🔴 Red | Critical | > 85% | Immediate action required |

### Cluster Health

Overall cluster health is determined by the **maximum** of CPU and memory usage percentages:

```
Cluster Health = max(CPU Usage %, Memory Usage %)
```

**Example**:
- CPU Usage: 42%
- Memory Usage: 68%
- Cluster Health: 68% (Yellow - Warning)

## Use Cases

### 1. Capacity Planning

**Question**: Do I need to add more nodes?

**Check**:
- CPU Request % > 80% → Add nodes soon
- CPU Request % > 90% → Add nodes immediately
- Memory Request % > 80% → Add nodes soon
- Memory Request % > 90% → Add nodes immediately

**Example**:
```
CPU Allocatable: 11.4 cores
CPU Requests: 10.5 cores (92%)
Action: Add 1-2 nodes to maintain headroom
```

### 2. Resource Optimization

**Question**: Are my pods over-provisioned?

**Check**:
- Large gap between Requests and Usage
- Usage % significantly lower than Request %

**Example**:
```
CPU Requests: 6.5 cores (57% of allocatable)
CPU Usage: 4.8 cores (42% of allocatable)
Gap: 1.7 cores (15% wasted)
Action: Reduce CPU requests by 20-30%
```

### 3. Troubleshooting Performance Issues

**Question**: Why are my pods slow?

**Check**:
- CPU Usage % > 85% → CPU throttling likely
- Memory Usage % > 85% → Memory pressure, OOM risk
- Individual node metrics → Identify hot nodes

**Example**:
```
Node-1: CPU 95%, Memory 88% (Critical)
Node-2: CPU 45%, Memory 52% (Healthy)
Node-3: CPU 38%, Memory 48% (Healthy)
Action: Drain and rebalance Node-1
```

### 4. Cost Optimization

**Question**: Am I wasting money on unused resources?

**Check**:
- Usage % vs Request % gap
- Identify over-provisioned deployments

**Example**:
```
CPU Requests: 8.0 cores
CPU Usage: 4.0 cores
Waste: 4.0 cores (50%)
Monthly Cost: $115 wasted (4 cores × $0.04/hour × 720 hours)
Action: Right-size pod requests
```

### 5. Scaling Decisions

**Question**: Should I scale up or scale out?

**Check**:
- CPU Usage % > 70% → Scale up (more pods)
- CPU Request % > 80% → Scale out (more nodes)
- Memory Usage % > 70% → Scale up
- Memory Request % > 80% → Scale out

**Example**:
```
CPU Usage: 75% (High)
CPU Request: 65% (OK)
Action: Scale up pods (HPA will handle)

CPU Usage: 85% (Critical)
CPU Request: 92% (Critical)
Action: Scale out (add nodes first, then scale up)
```

## Namespace Filtering

### Using the Filter

1. **Select Namespace**: Click the dropdown at the top of the dashboard
2. **Filter Applied**: Only deployments in selected namespace are shown
3. **Persistent**: Filter persists when switching tabs
4. **Reset**: Select "All Namespaces" to show all

### Use Cases

- **Multi-tenant Clusters**: View resources per tenant
- **Environment Separation**: Filter by dev/staging/prod
- **Team Isolation**: View only your team's deployments
- **Troubleshooting**: Focus on specific namespace

## Historical Trends

### CPU Trend Chart (24h)

Shows:
- CPU Requests (yellow line)
- CPU Usage (green line)

**Patterns to Look For**:
- **Steady Gap**: Over-provisioned (requests > usage)
- **Converging Lines**: Well-tuned (requests ≈ usage)
- **Usage > Requests**: Under-provisioned (pods bursting)
- **Spikes**: Traffic patterns, batch jobs

### Memory Trend Chart (24h)

Shows:
- Average node utilization (purple line)

**Patterns to Look For**:
- **Steady Increase**: Memory leak
- **Periodic Spikes**: Batch jobs, cron tasks
- **Gradual Growth**: Application growth
- **Flat Line**: Stable workload

## Prometheus Requirements

### Required Metrics

The cluster monitoring feature requires these Prometheus metrics:

#### kube-state-metrics
```bash
# Install if not present
kubectl apply -f https://github.com/kubernetes/kube-state-metrics/releases/latest/download/kube-state-metrics.yaml
```

Provides:
- `kube_node_info`
- `kube_node_status_capacity`
- `kube_node_status_allocatable`
- `kube_pod_container_resource_requests`

#### node-exporter
```bash
# Usually included in Prometheus operator
# Or install manually
helm install node-exporter prometheus-community/prometheus-node-exporter
```

Provides:
- `node_cpu_seconds_total`
- `node_memory_MemTotal_bytes`
- `node_memory_MemAvailable_bytes`

#### cAdvisor (built into kubelet)
Provides:
- `container_cpu_usage_seconds_total`
- `container_memory_working_set_bytes`

### Verifying Metrics

Check if metrics are available:

```bash
# Check kube-state-metrics
kubectl get pods -n kube-system | grep kube-state-metrics

# Query Prometheus
curl -G http://prometheus:9090/api/v1/query --data-urlencode 'query=kube_node_info'

# Check node-exporter
curl -G http://prometheus:9090/api/v1/query --data-urlencode 'query=node_cpu_seconds_total'
```

## Troubleshooting

### No Cluster Metrics Showing

**Symptoms**: Cluster tab shows "-" for all metrics

**Causes**:
1. Prometheus not accessible
2. kube-state-metrics not installed
3. Metrics not scraped by Prometheus

**Solutions**:
```bash
# Check Prometheus connectivity
kubectl port-forward -n monitoring svc/prometheus-server 9090:9090
curl http://localhost:9090/api/v1/query?query=up

# Check kube-state-metrics
kubectl get pods -n kube-system | grep kube-state-metrics
kubectl logs -n kube-system <kube-state-metrics-pod>

# Check Prometheus scrape config
kubectl get configmap -n monitoring prometheus-server -o yaml | grep kube-state-metrics
```

### Inaccurate Node Metrics

**Symptoms**: Node CPU/memory shows 0 or incorrect values

**Causes**:
1. node-exporter not running
2. Node labels don't match query
3. Prometheus not scraping nodes

**Solutions**:
```bash
# Check node-exporter
kubectl get pods -n kube-system | grep node-exporter

# Check node labels
kubectl get nodes --show-labels

# Test query manually
curl -G http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=node_cpu_seconds_total{mode!="idle"}'
```

### Historical Charts Not Loading

**Symptoms**: Charts show "No data"

**Causes**:
1. No historical data in database
2. Database query error
3. Not enough data points

**Solutions**:
```bash
# Check database
sqlite3 /data/autoscaler.db "SELECT COUNT(*) FROM metrics_history;"

# Wait for data to accumulate (need at least 10 data points)
# Check interval: default is 60 seconds

# Check logs
kubectl logs -n autoscaler-system <autoscaler-pod> | grep "cluster/history"
```

### Namespace Filter Not Working

**Symptoms**: Filter doesn't hide deployments

**Causes**:
1. JavaScript error
2. Namespace mismatch
3. Browser cache

**Solutions**:
```bash
# Check browser console for errors
# Clear browser cache
# Verify namespace names match exactly
```

## Best Practices

### 1. Regular Monitoring

- Check cluster health daily
- Review trends weekly
- Plan capacity monthly

### 2. Set Thresholds

- Alert when CPU Request % > 80%
- Alert when Memory Request % > 80%
- Alert when Usage % > 85%

### 3. Capacity Planning

- Maintain 20-30% headroom
- Plan for 2-3x peak load
- Add nodes before hitting 90% requests

### 4. Cost Optimization

- Review usage vs requests weekly
- Right-size over-provisioned pods
- Use FinOps recommendations

### 5. Performance Tuning

- Balance pods across nodes
- Avoid hot nodes (>85% usage)
- Use node affinity for critical workloads

## Integration with Other Features

### Priority-Based Scaling

Cluster metrics help determine:
- When to trigger preemptive scaling
- Cluster pressure for priority adjustments
- Resource availability for critical services

### Cost Optimization

Cluster metrics feed into:
- Wasted capacity calculations
- Right-sizing recommendations
- Monthly cost projections

### Predictive Scaling

Historical trends enable:
- Pattern detection
- Capacity forecasting
- Proactive scaling decisions

## API Reference

### GET /api/cluster/metrics

Returns current cluster metrics.

**Response**:
```json
{
  "nodes": [...],
  "node_count": 3,
  "summary": {
    "cpu": {...},
    "memory": {...}
  },
  "namespaces": [...]
}
```

### GET /api/cluster/history?hours=24

Returns historical cluster metrics.

**Parameters**:
- `hours` (optional): Number of hours to query (default: 24)

**Response**:
```json
{
  "history": [...],
  "hours": 24
}
```

## Future Enhancements

- [ ] Custom time range selection (1h, 6h, 24h, 7d, 30d)
- [ ] Pod-level resource breakdown
- [ ] Persistent volume metrics
- [ ] Network I/O metrics
- [ ] Export to CSV/JSON
- [ ] Alerting based on thresholds
- [ ] Multi-cluster support
- [ ] Resource quota visualization
- [ ] Namespace-level limits
- [ ] Cost breakdown by namespace
- [ ] Predictive capacity planning
- [ ] Anomaly detection for cluster metrics

## Support

For issues or questions:
- Check logs: `kubectl logs -n autoscaler-system <pod>`
- Review Prometheus metrics availability
- Verify kube-state-metrics is running
- Check GitHub issues: [Smart Autoscaler Issues](https://github.com/your-repo/issues)
