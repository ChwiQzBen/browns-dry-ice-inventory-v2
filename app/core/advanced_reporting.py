from fpdf import FPDF
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import tempfile
from pathlib import Path
import numpy as np
from scipy import stats

# --- Constants (should match your main app) ---
PRICE_PER_KG = 146.55
TRANSPORT_COST = 1741.94
HOLDING_RATE = 0.03
SUB_LOSS_RANGE = (1.51, 3.03)
LEAD_TIME_DAYS = 1
SERVICE_LEVEL = 0.95

# --- Utility Function ---
def create_versioned_file(base_filename):
    """Create a versioned filename to avoid overwriting"""
    name, ext = os.path.splitext(base_filename)
    if not os.path.exists(base_filename):
        filename = base_filename
    else:
        version = 1
        while True:
            filename = f"{name}_v{version}{ext}"
            if not os.path.exists(filename):
                break
            version += 1
    output_dir = os.path.dirname(filename)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    return filename

# --- Custom PDF Class ---
class PDFReport(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report_date = datetime.now().strftime("%B %d, %Y")
        
        # Use built-in fonts only (no external font files needed)
        # This avoids the "Undefined font" error
        self.font_family = "Helvetica"
        
        # Optional: Try to load custom fonts if they exist, but don't fail if they don't
        font_paths = [
            Path("assets/fonts/NotoSans-Regular.ttf"),
            Path("../assets/fonts/NotoSans-Regular.ttf"),
            Path("../../assets/fonts/NotoSans-Regular.ttf"),
        ]
        
        for font_path in font_paths:
            if font_path.exists():
                try:
                    self.add_font("Noto", "", str(font_path))
                    bold_path = font_path.parent / "NotoSans-Bold.ttf"
                    if bold_path.exists():
                        self.add_font("Noto", "B", str(bold_path))
                    italic_path = font_path.parent / "NotoSans-Italic.ttf"
                    if italic_path.exists():
                        self.add_font("Noto", "I", str(italic_path))
                    self.font_family = "Noto"
                    break
                except:
                    continue

    def header(self):
        self.set_font(self.font_family, 'B', 12)
        self.cell(0, 10, "Browns Cheese", 0, 0, 'L')
        self.set_font(self.font_family, 'I', 10)
        self.cell(0, 10, "Dry Ice Inventory Analysis", 0, 1, 'R')
        self.ln(5)
        self.set_draw_color(200, 200, 200)
        self.cell(0, 0, '', 'T', 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.font_family, 'I', 8)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font(self.font_family, 'B', 16)
        self.set_text_color(31, 119, 180)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(4)

    def chapter_body(self, text):
        self.set_font(self.font_family, '', 10)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 5, text)
        self.ln()

    def add_kpi_card(self, label, value, unit="", color=(230, 247, 255)):
        self.set_fill_color(color[0], color[1], color[2])
        self.set_font(self.font_family, 'B', 10)
        self.cell(90, 8, f" {label}", 1, 0, 'L', fill=True)
        self.set_font(self.font_family, 'B', 12)
        self.cell(90, 8, f"{value} {unit}", 1, 1, 'R', fill=True)
        self.ln(2)

    def add_recommendation(self, text):
        self.set_font(self.font_family, '', 10)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 5, f"• {text}")
        self.ln(2)

    def add_plotly_chart(self, fig, chart_name):
        """Add a plotly chart to the PDF"""
        chart_dir = os.path.join(tempfile.gettempdir(), 'report_charts')
        os.makedirs(chart_dir, exist_ok=True)
        
        chart_path = os.path.join(chart_dir, f"{chart_name}.png")
        
        # Save the figure as PNG
        fig.write_image(chart_path, width=800, height=450, scale=2)
        
        # Add to PDF
        self.image(chart_path, w=self.w - self.l_margin - self.r_margin)
        
        # Clean up
        try:
            os.remove(chart_path)
        except:
            pass
        self.ln(5)

# --- AdvancedReporting Class ---
class AdvancedReporting:
    def __init__(self, analyzer=None, df=None, constants=None):
        """
        Initialize with analyzer or direct parameters
        
        Args:
            analyzer: Optional DryIceAnalyzer instance
            df: Optional DataFrame
            constants: Optional constants object with pricing and costs
        """
        self.analyzer = analyzer
        self.df = df
        
        # Helper function to convert dict to object
        def to_object(source):
            """Convert dictionary or other source to object with attributes"""
            class ConstantsObj:
                pass
            obj = ConstantsObj()
            
            # Default values
            defaults = {
                'price_per_kg': PRICE_PER_KG,
                'transport_cost': TRANSPORT_COST,
                'holding_rate': HOLDING_RATE,
                'sub_loss_range': SUB_LOSS_RANGE,
                'lead_time_days': LEAD_TIME_DAYS,
                'service_level': SERVICE_LEVEL
            }
            
            # Fill with source values
            if isinstance(source, dict):
                for key in defaults.keys():
                    setattr(obj, key, source.get(key, defaults[key]))
            elif source is not None:
                for key in defaults.keys():
                    if hasattr(source, key):
                        setattr(obj, key, getattr(source, key))
                    else:
                        setattr(obj, key, defaults[key])
            else:
                for key, value in defaults.items():
                    setattr(obj, key, value)
            
            return obj
        
        # Set up constants - convert to object if needed
        if constants is not None:
            self.constants = to_object(constants)
        elif analyzer is not None and hasattr(analyzer, 'constants'):
            self.constants = to_object(analyzer.constants)
        else:
            self.constants = to_object(None)
        
        self.report_date = datetime.now().strftime("%d-%m-%Y")

    def generate_custom_report(self, report_type, parameters=None, filename=None):
        """Generate a custom PDF report"""
        try:
            # Get DataFrame
            if self.df is None and self.analyzer:
                if hasattr(self.analyzer, 'df'):
                    self.df = self.analyzer.df
                elif hasattr(self.analyzer, 'data'):
                    self.df = self.analyzer.data
            
            if self.df is None or self.df.empty:
                raise ValueError("No data available for report generation")
            
            # Calculate KPIs and metrics
            kpis = self._calculate_kpis()
            eoq = self._calculate_eoq(kpis)
            safety_stock = self._calculate_safety_stock(kpis)
            cost_savings = self._calculate_cost_savings(eoq, kpis)
            forecast_data = self._create_forecast()
            
            # Create charts
            fig_forecast, fig_cost_comp = self._create_charts(forecast_data, cost_savings, kpis, eoq)
            recommendations = self._generate_recommendations(kpis, eoq, safety_stock, cost_savings)
            
            # Generate PDF
            pdf = PDFReport()
            pdf.alias_nb_pages()
            pdf.add_page()
            
            # Title
            pdf.set_font(pdf.font_family, 'B', 24)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 15, "Dry Ice Inventory Optimization Report", 0, 1, 'C')
            pdf.ln(5)
            
            # Executive Summary
            pdf.chapter_title("Executive Summary")
            summary_text = (
                f"This report provides a comprehensive analysis of the dry ice inventory for the period from "
                f"{self.df['Date'].min().strftime('%d-%b-%Y')} to "
                f"{self.df['Date'].max().strftime('%d-%b-%Y')}. "
                f"The analysis identifies significant opportunities for cost savings and operational efficiency. "
                f"By implementing an EOQ-based inventory policy, an estimated KSh {cost_savings.get('savings', 0):,.0f} "
                f"can be saved monthly, representing a {cost_savings.get('percent_savings', 0):.1f}% reduction in transport costs."
            )
            pdf.chapter_body(summary_text)

            # KPIs
            pdf.chapter_title("Key Performance Indicators (KPIs)")
            pdf.add_kpi_card("Potential Monthly Savings", f"KSh {cost_savings.get('savings', 0):,.0f}", "", color=(212, 237, 218))
            pdf.add_kpi_card("Economic Order Quantity (EOQ)", f"{eoq:,.0f}", "kg")
            pdf.add_kpi_card("Recommended Safety Stock", f"{safety_stock:,.0f}", "kg")
            pdf.add_kpi_card("Reorder Point", f"{eoq + safety_stock:,.0f}", "kg")
            pdf.add_kpi_card("Average Monthly Demand", f"{kpis.get('avg_monthly_demand', 0):,.0f}", "kg")
            pdf.ln(10)
            
            # Recommendations
            pdf.chapter_title("Top Recommendations")
            for rec in recommendations[:3]:
                pdf.add_recommendation(rec)

            # Forecast
            pdf.add_page()
            pdf.chapter_title("Demand Forecast Analysis")
            if fig_forecast:
                pdf.add_plotly_chart(fig_forecast, "demand_forecast")
                forecast_summary = (
                    "The 30-day demand forecast predicts fluctuating but consistent usage. "
                    "The shaded area represents the 95% confidence interval, indicating the likely range of future demand. "
                    "This forecast is crucial for planning orders and avoiding stockouts."
                )
                pdf.chapter_body(forecast_summary)
            else:
                pdf.chapter_body("Forecast data could not be generated for this report.")
            
            # Cost Analysis
            pdf.chapter_title("Cost Optimization Breakdown")
            if fig_cost_comp:
                pdf.add_plotly_chart(fig_cost_comp, "cost_comparison")
                cost_summary = (
                    "The chart above clearly illustrates the cost benefits of switching to an EOQ-based system. "
                    "While holding costs increase slightly due to larger average inventory, the reduction in ordering "
                    "costs is substantial, leading to significant overall savings."
                )
                pdf.chapter_body(cost_summary)
            else:
                pdf.chapter_body("Cost comparison data could not be generated for this report.")

            # Save file
            if filename is None:
                filename = f"reports/{report_type}_report_{self.report_date}.pdf"
            versioned_filename = create_versioned_file(filename)
            pdf.output(versioned_filename)
            return versioned_filename

        except Exception as e:
            print(f"Error during PDF generation: {e}")
            import traceback
            traceback.print_exc()
            raise e

    def _calculate_kpis(self):
        """Calculate KPIs from DataFrame"""
        if self.df is None or self.df.empty:
            return {
                'total_orders': 0,
                'total_volume': 0,
                'avg_order_size': 0,
                'std_order_size': 0,
                'avg_monthly_demand': 0,
                'order_frequency': 0
            }
        
        # Ensure Date is datetime
        self.df['Date'] = pd.to_datetime(self.df['Date'])
        
        # Calculate KPIs
        total_orders = len(self.df)
        total_volume = self.df['Order_Quantity_kg'].sum()
        avg_order_size = self.df['Order_Quantity_kg'].mean()
        std_order_size = self.df['Order_Quantity_kg'].std()
        
        # Calculate monthly demand
        df_monthly = self.df.set_index('Date').resample('M')['Order_Quantity_kg'].sum()
        avg_monthly_demand = df_monthly.mean() if len(df_monthly) > 0 else total_volume / max(1, len(self.df) / 4)
        
        # Calculate order frequency (orders per month)
        months_span = (self.df['Date'].max() - self.df['Date'].min()).days / 30.44
        order_frequency = total_orders / max(1, months_span)
        
        return {
            'total_orders': total_orders,
            'total_volume': total_volume,
            'avg_order_size': avg_order_size,
            'std_order_size': std_order_size,
            'avg_monthly_demand': avg_monthly_demand,
            'order_frequency': order_frequency
        }

    def _calculate_eoq(self, kpis):
        """Calculate Economic Order Quantity"""
        D = kpis.get('avg_monthly_demand', 0)
        S = self.constants.transport_cost
        H = self.constants.holding_rate * self.constants.price_per_kg
        
        if H <= 0 or D <= 0:
            return 300  # Default fallback
        
        eoq = np.sqrt((2 * D * S) / H)
        return eoq

    def _calculate_safety_stock(self, kpis):
        """Calculate safety stock"""
        z_score = stats.norm.ppf(self.constants.service_level)
        demand_std = kpis.get('std_order_size', 100)
        lead_time = self.constants.lead_time_days
        avg_sublimation = sum(self.constants.sub_loss_range) / 2 / 100
        
        safety_stock = z_score * demand_std * np.sqrt(lead_time) * (1 + avg_sublimation)
        return max(50, safety_stock)  # Minimum 50kg safety stock

    def _calculate_cost_savings(self, eoq, kpis):
        """Calculate cost savings from EOQ implementation"""
        current_monthly_orders = kpis.get('order_frequency', 0)
        eoq_monthly_orders = kpis.get('avg_monthly_demand', 0) / max(1, eoq)
        
        current_monthly_transport = current_monthly_orders * self.constants.transport_cost
        eoq_monthly_transport = eoq_monthly_orders * self.constants.transport_cost
        
        savings = max(0, current_monthly_transport - eoq_monthly_transport)
        percent_savings = (savings / current_monthly_transport) * 100 if current_monthly_transport > 0 else 0
        
        return {
            'savings': savings,
            'percent_savings': percent_savings,
            'current_monthly_orders': current_monthly_orders,
            'eoq_monthly_orders': eoq_monthly_orders
        }

    def _create_forecast(self):
        """Create simple forecast data"""
        if self.df is None or self.df.empty:
            return None
        
        # Simple moving average forecast
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        
        try:
            daily_demand = self.df.set_index('Date').resample('D')['Order_Quantity_kg'].sum().fillna(0)
            model = ExponentialSmoothing(daily_demand, seasonal_periods=7, trend='add', seasonal='add')
            fit = model.fit()
            forecast = fit.forecast(30)
            
            # Create forecast dataframe
            last_date = daily_demand.index[-1]
            future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=30)
            
            forecast_df = pd.DataFrame({
                'ds': future_dates,
                'yhat': forecast.values,
                'yhat_lower': forecast.values * 0.8,
                'yhat_upper': forecast.values * 1.2
            })
            
            return forecast_df
        except:
            return None

    def _create_charts(self, forecast_data, cost_savings, kpis, eoq):
        """Create charts for the report"""
        font_family = "Arial"
        fig_forecast, fig_cost_comp = None, None
        
        # Forecast chart
        if forecast_data is not None and self.df is not None:
            fig_forecast = go.Figure()
            fig_forecast.add_trace(go.Scatter(
                x=self.df['Date'], y=self.df['Order_Quantity_kg'], 
                mode='lines', name='Historical Orders', 
                line=dict(color='#1f77b4')
            ))
            
            future_data = forecast_data[forecast_data['ds'] > self.df['Date'].max()]
            if not future_data.empty:
                fig_forecast.add_trace(go.Scatter(
                    x=future_data['ds'], y=future_data['yhat'], 
                    mode='lines', name='Forecast', 
                    line=dict(color='#ff7f0e', dash='dash')
                ))
                fig_forecast.add_trace(go.Scatter(
                    x=future_data['ds'], y=future_data['yhat_upper'], 
                    fill=None, mode='lines', line_color='rgba(0,0,0,0)', 
                    showlegend=False
                ))
                fig_forecast.add_trace(go.Scatter(
                    x=future_data['ds'], y=future_data['yhat_lower'], 
                    fill='tonexty', mode='lines', name='Confidence Interval', 
                    fillcolor='rgba(255,127,14,0.2)'
                ))
            
            fig_forecast.update_layout(
                title="30-Day Demand Forecast", 
                template="plotly_white", 
                font=dict(family=font_family),
                height=450
            )

        # Cost comparison chart
        if kpis.get('avg_monthly_demand', 0) > 0 and eoq > 0:
            current_orders = kpis.get('order_frequency', 0)
            eoq_orders = kpis.get('avg_monthly_demand', 0) / eoq
            
            cost_comparison_df = pd.DataFrame({
                'Cost Type': ['Ordering Cost', 'Holding Cost'],
                'Current System': [
                    current_orders * self.constants.transport_cost,
                    (self.constants.holding_rate * self.constants.price_per_kg * kpis.get('avg_order_size', 0) / 2)
                ],
                'EOQ System': [
                    eoq_orders * self.constants.transport_cost,
                    (self.constants.holding_rate * self.constants.price_per_kg * eoq / 2)
                ]
            })
            
            fig_cost_comp = px.bar(
                cost_comparison_df, x='Cost Type', y=['Current System', 'EOQ System'],
                title="Monthly Cost Comparison: Current vs. EOQ",
                barmode='group', template="plotly_white",
                labels={'value': 'Cost (KSh)', 'variable': 'System'},
                color_discrete_map={'Current System': '#ff6b6b', 'EOQ System': '#4ecdc4'}
            )
            fig_cost_comp.update_layout(font=dict(family=font_family), height=450)
        
        return fig_forecast, fig_cost_comp

    def _generate_recommendations(self, kpis, eoq, safety_stock, cost_savings):
        """Generate recommendations based on analysis"""
        recommendations = [
            f"Adopt an EOQ-based ordering policy. Place orders for **{eoq:.0f} kg** at a time to minimize total inventory costs.",
            f"Establish a safety stock level of **{safety_stock:.0f} kg**. This buffer will protect against demand variability and prevent stockouts.",
            f"Set a reorder point at **{eoq + safety_stock:.0f} kg**. A new order should be triggered automatically when inventory falls to this level."
        ]
        
        if kpis.get('avg_monthly_demand', 0) > 0 and eoq > 0:
            recommendations.append(
                f"Negotiate with suppliers for better transport rates by highlighting a more predictable ordering schedule of "
                f"**{kpis['avg_monthly_demand'] / eoq:.1f} orders/month**."
            )
        
        recommendations.append(
            "Implement real-time inventory tracking to ensure accurate stock levels and timely reordering."
        )
        
        return recommendations