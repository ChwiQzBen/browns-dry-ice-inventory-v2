# app/core/external_factors.py
"""
External factors that affect demand forecasting.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple 
from datetime import datetime, timedelta
import requests
import json
import holidays
import logging

logger = logging.getLogger(__name__)

class ExternalFactors:
    """
    Collect and manage external factors affecting demand.
    """
    
    def __init__(self):
        self.country = 'KE'
        self.holidays = holidays.Kenya()
    
    def get_weather_data(self, location: str = "Nairobi") -> Dict:
        """
        Get weather forecast data.
        
        Args:
            location: City name
        
        Returns:
            Dict with weather data
        """
        try:
            # In production, use a real weather API like OpenWeatherMap
            # For demo, return simulated data
            return self._simulate_weather(location)
        except Exception as e:
            logger.error(f"Weather data error: {e}")
            return {}
    
    def _simulate_weather(self, location: str) -> Dict:
        """Simulate weather data for demo."""
        return {
            'temperature': np.random.normal(25, 5, 30).tolist(),
            'rainfall': np.random.exponential(10, 30).tolist(),
            'humidity': np.random.normal(70, 10, 30).tolist(),
            'location': location
        }
    
    def get_holiday_calendar(self, year: int = None) -> Dict:
        """
        Get holiday calendar for a year.
        
        Args:
            year: Year to get holidays for
        
        Returns:
            Dict with holiday dates
        """
        if year is None:
            year = datetime.now().year
        
        holidays_dict = {}
        for date, name in self.holidays.items():
            if date.year == year:
                holidays_dict[date.strftime('%Y-%m-%d')] = name
        
        return holidays_dict
    
    def get_economic_indicators(self) -> Dict:
        """
        Get economic indicators affecting demand.
        
        Returns:
            Dict with economic indicators
        """
        # In production, use a real economic API
        # For demo, return simulated data
        return {
            'inflation_rate': np.random.normal(5, 1),
            'gdp_growth': np.random.normal(3, 0.5),
            'unemployment_rate': np.random.normal(8, 1),
            'consumer_confidence': np.random.normal(100, 10)
        }
    
    def get_competitor_data(self) -> Dict:
        """
        Get competitor pricing and activity data.
        
        Returns:
            Dict with competitor data
        """
        # In production, use web scraping or API
        # For demo, return simulated data
        competitors = ['Competitor_A', 'Competitor_B', 'Competitor_C']
        return {
            comp: {
                'price': np.random.normal(150, 20),
                'promotion': np.random.choice([0, 0.1, 0.2, 0.3])
            }
            for comp in competitors
        }
    
    def get_all_external_factors(self) -> Dict:
        """
        Get all external factors combined.
        
        Returns:
            Dict with all external factors
        """
        return {
            'weather': self.get_weather_data(),
            'holidays': self.get_holiday_calendar(),
            'economic': self.get_economic_indicators(),
            'competitors': self.get_competitor_data()
        }
    
    def prepare_external_features(self, dates: list) -> pd.DataFrame:
        """
        Prepare external features for forecasting.
        
        Args:
            dates: List of dates to prepare features for
        
        Returns:
            DataFrame with external features
        """
        features = []
        
        for date in dates:
            # Check if holiday
            is_holiday = date in self.holidays
            
            # Day of week
            day_of_week = date.weekday()
            is_weekend = day_of_week in [5, 6]
            
            # Month
            month = date.month
            
            # Season
            if month in [12, 1, 2]:
                season = 'summer'
            elif month in [3, 4, 5]:
                season = 'autumn'
            elif month in [6, 7, 8]:
                season = 'winter'
            else:
                season = 'spring'
            
            features.append({
                'date': date,
                'is_holiday': 1 if is_holiday else 0,
                'is_weekend': 1 if is_weekend else 0,
                'day_of_week': day_of_week,
                'month': month,
                'season': season
            })
        
        return pd.DataFrame(features)