import streamlit as st
from datetime import datetime
import config.constants as const

class SmartAlerts:
    def __init__(self, inventory_tracker):
        self.inventory_tracker = inventory_tracker
        self.alerts = []
        self.alert_types = {
            'LOW_STOCK': {'threshold': 'safety_stock', 'priority': 'HIGH'},
            'REORDER_DUE': {'threshold': 'reorder_point', 'priority': 'MEDIUM'},
            'UNUSUAL_DEMAND': {'threshold': '2_std_dev', 'priority': 'MEDIUM'},
            'COST_SPIKE': {'threshold': '10_percent', 'priority': 'LOW'}
        }
    
    def check_conditions(self, current_demand, avg_demand, std_demand, current_cost, avg_cost):
        """Check all alert conditions"""
        # Check stock alerts
        stock_status = self.inventory_tracker.get_stock_status()
        if stock_status['status'] == 'CRITICAL':
            self.send_notification('LOW_STOCK', f"CRITICAL stock level: {self.inventory_tracker.current_stock} kg")
        elif stock_status['status'] == 'LOW':
            self.send_notification('REORDER_DUE', f"Low stock level: {self.inventory_tracker.current_stock} kg")
        
        # Check demand anomalies
        if abs(current_demand - avg_demand) > 2 * std_demand:
            self.send_notification('UNUSUAL_DEMAND', 
                                  f"Unusual demand detected: {current_demand} kg vs average {avg_demand:.1f} kg")
        
        # Check cost spikes
        if current_cost > avg_cost * 1.1:
            self.send_notification('COST_SPIKE', 
                                  f"Cost spike detected: KSh {current_cost:.2f} vs average KSh {avg_cost:.2f}")
        
        return self.alerts
    
    def send_notification(self, alert_type, message, channels=None):
        """Multi-channel notifications"""
        if channels is None:
            channels = const.INVENTORY_PARAMETERS['ALERT_CHANNELS']
            
        alert = {
            'timestamp': datetime.now(),
            'type': alert_type,
            'message': message,
            'priority': self.alert_types[alert_type]['priority'],
            'channels': channels,
            'status': 'PENDING'
        }
        
        self.alerts.append(alert)
        return alert
    
    def send_email(self, message):
        """Stub for email integration"""
        # Integration with email service would go here
        return True
    
    def send_sms(self, message):
        """Stub for SMS integration"""
        # Integration with SMS gateway would go here
        return True
    
    def show_popup(self, message):
        """Display dashboard alert"""
        # This will be handled in the Streamlit interface
        return True
    
    def get_active_alerts(self):
        """Get unprocessed alerts"""
        return [alert for alert in self.alerts if alert['status'] == 'PENDING']
    
    def mark_alert_processed(self, alert_id):
        """Mark alert as processed"""
        if 0 <= alert_id < len(self.alerts):
            self.alerts[alert_id]['status'] = 'PROCESSED'
            return True
        return False
