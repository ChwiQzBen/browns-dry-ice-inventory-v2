"""
app/core/commercial_reports.py
=================================
Report data builder + PDF generator for Commercial (Sales + LPO) — mirrors
the split already used for Manufacturing's production_reports.py: a plain
dataclass built from cheese_data_access queries, a text summary, and a
reportlab PDF, all independent of Streamlit.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Dict, Any


@dataclass
class CommercialReportData:
    start_date: date
    end_date: date
    total_revenue: float
    total_kg: float
    total_sales_transactions: int
    revenue_by_product: List[Dict[str, Any]] = field(default_factory=list)
    revenue_by_customer: List[Dict[str, Any]] = field(default_factory=list)
    lpo_total_kg: float = 0.0
    lpo_fill_rate_pct: float = 0.0
    lpo_cancelled_count: int = 0
    lpo_status_counts: Dict[str, int] = field(default_factory=dict)


def build_commercial_report_data(sales: List[Dict[str, Any]],
                                  lpo_lines: List[Dict[str, Any]],
                                  start_date: date, end_date: date) -> CommercialReportData:
    total_revenue = sum(float(s["revenue"]) for s in sales)
    total_kg = sum(float(s["quantity_kg"]) for s in sales)

    by_product: Dict[str, Dict[str, float]] = {}
    for s in sales:
        d = by_product.setdefault(s["cheese_name"], {"revenue": 0.0, "kg": 0.0, "count": 0})
        d["revenue"] += float(s["revenue"])
        d["kg"] += float(s["quantity_kg"])
        d["count"] += 1
    revenue_by_product = sorted(
        [{"cheese_name": k, **v} for k, v in by_product.items()],
        key=lambda r: r["revenue"], reverse=True,
    )

    by_customer: Dict[str, Dict[str, float]] = {}
    for s in sales:
        name = (s.get("customer") or "").strip()
        if not name:
            continue
        d = by_customer.setdefault(name, {"revenue": 0.0, "kg": 0.0, "count": 0})
        d["revenue"] += float(s["revenue"])
        d["kg"] += float(s["quantity_kg"])
        d["count"] += 1
    revenue_by_customer = sorted(
        [{"customer": k, **v} for k, v in by_customer.items()],
        key=lambda r: r["revenue"], reverse=True,
    )

    lpo_total_kg = sum(float(l["quantity_kg"]) for l in lpo_lines)
    delivered = [l for l in lpo_lines if l["status"] in ("Delivered", "Partially Delivered")]
    delivered_kg = sum(float(l.get("quantity_delivered_kg") or 0) for l in delivered)
    fill_rate = (delivered_kg / lpo_total_kg * 100) if lpo_total_kg > 0 else 0.0
    cancelled = sum(1 for l in lpo_lines if l["status"] == "Cancelled")
    status_counts: Dict[str, int] = {}
    for l in lpo_lines:
        status_counts[l["status"]] = status_counts.get(l["status"], 0) + 1

    return CommercialReportData(
        start_date=start_date, end_date=end_date,
        total_revenue=total_revenue, total_kg=total_kg, total_sales_transactions=len(sales),
        revenue_by_product=revenue_by_product, revenue_by_customer=revenue_by_customer,
        lpo_total_kg=lpo_total_kg, lpo_fill_rate_pct=fill_rate,
        lpo_cancelled_count=cancelled, lpo_status_counts=status_counts,
    )


def summarize_commercial_report_data(data: CommercialReportData) -> str:
    lines = [
        f"Commercial Report — {data.start_date} to {data.end_date}",
        f"Revenue: KSh {data.total_revenue:,.0f} across {data.total_sales_transactions} sale(s), "
        f"{data.total_kg:,.1f} kg total.",
        f"LPO volume: {data.lpo_total_kg:,.1f} kg, {data.lpo_fill_rate_pct:.0f}% fill rate, "
        f"{data.lpo_cancelled_count} cancelled.",
    ]
    if data.revenue_by_product:
        top = data.revenue_by_product[0]
        lines.append(f"Top product: {top['cheese_name']} (KSh {top['revenue']:,.0f}).")
    if data.revenue_by_customer:
        top_c = data.revenue_by_customer[0]
        lines.append(f"Top customer: {top_c['customer']} (KSh {top_c['revenue']:,.0f}).")
    return "\n".join(lines)


def generate_commercial_report(data: CommercialReportData, output_path: str) -> str:
    """Builds a PDF at output_path and returns the path — same reportlab
    pattern as main.py's generate_enhanced_pdf_report / the dry ice reports,
    so the download flow in the UI tab matches Production Reports exactly."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER
    except ImportError as e:
        raise ImportError("PDF generation requires reportlab: pip install reportlab") from e

    doc = SimpleDocTemplate(output_path, pagesize=letter,
                             rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=22,
                                  textColor=colors.HexColor('#1f77b4'), alignment=TA_CENTER, spaceAfter=24)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=15,
                                    textColor=colors.HexColor('#333333'), spaceAfter=10)

    elements.append(Paragraph("Commercial Report", title_style))
    elements.append(Paragraph(f"{data.start_date.strftime('%b %d, %Y')} \u2013 {data.end_date.strftime('%b %d, %Y')}",
                               styles['Normal']))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
    elements.append(Spacer(1, 16))

    elements.append(Paragraph("Summary", heading_style))
    summary_data = [
        ['Metric', 'Value'],
        ['Total Revenue', f"KSh {data.total_revenue:,.0f}"],
        ['Total Volume', f"{data.total_kg:,.1f} kg"],
        ['Sales Transactions', f"{data.total_sales_transactions}"],
        ['LPO Volume', f"{data.lpo_total_kg:,.1f} kg"],
        ['LPO Fill Rate', f"{data.lpo_fill_rate_pct:.0f}%"],
        ['LPOs Cancelled', f"{data.lpo_cancelled_count}"],
    ]
    summary_table = Table(summary_data, colWidths=[2.5 * inch, 2.5 * inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4e79a7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6), ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    if data.revenue_by_product:
        elements.append(Paragraph("Revenue by Product", heading_style))
        prod_data = [['Cheese', 'Revenue', 'Kg', 'Sales']]
        for r in data.revenue_by_product:
            prod_data.append([r['cheese_name'], f"KSh {r['revenue']:,.0f}", f"{r['kg']:,.1f}", f"{r['count']}"])
        prod_table = Table(prod_data, colWidths=[2 * inch, 1.7 * inch, 1.3 * inch, 1 * inch])
        prod_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 5), ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ]))
        elements.append(prod_table)
        elements.append(Spacer(1, 20))

    if data.revenue_by_customer:
        elements.append(Paragraph("Revenue by Customer", heading_style))
        cust_data = [['Customer', 'Revenue', 'Kg', 'Sales']]
        for r in data.revenue_by_customer[:20]:
            cust_data.append([r['customer'], f"KSh {r['revenue']:,.0f}", f"{r['kg']:,.1f}", f"{r['count']}"])
        if len(data.revenue_by_customer) > 20:
            cust_data.append(['', '', f'and {len(data.revenue_by_customer) - 20} more...', ''])
        cust_table = Table(cust_data, colWidths=[2 * inch, 1.7 * inch, 1.3 * inch, 1 * inch])
        cust_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 5), ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ]))
        elements.append(cust_table)
        elements.append(Spacer(1, 20))

    if data.lpo_status_counts:
        elements.append(Paragraph("LPO Status Breakdown", heading_style))
        status_data = [['Status', 'Count']] + [[k, str(v)] for k, v in data.lpo_status_counts.items()]
        status_table = Table(status_data, colWidths=[2.5 * inch, 2.5 * inch])
        status_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ff9800')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fff3e0')),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6), ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        elements.append(status_table)

    elements.append(Spacer(1, 30))
    elements.append(Paragraph("Report generated by Browns Cheese \u2014 MarginIQ Ops Suite", styles['Normal']))

    doc.build(elements)
    return output_path


if __name__ == "__main__":
    import os

    sales = [
        {"date": "2026-07-01", "cheese_name": "Mozzarella", "quantity_kg": 10.0, "revenue": 6500.0, "customer": "Java House"},
        {"date": "2026-07-02", "cheese_name": "Cheddar", "quantity_kg": 5.0, "revenue": 3750.0, "customer": "Carrefour"},
        {"date": "2026-07-03", "cheese_name": "Mozzarella", "quantity_kg": 8.0, "revenue": 5200.0, "customer": ""},
    ]
    lpo_lines = [
        {"quantity_kg": 15.0, "quantity_delivered_kg": 15.0, "status": "Delivered"},
        {"quantity_kg": 10.0, "quantity_delivered_kg": None, "status": "Pending"},
        {"quantity_kg": 5.0, "quantity_delivered_kg": None, "status": "Cancelled"},
    ]

    print("Test 1: build_commercial_report_data")
    data = build_commercial_report_data(sales, lpo_lines, date(2026, 7, 1), date(2026, 7, 31))
    print(f"  total_revenue={data.total_revenue}, total_kg={data.total_kg}, "
          f"transactions={data.total_sales_transactions}")
    assert data.total_revenue == 15450.0
    assert data.total_kg == 23.0
    assert data.total_sales_transactions == 3
    assert len(data.revenue_by_customer) == 2, "blank customer sale should be excluded"
    assert data.revenue_by_product[0]["cheese_name"] == "Mozzarella"  # 6500+5200=11700 > Cheddar's 3750
    assert data.lpo_total_kg == 30.0
    assert data.lpo_fill_rate_pct == 50.0, f"got {data.lpo_fill_rate_pct}"  # 15/30
    assert data.lpo_cancelled_count == 1

    print("\nTest 2: summarize_commercial_report_data")
    summary = summarize_commercial_report_data(data)
    print(summary)

    print("\nTest 3: generate_commercial_report (actual PDF via reportlab)")
    out_path = "/tmp/test_commercial_report.pdf"
    result_path = generate_commercial_report(data, out_path)
    assert os.path.exists(result_path), "PDF file should exist"
    size = os.path.getsize(result_path)
    print(f"  PDF generated at {result_path}, size={size} bytes")
    assert size > 1000, "PDF should have real content, not be near-empty"
    with open(result_path, "rb") as f:
        header = f.read(5)
    assert header == b"%PDF-", "file should be a valid PDF"
    os.remove(result_path)

    print("\nAll commercial_reports checks passed.")