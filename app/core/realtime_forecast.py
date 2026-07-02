# app/core/realtime_forecast.py
"""
Real-time forecasting with streaming updates.
"""

import asyncio
import threading
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import streamlit as st
import logging

logger = logging.getLogger(__name__)

class RealTimeForecaster:
    """
    Real-time forecasting with auto-updates.
    """
    
    def __init__(self, update_interval: int = 60):
        """
        Initialize real-time forecaster.
        
        Args:
            update_interval: Update interval in seconds
        """
        self.update_interval = update_interval
        self.is_running = False
        self.forecast_data = None
        self.last_update = None
        self.thread = None
        
    def start(self, df, forecast_days: int = 30):
        """
        Start real-time forecasting in background.
        
        Args:
            df: Historical data
            forecast_days: Number of days to forecast
        """
        if self.is_running:
            return
        
        self.is_running = True
        self.thread = threading.Thread(
            target=self._run_forecast_loop,
            args=(df, forecast_days),
            daemon=True
        )
        self.thread.start()
        
        logger.info(f"Real-time forecasting started (interval: {self.update_interval}s)")
    
    def stop(self):
        """Stop real-time forecasting."""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Real-time forecasting stopped")
    
    def _run_forecast_loop(self, df, forecast_days: int):
        """Background loop for real-time forecasting."""
        while self.is_running:
            try:
                # Get latest data
                latest_data = self._get_latest_data(df)
                
                # Update forecast
                self.forecast_data = self._update_forecast(latest_data, forecast_days)
                self.last_update = datetime.now()
                
                logger.info(f"Forecast updated at {self.last_update}")
                
            except Exception as e:
                logger.error(f"Real-time forecast error: {e}")
            
            # Wait for next update
            time.sleep(self.update_interval)
    
    def _get_latest_data(self, df):
        """Get latest data from database."""
        # In production, query your database
        # For demo, simulate new data
        last_date = df['Date'].max()
        new_date = last_date + timedelta(days=1)
        
        # Simulate new order
        new_order = {
            'Date': new_date,
            'Order_Quantity_kg': np.random.poisson(300)
        }
        
        # Append to existing data
        latest_df = pd.concat([df, pd.DataFrame([new_order])], ignore_index=True)
        return latest_df.tail(90)  # Keep last 90 days
    
    def _update_forecast(self, df, forecast_days: int):
        """Update forecast with new data."""
        from app.core.advanced_forecasting import AdvancedForecaster
        
        forecaster = AdvancedForecaster()
        results = forecaster.forecast(df, forecast_days)
        
        return {
            'results': results,
            'timestamp': datetime.now().isoformat(),
            'data_points': len(df)
        }
    
    def get_forecast(self):
        """Get latest forecast."""
        if self.forecast_data:
            return self.forecast_data
        return None
    
    def render_realtime_status(self):
        """Render real-time status in UI."""
        if self.is_running:
            status = "🟢 Running"
            color = "#28a745"
        else:
            status = "🔴 Stopped"
            color = "#dc3545"
        
        last_update = self.last_update.strftime("%H:%M:%S") if self.last_update else "Never"
        
        st.markdown(f"""
        <div style="
            background: rgba({'40, 167, 69' if self.is_running else '220, 53, 69'}, 0.1);
            border-radius: 8px;
            padding: 10px 15px;
            border-left: 3px solid {color};
        ">
            <div style="display: flex; justify-content: space-between;">
                <div>
                    <strong>📡 Real-Time Updates</strong>
                </div>
                <div style="color: {color}; font-weight: 600;">
                    {status}
                </div>
            </div>
            <div style="font-size: 12px; color: #888; margin-top: 4px;">
                Last update: {last_update} · Interval: {self.update_interval}s
            </div>
        </div>
        """, unsafe_allow_html=True)

# Singleton instance
_realtime_forecaster = None

def get_realtime_forecaster():
    """Get or create real-time forecaster instance."""
    global _realtime_forecaster
    if _realtime_forecaster is None:
        _realtime_forecaster = RealTimeForecaster(update_interval=60)
    return _realtime_forecaster