"""
app/core/report_ui.py
=======================
Shared Streamlit "Reports tab" shell used by cheese_production_ui.py and
commercial_ui.py. Domain logic (KPIs, tables, charts, PDF generation)
stays in production_reports.py / commercial_reports.py — this file only
owns the Streamlit shell around them.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta, datetime
from typing import Any, Callable
import os
import streamlit as st
import pandas as pd


@dataclass
class KPI:
    label: str
    value_fn: Callable[[Any], Any]


@dataclass
class TableSection:
    heading: str
    has_data_fn: Callable[[Any], bool]
    rows_fn: Callable[[Any], list]


@dataclass
class ChartSection:
    heading: str
    has_data_fn: Callable[[Any], bool]
    rows_fn: Callable[[Any], list]   # data -> list[dict], one dict per point
    x: str                            # dict key for the x-axis
    y: str                            # dict key for the y-axis
    kind: str = "line"                # "line" or "bar"


def render_report_tab(
    *,
    title: str,
    caption: str,
    session_key: str,
    build_fn: Callable[[date, date], Any],
    summarize_fn: Callable[[Any], str],
    pdf_fn: Callable[..., str],
    pdf_filename_prefix: str,
    kpis: list[KPI],
    table_sections: list[TableSection],
    chart_sections: list[ChartSection] | None = None,
    default_days_back: int = 30,
    date_key_prefix: str = "report",
) -> None:
    st.markdown(f"### {title}")
    st.caption(caption)

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date", value=date.today() - timedelta(days=default_days_back),
            key=f"{date_key_prefix}_start_date",
        )
    with col2:
        end_date = st.date_input("End Date", value=date.today(), key=f"{date_key_prefix}_end_date")

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    if st.button("📊 Generate Report", type="primary", key=f"{date_key_prefix}_generate_btn"):
        try:
            st.session_state[session_key] = build_fn(start_date, end_date)
            st.success("Report generated successfully.")
        except Exception as e:
            st.error(f"Could not generate report: {e}")
            return

    if session_key not in st.session_state:
        return

    data = st.session_state[session_key]

    st.divider()
    st.subheader("📊 Summary")
    st.text(summarize_fn(data))

    for i in range(0, len(kpis), 3):
        row = kpis[i:i + 3]
        cols = st.columns(len(row))
        for col, kpi in zip(cols, row):
            col.metric(kpi.label, kpi.value_fn(data))

    for section in (chart_sections or []):
        if section.has_data_fn(data):
            st.subheader(section.heading)
            df = pd.DataFrame(section.rows_fn(data)).set_index(section.x)
            if section.kind == "bar":
                st.bar_chart(df[section.y])
            else:
                st.line_chart(df[section.y])

    for section in table_sections:
        if section.has_data_fn(data):
            st.subheader(section.heading)
            st.dataframe(pd.DataFrame(section.rows_fn(data)), use_container_width=True)

    st.divider()
    if st.button("📄 Generate PDF Report", key=f"{date_key_prefix}_pdf_btn"):
        try:
            filename = f"{pdf_filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            pdf_path = pdf_fn(data, output_path=filename)
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            st.download_button(
                label="📥 Download PDF Report", data=pdf_bytes, file_name=filename,
                mime="application/pdf", key=f"{date_key_prefix}_download_pdf",
            )
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
        except ImportError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Could not generate PDF: {e}")