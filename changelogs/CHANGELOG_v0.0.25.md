# Changelog v0.0.25

**Release Date:** 2025-01-04  
**Status:** ✅ Stable

## 🎯 Major Features

### 📊 Advanced Cost Allocation
- **Auto-Pricing Detection**: Automatically detects cloud provider and uses actual instance pricing
  - **GCP**: Detects GKE nodes and uses Singapore (asia-southeast1) pricing
    - All families: E2, N1, N2, N2D, T2D, T2A (Arm), C2, C2D, C3, C3D, M1, M2, M3, A2, A3, G2
    - Latest generations: C3/C3D (Sapphire Rapids/Genoa), M3, T2A (Arm-based)
  - **AWS**: Detects EKS nodes and uses Singapore (ap-southeast-1) pricing
    - All families: T2, T3, T4g (Graviton2), M5, M6i, M6g, M7g (Graviton3), M7i, C5, C6i, C6g, C7g (Graviton3), C7i, R5, R6i, R6g, R7g (Graviton3), R7i, X1, X2, I3, I4i
    - Latest generations: M7i, C7i, R7i, M7g/C7g/R7g (Graviton3)
  - **Azure**: Detects AKS nodes and uses Southeast Asia (Singapore) pricing
    - All families: A, B, D (v2-v5), Dps (Arm), F, Fx, E (v3-v5), Eps (Arm), M, Mv2, L, NC, ND
    - Latest generations: D5/E5 series, Dps/Eps (Arm-based)
  - **Pricing Updates**: Pricing data updated with each release from official cloud provider pages
  - **Optional API Updates**: Script provided to fetch latest pricing from cloud APIs (Azure public API supported)
  - Fallback to Singapore region average if detection fails
  - Manual override option available
- **Multi-Dimensional Tracking**: Group costs by team, project, namespace, environment
- **Label-Based Allocation**: Automatic cost tagging from Kubernetes deployment labels
- **Chargeback/Showback**: Enterprise-grade cost allocation for billing and budgeting
- **Cost Anomaly Detection**: Statistical analysis to identify unusual cost spikes (2-3 standard deviations)
- **Idle Resource Detection**: Find underutilized deployments wasting budget (<20% utilization)
- **Historical Trends**: 30/60/90-day cost analysis and comparisons
- **Team/Project/Namespace Views**: Multiple dimensions for cost visibility

### 📈 Advanced Reporting
- **Executive Summary**: High-level reports for leadership with key metrics, ROI, and recommendations
- **Team Reports**: Detailed cost and performance analysis per team with deployment breakdowns
- **Cost Forecasting**: Predict future costs using linear regression (30/60/90 days ahead)
- **ROI Analysis**: Calculate savings from optimization recommendations with payback period
- **Trend Analysis**: Week-over-week and month-over-month cost comparisons
- **Automated Reports**: API-driven reports for integration with BI tools and dashboards
- **Dashboard Integration**: New "Reports" tab with interactive visualizations

## 🎨 Dashboard Enhancements

### New Reports Tab
- **Executive Summary View**: Key metrics cards with efficiency score, costs, and savings
- **Cost Allocation View**: Team and namespace cost breakdowns with sortable tables
- **Cost Forecast View**: 30/60/90-day projections with confidence indicators
- **ROI Calculator**: Current vs optimized costs with savings breakdown
- **Trend Analysis View**: Historical data with week-over-week and month-over-month changes
- **Interactive Reports**: One-click switching between report types
- **Real-time Data**: Auto-refresh with cached API responses

## 🔧 API Endpoints

### Cost Allocation APIs
- `GET /api/cost/allocation/team?hours=24` - Costs grouped by team
- `GET /api/cost/allocation/namespace?hours=24` - Costs grouped by namespace
- `GET /api/cost/allocation/project?hours=24` - Costs grouped by project
- `GET /api/cost/anomalies` - Detect cost anomalies
- `GET /api/cost/idle-resources?threshold=0.2` - Idle/underutilized resources
- `GET /api/cost/pricing-info` - Auto-detected cloud pricing information

### Reporting APIs
- `GET /api/reports/executive-summary?days=30` - Executive summary report
- `GET /api/reports/team/{team}?days=30` - Team-specific report
- `GET /api/reports/forecast?days=90` - Cost forecast
- `GET /api/reports/roi` - ROI analysis
- `GET /api/reports/trends?days=30` - Trend analysis

## 📚 Documentation

### New Documentation
- **docs/COST_ALLOCATION.md**: Complete guide to cost allocation features
  - Label-based cost tagging
  - Chargeback/showback setup
  - Cost anomaly detection
  - Idle resource identification
  - API reference and examples
  - Integration guides (Grafana, Slack)

- **docs/REPORTING.md**: Advanced reporting guide
  - Executive summary reports
  - Team budget tracking
  - Cost forecasting for planning
  - ROI justification
  - Automated reporting scripts
  - Dashboard integration

### Updated Documentation
- **README.md**: 
  - Added Advanced Cost Allocation section
  - Added Advanced Reporting section
  - Updated API endpoints list
  - Added new documentation links
  - Updated version badge to 0.0.25

## 🧪 Testing

### New Tests
- **tests/test_cloud_pricing.py**: Comprehensive test suite for cloud pricing auto-detection
  - Provider detection tests (GCP/AWS/Azure)
  - Instance family extraction tests
  - Pricing lookup tests
  - Auto-detection workflow tests
  - Fallback behavior tests

- **tests/test_cost_allocation.py**: Comprehensive test suite for cost allocation
  - Cost tag extraction tests
  - Deployment cost calculation tests
  - Team/namespace/project cost aggregation tests
  - Cost anomaly detection tests
  - Idle resource detection tests

- **tests/test_reporting.py**: Comprehensive test suite for reporting
  - Executive summary generation tests
  - Team report generation tests
  - Cost forecast tests
  - ROI calculation tests
  - Trend analysis tests

## 🔧 Technical Changes

### Backend
- **src/cloud_pricing.py**: New module for cloud pricing auto-detection
  - `CloudPricingDetector` class with provider detection
  - GCP/AWS/Azure instance type recognition
  - Instance family pricing database
  - Auto-detection from node labels
  - Fallback to default pricing

- **src/cost_allocation.py**: New module for cost allocation
  - `CostAllocator` class with multi-dimensional cost tracking
  - Auto-pricing detection integration
  - Label-based cost tag extraction
  - Cost anomaly detection with statistical analysis
  - Idle resource identification
  - Historical cost trend analysis

- **src/reporting.py**: New module for advanced reporting
  - `ReportGenerator` class with multiple report types
  - Executive summary with key metrics and recommendations
  - Team-specific reports with deployment details
  - Cost forecasting using linear regression
  - ROI calculations with optimization breakdown
  - Trend analysis with WoW and MoM comparisons

### Dashboard
- **templates/dashboard.html**: Enhanced with Reports tab
  - New "Reports" tab button with chart icon
  - Interactive report type selector
  - Executive summary view with metric cards
  - Cost allocation tables (team/namespace)
  - Cost forecast with confidence indicators
  - ROI analysis with savings breakdown
  - Trend analysis with historical data
  - JavaScript functions for all report types

### Integration
- **src/dashboard.py**: Integrated cost allocation and reporting
  - Initialized `CostAllocator` and `ReportGenerator`
  - Added 10 new API endpoints for cost allocation and reporting
  - Error handling with graceful degradation
  - Caching support for performance

## 📦 Dependencies

No new dependencies added. All features use existing libraries.

## 🔄 Migration Notes

### From v0.0.24 to v0.0.25

**No breaking changes.** This is a feature addition release.

**New Features Available:**
1. Navigate to "Reports" tab in dashboard to view cost allocation and reports
2. Use new API endpoints for programmatic access to cost data
3. Add labels to deployments for automatic cost allocation

**Optional Configuration:**
- Add cost allocation labels to deployments:
  ```yaml
  labels:
    team: backend
    project: user-api
    environment: production
    cost-center: engineering
  ```

- Configure cost rates (optional, defaults provided):
  ```yaml
  COST_PER_VCPU_HOUR: "0.04"
  COST_PER_GB_MEMORY_HOUR: "0.005"
  ```

## 🐛 Bug Fixes

### v0.0.25-v5 (UI Improvements)
- **Fixed report tab highlighting**: Active button now highlights when switching between report types
- **Better error handling**: Show actual error messages from API instead of generic errors
- **Fixed cost allocation error**: Properly check for `.error` property in API responses
- Added `selectReport()` function to manage button active states
- Improved user experience in Reports tab

### v0.0.25-v4 (Dashboard Fix)
- **Fixed executive summary error**: Handle missing `scaling_events` table gracefully
- Check if table exists before querying to prevent SQL errors
- Return empty data when table doesn't exist yet
- Fixes "Error: Failed to load executive summary" in dashboard Reports tab
- All 172 tests passing (31% coverage)

### v0.0.25-v3 (Production Fix - CRITICAL)
- **Fixed AttributeError on startup**: Changed `config.get()` to `getattr()` for OperatorConfig dataclass
- OperatorConfig is a dataclass with attributes, not a dictionary
- This was causing crashes in production: `'OperatorConfig' object has no attribute 'get'`
- Updated test assertions for new default pricing (0.045/0.006)
- All 172 tests passing (31% coverage)

### v0.0.25-v2 (Test Fixes)
- Fixed test assertions for updated default pricing (0.045 vs 0.04)
- Lowered pricing threshold for micro instances (e2-micro at $0.0084/vCPU)
- Added proper mock for operator.config in dashboard tests
- Improved error handling for Mock objects in cost allocation
- All 172 tests passing (31% coverage, above 25% minimum)

## 🎨 UI/UX Improvements

- Added Reports tab with professional Material Design icons
- Interactive report type selector with one-click switching
- Color-coded metrics (green for savings, red for costs, yellow for warnings)
- Responsive grid layouts for metric cards
- Sortable tables for cost allocation data
- Clear visual hierarchy in reports
- Empty states with helpful messages

## 📊 Metrics & Monitoring

### New Metrics Available
- Team/project/namespace cost breakdowns
- Cost anomaly detection results
- Idle resource identification
- Cost forecast predictions
- ROI calculations
- Week-over-week and month-over-month trends

## 🔮 What's Next (v0.0.26)

Potential features for next release:
- VPA (Vertical Pod Autoscaler) integration
- Spot instance optimization recommendations
- Multi-cluster cost aggregation
- Budget alerts and notifications
- Cost allocation by custom labels
- PDF report generation
- Email report scheduling

## 🚀 Enterprise Features

This release adds enterprise-grade features:
- **Chargeback/Showback**: Bill teams for their infrastructure usage
- **Budget Tracking**: Monitor team spending against budgets
- **Cost Forecasting**: Plan future budgets with confidence
- **ROI Justification**: Prove value of optimization efforts
- **Executive Reporting**: Data-driven insights for leadership

---

## 📝 Full Changelog

**Features:**
- Advanced Cost Allocation with multi-dimensional tracking
- Advanced Reporting with executive summaries and forecasts
- Dashboard Reports tab with interactive visualizations
- 10 new API endpoints for cost allocation and reporting

**Improvements:**
- Enhanced dashboard with Reports tab
- Better cost visibility across teams and projects
- Automated cost anomaly detection
- Idle resource identification for savings

**Documentation:**
- New COST_ALLOCATION.md guide
- New REPORTING.md guide
- Updated README with new features
- API reference updates

**Testing:**
- New test suite for cost allocation
- New test suite for reporting
- Comprehensive unit tests for all new features

---

**Docker Images:**
```bash
# Pull the latest release
docker pull ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:v0.0.25

# Or use latest tag
docker pull ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:latest
```

**Helm Chart:**
```bash
helm upgrade smart-autoscaler ./helm/smart-autoscaler \
  --version 0.0.25 \
  --reuse-values
```

**Quick Update:**
```bash
# Update deployment
kubectl set image deployment/smart-autoscaler \
  smart-autoscaler=ghcr.io/phamngocsonls/enhanced-smart-k8s-autoscaler:v0.0.25 \
  -n autoscaler-system

# Or with Helm
helm upgrade smart-autoscaler ./helm/smart-autoscaler \
  --set image.tag=v0.0.25 \
  --reuse-values
```

---

**Version**: v0.0.25  
**Status**: ✅ Stable  
**Recommended for**: Production use
