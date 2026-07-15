"""
production_reports.py
========================
Generates a PDF report covering batch yield and QC statistics for the
Cheese Production system, reading directly from BatchTracker/RecipeBook —
no separate reporting database, no re-derivation of business logic.

Two-step design so the numbers can be tested (and shown inline in the UI
as a quick preview) without necessarily rendering a PDF every time:

    data = build_report_data(tracker, book, start_date, end_date)
    path = generate_production_report_pdf(data, output_path)

or just:

    path = generate_production_report(tracker, book, start_date, end_date)

SCOPE OF "PERIOD" FILTERING
---------------------------
Batch-yield figures (batches started, kg produced, kg released) are scoped
to [start_date, end_date] using each batch's own date field (created_at /
packaging_date). QC ALERTS (currently failed-QC batches, currently-aging
batches, aging batches with a failed quarterly check) are NOT date-scoped —
these reflect CURRENT operational state regardless of the report period,
the same way the Batch Tracking & QC tab always shows live status rather
than a historical snapshot. A batch that failed QC three weeks ago and is
still sitting unresolved is still something this report should surface.

DEPENDENCY NOTE
----------------
Uses reportlab (per the project's pdf-creation convention — main.py's
existing generate_enhanced_pdf_report() for All-Items reports already
uses it). reportlab was NOT in the requirements.txt checked against —
add it or this raises ImportError at generate time, with a clear message
rather than a silent failure.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional
import os

from production_tracking import (
    BatchTracker, RecipeBook, ProductionBatch, AgingBatch, FinishedGoodBatch,
    BatchStatus,
)


@dataclass
class QCStageStats:
    stage: str
    passed: int = 0
    failed: int = 0
    pending: int = 0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.pending

    @property
    def pass_rate(self) -> float:
        resolved = self.passed + self.failed
        return (self.passed / resolved) if resolved > 0 else 0.0


@dataclass
class YieldComparison:
    cheese_name: str
    aging_batch_id: str
    aging_years: float
    starting_quantity_kg: float
    expected_yield_kg: float
    actual_yield_kg: float

    @property
    def variance_pct(self) -> float:
        if self.expected_yield_kg <= 0:
            return 0.0
        return (self.actual_yield_kg - self.expected_yield_kg) / self.expected_yield_kg * 100


@dataclass
class ProductionReportData:
    period_start: Optional[datetime]
    period_end: Optional[datetime]
    generated_at: datetime
    total_batches_started: int
    total_kg_produced: float
    total_kg_released: float
    batches_by_status: Dict[str, int]
    production_qc_stats: List[QCStageStats]
    aging_qc_stats: List[QCStageStats]
    failed_qc_batches: List[ProductionBatch]
    failed_aging_batches: List[AgingBatch]
    currently_aging: List[AgingBatch]
    yield_comparisons: List[YieldComparison]
    finished_batches_in_period: List[FinishedGoodBatch]


def _in_range(dt: datetime, start: Optional[datetime], end: Optional[datetime]) -> bool:
    if start is not None and dt < start:
        return False
    if end is not None and dt > end:
        return False
    return True


def _tally_checkpoints(batches, get_checkpoints) -> List[QCStageStats]:
    stats: Dict[str, QCStageStats] = {}
    for batch in batches:
        for cp in get_checkpoints(batch):
            s = stats.setdefault(cp.stage, QCStageStats(stage=cp.stage))
            if cp.status == "Passed":
                s.passed += 1
            elif cp.status == "Failed":
                s.failed += 1
            else:
                s.pending += 1
    return list(stats.values())


def build_report_data(tracker: BatchTracker, book: RecipeBook,
                       start_date: Optional[date] = None,
                       end_date: Optional[date] = None) -> ProductionReportData:
    """Builds all report figures from live tracker state. start_date/end_date
    scope the yield figures; QC alerts and aging status are always current
    (see module docstring)."""

    period_start = datetime.combine(start_date, datetime.min.time()) if start_date else None
    period_end = datetime.combine(end_date, datetime.max.time()) if end_date else None

    production_in_period = [
        b for b in tracker.production_batches.values()
        if _in_range(b.created_at, period_start, period_end)
    ]
    aging_in_period = [
        b for b in tracker.aging_batches.values()
        if _in_range(b.start_date, period_start, period_end)
    ]
    finished_in_period = [
        b for b in tracker.finished_batches.values()
        if _in_range(b.packaging_date, period_start, period_end)
    ]

    batches_by_status: Dict[str, int] = {}
    for b in production_in_period:
        batches_by_status[b.status.value] = batches_by_status.get(b.status.value, 0) + 1

    production_qc_stats = _tally_checkpoints(production_in_period, lambda b: b.checkpoints)
    aging_qc_stats = _tally_checkpoints(aging_in_period, lambda b: b.checkpoints)

    # Always-current operational alerts (not period-scoped) — see docstring.
    failed_qc_batches = [
        b for b in tracker.production_batches.values() if b.status == BatchStatus.FAILED_QC
    ]
    failed_aging_batches = [
        b for b in tracker.aging_batches.values() if b.any_failed()
    ]
    currently_aging = [
        b for b in tracker.aging_batches.values() if b.status == BatchStatus.AGING
    ]

    yield_comparisons = []
    for fb in finished_in_period:
        if not fb.aging_batch_id:
            continue  # fresh-release path has no separate expected-vs-actual figure today
        ab = tracker.aging_batches.get(fb.aging_batch_id)
        if ab is None:
            continue
        recipe = book.get(fb.cheese_name) if fb.cheese_name in book else None
        if recipe and recipe.aging:
            expected_yield = ab.starting_quantity_kg * (recipe.aging.yield_rate ** ab.aging_years)
        else:
            expected_yield = ab.starting_quantity_kg
        yield_comparisons.append(YieldComparison(
            cheese_name=fb.cheese_name,
            aging_batch_id=ab.batch_id,
            aging_years=ab.aging_years,
            starting_quantity_kg=ab.starting_quantity_kg,
            expected_yield_kg=expected_yield,
            actual_yield_kg=fb.quantity_kg,
        ))

    return ProductionReportData(
        period_start=period_start,
        period_end=period_end,
        generated_at=datetime.now(),
        total_batches_started=len(production_in_period),
        total_kg_produced=sum(b.quantity_kg for b in production_in_period),
        total_kg_released=sum(b.quantity_kg for b in finished_in_period),
        batches_by_status=batches_by_status,
        production_qc_stats=production_qc_stats,
        aging_qc_stats=aging_qc_stats,
        failed_qc_batches=failed_qc_batches,
        failed_aging_batches=failed_aging_batches,
        currently_aging=currently_aging,
        yield_comparisons=yield_comparisons,
        finished_batches_in_period=finished_in_period,
    )


def summarize_report_data(data: ProductionReportData) -> str:
    """Plain-text preview — same idea as ProductionPlan.summary()."""
    lines = ["Production Report"]
    period = "All time"
    if data.period_start or data.period_end:
        s = data.period_start.strftime("%Y-%m-%d") if data.period_start else "…"
        e = data.period_end.strftime("%Y-%m-%d") if data.period_end else "…"
        period = f"{s} to {e}"
    lines.append(f"Period: {period}  |  Generated: {data.generated_at.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append(f"Batches started: {data.total_batches_started}  ({data.total_kg_produced:.1f} kg)")
    lines.append(f"Batches released to finished goods: {len(data.finished_batches_in_period)}  "
                 f"({data.total_kg_released:.1f} kg)")
    if data.batches_by_status:
        lines.append("Status breakdown: " + ", ".join(f"{k}: {v}" for k, v in data.batches_by_status.items()))
    lines.append("")
    lines.append(f"⚠ Currently failed QC (unresolved): {len(data.failed_qc_batches)}")
    lines.append(f"⚠ Aging batches with a failed check: {len(data.failed_aging_batches)}")
    lines.append(f"🧊 Currently aging: {len(data.currently_aging)}")
    if data.yield_comparisons:
        avg_variance = sum(y.variance_pct for y in data.yield_comparisons) / len(data.yield_comparisons)
        lines.append(f"📊 Aged-release yield comparisons: {len(data.yield_comparisons)}  "
                     f"(avg variance {avg_variance:+.1f}%)")
    return "\n".join(lines)


def generate_production_report_pdf(data: ProductionReportData, output_path: str) -> str:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    except ImportError as e:
        raise ImportError(
            "reportlab is required to generate PDF reports but isn't installed. "
            "Add 'reportlab' to requirements.txt."
        ) from e

    doc = SimpleDocTemplate(output_path, pagesize=letter,
                             rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=22,
                                  textColor=colors.HexColor('#1a237e'), alignment=TA_CENTER, spaceAfter=20)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=15,
                                    textColor=colors.HexColor('#333333'), spaceBefore=16, spaceAfter=8)

    def styled_table(data_rows, col_widths, header_color='#4e79a7'):
        t = Table(data_rows, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(header_color)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
        ]))
        return t

    elements = []
    elements.append(Paragraph("Cheese Production Report", title_style))
    period = "All time"
    if data.period_start or data.period_end:
        s = data.period_start.strftime("%B %d, %Y") if data.period_start else "…"
        e = data.period_end.strftime("%B %d, %Y") if data.period_end else "…"
        period = f"{s} — {e}"
    elements.append(Paragraph(f"Period: {period}", styles['Normal']))
    elements.append(Paragraph(f"Generated: {data.generated_at.strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
    elements.append(Spacer(1, 16))

    # ---- Executive summary ----
    elements.append(Paragraph("Executive Summary", heading_style))
    summary_rows = [['Metric', 'Value']]
    summary_rows.append(['Batches started', f"{data.total_batches_started}"])
    summary_rows.append(['Kg produced', f"{data.total_kg_produced:,.1f} kg"])
    summary_rows.append(['Batches released to finished goods', f"{len(data.finished_batches_in_period)}"])
    summary_rows.append(['Kg released', f"{data.total_kg_released:,.1f} kg"])
    for status, count in data.batches_by_status.items():
        summary_rows.append([f"  status: {status}", f"{count}"])
    elements.append(styled_table(summary_rows, [3.5 * inch, 2 * inch]))
    elements.append(Spacer(1, 12))

    # ---- Operational alerts (always current) ----
    elements.append(Paragraph("Operational Alerts (Current, Not Period-Scoped)", heading_style))
    alert_rows = [['Alert', 'Count']]
    alert_rows.append(['Batches currently failed QC (unresolved)', f"{len(data.failed_qc_batches)}"])
    alert_rows.append(['Aging batches with a failed quarterly check', f"{len(data.failed_aging_batches)}"])
    alert_rows.append(['Batches currently aging', f"{len(data.currently_aging)}"])
    elements.append(styled_table(alert_rows, [4 * inch, 1.5 * inch], header_color='#dc3545'))

    if data.failed_qc_batches:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("Failed-QC batches needing resolution:", styles['Normal']))
        rows = [['Batch ID', 'Cheese', 'Qty (kg)', 'Operator']]
        for b in data.failed_qc_batches[:20]:
            rows.append([b.batch_id, b.cheese_name, f"{b.quantity_kg:.1f}", b.operator])
        elements.append(styled_table(rows, [1.6 * inch, 1.6 * inch, 1 * inch, 1.6 * inch], header_color='#dc3545'))

    if data.failed_aging_batches:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("Aging batches with a failed check — cannot be released:", styles['Normal']))
        rows = [['Batch ID', 'Cheese', 'Starting Kg', 'Days Remaining']]
        for b in data.failed_aging_batches[:20]:
            rows.append([b.batch_id, b.cheese_name, f"{b.starting_quantity_kg:.1f}", f"{b.days_remaining()}"])
        elements.append(styled_table(rows, [1.6 * inch, 1.6 * inch, 1.2 * inch, 1.4 * inch], header_color='#dc3545'))

    elements.append(Spacer(1, 12))

    # ---- QC stage stats ----
    elements.append(Paragraph("Production QC Checkpoint Stats (Period)", heading_style))
    if data.production_qc_stats:
        rows = [['Stage', 'Passed', 'Failed', 'Pending', 'Pass Rate']]
        for s in data.production_qc_stats:
            rows.append([s.stage, f"{s.passed}", f"{s.failed}", f"{s.pending}", f"{s.pass_rate:.0%}"])
        elements.append(styled_table(rows, [2.2 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 1 * inch],
                                      header_color='#28a745'))
    else:
        elements.append(Paragraph("No production batches in this period.", styles['Normal']))

    if data.aging_qc_stats:
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Aging QC Checkpoint Stats (Period)", heading_style))
        rows = [['Stage', 'Passed', 'Failed', 'Pending', 'Pass Rate']]
        for s in data.aging_qc_stats:
            rows.append([s.stage, f"{s.passed}", f"{s.failed}", f"{s.pending}", f"{s.pass_rate:.0%}"])
        elements.append(styled_table(rows, [2.2 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 1 * inch],
                                      header_color='#28a745'))

    # ---- Yield comparisons ----
    if data.yield_comparisons:
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Aged-Release Yield: Expected vs Actual", heading_style))
        elements.append(Paragraph(
            "Expected yield uses the recipe's configured yield_rate ** aging_years — "
            "the same formula shown at release time in the Batch Tracking &amp; QC tab.",
            styles['Normal']))
        elements.append(Spacer(1, 6))
        rows = [['Batch ID', 'Cheese', 'Starting Kg', 'Expected Kg', 'Actual Kg', 'Variance']]
        for y in data.yield_comparisons:
            rows.append([
                y.aging_batch_id, y.cheese_name, f"{y.starting_quantity_kg:.1f}",
                f"{y.expected_yield_kg:.1f}", f"{y.actual_yield_kg:.1f}", f"{y.variance_pct:+.1f}%",
            ])
        elements.append(styled_table(
            rows, [1.3 * inch, 1.2 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch],
            header_color='#9c27b0'))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Report generated by Browns Cheese — BCPOS", styles['Normal']))

    doc.build(elements)
    return output_path


def generate_production_report(tracker: BatchTracker, book: RecipeBook,
                                start_date: Optional[date] = None,
                                end_date: Optional[date] = None,
                                output_path: Optional[str] = None) -> str:
    """Convenience: build data + render PDF in one call."""
    data = build_report_data(tracker, book, start_date, end_date)
    if output_path is None:
        output_path = f"cheese_production_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return generate_production_report_pdf(data, output_path)


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    from newsvendor_engine import AgingConfig
    from production_tracking import CheeseRecipe, BOMLineItem, OperationStep, DEFAULT_PRODUCTION_CHECKPOINTS

    print("=" * 60)
    print("Setting up recipes and a tracker with a full batch lifecycle")
    print("=" * 60)

    book = RecipeBook()
    book.add(CheeseRecipe(
        name="Mozzarella", product_code="MOZZ-5", category="Fresh Cheese",
        batch_size_kg=6.0, milk_liters_per_batch=50.0, shelf_life_days=30, lead_time_days=1,
        non_milk_ingredients=[BOMLineItem("Bacterial Culture", 0.3, "liters", 1200.0)],
        packaging=[BOMLineItem("Plastic Wrap", 0.5, "roll", 150.0)],
        operations=[OperationStep("Pasteurization", 0.3, "Pasteurizer", 500.0)],
    ))
    parmesan_aging = AgingConfig(aging_years=2.0, storage_cost_rate=0.035, aging_loss_rate=0.025,
                                  financing_rate=0.06, yield_rate=0.88, overage_penalty_multiplier=1.5)
    book.add(CheeseRecipe(
        name="Reserve Parmesan", product_code="PARM-24", category="Aged Hard Cheese",
        batch_size_kg=35.0, milk_liters_per_batch=550.0, shelf_life_days=365 * 3,
        lead_time_days=365 * 2 + 30,
        non_milk_ingredients=[BOMLineItem("Bacterial Culture", 0.8, "liters", 1500.0)],
        packaging=[BOMLineItem("Wooden Crate", 1, "unit", 350.0)],
        operations=[OperationStep("Pressing", 4.0, "Press", 300.0)],
        aging=parmesan_aging,
    ))

    tracker = BatchTracker()

    # --- Batch 1: fresh cheese, passes QC, released fresh ---
    pb1 = tracker.start_production("Mozzarella", "v1.0", 20.0, ["MILK-001"], "J. Kamau")
    for stage in DEFAULT_PRODUCTION_CHECKPOINTS:
        tracker.record_production_checkpoint(pb1.batch_id, stage, passed=True)
    tracker.release_fresh_to_finished(pb1.batch_id, 30)

    # --- Batch 2: fresh cheese, FAILS QC (stays unresolved) ---
    pb2 = tracker.start_production("Mozzarella", "v1.0", 15.0, ["MILK-002"], "M. Otieno")
    tracker.record_production_checkpoint(pb2.batch_id, "Raw Milk Inspection", passed=True)
    tracker.record_production_checkpoint(pb2.batch_id, "Pasteurization Check", passed=False, notes="Temp excursion")

    # --- Batch 3: aged cheese, passes QC, ages, passes quarterly checks,
    #     released with actual yield BELOW expected (negative variance) ---
    pb3 = tracker.start_production("Reserve Parmesan", "v1.0", 35.0, ["MILK-003"], "J. Kamau")
    for stage in DEFAULT_PRODUCTION_CHECKPOINTS:
        tracker.record_production_checkpoint(pb3.batch_id, stage, passed=True)
    ab3 = tracker.start_aging(pb3.batch_id, aging_years=2.0)
    for cp in ab3.checkpoints:
        tracker.record_aging_checkpoint(ab3.batch_id, cp.stage, passed=True)
    expected_yield_3 = ab3.starting_quantity_kg * (parmesan_aging.yield_rate ** ab3.aging_years)
    tracker.release_from_aging(ab3.batch_id, actual_yield_kg=expected_yield_3 * 0.9, shelf_life_days=1095)

    # --- Batch 4: aged cheese, FAILS a quarterly check (cannot be released) ---
    pb4 = tracker.start_production("Reserve Parmesan", "v1.0", 35.0, ["MILK-004"], "M. Otieno")
    for stage in DEFAULT_PRODUCTION_CHECKPOINTS:
        tracker.record_production_checkpoint(pb4.batch_id, stage, passed=True)
    ab4 = tracker.start_aging(pb4.batch_id, aging_years=2.0)
    tracker.record_aging_checkpoint(ab4.batch_id, ab4.checkpoints[0].stage, passed=False, notes="Mold contamination")

    print("Lifecycle set up: 4 production batches, 2 aging batches, 2 finished batches")

    print("\n" + "=" * 60)
    print("Building report data (all time)")
    print("=" * 60)
    data = build_report_data(tracker, book)
    print(summarize_report_data(data))

    # ---- Assertions ----
    assert data.total_batches_started == 4
    assert len(data.failed_qc_batches) == 1 and data.failed_qc_batches[0].batch_id == pb2.batch_id
    assert len(data.failed_aging_batches) == 1 and data.failed_aging_batches[0].batch_id == ab4.batch_id
    # record_aging_checkpoint flips status to FAILED_QC on failure (see production_tracking.py),
    # so ab4 should NOT still show as AGING.
    assert len(data.currently_aging) == 0
    assert len(data.yield_comparisons) == 1
    yc = data.yield_comparisons[0]
    assert yc.variance_pct < 0, "actual yield was deliberately set below expected"
    print(f"\nYield variance check: {yc.variance_pct:+.1f}% (expected negative)")
    assert len(data.finished_batches_in_period) == 2

    print("\n" + "=" * 60)
    print("Generating PDF report")
    print("=" * 60)
    try:
        path = generate_production_report(tracker, book, output_path="test_production_report.pdf")
        assert os.path.exists(path) and os.path.getsize(path) > 0
        print(f"PDF generated: {path} ({os.path.getsize(path):,} bytes)")
    except ImportError as e:
        print(f"⚠ Skipping PDF generation check — reportlab not installed in this environment: {e}")

    print("\nAll checks passed.")