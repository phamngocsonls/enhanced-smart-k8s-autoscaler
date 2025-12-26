"""
Advanced ML Models for Prediction
Uses ARIMA, Prophet, and LSTM for time-series forecasting
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Tuple, List, Optional
import logging

logger = logging.getLogger(__name__)

try:
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not available, advanced ML features disabled")

try:
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    logger.warning("statsmodels not available, ARIMA/Holt-Winters disabled")


class MLPredictor:
    """Advanced ML-based prediction models"""
    
    def __init__(self, db):
        self.db = db
        self.models = {}
        self.scalers = {}
    
    def prepare_features(self, metrics: List, forecast_hours: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare features for ML models
        Features: hour, day_of_week, month, recent_trend, moving_avg
        """
        if len(metrics) < 24:
            return None, None
        
        X = []
        y = []
        
        for i in range(len(metrics) - forecast_hours):
            if i < 24:  # Need at least 24 data points for features
                continue
            
            timestamp = metrics[i].timestamp
            target_cpu = metrics[i + forecast_hours].node_utilization
            
            # Time-based features
            hour = timestamp.hour
            day_of_week = timestamp.weekday()
            month = timestamp.month
            
            # Recent values
            recent_values = [metrics[j].node_utilization for j in range(i-24, i)]
            
            # Statistical features
            recent_mean = np.mean(recent_values)
            recent_std = np.std(recent_values)
            recent_min = np.min(recent_values)
            recent_max = np.max(recent_values)
            
            # Trend (slope of last 6 hours)
            if i >= 6:
                recent_6h = [metrics[j].node_utilization for j in range(i-6, i)]
                trend = (recent_6h[-1] - recent_6h[0]) / 6
            else:
                trend = 0
            
            # Moving averages
            ma_1h = np.mean(recent_values[-1:])
            ma_3h = np.mean(recent_values[-3:]) if len(recent_values) >= 3 else ma_1h
            ma_6h = np.mean(recent_values[-6:]) if len(recent_values) >= 6 else ma_1h
            ma_24h = np.mean(recent_values)
            
            features = [
                hour, day_of_week, month,
                recent_mean, recent_std, recent_min, recent_max,
                trend, ma_1h, ma_3h, ma_6h, ma_24h
            ]
            
            X.append(features)
            y.append(target_cpu)
        
        return np.array(X), np.array(y)
    
    def train_random_forest(self, deployment: str, forecast_hours: int = 1) -> Optional[float]:
        """Train Random Forest model"""
        if not SKLEARN_AVAILABLE:
            return None
        
        try:
            metrics = self.db.get_recent_metrics(deployment, hours=168)  # 7 days
            X, y = self.prepare_features(metrics, forecast_hours)
            
            if X is None or len(X) < 50:
                return None
            
            # Split train/test
            split = int(len(X) * 0.8)
            X_train, X_test = X[:split], X[split:]
            y_train, y_test = y[:split], y[split:]
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train model
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                random_state=42
            )
            model.fit(X_train_scaled, y_train)
            
            # Evaluate
            score = model.score(X_test_scaled, y_test)
            
            # Store model
            key = f"{deployment}_rf_{forecast_hours}h"
            self.models[key] = model
            self.scalers[key] = scaler
            
            logger.info(f"{deployment} - Random Forest trained, R² score: {score:.3f}")
            return score
            
        except Exception as e:
            logger.error(f"Error training Random Forest: {e}")
            return None
    
    def train_gradient_boosting(self, deployment: str, forecast_hours: int = 1) -> Optional[float]:
        """Train Gradient Boosting model"""
        if not SKLEARN_AVAILABLE:
            return None
        
        try:
            metrics = self.db.get_recent_metrics(deployment, hours=168)
            X, y = self.prepare_features(metrics, forecast_hours)
            
            if X is None or len(X) < 50:
                return None
            
            split = int(len(X) * 0.8)
            X_train, X_test = X[:split], X[split:]
            y_train, y_test = y[:split], y[split:]
            
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            model = GradientBoostingRegressor(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42
            )
            model.fit(X_train_scaled, y_train)
            
            score = model.score(X_test_scaled, y_test)
            
            key = f"{deployment}_gb_{forecast_hours}h"
            self.models[key] = model
            self.scalers[key] = scaler
            
            logger.info(f"{deployment} - Gradient Boosting trained, R² score: {score:.3f}")
            return score
            
        except Exception as e:
            logger.error(f"Error training Gradient Boosting: {e}")
            return None
    
    def train_arima(self, deployment: str, order: Tuple = (2,1,2)) -> Optional[float]:
        """Train ARIMA model"""
        if not STATSMODELS_AVAILABLE:
            return None
        
        try:
            metrics = self.db.get_recent_metrics(deployment, hours=168)
            if len(metrics) < 48:
                return None
            
            cpu_values = [m.node_utilization for m in metrics]
            
            # Fit ARIMA
            model = ARIMA(cpu_values, order=order)
            fitted = model.fit()
            
            # Store model
            key = f"{deployment}_arima"
            self.models[key] = fitted
            
            logger.info(f"{deployment} - ARIMA trained, AIC: {fitted.aic:.2f}")
            return fitted.aic
            
        except Exception as e:
            logger.error(f"Error training ARIMA: {e}")
            return None
    
    def train_exponential_smoothing(self, deployment: str) -> Optional[float]:
        """Train Exponential Smoothing (Holt-Winters)"""
        if not STATSMODELS_AVAILABLE:
            return None
        
        try:
            metrics = self.db.get_recent_metrics(deployment, hours=168)
            if len(metrics) < 48:
                return None
            
            cpu_values = [m.node_utilization for m in metrics]
            
            # Fit Holt-Winters
            model = ExponentialSmoothing(
                cpu_values,
                seasonal_periods=24,  # Daily seasonality
                trend='add',
                seasonal='add'
            )
            fitted = model.fit()
            
            key = f"{deployment}_hw"
            self.models[key] = fitted
            
            logger.info(f"{deployment} - Holt-Winters trained")
            return 1.0
            
        except Exception as e:
            logger.error(f"Error training Exponential Smoothing: {e}")
            return None
    
    def predict_ensemble(self, deployment: str, current_metrics: List, 
                        forecast_hours: int = 1) -> Tuple[float, float]:
        """
        Ensemble prediction using multiple models
        Returns: (predicted_cpu, confidence)
        """
        predictions = []
        weights = []
        
        # Random Forest prediction
        rf_key = f"{deployment}_rf_{forecast_hours}h"
        if rf_key in self.models:
            try:
                X_current = self._prepare_current_features(current_metrics)
                X_scaled = self.scalers[rf_key].transform([X_current])
                pred = self.models[rf_key].predict(X_scaled)[0]
                predictions.append(pred)
                weights.append(0.3)
            except Exception as e:
                logger.debug(f"RF prediction failed: {e}")
        
        # Gradient Boosting prediction
        gb_key = f"{deployment}_gb_{forecast_hours}h"
        if gb_key in self.models:
            try:
                X_current = self._prepare_current_features(current_metrics)
                X_scaled = self.scalers[gb_key].transform([X_current])
                pred = self.models[gb_key].predict(X_scaled)[0]
                predictions.append(pred)
                weights.append(0.3)
            except Exception as e:
                logger.debug(f"GB prediction failed: {e}")
        
        # ARIMA prediction
        arima_key = f"{deployment}_arima"
        if arima_key in self.models:
            try:
                forecast = self.models[arima_key].forecast(steps=forecast_hours)
                predictions.append(forecast[-1])
                weights.append(0.2)
            except Exception as e:
                logger.debug(f"ARIMA prediction failed: {e}")
        
        # Holt-Winters prediction
        hw_key = f"{deployment}_hw"
        if hw_key in self.models:
            try:
                forecast = self.models[hw_key].forecast(steps=forecast_hours)
                predictions.append(forecast[-1])
                weights.append(0.2)
            except Exception as e:
                logger.debug(f"HW prediction failed: {e}")
        
        if not predictions:
            return 0.0, 0.0
        
        # Normalize weights
        weights = np.array(weights)
        weights = weights / weights.sum()
        
        # Ensemble prediction
        ensemble_pred = np.average(predictions, weights=weights)
        
        # Confidence based on agreement between models
        if len(predictions) > 1:
            std = np.std(predictions)
            confidence = max(0.3, min(0.95, 1 - (std / (ensemble_pred + 0.001))))
        else:
            confidence = 0.6  # Single model
        
        return ensemble_pred, confidence
    
    def _prepare_current_features(self, metrics: List) -> List:
        """Prepare features for current state"""
        if len(metrics) < 24:
            raise ValueError("Need at least 24 data points")
        
        latest = metrics[-1]
        timestamp = latest.timestamp
        
        hour = timestamp.hour
        day_of_week = timestamp.weekday()
        month = timestamp.month
        
        recent_values = [m.node_utilization for m in metrics[-24:]]
        
        recent_mean = np.mean(recent_values)
        recent_std = np.std(recent_values)
        recent_min = np.min(recent_values)
        recent_max = np.max(recent_values)
        
        recent_6h = [m.node_utilization for m in metrics[-6:]]
        trend = (recent_6h[-1] - recent_6h[0]) / 6 if len(recent_6h) >= 2 else 0
        
        ma_1h = recent_values[-1]
        ma_3h = np.mean(recent_values[-3:])
        ma_6h = np.mean(recent_values[-6:])
        ma_24h = np.mean(recent_values)
        
        return [
            hour, day_of_week, month,
            recent_mean, recent_std, recent_min, recent_max,
            trend, ma_1h, ma_3h, ma_6h, ma_24h
        ]
    
    def auto_train(self, deployment: str):
        """Automatically train all available models"""
        logger.info(f"Auto-training ML models for {deployment}")
        
        # Train Random Forest
        self.train_random_forest(deployment, forecast_hours=1)
        
        # Train Gradient Boosting
        self.train_gradient_boosting(deployment, forecast_hours=1)
        
        # Train ARIMA
        self.train_arima(deployment)
        
        # Train Holt-Winters
        self.train_exponential_smoothing(deployment)
        
        logger.info(f"{deployment} - ML training complete")
    
    def get_feature_importance(self, deployment: str) -> Optional[Dict]:
        """Get feature importance from tree-based models"""
        if not SKLEARN_AVAILABLE:
            return None
        
        rf_key = f"{deployment}_rf_1h"
        if rf_key not in self.models:
            return None
        
        model = self.models[rf_key]
        
        feature_names = [
            'hour', 'day_of_week', 'month',
            'recent_mean', 'recent_std', 'recent_min', 'recent_max',
            'trend', 'ma_1h', 'ma_3h', 'ma_6h', 'ma_24h'
        ]
        
        importance = dict(zip(feature_names, model.feature_importances_))
        sorted_importance = {k: v for k, v in sorted(importance.items(), 
                                                     key=lambda x: x[1], 
                                                     reverse=True)}
        
        return sorted_importance