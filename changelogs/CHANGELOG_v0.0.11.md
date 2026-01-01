# Changelog - Version 0.0.11

## Release Date: 2026-01-01

## 🖥️ Major Feature: Comprehensive Cluster Monitoring Dashboard

### Overview
Added a complete cluster monitoring dashboard with real-time metrics, historical trends, and namespace filtering capabilities.

### New Features

#### 1. Cluster Monitoring Tab
- **Real-time Cluster Metrics**: Live view of cluster health and resource utilization
- **Node-Level Visibility**: Detailed metrics for each node in the cluster
- **Historical Trends**: 24-hour historical charts for CPU and memory
- **Namespace Filtering**: Filter deployments by namespace across all tabs

#### 2. CPU Dashboard
- **Total CPU Capacity**: Total CPU cores available in the cluster
- **Total CPU Allocatable**: CPU cores available for scheduling (after system reservations)
- **Total CPU Requests**: Sum of all pod CPU requests
- **Total CPU Usage**: Actual CPU usage across all pods
- **Visual Progress Bars**: Color-coded bars showing usage vs allocatable
- **Percentage Indicators**: Request % and usage % of allocatable resources
- **Historical Chart**: 24-hour trend showing requests vs usage

#### 3. Memory Dashboard
- **Total Memory Capacity**: Total memory (GB) available in the cluster
- **Total Memory Allocatable**: Memory available for scheduling
- **Total Memory Requests**: Sum of all pod memory requests
- **Total Memory Usage**: Actual memory usage across all pods
- **Visual Progress Bars**: Color-coded bars showing usage vs allocatable
- **Percentage Indicators**: Request % and usage % of allocatable resources
- **Historical Chart**: 24-hour trend showing utilization patterns

#### 4. Nodes Detail Table
Per-node breakdown showing:
- Node name
- CPU capacity and allocatable
- CPU usage (cores and %)
- Memory capacity and allocatable
- Memory usage (GB and %)
- Health status (healthy/warning/critical)
- Visual progress bars for each metric

#### 5. Cluster Summary Cards
- **Node Count**: Total active nodes in cluster
- **Total Pods**: Sum of pods across all watched deployments
- **Cluster Health**: Overall health status based on resource pressure

#### 6. Namespace Filter
- **Global Filter**: Dropdown to filter deployments by namespace
- **Applies to All Tabs**: Filter persists across tab switches
- **Auto-populated**: Dynamically populated from watched deployments

### API Endpoints

#### `/api/cluster/metrics`
Returns comprehensive cluster metrics:
```json
{
  "nodes": [
    {
      "name": "node-1",
      "cpu_capacity": 4.0,
      "cpu_allocatable": 3.8,
      "cpu_usage": 2.1,
      "memory_capacity_gb": 16.0,
      "memory_allocatable_gb": 14.5,
      "memory_usage_gb": 8.2
    }
  ],
  "node_count": 3,
  "summary": {
    "cpu": {
      "capacity": 12.0,
      "allocatable": 11.4,
      "requests": 6.5,
      "usage": 4.8,
      "requests_percent": 57.0,
      "usage_percent": 42.1
    },
    "memory": {
      "capacity_gb": 48.0,
      "allocatable_gb": 43.5,
      "requests_gb": 24.0,
      "usage_gb": 18.5,
      "requests_percent": 55.2,
      "usage_percent": 42.5
    }
  },
  "namespaces": ["default", "production", "staging"]
}
```

#### `/api/cluster/history`
Returns historical cluster metrics:
```json
{
  "history": [
    {
      "timestamp": "2026-01-01 10:00",
      "total_pods": 45,
      "avg_node_utilization": 65.5,
      "total_cpu_request_millicores": 6500,
      "total_cpu_usage_millicores": 4800
    }
  ],
  "hours": 24
}
```

### Prometheus Queries Used

The dashboard queries the following Prometheus metrics:

#### Node Metrics
- `kube_node_info` - Node information
- `kube_node_status_capacity{resource="cpu"}` - CPU capacity per node
- `kube_node_status_allocatable{resource="cpu"}` - CPU allocatable per node
- `kube_node_status_capacity{resource="memory"}` - Memory capacity per node
- `kube_node_status_allocatable{resource="memory"}` - Memory allocatable per node
- `node_cpu_seconds_total{mode!="idle"}` - CPU usage per node
- `node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes` - Memory usage per node

#### Cluster-Wide Metrics
- `sum(kube_pod_container_resource_requests{resource="cpu"})` - Total CPU requests
- `sum(kube_pod_container_resource_requests{resource="memory"})` - Total memory requests
- `sum(rate(container_cpu_usage_seconds_total[5m]))` - Total CPU usage
- `sum(container_memory_working_set_bytes)` - Total memory usage

### Visual Indicators

#### Color Coding
- **Green (Healthy)**: Usage < 70%
- **Yellow (Warning)**: Usage 70-85%
- **Red (Critical)**: Usage > 85%

#### Progress Bars
- Real-time visual representation of resource utilization
- Color-coded based on thresholds
- Smooth transitions with CSS animations

### Files Modified

1. **src/dashboard.py**
   - Added `/api/cluster/metrics` endpoint
   - Added `/api/cluster/history` endpoint
   - Queries Prometheus for node and cluster metrics
   - Aggregates data across all nodes
   - Returns namespace list for filtering

2. **templates/dashboard.html**
   - Added Cluster Monitoring tab
   - Added namespace filter dropdown
   - Added CPU dashboard section
   - Added Memory dashboard section
   - Added nodes detail table
   - Added historical trend charts
   - Added JavaScript functions for cluster metrics
   - Added tab switching logic for cluster tab
   - Added namespace filter event handler

3. **src/__init__.py**
   - Version bump to 0.0.11

### Usage

#### Viewing Cluster Metrics
1. Open dashboard at `http://localhost:5000`
2. Click "🖥️ Cluster" tab
3. View real-time cluster metrics
4. Scroll down to see node details

#### Filtering by Namespace
1. Use the namespace dropdown at the top
2. Select a namespace to filter deployments
3. Filter applies to all tabs
4. Select "All Namespaces" to reset

#### Historical Analysis
- CPU and Memory trend charts show 24-hour history
- Data refreshes automatically every 30 seconds
- Click "🔄 Refresh" to update immediately

### Benefits

1. **Complete Visibility**: See entire cluster health at a glance
2. **Resource Planning**: Identify capacity constraints before they impact workloads
3. **Cost Optimization**: Spot over-provisioned resources
4. **Troubleshooting**: Quickly identify problematic nodes
5. **Capacity Planning**: Historical trends help predict future needs
6. **Multi-Tenant Support**: Namespace filtering for multi-tenant clusters

### Performance

- Minimal overhead: Queries cached by Prometheus
- Efficient aggregation: Server-side calculations
- Lazy loading: Metrics loaded only when tab is active
- Auto-refresh: Updates every 30 seconds with countdown

### Requirements

The cluster monitoring feature requires:
- **Prometheus** with kube-state-metrics
- **node-exporter** for node metrics
- **cAdvisor** for container metrics (usually built into kubelet)
- **metrics-server** for pod metrics

All these are typically included in standard Kubernetes monitoring setups.

### Backward Compatibility

- ✅ Existing features unchanged
- ✅ No configuration changes required
- ✅ Graceful degradation if metrics unavailable
- ✅ Works with existing Prometheus setup

### Known Limitations

- Historical data limited to what's stored in SQLite database
- Node metrics require node-exporter
- Memory usage may not be 100% accurate without proper cAdvisor setup
- Large clusters (>100 nodes) may experience slower load times

### Future Enhancements

- [ ] Pod-level resource breakdown
- [ ] Persistent volume metrics
- [ ] Network I/O metrics
- [ ] Custom time range selection
- [ ] Export metrics to CSV
- [ ] Alerting based on cluster thresholds
- [ ] Multi-cluster support
- [ ] Resource quota visualization
- [ ] Namespace-level resource limits

### Migration Guide

No migration required. The feature is automatically available after upgrade.

### Testing

1. **Test Cluster Tab**:
   ```bash
   # Port forward dashboard
   kubectl port-forward -n autoscaler-system svc/smart-autoscaler 5000:5000
   
   # Open browser
   open http://localhost:5000
   
   # Click "Cluster" tab
   ```

2. **Test Namespace Filter**:
   - Select different namespaces from dropdown
   - Verify deployments table filters correctly
   - Switch tabs and verify filter persists

3. **Test Historical Charts**:
   - Wait for data to accumulate (or use existing data)
   - Verify charts display correctly
   - Check 24-hour time range

### Screenshots

#### Cluster Dashboard
- Node count, pod count, cluster health summary
- CPU dashboard with capacity, allocatable, requests, usage
- Memory dashboard with capacity, allocatable, requests, usage
- Visual progress bars with color coding
- Historical trend charts (24h)
- Nodes detail table with per-node metrics

#### Namespace Filter
- Dropdown at top of page
- Dynamically populated from watched deployments
- Filters all deployment views

### Version Bump

- Previous: 0.0.10
- Current: 0.0.11

### Contributors

- Smart Autoscaler Team

---

## Summary

Version 0.0.11 adds comprehensive cluster monitoring capabilities to the dashboard. Users can now see real-time cluster health, node-level metrics, resource utilization trends, and filter by namespace. This provides complete visibility into cluster resources and helps with capacity planning, troubleshooting, and cost optimization.
