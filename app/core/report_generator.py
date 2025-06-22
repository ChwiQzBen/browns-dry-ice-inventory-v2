from fpdf import FPDF
from datetime import datetime
import os
import pandas as pd
from .advanced_reporting import AdvancedReporting


class ReportGenerator(AdvancedReporting):
    def generate_pdf(self):
        """Generate a comprehensive, visually-rich PDF report."""
        # The base class method now handles everything. We just specify the report type.
        return super().generate_custom_report(
            'executive_summary', 
            {'period': 'July 2024 - June 2025'}, # Parameters can be used for future customization
            f"reports/dry_ice_analysis_report_{self.report_date}.pdf"
        )
