from fpdf import FPDF
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import tempfile
from pathlib import Path # <--- 1. IMPORT PATHLIB

# --- Utility Function ---
def create_versioned_file(base_filename):
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
        
        # --- 2. THE FIX: BUILD ROBUST FILE PATHS ---
        # Get the project root directory (which is 3 levels up from this file)
        # app/core/advanced_reporting.py -> app/core -> app -> [project_root]
        project_root = Path(__file__).parent.parent.parent
        font_dir = project_root / "assets" / "fonts"

        try:
            self.add_font("Noto", "", font_dir / "NotoSans-Regular.ttf")
            self.add_font("Noto", "B", font_dir / "NotoSans-Bold.ttf")
            self.add_font("Noto", "I", font_dir / "NotoSans-Italic.ttf")
            self.font_family = "Noto"
        except RuntimeError as e:
            # This error will now be more descriptive on the server
            print(f"ERROR: Could not load font. Path: {font_dir}. Error: {e}")
            self.font_family = "Arial"


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
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", 0, 0, 'C')

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
        self.cell(90, 8, f"{value} {unit} ", 1, 1, 'R', fill=True)
        self.ln(2)

    def add_recommendation(self, text):
        self.set_font(self.font_family, '', 10)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 5, f"• {text}")
        self.ln(2)

    def add_plotly_chart(self, fig, chart_name):
        chart_dir = os.path.join(tempfile.gettempdir(), 'report_charts')
        os.makedirs(chart_dir, exist_ok=True)
        
        chart_path = os.path.join(chart_dir, f"{chart_name}.png")
        fig.write_image(chart_path, width=800, height=450, scale=2)
        
        self.image(chart_path, w=self.w - self.l_margin - self.r_margin)
        
        os.remove(chart_path)
        self.ln(5)

# --- AdvancedReporting Class (no changes here) ---
class AdvancedReporting:
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.report_date = datetime.now().strftime("%d-%m-%Y")

    def generate_custom_report(self, report_type, parameters, filename=None):
        try:
            kpis = self.analyzer.calculate_kpis()
            eoq = self.analyzer.calculate_eoq()
            safety_stock = self.analyzer.calculate_safety_stock()
            cost_savings = self.analyzer.calculate_cost_savings(eoq)
            forecast_data = self.analyzer.forecast_demand(periods=30)
            
            fig_forecast, fig_cost_comp = self._create_charts(forecast_data, cost_savings, kpis, eoq)
            recommendations = self._generate_recommendations(kpis, eoq, safety_stock, cost_savings)
            
            pdf = PDFReport()
            pdf.alias_nb_pages()
            pdf.add_page()
            
            pdf.set_font(pdf.font_family, 'B', 24)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 15, "Dry Ice Inventory Optimization Report", 0, 1, 'C')
            pdf.ln(5)
            
            pdf.chapter_title("Executive Summary")
            summary_text = (
                f"This report provides a comprehensive analysis of the dry ice inventory for the period from "
                f"{self.analyzer.data_loader.df['Date'].min().strftime('%d-%b-%Y')} to "
                f"{self.analyzer.data_loader.df['Date'].max().strftime('%d-%b-%Y')}. "
                f"The analysis identifies significant opportunities for cost savings and operational efficiency. "
                f"By implementing an EOQ-based inventory policy, an estimated KSh {cost_savings['savings']:,.0f} "
                f"can be saved monthly, representing a {cost_savings['percent_savings']:.1f}% reduction in inventory costs."
            )
            pdf.chapter_body(summary_text)

            pdf.chapter_title("Key Performance Indicators (KPIs)")
            pdf.add_kpi_card("Potential Monthly Savings", f"KSh {cost_savings['savings']:,.0f}", "", color=(212, 237, 218))
            pdf.add_kpi_card("Economic Order Quantity (EOQ)", f"{eoq:,.0f}", "kg")
            pdf.add_kpi_card("Recommended Safety Stock", f"{safety_stock:,.0f}", "kg")
            pdf.add_kpi_card("Reorder Point", f"{eoq + safety_stock:,.0f}", "kg")
            pdf.add_kpi_card("Average Monthly Demand", f"{kpis['avg_monthly_demand']:,.0f}", "kg")
            pdf.ln(10)
            
            pdf.chapter_title("Top Recommendations")
            for rec in recommendations[:3]:
                pdf.add_recommendation(rec)

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

            if filename is None:
                filename = f"reports/{report_type}_report_{self.report_date}.pdf"
            versioned_filename = create_versioned_file(filename)
            pdf.output(versioned_filename)
            return versioned_filename

        except Exception as e:
            print(f"FATAL ERROR during PDF generation: {e}")
            import traceback
            traceback.print_exc()
            raise e

    def _create_charts(self, forecast_data, cost_savings, kpis, eoq):
        font_family = "Noto Sans" if os.path.exists("assets/fonts/NotoSans-Regular.ttf") else "Arial"
        fig_forecast, fig_cost_comp = None, None
        
        if forecast_data is not None:
            df = self.analyzer.data_loader.df
            fig_forecast = go.Figure()
            fig_forecast.add_trace(go.Scatter(
                x=df['Date'], y=df['Order_Quantity_kg'], mode='lines', name='Historical Orders', line=dict(color='#1f77b4')
            ))
            future_data = forecast_data[forecast_data['ds'] > df['Date'].max()]
            fig_forecast.add_trace(go.Scatter(
                x=future_data['ds'], y=future_data['yhat'], mode='lines', name='Forecast', line=dict(color='#ff7f0e', dash='dash')
            ))
            fig_forecast.add_trace(go.Scatter(
                x=future_data['ds'], y=future_data['yhat_upper'], fill=None, mode='lines', line_color='rgba(0,0,0,0)', showlegend=False
            ))
            fig_forecast.add_trace(go.Scatter(
                x=future_data['ds'], y=future_data['yhat_lower'], fill='tonexty', mode='lines', name='Confidence Interval', fillcolor='rgba(255,127,14,0.2)'
            ))
            fig_forecast.update_layout(title="30-Day Demand Forecast", template="plotly_white", font=dict(family=font_family))

        cost_comparison_df = pd.DataFrame({
            'Cost Type': ['Ordering Cost', 'Holding Cost'],
            'Current System': [
                (kpis['current_monthly_volume'] / kpis['avg_order_size']) * self.analyzer.constants['TRANSPORT_COST'],
                (self.analyzer.constants['HOLDING_RATE'] * self.analyzer.constants['PRICE_PER_KG'] * kpis['avg_order_size'] / 2)
            ],
            'EOQ System': [
                (kpis['current_monthly_volume'] / eoq) * self.analyzer.constants['TRANSPORT_COST'],
                (self.analyzer.constants['HOLDING_RATE'] * self.analyzer.constants['PRICE_PER_KG'] * eoq / 2)
            ]
        })
        fig_cost_comp = px.bar(
            cost_comparison_df, x='Cost Type', y=['Current System', 'EOQ System'],
            title="Monthly Cost Comparison: Current vs. EOQ",
            barmode='group', template="plotly_white",
            labels={'value': 'Cost (KSh)', 'variable': 'System'},
            color_discrete_map={'Current System': '#ff6b6b', 'EOQ System': '#4ecdc4'}
        )
        fig_cost_comp.update_layout(font=dict(family=font_family))
        
        return fig_forecast, fig_cost_comp

    def _generate_recommendations(self, kpis, eoq, safety_stock, cost_savings):
        return [
            f"Adopt an EOQ-based ordering policy. Place orders for **{eoq:.0f} kg** at a time to minimize total inventory costs.",
            f"Establish a safety stock level of **{safety_stock:.0f} kg**. This buffer will protect against demand variability and prevent stockouts.",
            f"Set a reorder point at **{eoq + safety_stock:.0f} kg**. A new order should be triggered automatically when inventory falls to this level.",
            f"Negotiate with suppliers for better transport rates by highlighting a more predictable ordering schedule of **{kpis['current_monthly_volume'] / eoq:.1f} orders/month**.",
            "Implement real-time inventory tracking to ensure accurate stock levels and timely reordering."
        ]