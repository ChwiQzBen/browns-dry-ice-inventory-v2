import pandas as pd
import numpy as np
from prophet import Prophet
from scipy.stats import norm
import config.constants as const
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class DryIceAnalyzer:
    def __init__(self, data_loader):
        self.data_loader = data_loader
        self.constants = const.INVENTORY_PARAMETERS
        
    def calculate_kpis(self):
        """Calculate all key performance indicators"""
        df = self.data_loader.df
        total_volume = df['Order_Quantity_kg'].sum()
        avg_order = df['Order_Quantity_kg'].mean()
        std_order = df['Order_Quantity_kg'].std()
        avg_monthly_demand = avg_order * 30
        
        # Calculate time span for monthly volume
        time_span_days = (df['Date'].max() - df['Date'].min()).days
        current_monthly_volume = total_volume / time_span_days * 30 if time_span_days > 0 else avg_monthly_demand
        
        # Calculate order frequency
        order_frequency = len(df) / time_span_days * 30 if time_span_days > 0 else 30
        
        return {
            'total_orders': len(df),
            'total_volume': total_volume,
            'avg_order_size': avg_order,
            'std_order_size': std_order,
            'avg_monthly_demand': avg_monthly_demand,
            'current_monthly_volume': current_monthly_volume,
            'order_frequency': order_frequency,
            'container_utilization': (
                df['Order_Quantity_kg'].sum() / 
                (df['Containers_Used'].sum() * self.constants['CONTAINER_SIZE'])
            ),
            'total_cost': df['Total_Cost'].sum(),
            'avg_cost_per_order': df['Total_Cost'].mean()
        }
    
    def calculate_eoq(self):
        """Economic Order Quantity calculation"""
        kpis = self.calculate_kpis()
        demand = kpis['avg_monthly_demand']
        return np.sqrt(
            (2 * demand * self.constants['TRANSPORT_COST']) / 
            (self.constants['HOLDING_RATE'] * self.constants['PRICE_PER_KG'])
        )
    
    def calculate_safety_stock(self):
        """Calculate safety stock based on service level"""
        df = self.data_loader.df
        daily_demand = df.groupby(df['Date'].dt.date)['Order_Quantity_kg'].sum()
        
        if len(daily_demand) < 2:
            # Fallback for insufficient data
            return df['Order_Quantity_kg'].mean() * 0.5
        
        daily_std = daily_demand.std()
        z_score = norm.ppf(self.constants['SERVICE_LEVEL'])
        lead_time_factor = np.sqrt(self.constants['LEAD_TIME_DAYS'])
        
        return z_score * daily_std * lead_time_factor
    
    def forecast_demand(self, periods=30):
        """Generate demand forecast with Prophet"""
        try:
            # Prepare data for Prophet
            prophet_df = self.data_loader.df.groupby('Date')['Order_Quantity_kg'].sum().reset_index()
            prophet_df = prophet_df.rename(columns={'Date': 'ds', 'Order_Quantity_kg': 'y'})
            
            # Create and fit model
            model = Prophet(
                seasonality_mode='multiplicative',
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False
            )
            model.fit(prophet_df)
            
            # Generate forecast
            future = model.make_future_dataframe(periods=periods)
            forecast = model.predict(future)
            
            return forecast
        except Exception as e:
            return None
    
    def calculate_cost_savings(self, eoq):
        """Compare current costs vs EOQ optimized costs"""
        kpis = self.calculate_kpis()
        transport_cost = self.constants['TRANSPORT_COST']
        holding_rate = self.constants['HOLDING_RATE']
        price_per_kg = self.constants['PRICE_PER_KG']
        
        # Current ordering and holding costs
        current_order_cost = (
            (kpis['current_monthly_volume'] / kpis['avg_order_size']) * transport_cost + 
            (holding_rate * price_per_kg * kpis['avg_order_size'] / 2)
        )
        
        # EOQ optimized costs
        eoq_order_cost = (
            (kpis['current_monthly_volume'] / eoq) * transport_cost + 
            (holding_rate * price_per_kg * eoq / 2)
        )
        
        savings = max(0, current_order_cost - eoq_order_cost)
        percent_savings = (savings / current_order_cost * 100) if current_order_cost > 0 else 0
        
        return {
            'current_cost': current_order_cost,
            'eoq_cost': eoq_order_cost,
            'savings': savings,
            'percent_savings': percent_savings
        }
