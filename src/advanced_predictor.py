"""
Advanced Predictive Scaling Module
Sophisticated ML models for CPU/Memory prediction

Features:
- ARIMA-based time series forecasting
- Exponential Smoothing (Holt-Winters)
- Prophet-like decomposition (trend + seasonality)
- Adaptive model selection per workload
- Confidence intervals for predictions
- Model performance tracking
"""

import logging
import statistics
from typing import Dict, List, Optional, Tuple, NamedTuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)

# Try to import advanced ML libraries
try:
    from scipy import stats
    from scipy.optimize import minimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy not available - some advanced features disabled")

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.seasonal import seasonal_decompose
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    logger.warning("statsmodels not available - using fallback models")

try:
    from sklearn.linear_model import Ridge, LinearRegression
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("sklearn not available - using numpy fallback")


class PredictionModel(Enum):
    """Available prediction models"""
    MEAN = "mean"                    # Simple historical mean
    TREND = "trend"                  # Linear trend
    SEASONAL = "seasonal"            # Weekly/daily seasonality
    HOLT_WINTERS = "holt_winters"    # Exponential smoothing
    ARIMA = "arima"                  # ARIMA time series
    ENSEMBLE = "ensemble"            # Weighted ensemble
    PROPHET_LIKE = "prophet_like"    # Trend + multi-seasonality


@dataclass
class PredictionResult:
    """Result of a prediction"""
    predicted_value: float
    confidence: float
    lower_bound: float
    upper_bound: float
    model_used: str
    reasoning: str
    components: Dict[str, float] = field(default_factory=dict)


@dataclass
class ModelPerformance:
    """Track model performance per deployment"""
    total_predictions: int = 0
    accurate_predictions: int = 0
    mape: float = 0.0  # Mean Absolute Percentage Error
    rmse: float = 0.0  # Root Mean Square Error
    last_updated: datetime = field(default_factory=datetime.now)


class AdvancedPredictor:
    """
    Advanced CPU/Memory predictor with multiple ML models.
    
    Supports:
    - Multiple prediction windows (15min, 30min, 1hr, 2hr, 4hr)
    - Adaptive model selection based on workload characteristics
    - Confidence intervals for predictions
    - Model performance tracking and auto-selection
    """
    
    def __init__(self, db):
        """
        Initialize advanced predictor.
        
        Args:
            db: TimeSeriesDatabase instance
        """
        self.db = db
        
        # Prediction windows
        self.prediction_windows = {
            '15min': 15,
            '30min': 30,
            '1hr': 60,
            '2hr': 120,
            '4hr': 240
        }
        
        # Model performance tracking per deployment
        self.model_performance: Dict[str, Dict[str, ModelPerformance]] = defaultdict(
            lambda: defaultdict(ModelPerformance)
        )
        
        # Cache for decomposed components
        self._decomposition_cache: Dict[str, Tuple[Dict, datetime]] = {}
        self._cache_ttl = 3600  # 1 hour
        
        # Minimum samples for different models
        self.min_samples = {
            PredictionModel.MEAN: 10,
            PredictionModel.TREND: 20,
            PredictionModel.SEASONAL: 168,  # 1 week at hourly
            PredictionModel.HOLT_WINTERS: 48,
            PredictionModel.ARIMA: 100,
            PredictionModel.PROPHET_LIKE: 168
        }
        
        logger.info(
            f"AdvancedPredictor initialized - "
            f"scipy={SCIPY_AVAILABLE}, statsmodels={STATSMODELS_AVAILABLE}, sklearn={SKLEARN_AVAILABLE}"
        )
    
    def predict(
        self,
        deployment: str,
        window: str = '1hr',
        metric: str = 'cpu'
    ) -> PredictionResult:
        """
        Make a prediction for the specified deployment and window.
        
        Args:
            deployment: Deployment name
            window: Prediction window ('15min', '30min', '1hr', '2hr', '4hr')
            metric: 'cpu' or 'memory'
        
        Returns:
            PredictionResult with prediction and confidence
        """
        minutes_ahead = self.prediction_windows.get(window, 60)
        
        # Get historical data
        hours_needed = max(168, minutes_ahead // 60 * 4)  # At least 1 week or 4x window
        metrics = self.db.get_recent_metrics(deployment, hours=hours_needed)
        
        if len(metrics) < 10:
            return PredictionResult(
                predicted_value=0.0,
                confidence=0.0,
                lower_bound=0.0,
                upper_bound=0.0,
                model_used="none",
                reasoning=f"Insufficient data ({len(metrics)} samples, need 10+)"
            )
        
        # Extract values based on metric type
        if metric == 'cpu':
            values = [m.pod_cpu_usage for m in metrics if m.pod_cpu_usage > 0]
        else:
            values = [m.memory_usage for m in metrics if m.memory_usage > 0]
        
        if len(values) < 10:
            return PredictionResult(
                predicted_value=0.0,
                confidence=0.0,
                lower_bound=0.0,
                upper_bound=0.0,
                model_used="none",
                reasoning=f"Insufficient {metric} data ({len(values)} samples)"
            )
        
        # Get timestamps for seasonality
        timestamps = [m.timestamp for m in metrics if (
            m.pod_cpu_usage > 0 if metric == 'cpu' else m.memory_usage > 0
        )]
        
        # Select best model based on data characteristics and past performance
        best_model = self._select_best_model(deployment, values, timestamps)
        
        # Make prediction using selected model
        result = self._predict_with_model(
            deployment, values, timestamps, minutes_ahead, best_model
        )
        
        return result
    
    def predict_all_windows(
        self,
        deployment: str,
        metric: str = 'cpu'
    ) -> Dict[str, PredictionResult]:
        """
        Make predictions for all time windows.
        
        Args:
            deployment: Deployment name
            metric: 'cpu' or 'memory'
        
        Returns:
            Dict mapping window name to PredictionResult
        """
        results = {}
        for window in self.prediction_windows:
            results[window] = self.predict(deployment, window, metric)
        return results
    
    def _select_best_model(
        self,
        deployment: str,
        values: List[float],
        timestamps: List[datetime]
    ) -> PredictionModel:
        """
        Select the best model based on data characteristics and past performance.
        
        Args:
            deployment: Deployment name
            values: Historical values
            timestamps: Corresponding timestamps
        
        Returns:
            Best PredictionModel to use
        """
        n_samples = len(values)
        
        # Check past model performance
        perf = self.model_performance.get(deployment, {})
        if perf:
            # Find model with best accuracy (if we have enough data)
            best_perf = None
            best_model = None
            for model_name, model_perf in perf.items():
                if model_perf.total_predictions >= 10:
                    accuracy = model_perf.accurate_predictions / model_perf.total_predictions
                    if best_perf is None or accuracy > best_perf:
                        best_perf = accuracy
                        best_model = model_name
            
            if best_model and best_perf > 0.7:
                logger.debug(f"{deployment} - Using historically best model: {best_model} (accuracy: {best_perf:.0%})")
                return PredictionModel(best_model)
        
        # Analyze data characteristics
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0
        cv = std / mean if mean > 0 else 0
        
        # Check for seasonality
        has_weekly = self._detect_seasonality(values, period=168) if n_samples >= 336 else False
        has_daily = self._detect_seasonality(values, period=24) if n_samples >= 48 else False
        
        # Check for trend
        has_trend = self._detect_trend(values)
        
        # Model selection logic
        if n_samples < 20:
            return PredictionModel.MEAN
        
        if cv < 0.1:  # Very steady workload
            return PredictionModel.MEAN
        
        if has_weekly or has_daily:
            if STATSMODELS_AVAILABLE and n_samples >= 168:
                return PredictionModel.PROPHET_LIKE
            elif STATSMODELS_AVAILABLE and n_samples >= 48:
                return PredictionModel.HOLT_WINTERS
            else:
                return PredictionModel.SEASONAL
        
        if has_trend:
            if STATSMODELS_AVAILABLE and n_samples >= 100:
                return PredictionModel.ARIMA
            else:
                return PredictionModel.TREND
        
        # Default to ensemble for complex patterns
        if n_samples >= 50:
            return PredictionModel.ENSEMBLE
        
        return PredictionModel.TREND
    
    def _detect_seasonality(self, values: List[float], period: int) -> bool:
        """Detect if data has seasonality at given period."""
        if len(values) < period * 2:
            return False
        
        try:
            arr = np.array(values[-period*3:] if len(values) > period*3 else values)
            
            # Autocorrelation at lag = period
            n = len(arr)
            if n < period + 10:
                return False
            
            mean = np.mean(arr)
            var = np.var(arr)
            if var == 0:
                return False
            
            # Calculate autocorrelation
            autocorr = np.correlate(arr - mean, arr - mean, mode='full')
            autocorr = autocorr[n-1:] / (var * n)
            
            if period < len(autocorr):
                # Check if autocorrelation at period is significant
                return autocorr[period] > 0.3
            
            return False
        except Exception as e:
            logger.debug(f"Error detecting seasonality: {e}")
            return False
    
    def _detect_trend(self, values: List[float]) -> bool:
        """Detect if data has a significant trend."""
        if len(values) < 20:
            return False
        
        try:
            # Compare first and last quarters
            n = len(values)
            q1 = statistics.mean(values[:n//4])
            q4 = statistics.mean(values[-n//4:])
            
            change = abs(q4 - q1) / q1 if q1 > 0 else 0
            return change > 0.15  # 15% change indicates trend
        except Exception:
            return False
    
    def _predict_with_model(
        self,
        deployment: str,
        values: List[float],
        timestamps: List[datetime],
        minutes_ahead: int,
        model: PredictionModel
    ) -> PredictionResult:
        """
        Make prediction using specified model.
        
        Args:
            deployment: Deployment name
            values: Historical values
            timestamps: Corresponding timestamps
            minutes_ahead: Minutes to predict ahead
            model: Model to use
        
        Returns:
            PredictionResult
        """
        try:
            if model == PredictionModel.MEAN:
                return self._predict_mean(values, minutes_ahead)
            elif model == PredictionModel.TREND:
                return self._predict_trend(values, minutes_ahead)
            elif model == PredictionModel.SEASONAL:
                return self._predict_seasonal(values, timestamps, minutes_ahead)
            elif model == PredictionModel.HOLT_WINTERS:
                return self._predict_holt_winters(values, minutes_ahead)
            elif model == PredictionModel.ARIMA:
                return self._predict_arima(values, minutes_ahead)
            elif model == PredictionModel.PROPHET_LIKE:
                return self._predict_prophet_like(values, timestamps, minutes_ahead)
            elif model == PredictionModel.ENSEMBLE:
                return self._predict_ensemble(deployment, values, timestamps, minutes_ahead)
            else:
                return self._predict_mean(values, minutes_ahead)
        except Exception as e:
            logger.warning(f"{deployment} - Model {model.value} failed: {e}, falling back to mean")
            return self._predict_mean(values, minutes_ahead)
    
    def _predict_mean(self, values: List[float], minutes_ahead: int) -> PredictionResult:
        """Simple mean prediction with confidence interval."""
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else mean * 0.1
        
        # Confidence decreases with prediction window
        base_confidence = min(0.9, len(values) / 100)
        window_penalty = 1 - (minutes_ahead / 480)  # Max 8hr penalty
        confidence = base_confidence * max(0.5, window_penalty)
        
        # 95% confidence interval
        z = 1.96
        margin = z * std / np.sqrt(len(values))
        
        return PredictionResult(
            predicted_value=mean,
            confidence=confidence,
            lower_bound=max(0, mean - margin),
            upper_bound=mean + margin,
            model_used="mean",
            reasoning=f"Historical mean: {mean:.2f} ± {margin:.2f}",
            components={'mean': mean, 'std': std}
        )
    
    def _predict_trend(self, values: List[float], minutes_ahead: int) -> PredictionResult:
        """Linear trend prediction."""
        n = len(values)
        x = np.arange(n)
        y = np.array(values)
        
        # Linear regression
        slope, intercept = np.polyfit(x, y, 1)
        
        # Predict future value
        future_x = n + (minutes_ahead / 10)  # Assuming ~10min intervals
        predicted = intercept + slope * future_x
        predicted = max(0, predicted)  # Can't be negative
        
        # Calculate R-squared for confidence
        y_pred = intercept + slope * x
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Confidence based on R-squared and window
        confidence = r_squared * (1 - minutes_ahead / 480)
        confidence = max(0.3, min(0.9, confidence))
        
        # Prediction interval
        std_err = np.sqrt(ss_res / (n - 2)) if n > 2 else np.std(values)
        margin = 1.96 * std_err * np.sqrt(1 + 1/n + (future_x - np.mean(x))**2 / np.sum((x - np.mean(x))**2))
        
        return PredictionResult(
            predicted_value=predicted,
            confidence=confidence,
            lower_bound=max(0, predicted - margin),
            upper_bound=predicted + margin,
            model_used="trend",
            reasoning=f"Linear trend: slope={slope:.4f}/interval, R²={r_squared:.2f}",
            components={'slope': slope, 'intercept': intercept, 'r_squared': r_squared}
        )
    
    def _predict_seasonal(
        self,
        values: List[float],
        timestamps: List[datetime],
        minutes_ahead: int
    ) -> PredictionResult:
        """Seasonal prediction based on hour-of-day and day-of-week."""
        # Build hourly patterns by day of week
        patterns: Dict[int, Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))
        
        for ts, val in zip(timestamps, values):
            dow = ts.weekday()
            hour = ts.hour
            patterns[dow][hour].append(val)
        
        # Target time
        target_time = datetime.now() + timedelta(minutes=minutes_ahead)
        target_dow = target_time.weekday()
        target_hour = target_time.hour
        
        # Get prediction for target time
        if target_dow in patterns and target_hour in patterns[target_dow]:
            hour_values = patterns[target_dow][target_hour]
            predicted = statistics.mean(hour_values)
            std = statistics.stdev(hour_values) if len(hour_values) > 1 else predicted * 0.1
            confidence = min(0.85, len(hour_values) / 10)
        else:
            # Fallback to overall mean for that hour
            all_hour_values = []
            for dow_patterns in patterns.values():
                if target_hour in dow_patterns:
                    all_hour_values.extend(dow_patterns[target_hour])
            
            if all_hour_values:
                predicted = statistics.mean(all_hour_values)
                std = statistics.stdev(all_hour_values) if len(all_hour_values) > 1 else predicted * 0.1
                confidence = min(0.7, len(all_hour_values) / 20)
            else:
                predicted = statistics.mean(values)
                std = statistics.stdev(values) if len(values) > 1 else predicted * 0.1
                confidence = 0.5
        
        margin = 1.96 * std
        
        return PredictionResult(
            predicted_value=predicted,
            confidence=confidence,
            lower_bound=max(0, predicted - margin),
            upper_bound=predicted + margin,
            model_used="seasonal",
            reasoning=f"Seasonal pattern for {target_time.strftime('%A %H:00')}",
            components={'target_dow': target_dow, 'target_hour': target_hour}
        )
    
    def _predict_holt_winters(self, values: List[float], minutes_ahead: int) -> PredictionResult:
        """Holt-Winters exponential smoothing prediction."""
        if not STATSMODELS_AVAILABLE:
            return self._predict_trend(values, minutes_ahead)
        
        try:
            # Determine seasonal period (24 for daily, 168 for weekly)
            n = len(values)
            if n >= 336:
                seasonal_period = 168  # Weekly
            elif n >= 48:
                seasonal_period = 24  # Daily
            else:
                seasonal_period = None
            
            arr = np.array(values)
            
            # Fit Holt-Winters model
            if seasonal_period and n >= seasonal_period * 2:
                model = ExponentialSmoothing(
                    arr,
                    seasonal_periods=seasonal_period,
                    trend='add',
                    seasonal='add',
                    damped_trend=True
                )
            else:
                model = ExponentialSmoothing(
                    arr,
                    trend='add',
                    damped_trend=True
                )
            
            fitted = model.fit(optimized=True)
            
            # Forecast
            steps = max(1, minutes_ahead // 10)  # Assuming ~10min intervals
            forecast = fitted.forecast(steps)
            predicted = float(forecast[-1])
            predicted = max(0, predicted)
            
            # Confidence from model fit
            sse = fitted.sse
            mse = sse / n if n > 0 else 0
            rmse = np.sqrt(mse)
            
            # Confidence based on fit quality
            cv = rmse / np.mean(arr) if np.mean(arr) > 0 else 1
            confidence = max(0.4, min(0.9, 1 - cv))
            
            margin = 1.96 * rmse
            
            return PredictionResult(
                predicted_value=predicted,
                confidence=confidence,
                lower_bound=max(0, predicted - margin),
                upper_bound=predicted + margin,
                model_used="holt_winters",
                reasoning=f"Exponential smoothing (seasonal={seasonal_period}), RMSE={rmse:.2f}",
                components={'rmse': rmse, 'seasonal_period': seasonal_period or 0}
            )
        
        except Exception as e:
            logger.debug(f"Holt-Winters failed: {e}")
            return self._predict_trend(values, minutes_ahead)
    
    def _predict_arima(self, values: List[float], minutes_ahead: int) -> PredictionResult:
        """ARIMA time series prediction."""
        if not STATSMODELS_AVAILABLE:
            return self._predict_trend(values, minutes_ahead)
        
        try:
            arr = np.array(values[-500:])  # Limit to last 500 points for speed
            
            # Simple ARIMA(1,1,1) - works well for most workloads
            model = ARIMA(arr, order=(1, 1, 1))
            fitted = model.fit()
            
            # Forecast
            steps = max(1, minutes_ahead // 10)
            forecast = fitted.forecast(steps=steps)
            predicted = float(forecast[-1])
            predicted = max(0, predicted)
            
            # Get confidence interval
            conf_int = fitted.get_forecast(steps=steps).conf_int(alpha=0.05)
            lower = float(conf_int.iloc[-1, 0])
            upper = float(conf_int.iloc[-1, 1])
            
            # Confidence from AIC
            aic = fitted.aic
            confidence = max(0.5, min(0.85, 1 - (aic / 10000)))
            
            return PredictionResult(
                predicted_value=predicted,
                confidence=confidence,
                lower_bound=max(0, lower),
                upper_bound=upper,
                model_used="arima",
                reasoning=f"ARIMA(1,1,1), AIC={aic:.1f}",
                components={'aic': aic}
            )
        
        except Exception as e:
            logger.debug(f"ARIMA failed: {e}")
            return self._predict_trend(values, minutes_ahead)
    
    def _predict_prophet_like(
        self,
        values: List[float],
        timestamps: List[datetime],
        minutes_ahead: int
    ) -> PredictionResult:
        """
        Prophet-like decomposition: trend + weekly seasonality + daily seasonality.
        Lightweight implementation without requiring Prophet library.
        """
        try:
            n = len(values)
            arr = np.array(values)
            
            # 1. Extract trend using moving average
            window = min(24, n // 4)
            if window < 3:
                window = 3
            trend = np.convolve(arr, np.ones(window)/window, mode='valid')
            trend = np.pad(trend, (window//2, window - window//2 - 1), mode='edge')
            
            # Detrended series
            detrended = arr - trend
            
            # 2. Extract weekly seasonality (if enough data)
            weekly_seasonal = np.zeros(n)
            if n >= 336:  # 2 weeks
                for i in range(n):
                    dow = timestamps[i].weekday()
                    hour = timestamps[i].hour
                    idx = dow * 24 + hour
                    # Average of same hour/day across weeks
                    same_slots = [j for j in range(n) if 
                                  timestamps[j].weekday() == dow and 
                                  timestamps[j].hour == hour]
                    if same_slots:
                        weekly_seasonal[i] = np.mean(detrended[same_slots])
            
            # 3. Extract daily seasonality
            daily_seasonal = np.zeros(n)
            if n >= 48:  # 2 days
                for i in range(n):
                    hour = timestamps[i].hour
                    same_hours = [j for j in range(n) if timestamps[j].hour == hour]
                    if same_hours:
                        daily_seasonal[i] = np.mean(detrended[same_hours] - weekly_seasonal[same_hours])
            
            # 4. Residual
            residual = detrended - weekly_seasonal - daily_seasonal
            residual_std = np.std(residual)
            
            # 5. Predict future
            target_time = datetime.now() + timedelta(minutes=minutes_ahead)
            target_dow = target_time.weekday()
            target_hour = target_time.hour
            
            # Trend projection (linear extrapolation)
            trend_slope = (trend[-1] - trend[0]) / n if n > 1 else 0
            future_trend = trend[-1] + trend_slope * (minutes_ahead / 10)
            
            # Weekly seasonality for target
            target_weekly_idx = target_dow * 24 + target_hour
            same_weekly = [i for i in range(n) if 
                          timestamps[i].weekday() == target_dow and 
                          timestamps[i].hour == target_hour]
            future_weekly = np.mean(weekly_seasonal[same_weekly]) if same_weekly else 0
            
            # Daily seasonality for target
            same_daily = [i for i in range(n) if timestamps[i].hour == target_hour]
            future_daily = np.mean(daily_seasonal[same_daily]) if same_daily else 0
            
            # Combine
            predicted = future_trend + future_weekly + future_daily
            predicted = max(0, predicted)
            
            # Confidence based on residual variance
            cv = residual_std / np.mean(arr) if np.mean(arr) > 0 else 1
            confidence = max(0.5, min(0.9, 1 - cv * 0.5))
            
            margin = 1.96 * residual_std
            
            return PredictionResult(
                predicted_value=predicted,
                confidence=confidence,
                lower_bound=max(0, predicted - margin),
                upper_bound=predicted + margin,
                model_used="prophet_like",
                reasoning=f"Decomposition: trend={future_trend:.2f}, weekly={future_weekly:.2f}, daily={future_daily:.2f}",
                components={
                    'trend': future_trend,
                    'weekly_seasonal': future_weekly,
                    'daily_seasonal': future_daily,
                    'residual_std': residual_std
                }
            )
        
        except Exception as e:
            logger.debug(f"Prophet-like failed: {e}")
            return self._predict_seasonal(values, timestamps, minutes_ahead)
    
    def _predict_ensemble(
        self,
        deployment: str,
        values: List[float],
        timestamps: List[datetime],
        minutes_ahead: int
    ) -> PredictionResult:
        """
        Ensemble prediction combining multiple models.
        Weights based on historical performance.
        """
        predictions = []
        
        # Get predictions from available models
        models_to_try = [
            (PredictionModel.MEAN, self._predict_mean, [values, minutes_ahead]),
            (PredictionModel.TREND, self._predict_trend, [values, minutes_ahead]),
            (PredictionModel.SEASONAL, self._predict_seasonal, [values, timestamps, minutes_ahead]),
        ]
        
        if STATSMODELS_AVAILABLE and len(values) >= 48:
            models_to_try.append(
                (PredictionModel.HOLT_WINTERS, self._predict_holt_winters, [values, minutes_ahead])
            )
        
        for model, func, args in models_to_try:
            try:
                result = func(*args)
                if result.confidence > 0.3:
                    # Get historical performance weight
                    perf = self.model_performance[deployment].get(model.value)
                    if perf and perf.total_predictions >= 5:
                        accuracy = perf.accurate_predictions / perf.total_predictions
                        weight = accuracy * result.confidence
                    else:
                        weight = result.confidence
                    
                    predictions.append((result, weight))
            except Exception as e:
                logger.debug(f"Ensemble model {model.value} failed: {e}")
        
        if not predictions:
            return self._predict_mean(values, minutes_ahead)
        
        # Weighted average
        total_weight = sum(w for _, w in predictions)
        if total_weight == 0:
            return predictions[0][0]
        
        ensemble_value = sum(r.predicted_value * w for r, w in predictions) / total_weight
        ensemble_lower = sum(r.lower_bound * w for r, w in predictions) / total_weight
        ensemble_upper = sum(r.upper_bound * w for r, w in predictions) / total_weight
        ensemble_confidence = sum(r.confidence * w for r, w in predictions) / total_weight
        
        models_used = [r.model_used for r, _ in predictions]
        
        return PredictionResult(
            predicted_value=ensemble_value,
            confidence=ensemble_confidence,
            lower_bound=max(0, ensemble_lower),
            upper_bound=ensemble_upper,
            model_used="ensemble",
            reasoning=f"Ensemble of {len(predictions)} models: {', '.join(models_used)}",
            components={'models': models_used, 'weights': [w for _, w in predictions]}
        )

    
    def validate_prediction(
        self,
        deployment: str,
        predicted: float,
        actual: float,
        model_used: str
    ):
        """
        Validate a prediction and update model performance.
        
        Args:
            deployment: Deployment name
            predicted: Predicted value
            actual: Actual value
            model_used: Model that made the prediction
        """
        # Calculate error
        error = abs(predicted - actual)
        pct_error = (error / actual * 100) if actual > 0 else 0
        
        # Update model performance
        perf = self.model_performance[deployment][model_used]
        perf.total_predictions += 1
        
        # Consider accurate if within 15%
        if pct_error < 15:
            perf.accurate_predictions += 1
        
        # Update MAPE (rolling average)
        if perf.mape == 0:
            perf.mape = pct_error
        else:
            perf.mape = (perf.mape * (perf.total_predictions - 1) + pct_error) / perf.total_predictions
        
        # Update RMSE
        if perf.rmse == 0:
            perf.rmse = error
        else:
            old_mse = perf.rmse ** 2
            new_mse = (old_mse * (perf.total_predictions - 1) + error ** 2) / perf.total_predictions
            perf.rmse = np.sqrt(new_mse)
        
        perf.last_updated = datetime.now()
        
        logger.debug(
            f"{deployment} - Validated {model_used}: predicted={predicted:.2f}, actual={actual:.2f}, "
            f"error={pct_error:.1f}%, accuracy={perf.accurate_predictions}/{perf.total_predictions}"
        )
    
    def get_model_performance(self, deployment: str) -> Dict[str, Dict]:
        """
        Get model performance statistics for a deployment.
        
        Args:
            deployment: Deployment name
        
        Returns:
            Dict mapping model name to performance stats
        """
        result = {}
        for model_name, perf in self.model_performance[deployment].items():
            if perf.total_predictions > 0:
                result[model_name] = {
                    'total_predictions': perf.total_predictions,
                    'accurate_predictions': perf.accurate_predictions,
                    'accuracy_rate': perf.accurate_predictions / perf.total_predictions * 100,
                    'mape': perf.mape,
                    'rmse': perf.rmse,
                    'last_updated': perf.last_updated.isoformat()
                }
        return result
    
    def get_best_model(self, deployment: str) -> Optional[str]:
        """
        Get the best performing model for a deployment.
        
        Args:
            deployment: Deployment name
        
        Returns:
            Name of best model or None
        """
        best_model = None
        best_accuracy = 0
        
        for model_name, perf in self.model_performance[deployment].items():
            if perf.total_predictions >= 10:
                accuracy = perf.accurate_predictions / perf.total_predictions
                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    best_model = model_name
        
        return best_model
    
    def predict_with_confidence_interval(
        self,
        deployment: str,
        window: str = '1hr',
        confidence_level: float = 0.95
    ) -> Tuple[float, float, float]:
        """
        Get prediction with confidence interval.
        
        Args:
            deployment: Deployment name
            window: Prediction window
            confidence_level: Confidence level (default 95%)
        
        Returns:
            Tuple of (predicted, lower_bound, upper_bound)
        """
        result = self.predict(deployment, window)
        
        # Adjust bounds based on confidence level
        if confidence_level != 0.95:
            # Z-scores for common confidence levels
            z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
            z = z_scores.get(confidence_level, 1.96)
            
            # Recalculate bounds
            margin = (result.upper_bound - result.predicted_value) / 1.96 * z
            lower = max(0, result.predicted_value - margin)
            upper = result.predicted_value + margin
            return result.predicted_value, lower, upper
        
        return result.predicted_value, result.lower_bound, result.upper_bound
    
    def get_prediction_summary(self, deployment: str) -> Dict:
        """
        Get comprehensive prediction summary for a deployment.
        
        Args:
            deployment: Deployment name
        
        Returns:
            Dict with predictions, model performance, and recommendations
        """
        # Get predictions for all windows
        predictions = self.predict_all_windows(deployment)
        
        # Get model performance
        model_perf = self.get_model_performance(deployment)
        
        # Best model
        best_model = self.get_best_model(deployment)
        
        # Format predictions
        formatted_predictions = {}
        for window, result in predictions.items():
            formatted_predictions[window] = {
                'predicted': round(result.predicted_value, 2),
                'confidence': round(result.confidence * 100, 1),
                'lower_bound': round(result.lower_bound, 2),
                'upper_bound': round(result.upper_bound, 2),
                'model': result.model_used,
                'reasoning': result.reasoning
            }
        
        # Determine overall prediction quality
        avg_confidence = statistics.mean([r.confidence for r in predictions.values()])
        if avg_confidence > 0.8:
            quality = "excellent"
        elif avg_confidence > 0.6:
            quality = "good"
        elif avg_confidence > 0.4:
            quality = "moderate"
        else:
            quality = "low"
        
        return {
            'deployment': deployment,
            'predictions': formatted_predictions,
            'model_performance': model_perf,
            'best_model': best_model,
            'prediction_quality': quality,
            'average_confidence': round(avg_confidence * 100, 1),
            'timestamp': datetime.now().isoformat()
        }


class PredictiveScaler:
    """
    High-level predictive scaling controller.
    
    TRUE PRE-SCALING: Instead of just adjusting HPA targets (which only makes
    scaling more sensitive), this calculates the actual number of pods needed
    and recommends scaling NOW before traffic arrives.
    
    How it works:
    1. Predict CPU usage for future time windows
    2. Calculate pods needed: current_pods * (predicted_cpu / target_cpu)
    3. Recommend scaling to that pod count NOW
    4. Pods are ready and warm when traffic arrives
    """
    
    def __init__(self, predictor: AdvancedPredictor):
        """
        Initialize predictive scaler.
        
        Args:
            predictor: AdvancedPredictor instance
        """
        self.predictor = predictor
        
        # Thresholds for scaling decisions
        self.scale_up_threshold = 80.0  # Predict > 80% -> pre-scale up
        self.scale_down_threshold = 40.0  # Predict < 40% -> consider scale down
        self.confidence_threshold = 0.6  # Minimum confidence to act
        
        # Cooldown tracking
        self.last_action: Dict[str, Tuple[str, datetime]] = {}
        self.cooldown_minutes = 15
        
        # Safety limits
        self.max_scale_factor = 3.0  # Max 3x current pods
        self.min_scale_factor = 0.5  # Min 50% of current pods
    
    def calculate_required_replicas(
        self,
        current_replicas: int,
        current_cpu: float,
        predicted_cpu: float,
        target_cpu: float,
        min_replicas: int = 1,
        max_replicas: int = 100
    ) -> int:
        """
        Calculate the number of replicas needed to handle predicted load.
        
        Formula: required = current_replicas * (predicted_cpu / target_cpu)
        
        Example:
        - Current: 3 pods at 50% CPU, target 70%
        - Predicted: 90% CPU in 1 hour
        - Required: 3 * (90 / 70) = 3.86 → 4 pods
        
        Args:
            current_replicas: Current number of pods
            current_cpu: Current CPU utilization %
            predicted_cpu: Predicted CPU utilization %
            target_cpu: HPA target CPU %
            min_replicas: HPA minimum replicas
            max_replicas: HPA maximum replicas
        
        Returns:
            Recommended number of replicas
        """
        if current_replicas <= 0 or target_cpu <= 0:
            return current_replicas
        
        # Calculate scale factor based on predicted vs target
        scale_factor = predicted_cpu / target_cpu
        
        # Apply safety limits
        scale_factor = max(self.min_scale_factor, min(self.max_scale_factor, scale_factor))
        
        # Calculate required replicas
        required = int(np.ceil(current_replicas * scale_factor))
        
        # Respect HPA limits
        required = max(min_replicas, min(max_replicas, required))
        
        return required
    
    def get_scaling_recommendation(
        self,
        deployment: str,
        current_cpu: float,
        current_hpa_target: float,
        current_replicas: int = 1,
        min_replicas: int = 1,
        max_replicas: int = 100
    ) -> Dict:
        """
        Get scaling recommendation based on predictions.
        
        TRUE PRE-SCALING: Returns recommended replica count, not just HPA target.
        
        Args:
            deployment: Deployment name
            current_cpu: Current CPU utilization %
            current_hpa_target: Current HPA target %
            current_replicas: Current number of pods
            min_replicas: HPA minimum replicas
            max_replicas: HPA maximum replicas
        
        Returns:
            Dict with recommendation including:
            - action: 'pre_scale_up', 'scale_down', or 'maintain'
            - recommended_replicas: Number of pods to scale to NOW
            - reason: Explanation
        """
        # Get predictions for multiple windows
        predictions = self.predictor.predict_all_windows(deployment)
        
        # Check cooldown
        if deployment in self.last_action:
            last_action, last_time = self.last_action[deployment]
            if (datetime.now() - last_time).total_seconds() < self.cooldown_minutes * 60:
                return {
                    'action': 'maintain',
                    'reason': f'In cooldown period (last action: {last_action})',
                    'current_replicas': current_replicas,
                    'recommended_replicas': current_replicas,
                    'predictions': {k: v.predicted_value for k, v in predictions.items()}
                }
        
        # Analyze predictions - find the highest confident prediction above threshold
        best_scale_up = None
        best_scale_down = None
        
        for window, result in predictions.items():
            if result.confidence < self.confidence_threshold:
                continue
            
            if result.predicted_value > self.scale_up_threshold:
                if best_scale_up is None or result.confidence > best_scale_up[1].confidence:
                    best_scale_up = (window, result)
            elif result.predicted_value < self.scale_down_threshold:
                if best_scale_down is None or result.confidence > best_scale_down[1].confidence:
                    best_scale_down = (window, result)
        
        # Prioritize scale-up (safety first)
        if best_scale_up:
            window, result = best_scale_up
            
            # Calculate required replicas for predicted load
            required_replicas = self.calculate_required_replicas(
                current_replicas=current_replicas,
                current_cpu=current_cpu,
                predicted_cpu=result.predicted_value,
                target_cpu=current_hpa_target,
                min_replicas=min_replicas,
                max_replicas=max_replicas
            )
            
            # Only recommend if we need more pods
            if required_replicas > current_replicas:
                return {
                    'action': 'pre_scale_up',
                    'reason': f'Predicted {result.predicted_value:.1f}% CPU in {window}. '
                              f'Pre-scaling from {current_replicas} to {required_replicas} pods NOW.',
                    'current_replicas': current_replicas,
                    'recommended_replicas': required_replicas,
                    'scale_factor': round(required_replicas / current_replicas, 2),
                    'prediction_window': window,
                    'predicted_cpu': round(result.predicted_value, 1),
                    'confidence': round(result.confidence * 100, 1),
                    'model_used': result.model_used,
                    'upper_bound': round(result.upper_bound, 1),
                    'predictions': {k: {'value': round(v.predicted_value, 1), 
                                       'confidence': round(v.confidence * 100, 1)} 
                                   for k, v in predictions.items()}
                }
        
        # Scale down only if current CPU is also low
        if best_scale_down and current_cpu < 50:
            window, result = best_scale_down
            
            # Calculate reduced replicas
            required_replicas = self.calculate_required_replicas(
                current_replicas=current_replicas,
                current_cpu=current_cpu,
                predicted_cpu=result.predicted_value,
                target_cpu=current_hpa_target,
                min_replicas=min_replicas,
                max_replicas=max_replicas
            )
            
            # Only recommend if we can reduce pods
            if required_replicas < current_replicas:
                return {
                    'action': 'scale_down',
                    'reason': f'Predicted {result.predicted_value:.1f}% CPU in {window}, '
                              f'current {current_cpu:.1f}%. Can reduce to {required_replicas} pods.',
                    'current_replicas': current_replicas,
                    'recommended_replicas': required_replicas,
                    'scale_factor': round(required_replicas / current_replicas, 2),
                    'prediction_window': window,
                    'predicted_cpu': round(result.predicted_value, 1),
                    'confidence': round(result.confidence * 100, 1),
                    'model_used': result.model_used,
                    'predictions': {k: {'value': round(v.predicted_value, 1), 
                                       'confidence': round(v.confidence * 100, 1)} 
                                   for k, v in predictions.items()}
                }
        
        return {
            'action': 'maintain',
            'reason': 'No significant changes predicted or current state is optimal',
            'current_replicas': current_replicas,
            'recommended_replicas': current_replicas,
            'predictions': {k: {'value': round(v.predicted_value, 1), 
                               'confidence': round(v.confidence * 100, 1)} 
                           for k, v in predictions.items()}
        }
    
    def record_action(self, deployment: str, action: str):
        """Record that an action was taken for cooldown tracking."""
        self.last_action[deployment] = (action, datetime.now())
    
    def should_enable_predictive(self, deployment: str) -> Tuple[bool, str]:
        """
        Determine if predictive scaling should be enabled for a deployment.
        
        Args:
            deployment: Deployment name
        
        Returns:
            Tuple of (should_enable, reason)
        """
        # Get model performance
        perf = self.predictor.get_model_performance(deployment)
        
        if not perf:
            return False, "No prediction history yet"
        
        # Check if any model has good accuracy
        best_accuracy = 0
        best_model = None
        for model, stats in perf.items():
            if stats['total_predictions'] >= 10:
                if stats['accuracy_rate'] > best_accuracy:
                    best_accuracy = stats['accuracy_rate']
                    best_model = model
        
        if best_accuracy >= 70:
            return True, f"Good prediction accuracy ({best_accuracy:.0f}% with {best_model})"
        elif best_accuracy >= 50:
            return True, f"Moderate prediction accuracy ({best_accuracy:.0f}%), monitoring"
        else:
            return False, f"Low prediction accuracy ({best_accuracy:.0f}%), disabled"
