import pandas as pd
import streamlit as st
from datetime import datetime
from app.core.analyzer import DryIceAnalyzer


class InventoryTracker:
    def __init__(self, initial_stock=0, analyzer: DryIceAnalyzer=None):
        self.current_stock = initial_stock
        self.dry_ice_analyzer = analyzer
        self.alerts_enabled = True
        self.stock_history = []
    
    @property
    def reorder_point(self):
        eoq = self.dry_ice_analyzer.calculate_eoq()
        safety_stock = self.dry_ice_analyzer.calculate_safety_stock()
        return eoq + safety_stock

    @property
    def safety_stock(self):
        return self.dry_ice_analyzer.calculate_safety_stock()

        
    def update_stock(self, quantity_used, transaction_type="Consumption"):
        """Real-time stock updates with transaction logging"""
        self.current_stock -= quantity_used
        self._log_transaction(quantity_used, transaction_type)
        return self.check_reorder_point()
        
    def _log_transaction(self, quantity, transaction_type):
        """Record stock transactions"""
        self.stock_history.append({
            'timestamp': datetime.now(),
            'quantity': quantity,
            'type': transaction_type,
            'balance': self.current_stock
        })
        
    def check_reorder_point(self):
        """Automated reorder alerts"""
        if self.current_stock <= self.reorder_point:
            return self.send_alert("REORDER REQUIRED")
        return None
            
    def get_stock_status(self):
        """Visual stock status with color coding"""
        print(f"Curremt Stock: {self.current_stock}\nSafetyStock: {self.safety_stock}\nReorder Point: {self.reorder_point}")
        if self.current_stock <= self.safety_stock:
            return {"status": "CRITICAL", "color": "red"}
        elif self.current_stock <= self.reorder_point:
            return {"status": "LOW", "color": "orange"}

        return {"status": "NORMAL", "color": "green"}
    
    def send_alert(self, message):
        """Generate alert message"""
        return {
            "timestamp": datetime.now(),
            "message": f"{message} - Current stock: {self.current_stock} kg",
            "priority": "HIGH" if self.current_stock <= self.safety_stock else "MEDIUM"
        }
    
    def get_stock_history(self):
        """Return transaction history"""
        return pd.DataFrame(self.stock_history)
