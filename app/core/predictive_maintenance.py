import numpy as np
import pandas as pd
import config.constants as const

class PredictiveMaintenance:
    def __init__(self):
        self.container_health_indicators = const.INVENTORY_PARAMETERS['CONTAINER_HEALTH_INDICATORS']
    
    def predict_container_failure(self, container_data):
        """Predict when containers need maintenance"""
        risk_score = 0
        weights = {
            'insulation_efficiency': 0.3,
            'seal_integrity': 0.25,
            'structural_condition': 0.3,
            'usage_cycles': 0.15
        }
        
        for indicator in self.container_health_indicators:
            risk_score += self.calculate_risk_factor(container_data[indicator]) * weights[indicator]
        
        return {
            'container_id': container_data['id'],
            'risk_score': risk_score,
            'failure_probability': self.calculate_failure_probability(risk_score),
            'estimated_life_remaining': self.calculate_remaining_life(risk_score),
            'maintenance_recommendations': self.generate_maintenance_plan(risk_score)
        }
    
    def calculate_risk_factor(self, value):
        """Calculate risk factor for an indicator"""
        # Normalize value to 0-1 scale (1 = highest risk)
        if value < 30:
            return 1.0
        elif value < 60:
            return 0.6
        elif value < 80:
            return 0.3
        return 0.1
    
    def calculate_failure_probability(self, risk_score):
        """Convert risk score to probability"""
        return min(0.95, risk_score * 1.2)
    
    def calculate_remaining_life(self, risk_score):
        """Estimate remaining life in days"""
        if risk_score > 0.8:
            return 7  # 1 week
        elif risk_score > 0.6:
            return 30  # 1 month
        elif risk_score > 0.4:
            return 90  # 3 months
        return 180  # 6 months
    
    def generate_maintenance_plan(self, risk_score):
        """Generate maintenance recommendations"""
        if risk_score > 0.8:
            return ["Immediate inspection", "Pressure testing", "Seal replacement"]
        elif risk_score > 0.6:
            return ["Weekly inspection", "Thermal imaging", "Cleaning"]
        elif risk_score > 0.4:
            return ["Monthly inspection", "Visual check"]
        return ["Routine maintenance in 6 months"]
