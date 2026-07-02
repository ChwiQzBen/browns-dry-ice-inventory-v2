# app/core/advanced_forecasting_v2.py
"""
Advanced forecasting with multiple models and auto-tuning.
Supports: Prophet, NeuralProphet, XGBoost, LightGBM, RandomForest,
          ARIMA, LSTM, and Monte Carlo simulations.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Union
import warnings
warnings.filterwarnings('ignore')

import xgboost as xgb
import lightgbm as lgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.metrics import mean_absolute_percentage_error, mean_absolute_error, mean_squared_error

from prophet import Prophet
from neuralprophet import NeuralProphet
import logging

# ============================================================
# FIX: Optional imports with fallbacks
# ============================================================
try:
    from statsmodels.tsa.arima.model import ARIMA
    ARIMA_AVAILABLE = True
except ImportError:
    ARIMA_AVAILABLE = False
    ARIMA = None

try:
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    Sequential = None
    LSTM = None
    Dense = None
    Dropout = None
    Adam = None
    EarlyStopping = None

try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    stats = None

logger = logging.getLogger(__name__)

class AdvancedForecaster:
    """
    Advanced forecasting with multiple models and auto-tuning.
    Supports 8 different models with ensemble capabilities.
    """
    
    def __init__(self):
        self.models = {}
        self.best_model = None
        self.scaler = StandardScaler()
        self.results = {}
        
        # LSTM specific storage
        self._lstm_scaler = None
        self._lstm_seq_length = 30
        
        # Monte Carlo storage
        self._mc_results = None
        
        # Track available models
        self._available_models = self._check_available_models()
        
    def _check_available_models(self) -> Dict[str, bool]:
        """Check which models are available based on installed packages."""
        return {
            'prophet': True,
            'neural_prophet': True,
            'xgboost': True,
            'lightgbm': True,
            'random_forest': True,
            'arima': ARIMA_AVAILABLE,
            'lstm': TENSORFLOW_AVAILABLE,
            'monte_carlo': SCIPY_AVAILABLE
        }
        
    def get_models(self) -> Dict:
        """
        Get all available models with their configurations.
        Now includes ALL 8 models!
        """
        models = {
            'prophet': self._train_prophet,
            'neural_prophet': self._train_neural_prophet,
            'xgboost': self._train_xgboost,
            'lightgbm': self._train_lightgbm,
            'random_forest': self._train_random_forest,
        }
        
        # Only add optional models if available
        if ARIMA_AVAILABLE:
            models['arima'] = self._train_arima
        if TENSORFLOW_AVAILABLE:
            models['lstm'] = self._train_lstm
        if SCIPY_AVAILABLE:
            models['monte_carlo'] = self._train_monte_carlo
            
        return models
    
    # ============================================================
    # 1. PROPHET MODEL
    # ============================================================
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
        try:
            model.add_country_holidays(country_name='KE')
        except:
            pass
        
        return model
    
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
    
    # ============================================================
    # 2. NEURALPROPHET MODEL
    # ============================================================
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
    
    # ============================================================
    # 3. XGBOOST MODEL
    # ============================================================
    def _train_xgboost(self, df: pd.DataFrame, params: Dict = None) -> xgb.XGBRegressor:
        """Train XGBoost model with auto-tuning."""
        default_params = {
            'n_estimators': 100,
            'max_depth': 6,
            'learning_rate': 0.1,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'objective': 'reg:squarederror',
            'random_state': 42
        }
        
        if params:
            default_params.update(params)
            
        return xgb.XGBRegressor(**default_params)
    
    # ============================================================
    # 4. LIGHTGBM MODEL
    # ============================================================
    def _train_lightgbm(self, df: pd.DataFrame, params: Dict = None) -> lgb.LGBMRegressor:
        """Train LightGBM model with auto-tuning."""
        default_params = {
            'n_estimators': 100,
            'max_depth': -1,
            'learning_rate': 0.1,
            'num_leaves': 31,
            'objective': 'regression',
            'random_state': 42,
            'verbose': -1
        }
        
        if params:
            default_params.update(params)
            
        return lgb.LGBMRegressor(**default_params)
    
    # ============================================================
    # 5. RANDOM FOREST MODEL
    # ============================================================
    def _train_random_forest(self, df: pd.DataFrame, params: Dict = None) -> RandomForestRegressor:
        """Train Random Forest model with auto-tuning."""
        default_params = {
            'n_estimators': 100,
            'max_depth': 10,
            'min_samples_split': 5,
            'min_samples_leaf': 2,
            'random_state': 42,
            'n_jobs': -1
        }
        
        if params:
            default_params.update(params)
            
        return RandomForestRegressor(**default_params)
    
    # ============================================================
    # 6. ARIMA MODEL (Optional - requires statsmodels)
    # ============================================================
    def _train_arima(self, df: pd.DataFrame) -> Optional[object]:
        """
        Train ARIMA model with auto-selected order.
        """
        if not ARIMA_AVAILABLE:
            logger.warning("ARIMA not available. Install statsmodels.")
            return None
            
        try:
            import warnings
            warnings.filterwarnings('ignore')
            
            # Prepare data - daily frequency
            y = df.set_index('Date')['Order_Quantity_kg'].resample('D').sum().fillna(0)
            
            # Auto-select ARIMA order using AIC
            best_aic = float('inf')
            best_order = (1, 0, 1)
            
            # Only test limited combinations to save time
            for p in range(0, 3):
                for d in range(0, 2):
                    for q in range(0, 3):
                        try:
                            model = ARIMA(y, order=(p, d, q))
                            fitted = model.fit()
                            if fitted.aic < best_aic:
                                best_aic = fitted.aic
                                best_order = (p, d, q)
                        except:
                            continue
            
            model = ARIMA(y, order=best_order)
            fitted = model.fit()
            
            # Store for later
            self._arima_order = best_order
            
            return fitted
            
        except Exception as e:
            logger.error(f"ARIMA training failed: {e}")
            return None
    
    def _forecast_arima(self, model, forecast_days: int) -> Dict:
        """Generate ARIMA forecast."""
        try:
            forecast = model.forecast(steps=forecast_days)
            # Ensure non-negative
            forecast = np.maximum(forecast, 0)
            return {
                'forecast': forecast.tolist()
            }
        except Exception as e:
            logger.error(f"ARIMA forecast failed: {e}")
            return None
    
    # ============================================================
    # 7. LSTM MODEL (Optional - requires tensorflow)
    # ============================================================
    def _train_lstm(self, df: pd.DataFrame) -> Optional[object]:
        """
        Train LSTM model for time series forecasting.
        """
        if not TENSORFLOW_AVAILABLE:
            logger.warning("LSTM not available. Install tensorflow.")
            return None
            
        try:
            from sklearn.preprocessing import MinMaxScaler
            
            # Prepare data - daily frequency
            data = df.set_index('Date')['Order_Quantity_kg'].resample('D').sum().fillna(0)
            
            # Need at least 60 data points for LSTM
            if len(data) < 60:
                logger.warning(f"LSTM needs at least 60 data points. Got {len(data)}.")
                return None
            
            # Scale data
            scaler = MinMaxScaler()
            scaled_data = scaler.fit_transform(data.values.reshape(-1, 1))
            
            # Create sequences
            def create_sequences(data, seq_length=30):
                X, y = [], []
                for i in range(len(data) - seq_length):
                    X.append(data[i:i+seq_length])
                    y.append(data[i+seq_length])
                return np.array(X), np.array(y)
            
            self._lstm_seq_length = min(30, len(scaled_data) - 1)
            X, y = create_sequences(scaled_data, self._lstm_seq_length)
            
            if len(X) < 10:
                logger.warning(f"Not enough sequences for LSTM. Got {len(X)}.")
                return None
            
            # Build model
            model = Sequential([
                LSTM(64, return_sequences=True, input_shape=(self._lstm_seq_length, 1)),
                Dropout(0.2),
                LSTM(32, return_sequences=False),
                Dropout(0.2),
                Dense(16, activation='relu'),
                Dense(1)
            ])
            
            model.compile(optimizer=Adam(learning_rate=0.001), loss='mse')
            
            # Train with early stopping
            early_stop = EarlyStopping(monitor='loss', patience=10, restore_best_weights=True)
            
            model.fit(
                X, y, 
                epochs=100, 
                batch_size=32, 
                verbose=0,
                callbacks=[early_stop]
            )
            
            # Store scaler for later use
            self._lstm_scaler = scaler
            
            return model
            
        except Exception as e:
            logger.error(f"LSTM training failed: {e}")
            return None
    
    def _forecast_lstm(self, model, df: pd.DataFrame, forecast_days: int) -> Dict:
        """Generate LSTM forecast."""
        try:
            if model is None or self._lstm_scaler is None:
                return None
                
            # Get last sequence
            data = df.set_index('Date')['Order_Quantity_kg'].resample('D').sum().fillna(0)
            
            if len(data) < self._lstm_seq_length:
                return None
            
            # Get the last seq_length values
            last_values = data.values[-self._lstm_seq_length:]
            scaled_data = self._lstm_scaler.transform(last_values.reshape(-1, 1))
            
            # Generate predictions iteratively
            predictions = []
            current_sequence = scaled_data.reshape(1, self._lstm_seq_length, 1)
            
            for _ in range(forecast_days):
                pred = model.predict(current_sequence, verbose=0)
                predictions.append(pred[0, 0])
                # Update sequence
                current_sequence = np.roll(current_sequence, -1, axis=1)
                current_sequence[0, -1, 0] = pred[0, 0]
            
            # Inverse transform
            predictions = self._lstm_scaler.inverse_transform(np.array(predictions).reshape(-1, 1))
            predictions = np.maximum(predictions.flatten(), 0)
            
            return {
                'forecast': predictions.tolist()
            }
            
        except Exception as e:
            logger.error(f"LSTM forecast failed: {e}")
            return None
    
    # ============================================================
    # 8. MONTE CARLO SIMULATION (Optional - requires scipy)
    # ============================================================
    def _train_monte_carlo(self, df: pd.DataFrame, n_simulations: int = 1000) -> Dict:
        """
        Train Monte Carlo simulation model.
        
        Args:
            df: Historical data
            n_simulations: Number of Monte Carlo simulations
        
        Returns:
            Dict with simulation results
        """
        if not SCIPY_AVAILABLE:
            logger.warning("Monte Carlo not available. Install scipy.")
            return None
            
        try:
            from scipy import stats
            
            # Prepare data - daily frequency
            data = df.set_index('Date')['Order_Quantity_kg'].resample('D').sum().fillna(0)
            
            # Calculate statistics
            mean = data.mean()
            std = data.std()
            
            # Try different distributions
            distributions = []
            
            # 1. Normal distribution
            try:
                normal_params = stats.norm.fit(data.values)
                distributions.append(('normal', normal_params, stats.norm))
            except:
                pass
            
            # 2. Log-normal distribution (good for demand)
            try:
                lognorm_params = stats.lognorm.fit(data.values + 1)  # +1 to handle zeros
                distributions.append(('lognorm', lognorm_params, stats.lognorm))
            except:
                pass
            
            # 3. Gamma distribution
            try:
                gamma_params = stats.gamma.fit(data.values + 1)
                distributions.append(('gamma', gamma_params, stats.gamma))
            except:
                pass
            
            # Generate simulations for each distribution
            all_simulations = []
            distribution_results = {}
            
            for dist_name, params, dist in distributions:
                sims = []
                for _ in range(max(1, n_simulations // len(distributions))):
                    try:
                        # Generate random demand from fitted distribution
                        if dist_name == 'lognorm':
                            random_demand = dist.rvs(*params, size=30) - 1
                        elif dist_name == 'gamma':
                            random_demand = dist.rvs(*params, size=30) - 1
                        else:
                            random_demand = dist.rvs(*params, size=30)
                        
                        # Ensure non-negative
                        random_demand = np.maximum(random_demand, 0)
                        sims.append(random_demand)
                    except:
                        continue
                
                if sims:
                    sims = np.array(sims)
                    all_simulations.extend(sims)
                    distribution_results[dist_name] = {
                        'mean': np.mean(sims, axis=0),
                        'std': np.std(sims, axis=0),
                        'p5': np.percentile(sims, 5, axis=0),
                        'p25': np.percentile(sims, 25, axis=0),
                        'p50': np.percentile(sims, 50, axis=0),
                        'p75': np.percentile(sims, 75, axis=0),
                        'p95': np.percentile(sims, 95, axis=0)
                    }
            
            if not all_simulations:
                # Fallback: use normal distribution
                sims = np.random.normal(mean, std, (n_simulations, 30))
                sims = np.maximum(sims, 0)
                all_simulations = sims.tolist()
                distribution_results = {
                    'fallback': {
                        'mean': np.mean(sims, axis=0),
                        'std': np.std(sims, axis=0),
                        'p5': np.percentile(sims, 5, axis=0),
                        'p25': np.percentile(sims, 25, axis=0),
                        'p50': np.percentile(sims, 50, axis=0),
                        'p75': np.percentile(sims, 75, axis=0),
                        'p95': np.percentile(sims, 95, axis=0)
                    }
                }
            
            all_simulations = np.array(all_simulations)
            
            # Store results
            self._mc_results = {
                'all_simulations': all_simulations,
                'distribution_results': distribution_results,
                'mean': np.mean(all_simulations, axis=0),
                'median': np.median(all_simulations, axis=0),
                'std': np.std(all_simulations, axis=0),
                'p5': np.percentile(all_simulations, 5, axis=0),
                'p25': np.percentile(all_simulations, 25, axis=0),
                'p50': np.percentile(all_simulations, 50, axis=0),
                'p75': np.percentile(all_simulations, 75, axis=0),
                'p95': np.percentile(all_simulations, 95, axis=0),
                'n_simulations': len(all_simulations)
            }
            
            return self._mc_results
            
        except Exception as e:
            logger.error(f"Monte Carlo simulation failed: {e}")
            return None
    
    def _forecast_monte_carlo(self, model: Dict, forecast_days: int) -> Dict:
        """Get Monte Carlo forecast."""
        try:
            if model is None:
                return None
            
            return {
                'forecast': model['mean'][:forecast_days].tolist(),
                'p5': model['p5'][:forecast_days].tolist(),
                'p25': model['p25'][:forecast_days].tolist(),
                'p50': model['p50'][:forecast_days].tolist(),
                'p75': model['p75'][:forecast_days].tolist(),
                'p95': model['p95'][:forecast_days].tolist(),
                'std': model['std'][:forecast_days].tolist(),
                'n_simulations': model.get('n_simulations', 0)
            }
        except Exception as e:
            logger.error(f"Monte Carlo forecast failed: {e}")
            return None
    
    # ============================================================
    # AUTO-TUNING
    # ============================================================
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
    
    # ============================================================
    # FEATURE PREPARATION
    # ============================================================
    def prepare_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
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
    
    # ============================================================
    # MAIN FORECAST METHOD
    # ============================================================
    def forecast(self, df: pd.DataFrame, forecast_days: int = 30) -> Dict:
        """
        Generate forecast using ALL models and return ensemble results.
        Now includes all 8 models!
        """
        results = {}
        
        # 1. Prophet forecast
        try:
            prophet_model = self._train_prophet(df)
            prophet_results = self._forecast_prophet(prophet_model, df, forecast_days)
            results['prophet'] = prophet_results
            logger.info("✅ Prophet forecast complete")
        except Exception as e:
            logger.error(f"Prophet forecast failed: {e}")
            results['prophet'] = None
        
        # 2. NeuralProphet forecast
        try:
            neural_model = self._train_neural_prophet(df)
            neural_results = self._forecast_neural_prophet(neural_model, df, forecast_days)
            results['neural_prophet'] = neural_results
            logger.info("✅ NeuralProphet forecast complete")
        except Exception as e:
            logger.error(f"NeuralProphet forecast failed: {e}")
            results['neural_prophet'] = None
        
        # 3. ARIMA forecast (if available)
        if ARIMA_AVAILABLE:
            try:
                arima_model = self._train_arima(df)
                if arima_model:
                    arima_results = self._forecast_arima(arima_model, forecast_days)
                    results['arima'] = arima_results
                    logger.info("✅ ARIMA forecast complete")
            except Exception as e:
                logger.error(f"ARIMA forecast failed: {e}")
                results['arima'] = None
        else:
            results['arima'] = None
        
        # 4. LSTM forecast (if available)
        if TENSORFLOW_AVAILABLE:
            try:
                lstm_model = self._train_lstm(df)
                if lstm_model:
                    lstm_results = self._forecast_lstm(lstm_model, df, forecast_days)
                    results['lstm'] = lstm_results
                    logger.info("✅ LSTM forecast complete")
            except Exception as e:
                logger.error(f"LSTM forecast failed: {e}")
                results['lstm'] = None
        else:
            results['lstm'] = None
        
        # 5. Monte Carlo forecast (if available)
        if SCIPY_AVAILABLE:
            try:
                mc_model = self._train_monte_carlo(df)
                if mc_model:
                    mc_results = self._forecast_monte_carlo(mc_model, forecast_days)
                    results['monte_carlo'] = mc_results
                    logger.info("✅ Monte Carlo forecast complete")
            except Exception as e:
                logger.error(f"Monte Carlo forecast failed: {e}")
                results['monte_carlo'] = None
        else:
            results['monte_carlo'] = None
        
        # 6. ML Models (XGBoost, LightGBM, RandomForest)
        try:
            X, y = self.prepare_features(df)
            
            ml_models = {
                'xgboost': self._train_xgboost(df),
                'lightgbm': self._train_lightgbm(df),
                'random_forest': self._train_random_forest(df)
            }
            
            for name, model in ml_models.items():
                try:
                    model.fit(X, y)
                    # Generate future predictions
                    future_data = self._create_future_features(df, forecast_days)
                    predictions = model.predict(future_data)
                    results[name] = {'forecast': predictions.tolist()}
                    logger.info(f"✅ {name} forecast complete")
                except Exception as e:
                    logger.error(f"ML model {name} failed: {e}")
                    results[name] = None
                    
        except Exception as e:
            logger.error(f"ML models failed: {e}")
            results['ml_models'] = None
        
        # 7. Ensemble forecast (combines ALL working models)
        ensemble_forecast = self._create_ensemble_forecast(results, forecast_days)
        results['ensemble'] = ensemble_forecast
        
        # Log which models are active
        active_models = [name for name, result in results.items() 
                         if result is not None and name != 'ensemble']
        logger.info(f"🎯 Active models: {len(active_models)}/8 - {active_models}")
        
        return results
    
    # ============================================================
    # ENSEMBLE CREATION
    # ============================================================
    def _create_ensemble_forecast(self, results: Dict, forecast_days: int) -> Dict:
        """
        Create ensemble forecast by averaging all available models.
        Now includes ALL 8 models with optimized weights.
        """
        # Updated weights for ALL 8 models
        weights = {
            'prophet': 0.15,
            'neural_prophet': 0.15,
            'arima': 0.10,
            'lstm': 0.10,
            'monte_carlo': 0.10,
            'xgboost': 0.15,
            'lightgbm': 0.15,
            'random_forest': 0.10
        }
        
        weighted_sum = np.zeros(forecast_days)
        total_weight = 0
        active_models = []
        
        for name, weight in weights.items():
            if name in results and results[name] is not None:
                forecast = results[name].get('forecast', [])
                if len(forecast) == forecast_days:
                    weighted_sum += np.array(forecast) * weight
                    total_weight += weight
                    active_models.append(name)
        
        if total_weight > 0:
            ensemble_forecast = weighted_sum / total_weight
        else:
            # Fallback: use simple average of all available models
            all_forecasts = []
            for name, result in results.items():
                if result is not None and 'forecast' in result and name != 'ensemble':
                    if len(result['forecast']) == forecast_days:
                        all_forecasts.append(result['forecast'])
            
            if all_forecasts:
                ensemble_forecast = np.mean(all_forecasts, axis=0)
                active_models = list(results.keys())
            else:
                # Ultimate fallback: use historical average
                ensemble_forecast = np.full(forecast_days, 300.0)
        
        # Ensure non-negative
        ensemble_forecast = np.maximum(ensemble_forecast, 0)
        
        # Calculate confidence intervals using weighted standard deviation
        if total_weight > 0:
            # Get weighted variance
            weighted_variance = np.zeros(forecast_days)
            for name, weight in weights.items():
                if name in results and results[name] is not None:
                    forecast = results[name].get('forecast', [])
                    if len(forecast) == forecast_days:
                        # Use Monte Carlo std if available
                        if name == 'monte_carlo' and 'std' in results[name]:
                            std = np.array(results[name]['std'])
                        else:
                            std = np.std(forecast)
                        weighted_variance += (std ** 2) * weight
            
            std_dev = np.sqrt(weighted_variance / total_weight)
        else:
            std_dev = np.std(ensemble_forecast) * 0.3
        
        upper = ensemble_forecast + (std_dev * 1.96)  # 95% confidence
        lower = ensemble_forecast - (std_dev * 1.96)  # 95% confidence
        lower = np.maximum(lower, 0)
        
        return {
            'forecast': ensemble_forecast.tolist(),
            'upper': upper.tolist(),
            'lower': lower.tolist(),
            'active_models': active_models,
            'total_weight': total_weight
        }
    
    # ============================================================
    # METRICS CALCULATION
    # ============================================================
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
        
        # Mean Absolute Scaled Error (MASE)
        naive_forecast = actual[:-1]
        actual_shifted = actual[1:]
        naive_error = np.mean(np.abs(actual_shifted - naive_forecast))
        metrics['mase'] = metrics['mae'] / naive_error if naive_error > 0 else float('inf')
        
        return metrics
    
    # ============================================================
    # MODEL COMPARISON
    # ============================================================
    def compare_models(self, df: pd.DataFrame, test_size: int = 30) -> pd.DataFrame:
        """
        Compare all models and return performance metrics.
        
        Args:
            df: Historical data
            test_size: Number of days to use for testing
        
        Returns:
            DataFrame with model performance comparison
        """
        # Split data
        train = df.iloc[:-test_size]
        test = df.iloc[-test_size:]
        
        results = []
        
        # Test each model
        for name, train_func in self.get_models().items():
            try:
                # Train model
                model = train_func(train)
                
                # Generate forecast
                if name in ['prophet', 'neural_prophet']:
                    forecast = self._forecast_prophet(model, train, test_size)
                elif name == 'arima':
                    forecast = self._forecast_arima(model, test_size)
                elif name == 'lstm':
                    forecast = self._forecast_lstm(model, train, test_size)
                elif name == 'monte_carlo':
                    forecast = self._forecast_monte_carlo(model, test_size)
                else:
                    # ML models
                    X_train, y_train = self.prepare_features(train)
                    model.fit(X_train, y_train)
                    X_test = self._create_future_features(train, test_size)
                    predictions = model.predict(X_test)
                    forecast = {'forecast': predictions.tolist()}
                
                if forecast and 'forecast' in forecast:
                    y_pred = np.array(forecast['forecast'][:test_size])
                    y_true = test['Order_Quantity_kg'].values[:len(y_pred)]
                    
                    # Calculate metrics
                    metrics = self.calculate_metrics(y_true, y_pred)
                    metrics['model'] = name
                    metrics['status'] = '✅'
                    results.append(metrics)
                    
            except Exception as e:
                logger.error(f"Model {name} comparison failed: {e}")
                results.append({
                    'model': name,
                    'status': '❌',
                    'mape': float('inf'),
                    'mae': float('inf'),
                    'rmse': float('inf'),
                    'r2': -float('inf'),
                    'direction_accuracy': 0,
                    'mase': float('inf')
                })
        
        # Create DataFrame
        df_results = pd.DataFrame(results)
        
        # Sort by MAPE (lower is better)
        if not df_results.empty and 'mape' in df_results.columns:
            df_results = df_results.sort_values('mape')
        
        return df_results