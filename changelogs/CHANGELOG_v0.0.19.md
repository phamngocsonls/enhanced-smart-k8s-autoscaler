# Changelog v0.0.19

**Release Date:** 2026-01-02

## 🎨 Dashboard Redesign
- Complete Grafana-inspired dark theme
- New color palette with improved contrast
- Monospace fonts for numeric values
- Animated status indicators
- Better panel structure with colored borders
- App version display in header

## 🔮 Prediction Accuracy Improvements
- Multiple prediction windows: 15min, 30min, 1hr, 2hr
- Model selection based on workload type (steady, bursty, periodic, growing)
- Ensemble ML predictions combining mean, trend, seasonal, and recent models
- Weekly pattern recognition
- Adaptive confidence based on historical accuracy

## 🧠 Auto-Tuning Enhancements
- Bayesian optimization for faster initial learning (3x faster convergence)
- Per-hour optimal targets (different for peak vs off-peak hours)
- Exploration vs exploitation balance (20%/80%)
- Automatic learning rate adjustment

## 📊 Pattern Detection Improvements
- 9 workload pattern types (added: weekly_seasonal, monthly_seasonal, event_driven)
- Weekly seasonal patterns (weekday vs weekend behavior)
- Monthly seasonal patterns (beginning/end of month spikes)
- Event-driven pattern detection (spike-decay analysis)
- Cross-deployment correlation detection with lag analysis
- Event marking API for external event correlation

## 💰 FinOps Enhancements
- New dedicated FinOps tab in dashboard
- Minimum CPU request enforcement (100m) for HPA stability
- Resource change detection with automatic HPA adjustment
- Low CPU request handling with higher HPA targets (85%+)
- Usage statistics display (avg, P50, P95, P99, max)
- YAML snippet generation for recommendations
- Visual comparison of current vs recommended configuration

## Files Changed
- `src/__init__.py` - Version bump
- `src/intelligence.py` - Enhanced PatternRecognizer, AutoTuner, CostOptimizer
- `src/pattern_detector.py` - Added seasonal patterns, correlation detection
- `src/dashboard.py` - Version API endpoint
- `templates/dashboard.html` - Complete Grafana-style redesign
- `README.md` - Updated documentation
