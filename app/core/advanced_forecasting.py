import pandas as pd
import numpy as np
from prophet import Prophet
from statsmodels.tsa.arima.model import ARIMA
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
import warnings
warnings.filterwarnings('ignore')
from sklearn.preprocessing import MinMaxScaler

class AdvancedForecasting:
    def __init__(self):
        self.models = ['Prophet', 'ARIMA', 'LSTM', 'Ensemble']
        
    def multi_model_forecast(self, data, periods=30):
        """Compare multiple forecasting models"""
        forecasts = {}
        for model in self.models:
            if model == 'Prophet':
                forecasts[model] = self.prophet_forecast(data, periods)
            elif model == 'ARIMA':
                forecasts[model] = self.arima_forecast(data, periods)
            elif model == 'LSTM':
                forecasts[model] = self.lstm_forecast(data, periods)
        
        # Create ensemble forecast (average of models)
        ensemble = pd.DataFrame()
        for model, forecast in forecasts.items():
            ensemble[model] = forecast['yhat']
        ensemble['Ensemble'] = ensemble.mean(axis=1)
        forecasts['Ensemble'] = ensemble[['Ensemble']]
        
        return forecasts
    
    def prophet_forecast(self, data, periods):
        """Prophet forecasting model"""
        model = Prophet(
            seasonality_mode='multiplicative',
            yearly_seasonality=True,
            weekly_seasonality=True
        )
        model.fit(data.rename(columns={'Date': 'ds', 'Order_Quantity_kg': 'y'}))
        future = model.make_future_dataframe(periods=periods)
        return model.predict(future)[['ds', 'yhat']].set_index('ds')
    
    def arima_forecast(self, data, periods):
        """ARIMA forecasting model"""
        model = ARIMA(data['Order_Quantity_kg'], order=(5,1,0))
        model_fit = model.fit()
        forecast = model_fit.forecast(steps=periods)
        future_dates = pd.date_range(
            start=data['Date'].max() + pd.Timedelta(days=1),
            periods=periods
        )
        return pd.DataFrame({'yhat': forecast.values}, index=future_dates)
    
    def lstm_forecast(self, data, periods, look_back=30):
        """LSTM forecasting model"""
        # Prepare data
        values = data['Order_Quantity_kg'].values
        values = values.reshape(-1, 1)
        
        # Normalize
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled = scaler.fit_transform(values)
        
        # Create dataset
        X, y = [], []
        for i in range(look_back, len(scaled)):
            X.append(scaled[i-look_back:i, 0])
            y.append(scaled[i, 0])
        X, y = np.array(X), np.array(y)
        X = np.reshape(X, (X.shape[0], X.shape[1], 1))
        
        # Build model
        model = Sequential()
        model.add(LSTM(50, return_sequences=True, input_shape=(X.shape[1], 1)))
        model.add(LSTM(50))
        model.add(Dense(1))
        model.compile(optimizer='adam', loss='mean_squared_error')
        
        # Train model
        model.fit(X, y, epochs=20, batch_size=32, verbose=0)
        
        # Make predictions
        inputs = scaled[-look_back:]
        predictions = []
        for _ in range(periods):
            x_input = np.reshape(inputs, (1, look_back, 1))
            yhat = model.predict(x_input, verbose=0)
            predictions.append(yhat[0,0])
            inputs = np.append(inputs[1:], yhat)
        
        # Inverse transform
        predictions = scaler.inverse_transform(np.array(predictions).reshape(-1, 1))
        future_dates = pd.date_range(
            start=data['Date'].max() + pd.Timedelta(days=1),
            periods=periods
        )
        return pd.DataFrame({'yhat': predictions.flatten()}, index=future_dates)
    
    def seasonal_decomposition(self, data):
        """Identify seasonal patterns"""
        # Using simple moving average for trend
        data['trend'] = data['Order_Quantity_kg'].rolling(window=30).mean()
        data['seasonal'] = data['Order_Quantity_kg'] - data['trend']
        data['residual'] = data['seasonal'] - data['seasonal'].mean()
        
        return {
            'trend': data['trend'],
            'seasonal': data['seasonal'],
            'residual': data['residual']
        }
    
    def confidence_intervals(self, forecast):
        """Generate prediction intervals"""
        return {
            'forecast': forecast,
            'lower_80': forecast * 0.9,
            'upper_80': forecast * 1.1,
            'lower_95': forecast * 0.85,
            'upper_95': forecast * 1.15
        }
