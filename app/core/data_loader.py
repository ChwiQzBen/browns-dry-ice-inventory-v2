import pandas as pd
from pathlib import Path
import config.constants as const
import numpy as np
import warnings
warnings.filterwarnings('ignore')

class DataLoader:
    def __init__(self):
        self.constants = const.INVENTORY_PARAMETERS
        self.df = None
        
    def load_orders(self, filepath):
        """Load and process order data with full processing"""
        df = pd.read_csv(filepath)
        
        # Convert to datetime with dayfirst for European format
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True)
        
        # Filter for July 2024 to June 2025
        df = df[
            (df['Date'] >= '2024-07-01') & 
            (df['Date'] <= '2025-06-30')
        ]
        
        # Calculate effective quantity after sublimation
        avg_loss = sum(self.constants['SUB_LOSS_RANGE'])/2/100
        df['Effective_Quantity'] = df['Order_Quantity_kg'] * (1 - avg_loss)
        
        # Calculate container utilization
        df['Containers_Used'] = np.ceil(
            df['Order_Quantity_kg'] / self.constants['CONTAINER_SIZE']
        )
        
        # Add cost calculations
        df['Transport_Cost'] = df['Containers_Used'] * (self.constants['TRANSPORT_COST'] / df['Containers_Used'].max())
        df['Total_Cost'] = df['Order_Quantity_kg'] * self.constants['PRICE_PER_KG']
        
        self.df = df.sort_values('Date')
        return self.df
