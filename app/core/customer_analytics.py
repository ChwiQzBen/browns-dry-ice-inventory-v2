"""
app/core/customer_analytics.py
=================================
Pure computation over customer-linked sales history — no Streamlit, no DB
calls. Takes plain lists of dicts (from cheese_data_access.get_sales_history
/ get_customers) and returns dataclasses the UI renders.

Requires customer_id-linked sales (see cheese_data_access.
reconcile_customers_from_history) — rows with customer_id=None are excluded
from per-customer breakdowns, since a freetext-only name can't be reliably
grouped (this is the whole reason the customer_id migration happened before
this module was written).
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict
import statistics


@dataclass
class CustomerOrderingPattern:
    customer_id: int
    customer_name: str
    total_orders: int
    total_kg: float
    total_revenue: float
    first_order_date: str
    last_order_date: str
    avg_days_between_orders: Optional[float]  # None if fewer than 2 orders
    most_common_weekday: Optional[str]


@dataclass
class CustomerProductMix:
    customer_id: int
    customer_name: str
    by_cheese_kg: Dict[str, float] = field(default_factory=dict)
    top_cheese: Optional[str] = None


def _linked_sales(sales: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sales rows with a real customer_id — the only rows these functions
    can group reliably. Call cheese_data_access.reconcile_customers_from_history
    first if this excludes most of your history."""
    return [s for s in sales if s.get("customer_id") is not None]


def compute_ordering_patterns(sales: List[Dict[str, Any]],
                               customers: List[Dict[str, Any]]) -> List[CustomerOrderingPattern]:
    name_by_id = {c["id"]: c["name"] for c in customers}
    by_customer: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for s in _linked_sales(sales):
        by_customer[s["customer_id"]].append(s)

    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    patterns = []
    for cid, rows in by_customer.items():
        rows_sorted = sorted(rows, key=lambda r: r["date"])
        dates = [datetime.fromisoformat(r["date"]).date() for r in rows_sorted]

        avg_gap = None
        if len(dates) >= 2:
            gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
            avg_gap = statistics.mean(gaps)

        weekday_counts: Dict[str, int] = defaultdict(int)
        for d in dates:
            weekday_counts[weekday_names[d.weekday()]] += 1
        most_common_weekday = max(weekday_counts, key=weekday_counts.get) if weekday_counts else None

        patterns.append(CustomerOrderingPattern(
            customer_id=cid,
            customer_name=name_by_id.get(cid, f"Customer #{cid}"),
            total_orders=len(rows),
            total_kg=sum(float(r["quantity_kg"]) for r in rows),
            total_revenue=sum(float(r["revenue"]) for r in rows),
            first_order_date=dates[0].isoformat(),
            last_order_date=dates[-1].isoformat(),
            avg_days_between_orders=round(avg_gap, 1) if avg_gap is not None else None,
            most_common_weekday=most_common_weekday,
        ))

    patterns.sort(key=lambda p: p.total_revenue, reverse=True)
    return patterns


def compute_product_mix(sales: List[Dict[str, Any]],
                         customers: List[Dict[str, Any]]) -> List[CustomerProductMix]:
    name_by_id = {c["id"]: c["name"] for c in customers}
    by_customer: Dict[int, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for s in _linked_sales(sales):
        by_customer[s["customer_id"]][s["cheese_name"]] += float(s["quantity_kg"])

    mixes = []
    for cid, cheese_totals in by_customer.items():
        top_cheese = max(cheese_totals, key=cheese_totals.get) if cheese_totals else None
        mixes.append(CustomerProductMix(
            customer_id=cid,
            customer_name=name_by_id.get(cid, f"Customer #{cid}"),
            by_cheese_kg=dict(cheese_totals),
            top_cheese=top_cheese,
        ))
    mixes.sort(key=lambda m: sum(m.by_cheese_kg.values()), reverse=True)
    return mixes


if __name__ == "__main__":
    customers = [{"id": 1, "name": "Java House"}, {"id": 2, "name": "Carrefour"}]
    sales = [
        {"date": "2026-06-01", "cheese_name": "Mozzarella", "quantity_kg": 10.0, "revenue": 6500.0, "customer_id": 1},
        {"date": "2026-06-08", "cheese_name": "Mozzarella", "quantity_kg": 12.0, "revenue": 7800.0, "customer_id": 1},
        {"date": "2026-06-15", "cheese_name": "Halloumi", "quantity_kg": 5.0, "revenue": 4000.0, "customer_id": 1},
        {"date": "2026-06-03", "cheese_name": "Cheddar", "quantity_kg": 20.0, "revenue": 15000.0, "customer_id": 2},
        {"date": "2026-06-01", "cheese_name": "Gouda", "quantity_kg": 3.0, "revenue": 2400.0, "customer_id": None},  # unlinked
    ]

    print("Test 1: ordering patterns")
    patterns = compute_ordering_patterns(sales, customers)
    for p in patterns:
        print(f"  {p.customer_name}: {p.total_orders} orders, avg gap={p.avg_days_between_orders}d, "
              f"usual day={p.most_common_weekday}, last={p.last_order_date}")
    java = next(p for p in patterns if p.customer_name == "Java House")
    assert java.total_orders == 3
    # 2026-06-01, 2026-06-08, 2026-06-15 are all Mondays
    assert java.most_common_weekday == "Monday", f"got {java.most_common_weekday}"
    assert java.avg_days_between_orders == 7.0, f"got {java.avg_days_between_orders}"
    carrefour = next(p for p in patterns if p.customer_name == "Carrefour")
    assert carrefour.avg_days_between_orders is None, "single order should have no gap"
    assert len(patterns) == 2, "unlinked sale (customer_id=None) must be excluded"

    print("\nTest 2: product mix")
    mixes = compute_product_mix(sales, customers)
    java_mix = next(m for m in mixes if m.customer_name == "Java House")
    print(f"  Java House mix: {java_mix.by_cheese_kg}, top={java_mix.top_cheese}")
    assert java_mix.top_cheese == "Mozzarella"
    assert java_mix.by_cheese_kg["Mozzarella"] == 22.0

    print("\nAll customer_analytics checks passed.")