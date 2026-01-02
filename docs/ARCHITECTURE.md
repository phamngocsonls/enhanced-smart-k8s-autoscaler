# Architecture Overview

Simple explanation of how Smart Autoscaler works.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Your Kubernetes Cluster                     │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Deployment 1 │  │ Deployment 2 │  │ Deployment 3 │          │
│  │   (Pods)     │  │   (Pods)     │  │   (Pods)     │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                   │
│         └──────────────────┴──────────────────┘                  │
│                            │                                      │
│                            ▼                                      │
│                    ┌───────────────┐                             │
│                    │  HPA (Native) │                             │
│                    │  Autoscaling  │                             │
│                    └───────┬───────┘                             │
│                            │                                      │
│                            │ ◄─── Smart Autoscaler adjusts       │
│                            │      HPA targets dynamically        │
│                            │                                      │
│         ┌──────────────────┴──────────────────┐                 │
│         │                                       │                 │
│         ▼                                       ▼                 │
│  ┌─────────────┐                      ┌──────────────┐          │
│  │ Prometheus  │                      │    Smart     │          │
│  │  (Metrics)  │◄─────────────────────│  Autoscaler  │          │
│  └─────────────┘                      │  (Operator)  │          │
│                                        └──────┬───────┘          │
│                                               │                   │
│                                               ▼                   │
│                                        ┌─────────────┐           │
│                                        │  Dashboard  │           │
│                                        │  (Web UI)   │           │
│                                        └─────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## How It Works

### 1. Data Collection
```
Prometheus ──► Smart Autoscaler
   │
   ├─ Node CPU/Memory usage
   ├─ Pod CPU/Memory usage
   ├─ Pod start times
   └─ Historical metrics
```

### 2. Intelligence Layer
```
Smart Autoscaler
   │
   ├─ Pattern Detection ──► Identifies workload type
   │                        (steady, bursty, periodic, etc.)
   │
   ├─ Prediction Engine ──► Forecasts future load
   │                        (15min, 30min, 1hr, 2hr)
   │
   ├─ Auto-Tuning ──────► Learns optimal HPA targets
   │                      (Bayesian optimization)
   │
   ├─ Cost Analysis ────► Calculates waste & savings
   │                      (FinOps recommendations)
   │
   └─ Node Awareness ───► Tracks cluster capacity
                          (Prevents overload)
```

### 3. Decision Making
```
Smart Autoscaler
   │
   ├─ Analyze current state
   ├─ Check node pressure
   ├─ Apply priority rules
   ├─ Filter startup spikes
   └─ Calculate optimal HPA target
```

### 4. Action
```
Smart Autoscaler ──► HPA ──► Kubernetes ──► Scale Pods
                      │
                      └─ Adjusts targetAverageUtilization
                         (e.g., 70% → 65% when node pressure high)
```

### 5. Feedback Loop
```
Pods Scale ──► Prometheus ──► Smart Autoscaler
                                    │
                                    └─ Learns from results
                                       Updates predictions
                                       Improves accuracy
```

## Components

### Smart Autoscaler Operator
- **Language**: Python
- **Runs as**: Kubernetes Deployment
- **Watches**: Multiple deployments simultaneously
- **Updates**: HPA targets every 60 seconds (configurable)

### Dashboard (Web UI)
- **Port**: 5000
- **Features**: 
  - Real-time cluster metrics
  - Predictions visualization
  - Cost analysis
  - Recommendations
  - Alerts

### Metrics Exporter
- **Port**: 8000
- **Format**: Prometheus metrics
- **Exports**: 
  - Prediction accuracy
  - Cost metrics
  - Confidence scores
  - Learning progress

### Database
- **Type**: SQLite
- **Storage**: Persistent Volume
- **Contains**:
  - Historical metrics (30 days)
  - Prediction accuracy
  - Learning data
  - Alert history

## Data Flow Example

Let's follow a scaling decision:

```
1. Prometheus Query
   ├─ "What's the current CPU usage?"
   └─ Result: 0.45 cores per pod

2. Pattern Detection
   ├─ "What pattern is this workload?"
   └─ Result: "periodic" (daily cycles)

3. Prediction
   ├─ "What will CPU be in 30 minutes?"
   └─ Result: 0.62 cores (lunch rush coming)

4. Node Check
   ├─ "How much capacity do we have?"
   └─ Result: 45% node utilization (safe)

5. Decision
   ├─ Current HPA target: 70%
   ├─ Node pressure: safe
   ├─ Prediction: load increasing
   └─ Decision: Keep target at 70% (no change needed)

6. Apply
   └─ No HPA update needed this cycle

7. Store Results
   ├─ Save metrics to database
   ├─ Update prediction accuracy
   └─ Learn for next cycle
```

## Startup Filter Example

How the startup filter prevents bad scaling decisions:

```
Time: 10:00:00
Startup Filter: 2 minutes

Pods:
┌─────────────────────────────────────────────────────┐
│ Pod A: Started 10:00:00 (age: 0 min)  ❌ EXCLUDED  │
│        CPU: 95% (JVM initializing)                  │
│                                                      │
│ Pod B: Started 09:59:00 (age: 1 min)  ❌ EXCLUDED  │
│        CPU: 80% (still warming up)                  │
│                                                      │
│ Pod C: Started 09:57:00 (age: 3 min)  ✅ INCLUDED  │
│        CPU: 45% (stable)                            │
│                                                      │
│ Pod D: Started 09:55:00 (age: 5 min)  ✅ INCLUDED  │
│        CPU: 42% (stable)                            │
└─────────────────────────────────────────────────────┘

Average CPU used for scaling decision:
(45% + 42%) / 2 = 43.5%  ← Accurate, stable metric

Without filter:
(95% + 80% + 45% + 42%) / 4 = 65.5%  ← Inflated by startup!
```

## Priority-Based Scaling

How priorities protect critical services:

```
Cluster State: High node pressure (85% CPU)

Deployments:
┌──────────────────────────────────────────────────────┐
│ Payment Service (CRITICAL)                           │
│ ├─ Current HPA: 55%                                  │
│ └─ Action: Lower to 50% (scale up aggressively)     │
│                                                       │
│ API Gateway (HIGH)                                    │
│ ├─ Current HPA: 60%                                  │
│ └─ Action: Lower to 55% (scale up moderately)       │
│                                                       │
│ Web Frontend (MEDIUM)                                 │
│ ├─ Current HPA: 70%                                  │
│ └─ Action: Keep at 70% (normal scaling)             │
│                                                       │
│ Background Jobs (LOW)                                 │
│ ├─ Current HPA: 80%                                  │
│ └─ Action: Raise to 85% (reduce resource usage)     │
│                                                       │
│ Analytics (BEST_EFFORT)                               │
│ ├─ Current HPA: 85%                                  │
│ └─ Action: Raise to 90% (minimize resource usage)   │
└──────────────────────────────────────────────────────┘

Result: Critical services get resources first!
```

## Predictive Scaling Example

How predictions enable proactive scaling:

```
Current Time: 11:00 AM
Historical Pattern: Lunch rush at 12:00 PM

┌─────────────────────────────────────────────────────┐
│                    CPU Usage                         │
│  100% │                                              │
│       │                    ╱╲                        │
│   80% │                   ╱  ╲                       │
│       │                  ╱    ╲                      │
│   60% │                 ╱      ╲                     │
│       │      ┌─────────╱        ╲─────────┐         │
│   40% │──────┘                            └─────    │
│       │                                              │
│   20% │                                              │
│       │                                              │
│    0% └──────────────────────────────────────────   │
│       9AM   10AM   11AM   12PM   1PM    2PM   3PM   │
│                     ▲                                │
│                   NOW                                │
└─────────────────────────────────────────────────────┘

Predictions:
├─ 15min (11:15): 45% CPU  ← Starting to climb
├─ 30min (11:30): 52% CPU  ← Climbing faster
├─ 1hr   (12:00): 75% CPU  ← Peak predicted!
└─ 2hr   (13:00): 48% CPU  ← Will drop after lunch

Action:
└─ Lower HPA target NOW (11:00) to 65%
   So pods scale up BEFORE the rush
   Instead of DURING the rush (too late!)
```

## Auto-Tuning Example

How Bayesian optimization learns optimal targets:

```
Day 1: Initial guess
├─ HPA Target: 70%
├─ Result: Some throttling at peak
└─ Score: 6/10

Day 2: Try lower target
├─ HPA Target: 65%
├─ Result: Better, but still some spikes
└─ Score: 7/10

Day 3: Try even lower
├─ HPA Target: 60%
├─ Result: Good performance, but costly
└─ Score: 7/10

Day 4: Bayesian suggests 63%
├─ HPA Target: 63%
├─ Result: Perfect balance!
└─ Score: 9/10

Day 5-7: Fine-tune around 63%
├─ HPA Target: 62-64% (varies by hour)
├─ Result: Optimal for each time of day
└─ Score: 9.5/10

After 7 days:
└─ Auto-applies learned targets
   Different target for each hour:
   - 9AM-11AM: 65% (morning ramp-up)
   - 12PM-1PM: 60% (lunch rush)
   - 2PM-5PM: 70% (steady afternoon)
   - 6PM-8AM: 75% (low traffic)
```

## Integration Points

### With Prometheus
```
Smart Autoscaler ──► Prometheus API
   │
   ├─ Queries: Node metrics, pod metrics, HPA status
   ├─ Rate limit: 10 queries/second (configurable)
   └─ Circuit breaker: Fails gracefully if Prometheus down
```

### With Kubernetes API
```
Smart Autoscaler ──► Kubernetes API
   │
   ├─ Reads: Deployments, HPAs, Pods, Nodes
   ├─ Writes: HPA spec updates
   ├─ Rate limit: 20 calls/second (configurable)
   └─ RBAC: Requires specific permissions (see k8s/rbac.yaml)
```

### With ArgoCD (Optional)
```
ArgoCD ──► HPA (Git source)
            │
            ├─ Annotation: argocd.argoproj.io/compare-options: IgnoreExtraneous
            └─ Result: ArgoCD ignores Smart Autoscaler's target changes
```

## Failure Modes & Resilience

### Prometheus Down
```
Smart Autoscaler
   ├─ Circuit breaker opens after 5 failures
   ├─ Stops making scaling decisions
   ├─ HPAs continue with last known targets
   └─ Logs error, waits for recovery
```

### Kubernetes API Issues
```
Smart Autoscaler
   ├─ Retries with exponential backoff
   ├─ Falls back to read-only mode
   ├─ Continues monitoring
   └─ Resumes updates when API recovers
```

### Database Corruption
```
Smart Autoscaler
   ├─ Detects corruption on startup
   ├─ Creates new database
   ├─ Loses historical data
   └─ Continues operating (rebuilds history)
```

### Out of Memory
```
Smart Autoscaler
   ├─ Memory monitoring (checks every 30s)
   ├─ Warning at 75% usage
   ├─ Triggers cleanup at 90%
   └─ Restarts if cleanup fails
```

## Performance Characteristics

### Resource Usage
```
Smart Autoscaler Pod:
├─ CPU: 50-200m (varies with deployment count)
├─ Memory: 256-512Mi (depends on history size)
└─ Storage: 1-10Gi (30 days of metrics)
```

### Scaling Latency
```
Event → Decision → Action
  │        │         │
  │        │         └─ HPA update: <1s
  │        └─ Analysis: 2-5s
  └─ Detection: 60s (check interval)

Total: ~60-65 seconds from event to HPA update
```

### Prediction Accuracy
```
After 7 days of learning:
├─ 15min predictions: 85-95% accurate
├─ 30min predictions: 80-90% accurate
├─ 1hr predictions: 75-85% accurate
└─ 2hr predictions: 70-80% accurate

Accuracy improves over time!
```

## Related Documentation

- [Quick Start](../QUICKSTART.md) - Get started in 5 minutes
- [Configuration Reference](../QUICK_REFERENCE.md) - All settings explained
- [Startup Filter](STARTUP_FILTER.md) - Java/JVM startup handling
- [HPA Anti-Flapping](HPA-ANTI-FLAPPING.md) - Prevent scaling thrashing
- [Predictive Scaling](PREDICTIVE_SCALING.md) - How predictions work
