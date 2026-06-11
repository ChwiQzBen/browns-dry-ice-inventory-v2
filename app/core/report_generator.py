from fpdf import FPDF
from datetime import datetime
import os
import pandas as pd
from .advanced_reporting import AdvancedReporting

class ReportGenerator:
    """Report generator that uses AdvancedReporting without inheritance"""
    
    def __init__(self, analyzer, df=None):
        """
        Initialize with:
        - analyzer: The analyzer object containing business logic
        - df: Optional explicit dataframe (falls back to analyzer.df or analyzer.data)
        """
        self.analyzer = analyzer
        self.report_date = datetime.now().strftime("%Y%m%d_%H%M")
        
        # Get dataframe from most available source
        self.df = df if df is not None else (
            analyzer.df if hasattr(analyzer, 'df') else
            analyzer.data if hasattr(analyzer, 'data') else
            None
        )
        
        if self.df is None:
            raise AttributeError("No DataFrame available for report generation")
        
        # Create AdvancedReporting instance (not inheritance)
        self.reporting = AdvancedReporting(analyzer=analyzer, df=self.df)

    def generate_pdf(self):
        """Generate a comprehensive PDF report"""
        try:
            os.makedirs("reports", exist_ok=True)
            
            # Use AdvancedReporting to generate the report
            return self.reporting.generate_custom_report(
                report_type='executive_summary',
                parameters={'period': 'July 2024 - June 2025'},
                filename=f"reports/dry_ice_analysis_report_{self.report_date}.pdf"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to generate PDF: {str(e)}")