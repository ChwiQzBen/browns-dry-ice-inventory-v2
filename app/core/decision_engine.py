from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List
import numpy as np


@dataclass
class InventorySnapshot:
    """
    Point-in-time snapshot of inventory state, fed into InventoryDecisionEngine.
    forecast_accuracy is expected on a 0-100 scale (multiply backtest_accuracy by 100).
    """
    current_stock: float
    eoq: float
    safety_stock: float
    reorder_point: float
    forecast_values: np.ndarray
    forecast_accuracy: float          # 0-100 scale
    lead_time_days: int
    transport_cost: float
    avg_order_size: float             # needed for realistic order-frequency math
    supplier_reliability: float = 95.0
    service_level: float = 95.0
    monthly_holding_cost: float = 0.0


class InventoryDecisionEngine:
    def __init__(self, snapshot: InventorySnapshot):
        self.s = snapshot

        self.avg_daily_demand = (
            float(np.mean(self.s.forecast_values))
            if len(self.s.forecast_values) > 0 and np.sum(self.s.forecast_values) > 0
            else 0.0
        )

        self.days_remaining = (
            self.s.current_stock / self.avg_daily_demand
            if self.avg_daily_demand > 0
            else 999.0
        )

        self.days_to_reorder = (
            (self.s.current_stock - self.s.reorder_point) / self.avg_daily_demand
            if self.avg_daily_demand > 0
            else 999.0
        )

    def inventory_recommendation(self) -> dict:
        purchase_required = (
            self.s.current_stock <= self.s.reorder_point
            or self.days_remaining <= self.s.lead_time_days
        )

        order_date = datetime.now().date()
        if purchase_required and self.days_to_reorder < 999:
            order_date = (datetime.now() + timedelta(days=max(0, self.days_to_reorder))).date()

        if purchase_required:
            action = "Purchase Inventory"
            recommendation = f"Order {self.s.eoq:,.0f} kg before {order_date}."
        else:
            action = "No Purchase Required"
            recommendation = f"Current inventory covers {self.days_remaining:.0f} days."

        return {
            "purchase_required": purchase_required,
            "action": action,
            "recommendation": recommendation,
            "recommended_quantity": round(self.s.eoq),
            "recommended_order_date": order_date.isoformat(),
            "days_remaining": round(min(self.days_remaining, 999)),
        }

    def risk_assessment(self) -> dict:
        score = 0
        if self.s.current_stock <= self.s.reorder_point:
            score += 40
        if self.days_remaining <= self.s.lead_time_days:
            score += 25
        if self.s.forecast_accuracy < 80:
            score += 15
        if self.s.supplier_reliability < 90:
            score += 10
        if self.s.service_level < 95:
            score += 10

        if score >= 70:
            level = "Critical"
        elif score >= 45:
            level = "High"
        elif score >= 20:
            level = "Medium"
        else:
            level = "Low"

        return {"score": score, "level": level}

    def financial_analysis(self) -> dict:
        orders_current = (
            (self.avg_daily_demand * 30) / max(self.s.avg_order_size, 1)
            if self.avg_daily_demand > 0 else 0
        )
        orders_eoq = (
            (self.avg_daily_demand * 30) / max(self.s.eoq, 1)
            if self.avg_daily_demand > 0 else 0
        )
        savings = max(0, orders_current - orders_eoq) * self.s.transport_cost

        return {
            "potential_monthly_savings": round(savings),
            "monthly_holding_cost": round(self.s.monthly_holding_cost),
        }

    def explanation(self) -> List[str]:
        reasons = []
        if self.s.current_stock <= self.s.reorder_point:
            reasons.append("Inventory has reached the reorder point.")
        if self.days_remaining <= self.s.lead_time_days:
            reasons.append("Remaining inventory is lower than supplier lead time.")
        if self.s.forecast_accuracy < 80:
            reasons.append("Forecast confidence is below target.")
        if self.s.supplier_reliability < 90:
            reasons.append("Supplier reliability has declined.")
        if not reasons:
            reasons.append("Inventory is healthy and no immediate action is required.")
        return reasons

    def executive_summary(self) -> dict:
        return {
            "inventory": self.inventory_recommendation(),
            "risk": self.risk_assessment(),
            "financial": self.financial_analysis(),
            "explanation": self.explanation(),
            "forecast_accuracy": round(self.s.forecast_accuracy, 1),
        }
    
    def generate_ai_insights(current_stock, safety_stock, reorder_point, eoq,
                          avg_daily_forecast, historical_avg_daily,
                          forecast_accuracy, container_efficiency):
        """
        Generate a short, prioritized list of rule-based insights.
        Returns up to 4 dicts: {icon, text, priority} — priority 0=critical, 1=warning, 2=good.
        """
        insights = []

        if current_stock <= 0:
            insights.append({'icon': '🔴', 'text': 'Stock is depleted — order immediately', 'priority': 0})
        elif current_stock < safety_stock:
            insights.append({'icon': '🔴', 'text': f'Stock ({current_stock:,.0f} kg) is below safety stock ({safety_stock:,.0f} kg)', 'priority': 0})
        elif current_stock <= reorder_point:
            insights.append({'icon': '⚠️', 'text': f'Stock has reached the reorder point — order {eoq:,.0f} kg soon', 'priority': 1})
        else:
            insights.append({'icon': '✅', 'text': 'No purchase required today', 'priority': 2})

        if historical_avg_daily > 0:
            pct_change = (avg_daily_forecast - historical_avg_daily) / historical_avg_daily * 100
            if pct_change >= 15:
                insights.append({'icon': '⚠️', 'text': f'Forecasted demand is {pct_change:.0f}% above recent average', 'priority': 1})
            elif pct_change <= -15:
                insights.append({'icon': 'ℹ️', 'text': f'Forecasted demand is {abs(pct_change):.0f}% below recent average', 'priority': 2})

        if forecast_accuracy < 70:
            insights.append({'icon': '⚠️', 'text': f'Forecast confidence is low ({forecast_accuracy:.0f}%) — treat recommendations cautiously', 'priority': 1})
        elif forecast_accuracy >= 90:
            insights.append({'icon': '✅', 'text': f'Forecast confidence is strong ({forecast_accuracy:.0f}%)', 'priority': 2})

        if container_efficiency < 70:
            insights.append({'icon': '⚠️', 'text': f'Container fill rate is low ({container_efficiency:.0f}%) — consolidate orders', 'priority': 1})

        insights.sort(key=lambda x: x['priority'])
        return insights[:4]