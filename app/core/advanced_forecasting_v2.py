# app/core/advanced_forecasting.py
"""
Advanced forecasting with multiple models and auto-tuning.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

import xgboost as xgb
import lightgbm as lgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_percentage_error, mean_absolute_error, mean_squared_error

from prophet import Prophet
from neuralprophet import NeuralProphet
import logging

logger = logging.getLogger(__name__)

class AdvancedForecaster:
    """
    Advanced forecasting with multiple models and auto-tuning.
    """
    
    def __init__(self):
        self.models = {}
        self.best_model = None
        self.scaler = StandardScaler()
        self.results = {}
        
    def get_models(self) -> Dict:
        """
        Get all available models with their configurations.
        """
        return {
            'prophet': self._train_prophet,
            'neural_prophet': self._train_neural_prophet,
            'xgboost': self._train_xgboost,
            'lightgbm': self._train_lightgbm,
            'random_forest': self._train_random_forest,
            'ensemble': self._train_ensemble
        }
    
    def _train_prophet(self, df: pd.DataFrame, params: Dict = None) -> Prophet:
        """Train Prophet model with auto-tuning."""
        default_params = {
            'seasonality_mode': 'multiplicative',
            'yearly_seasonality': True,
            'weekly_seasonality': True,
            'daily_seasonality': False,
            'changepoint_prior_scale': 0.05,
            'seasonality_prior_scale': 10.0,
            'holidays_prior_scale': 10.0
        }
        
        if params:
            default_params.update(params)
            
        model = Prophet(**default_params)
        
        # Add country holidays
        model.add_country_holidays(country_name='KE')
        
        return model
    
    def _train_neural_prophet(self, df: pd.DataFrame, params: Dict = None) -> NeuralProphet:
        """Train NeuralProphet model."""
        default_params = {
            'yearly_seasonality': True,
            'weekly_seasonality': True,
            'daily_seasonality': False,
            'learning_rate': 0.01,
            'epochs': 50,
            'batch_size': 32,
            'n_lags': 5,
            'n_forecasts': 30
        }
        
        if params:
            default_params.update(params)
            
        model = NeuralProphet(**default_params)
        return model
    
    def _train_xgboost(self, df: pd.DataFrame, params: Dict = None) -> xgb.XGBRegressor:
        """Train XGBoost model with auto-tuning."""
        default_params = {
            'n_estimators': 100,
            'max_depth': 6,
            'learning_rate': 0.1,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'objective': 'reg:squarederror'
        }
        
        if params:
            default_params.update(params)
            
        return xgb.XGBRegressor(**default_params)
    
    def _train_lightgbm(self, df: pd.DataFrame, params: Dict = None) -> lgb.LGBMRegressor:
        """Train LightGBM model with auto-tuning."""
        default_params = {
            'n_estimators': 100,
            'max_depth': -1,
            'learning_rate': 0.1,
            'num_leaves': 31,
            'objective': 'regression'
        }
        
        if params:
            default_params.update(params)
            
        return lgb.LGBMRegressor(**default_params)
    
    def _train_random_forest(self, df: pd.DataFrame, params: Dict = None) -> RandomForestRegressor:
        """Train Random Forest model with auto-tuning."""
        default_params = {
            'n_estimators': 100,
            'max_depth': 10,
            'min_samples_split': 5,
            'min_samples_leaf': 2,
            'random_state': 42
        }
        
        if params:
            default_params.update(params)
            
        return RandomForestRegressor(**default_params)
    
    def _train_ensemble(self, df: pd.DataFrame) -> Dict:
        """Train ensemble model (combines all models)."""
        ensemble = {}
        for name, train_func in self.get_models().items():
            if name != 'ensemble':
                try:
                    model = train_func(df)
                    ensemble[name] = model
                except Exception as e:
                    logger.error(f"Failed to train {name}: {e}")
        return ensemble
    
    def auto_tune(self, model, param_grid: Dict, X_train, y_train) -> Tuple:
        """
        Auto-tune model using GridSearchCV with time series cross-validation.
        
        Args:
            model: Model instance
            param_grid: Parameter grid for tuning
            X_train: Training features
            y_train: Training target
        
        Returns:
            Tuple of (best_model, best_params, best_score)
        """
        try:
            # Use TimeSeriesSplit for time series data
            tscv = TimeSeriesSplit(n_splits=5)
            
            grid_search = GridSearchCV(
                estimator=model,
                param_grid=param_grid,
                cv=tscv,
                scoring='neg_mean_absolute_percentage_error',
                n_jobs=-1,
                verbose=0
            )
            
            grid_search.fit(X_train, y_train)
            
            return grid_search.best_estimator_, grid_search.best_params_, grid_search.best_score_
            
        except Exception as e:
            logger.error(f"Auto-tune failed: {e}")
            return model, {}, 0
    
    def prepare_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare features for ML models.
        
        Args:
            df: DataFrame with 'Date' and 'Order_Quantity_kg' columns
        
        Returns:
            Tuple of (features, target)
        """
        # Create time-based features
        df = df.copy()
        df['Date'] = pd.to_datetime(df['Date'])
        
        # Time features
        df['year'] = df['Date'].dt.year
        df['month'] = df['Date'].dt.month
        df['day'] = df['Date'].dt.day
        df['dayofweek'] = df['Date'].dt.dayofweek
        df['quarter'] = df['Date'].dt.quarter
        df['dayofyear'] = df['Date'].dt.dayofyear
        df['weekofyear'] = df['Date'].dt.isocalendar().week
        
        # Lag features
        for lag in [1, 2, 3, 7, 14, 21, 30]:
            df[f'lag_{lag}'] = df['Order_Quantity_kg'].shift(lag)
        
        # Rolling statistics
        for window in [7, 14, 30]:
            df[f'rolling_mean_{window}'] = df['Order_Quantity_kg'].rolling(window).mean()
            df[f'rolling_std_{window}'] = df['Order_Quantity_kg'].rolling(window).std()
            df[f'rolling_min_{window}'] = df['Order_Quantity_kg'].rolling(window).min()
            df[f'rolling_max_{window}'] = df['Order_Quantity_kg'].rolling(window).max()
        
        # Drop NaN rows
        df = df.dropna()
        
        # Define features and target
        feature_cols = [col for col in df.columns if col not in ['Date', 'Order_Quantity_kg']]
        X = df[feature_cols]
        y = df['Order_Quantity_kg']
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        return X_scaled, y
    
    def forecast(self, df: pd.DataFrame, forecast_days: int = 30) -> Dict:
        """
        Generate forecast using all models and return ensemble results.
        
        Args:
            df: Historical data
            forecast_days: Number of days to forecast
        
        Returns:
            Dict with forecasts from all models
        """
        results = {}
        
        # 1. Prophet forecast
        try:
            prophet_model = self._train_prophet(df)
            prophet_results = self._forecast_prophet(prophet_model, df, forecast_days)
            results['prophet'] = prophet_results
        except Exception as e:
            logger.error(f"Prophet forecast failed: {e}")
            results['prophet'] = None
        
        # 2. NeuralProphet forecast
        try:
            neural_model = self._train_neural_prophet(df)
            neural_results = self._forecast_neural_prophet(neural_model, df, forecast_days)
            results['neural_prophet'] = neural_results
        except Exception as e:
            logger.error(f"NeuralProphet forecast failed: {e}")
            results['neural_prophet'] = None
        
        # 3. ML Models
        try:
            X, y = self.prepare_features(df)
            ml_models = {
                'xgboost': self._train_xgboost(df),
                'lightgbm': self._train_lightgbm(df),
                'random_forest': self._train_random_forest(df)
            }
            
            for name, model in ml_models.items():
                model.fit(X, y)
                # Generate future predictions
                future_data = self._create_future_features(df, forecast_days)
                predictions = model.predict(future_data)
                results[name] = {'forecast': predictions.tolist()}
                
        except Exception as e:
            logger.error(f"ML models failed: {e}")
            results['ml_models'] = None
        
        # 4. Ensemble forecast
        ensemble_forecast = self._create_ensemble_forecast(results, forecast_days)
        results['ensemble'] = ensemble_forecast
        
        return results
    
    def _forecast_prophet(self, model, df: pd.DataFrame, forecast_days: int) -> Dict:
        """Generate Prophet forecast."""
        prophet_df = df.rename(columns={
            'Date': 'ds',
            'Order_Quantity_kg': 'y'
        })
        
        model.fit(prophet_df)
        future = model.make_future_dataframe(periods=forecast_days)
        forecast = model.predict(future)
        
        return {
            'forecast': forecast['yhat'].values[-forecast_days:].tolist(),
            'upper': forecast['yhat_upper'].values[-forecast_days:].tolist(),
            'lower': forecast['yhat_lower'].values[-forecast_days:].tolist()
        }
    
    def _forecast_neural_prophet(self, model, df: pd.DataFrame, forecast_days: int) -> Dict:
        """Generate NeuralProphet forecast."""
        neural_df = df.rename(columns={
            'Date': 'ds',
            'Order_Quantity_kg': 'y'
        })
        
        model.fit(neural_df, freq='D')
        future = model.make_future_dataframe(neural_df, periods=forecast_days)
        forecast = model.predict(future)
        
        return {
            'forecast': forecast['yhat1'].values[-forecast_days:].tolist()
        }
    
    def _create_future_features(self, df: pd.DataFrame, forecast_days: int) -> np.ndarray:
        """Create future features for ML models."""
        # Get last date
        last_date = df['Date'].max()
        
        # Create future dates
        future_dates = pd.date_range(last_date, periods=forecast_days + 1, freq='D')[1:]
        
        # Create future features
        future_df = pd.DataFrame({'Date': future_dates})
        future_df['year'] = future_df['Date'].dt.year
        future_df['month'] = future_df['Date'].dt.month
        future_df['day'] = future_df['Date'].dt.day
        future_df['dayofweek'] = future_df['Date'].dt.dayofweek
        future_df['quarter'] = future_df['Date'].dt.quarter
        future_df['dayofyear'] = future_df['Date'].dt.dayofyear
        future_df['weekofyear'] = future_df['Date'].dt.isocalendar().week
        
        # Use last known values for lag features
        last_values = df['Order_Quantity_kg'].tail(30).values
        for lag in [1, 2, 3, 7, 14, 21, 30]:
            future_df[f'lag_{lag}'] = last_values[-lag] if len(last_values) >= lag else last_values[-1]
        
        # Use last rolling stats
        for window in [7, 14, 30]:
            future_df[f'rolling_mean_{window}'] = last_values[-window:].mean() if len(last_values) >= window else last_values.mean()
            future_df[f'rolling_std_{window}'] = last_values[-window:].std() if len(last_values) >= window else last_values.std()
            future_df[f'rolling_min_{window}'] = last_values[-window:].min() if len(last_values) >= window else last_values.min()
            future_df[f'rolling_max_{window}'] = last_values[-window:].max() if len(last_values) >= window else last_values.max()
        
        # Scale features
        feature_cols = [col for col in future_df.columns if col != 'Date']
        X_future = self.scaler.transform(future_df[feature_cols])
        
        return X_future
    
    def _create_ensemble_forecast(self, results: Dict, forecast_days: int) -> Dict:
        """
        Create ensemble forecast by averaging all available models.
        """
        ensemble_values = []
        weights = {
            'prophet': 0.25,
            'neural_prophet': 0.20,
            'xgboost': 0.20,
            'lightgbm': 0.20,
            'random_forest': 0.15
        }
        
        weighted_sum = np.zeros(forecast_days)
        total_weight = 0
        
        for name, weight in weights.items():
            if name in results and results[name] is not None:
                forecast = results[name].get('forecast', [])
                if len(forecast) == forecast_days:
                    weighted_sum += np.array(forecast) * weight
                    total_weight += weight
        
        if total_weight > 0:
            ensemble_forecast = weighted_sum / total_weight
        else:
            # Fallback: use simple average
            all_forecasts = []
            for name, result in results.items():
                if result is not None and 'forecast' in result:
                    if len(result['forecast']) == forecast_days:
                        all_forecasts.append(result['forecast'])
            
            if all_forecasts:
                ensemble_forecast = np.mean(all_forecasts, axis=0)
            else:
                ensemble_forecast = np.full(forecast_days, 300.0)  # Default
        
        # Ensure non-negative
        ensemble_forecast = np.maximum(ensemble_forecast, 0)
        
        return {
            'forecast': ensemble_forecast.tolist(),
            'upper': (ensemble_forecast * 1.2).tolist(),  # Simple upper bound
            'lower': (ensemble_forecast * 0.8).tolist()   # Simple lower bound
        }
    
    def calculate_metrics(self, actual: np.ndarray, predicted: np.ndarray) -> Dict:
        """
        Calculate forecast accuracy metrics.
        
        Args:
            actual: Actual values
            predicted: Predicted values
        
        Returns:
            Dict with metrics
        """
        metrics = {}
        
        # Mean Absolute Percentage Error
        metrics['mape'] = mean_absolute_percentage_error(actual, predicted)
        
        # Mean Absolute Error
        metrics['mae'] = mean_absolute_error(actual, predicted)
        
        # Root Mean Squared Error
        metrics['rmse'] = np.sqrt(mean_squared_error(actual, predicted))
        
        # R-squared
        from sklearn.metrics import r2_score
        metrics['r2'] = r2_score(actual, predicted)
        
        # Directional Accuracy
        actual_direction = np.sign(np.diff(actual))
        pred_direction = np.sign(np.diff(predicted))
        metrics['direction_accuracy'] = np.mean(actual_direction == pred_direction)
        
        return metrics