"""
newsvendor_engine.py
=====================
Production optimization engine for Browns Cheese.

Two pieces, deliberately separated from any Streamlit/UI/DB code so they can
be unit tested and reused (e.g. from the Dry Ice app's decision_engine.py):

1. NewsvendorModel   - ONE model for both fresh and aged cheese. Aging is an
                        optional config; when absent the math reduces exactly
                        to the standard newsvendor formulas.
2. MilkAllocator      - Daily, no-storage allocation of a fixed milk supply
                        across multiple cheese types, prioritized by expected
                        profit per liter, each cheese's target quantity coming
                        from its own NewsvendorModel.

No Streamlit, no SQLite, no session_state. Wire this into your existing
Supabase/SQLite data layer and UI separately.

CHANGE LOG
----------
- Added optional `capacity_by_cheese` to MilkAllocator.allocate(): lets a
  caller (e.g. ProductionPlanner, once it knows remaining aging-room
  capacity) cap production_quantity per cheese *before* milk is allocated,
  so the aging-room constraint is respected by the optimization itself
  rather than being a warning bolted on after the fact.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from scipy.stats import norm
import math


# ============================================================
# CONFIG OBJECTS
# ============================================================

@dataclass
class AgingConfig:
    """Only needed for cheeses that require long aging (e.g. Reserve Parmesan).
    Omit entirely for fresh/short-turnaround cheeses."""
    aging_years: float
    storage_cost_rate: float = 0.03      # annual, % of unit cost
    aging_loss_rate: float = 0.02        # annual weight/quality loss, %
    financing_rate: float = 0.05         # annual cost of capital, %
    yield_rate: float = 0.90             # fraction of production that survives aging
    overage_penalty_multiplier: float = 1.0  # extra penalty for aged overproduction


@dataclass
class NewsvendorResult:
    mean_demand: float
    std_demand: float
    critical_ratio: float
    z_score: float
    optimal_quantity: float        # quantity needed AT THE POINT OF SALE
    production_quantity: float     # quantity to actually PRODUCE today
                                    # (== optimal_quantity when aging_years=0)
    expected_sales: float
    expected_leftover: float
    expected_profit: float
    fill_rate: float
    stockout_probability: float
    effective_unit_cost: float
    underage_penalty: float
    overage_penalty: float
    capacity_applied: bool = False


# ============================================================
# UNIFIED NEWSVENDOR MODEL
# ============================================================

class NewsvendorModel:
    """
    Formulas
    --------
    Critical Ratio  = Cu / (Cu + Co)
    Q*              = mu + z * sigma
    E[Sales]        = mu * Phi(z) - sigma * phi(z)
    E[Leftover]     = Q* - E[Sales]
    E[Profit]       = (p - c_eff) * E[Sales] - Co * E[Leftover]

    Aging extension (only applied if `aging` is provided)
    -------------------------------------------------------
    holding_rate       = storage_rate + aging_loss_rate + financing_rate
    cost_factor         = (1 + holding_rate) ** aging_years
    c_eff (effective
      unit cost)        = unit_cost * cost_factor / yield_rate
    production_quantity = Q* / (yield_rate ** aging_years)

    With aging_years = 0 this collapses to c_eff = unit_cost and
    production_quantity = Q*, i.e. the plain fresh-cheese model.
    """

    def __init__(self,
                 selling_price: float,
                 unit_cost: float,
                 salvage_value: float = 0.0,
                 aging: Optional[AgingConfig] = None):
        if selling_price <= 0 or unit_cost <= 0:
            raise ValueError("selling_price and unit_cost must be positive")

        self.selling_price = selling_price
        self.unit_cost = unit_cost
        self.salvage_value = salvage_value
        self.aging = aging

        if aging is None:
            self.holding_rate = 0.0
            self.cost_factor = 1.0
            self.yield_rate = 1.0
            self.aging_years = 0.0
            overage_mult = 1.0
        else:
            self.holding_rate = (aging.storage_cost_rate
                                  + aging.aging_loss_rate
                                  + aging.financing_rate)
            self.cost_factor = (1 + self.holding_rate) ** aging.aging_years
            self.yield_rate = aging.yield_rate
            self.aging_years = aging.aging_years
            overage_mult = aging.overage_penalty_multiplier

        # Effective unit cost carries forward storage/financing/aging-loss cost
        self.effective_unit_cost = unit_cost * self.cost_factor / self.yield_rate

        self.underage_penalty = selling_price - self.effective_unit_cost
        self.overage_penalty = (self.effective_unit_cost - salvage_value) * overage_mult

        if self.underage_penalty <= 0:
            raise ValueError(
                f"Selling price (KSh {selling_price:.2f}) does not cover effective "
                f"unit cost (KSh {self.effective_unit_cost:.2f}) - check aging costs/pricing"
            )
        if self.overage_penalty <= 0:
            raise ValueError("Overage penalty must be positive - check salvage_value")

        self.critical_ratio = self.underage_penalty / (self.underage_penalty + self.overage_penalty)
        self.z_score = norm.ppf(self.critical_ratio)

    def solve(self,
              mean_demand: float,
              std_demand: float,
              current_inventory: float = 0.0,
              capacity: Optional[float] = None) -> NewsvendorResult:
        """
        Args:
            mean_demand: expected demand AT POINT OF SALE (i.e. in `aging_years`
                         from now, if aging is set)
            std_demand: standard deviation of that demand
            current_inventory: stock already on hand, netted out of Q*
            capacity: optional hard cap on production_quantity (e.g. aging
                      room space, daily production capacity)
        """
        z = self.z_score

        # Q* at point of sale
        optimal_qty = max(0.0, mean_demand + z * std_demand - current_inventory)

        # Convert to what must be PRODUCED today, accounting for aging loss
        aging_loss_factor = self.yield_rate ** self.aging_years if self.aging_years else 1.0
        production_qty = optimal_qty / aging_loss_factor if aging_loss_factor > 0 else optimal_qty

        capacity_applied = False
        if capacity is not None and production_qty > capacity:
            production_qty = max(0.0, capacity)
            capacity_applied = True

        # Expected sales, computed in "production units" then rescaled to sale units
        adj_mean = mean_demand / aging_loss_factor if aging_loss_factor else mean_demand
        adj_std = std_demand / aging_loss_factor if aging_loss_factor else std_demand
        cdf_z, pdf_z = norm.cdf(z), norm.pdf(z)
        expected_sales_units = max(0.0, adj_mean * cdf_z - adj_std * pdf_z)
        expected_sales = expected_sales_units * aging_loss_factor

        # If a capacity cap bit, sold quantity can't exceed what's actually
        # produced (after aging loss) either.
        max_sellable = production_qty * aging_loss_factor if aging_loss_factor else production_qty
        expected_sales = min(expected_sales, max_sellable)

        expected_leftover = max(0.0, production_qty * aging_loss_factor - expected_sales) \
            if aging_loss_factor else max(0.0, production_qty - expected_sales)

        expected_profit = ((self.selling_price - self.effective_unit_cost) * expected_sales
                            - self.overage_penalty * expected_leftover)

        return NewsvendorResult(
            mean_demand=mean_demand,
            std_demand=std_demand,
            critical_ratio=self.critical_ratio,
            z_score=z,
            optimal_quantity=optimal_qty,
            production_quantity=production_qty,
            expected_sales=expected_sales,
            expected_leftover=expected_leftover,
            expected_profit=expected_profit,
            fill_rate=(expected_sales / mean_demand) if mean_demand > 0 else 0.0,
            stockout_probability=1 - self.critical_ratio,
            effective_unit_cost=self.effective_unit_cost,
            underage_penalty=self.underage_penalty,
            overage_penalty=self.overage_penalty,
            capacity_applied=capacity_applied,
        )


# ============================================================
# DAILY MILK ALLOCATOR (NO STORAGE)
# ============================================================

@dataclass
class CheeseLine:
    """One cheese type's production parameters for today's allocation."""
    name: str
    yield_kg_per_liter: float      # kg of cheese per liter of milk
    selling_price: float           # KSh / kg
    production_cost: float         # KSh / kg (excludes milk cost, added separately)
    demand_mean: float             # kg
    demand_std: float              # kg
    current_inventory: float = 0.0
    salvage_rate: float = 0.30     # fraction of production_cost recovered if unsold
    aging: Optional[AgingConfig] = None


@dataclass
class AllocationLine:
    cheese: str
    milk_allocated_l: float
    cheese_produced_kg: float
    demand_kg: float
    current_inventory_kg: float
    expected_sales_kg: float
    expected_leftover_kg: float
    revenue: float
    cost: float
    profit: float
    profit_per_liter: float
    fully_allocated: bool
    capacity_applied: bool = False


@dataclass
class AllocationResult:
    milk_available_l: float
    milk_allocated_l: float
    milk_leftover_l: float
    milk_wasted_l: float
    milk_sold_raw_l: float
    disposal_method: str
    total_cheese_produced_kg: float
    total_profit: float
    profit_per_liter: float
    utilization_rate: float
    unmet_demand_kg: float
    lines: List[AllocationLine] = field(default_factory=list)


class MilkAllocator:
    """
    Allocates a FIXED daily milk supply (no storage - use it or lose it)
    across cheese types.

    Each cheese's target production comes from its own NewsvendorModel
    (correctly handling aging if configured). Milk is then handed out
    greedily to whichever cheese has the highest expected profit per
    liter of milk, until either milk runs out or every cheese has hit
    its newsvendor-optimal quantity. Anything left over is sold as raw
    milk if that beats the wastage cost, otherwise wasted.
    """

    def __init__(self,
                 milk_cost_per_liter: float,
                 raw_milk_price_per_liter: float,
                 wastage_cost_per_liter: Optional[float] = None):
        self.milk_cost = milk_cost_per_liter
        self.raw_milk_price = raw_milk_price_per_liter
        # Default: wasting a liter costs what you paid for it
        self.wastage_cost = wastage_cost_per_liter if wastage_cost_per_liter is not None else milk_cost_per_liter

    def allocate(self, milk_available_l: float, cheese_lines: List[CheeseLine],
                 capacity_by_cheese: Optional[Dict[str, float]] = None) -> AllocationResult:
        """
        Args:
            capacity_by_cheese: optional {cheese_name: max_production_kg} cap,
                applied BEFORE milk is handed out. Use this to enforce
                constraints like aging-room space for aged cheeses — the
                allocator will never recommend producing more of that cheese
                than the cap allows, and will route the milk it would have
                used elsewhere instead of wasting it.
        """
        if milk_available_l < 0:
            raise ValueError("milk_available_l cannot be negative")

        priced = []
        for line in cheese_lines:
            # Full unit cost MUST include milk, or the critical ratio (and
            # therefore the target quantity) understates true overage risk.
            milk_cost_per_kg = (self.milk_cost / line.yield_kg_per_liter
                                 if line.yield_kg_per_liter > 0 else 0.0)
            full_unit_cost = line.production_cost + milk_cost_per_kg
            salvage_value = full_unit_cost * line.salvage_rate
            model = NewsvendorModel(
                selling_price=line.selling_price,
                unit_cost=full_unit_cost,
                salvage_value=salvage_value,
                aging=line.aging,
            )
            line_capacity = capacity_by_cheese.get(line.name) if capacity_by_cheese else None
            result = model.solve(
                mean_demand=line.demand_mean,
                std_demand=line.demand_std,
                current_inventory=line.current_inventory,
                capacity=line_capacity,
            )
            milk_needed = (result.production_quantity / line.yield_kg_per_liter
                            if line.yield_kg_per_liter > 0 else 0.0)
            profit_per_kg = line.selling_price - full_unit_cost
            profit_per_liter = profit_per_kg * line.yield_kg_per_liter
            priced.append((line, result, milk_needed, profit_per_liter))

        # Highest profit-per-liter first
        priced.sort(key=lambda t: t[3], reverse=True)

        remaining_milk = milk_available_l
        lines_out: List[AllocationLine] = []
        total_profit_cheese = 0.0
        total_produced = 0.0
        unmet_demand = 0.0

        for line, result, milk_needed, _ in priced:
            if remaining_milk >= milk_needed:
                allocated_milk = milk_needed
                produced_kg = result.production_quantity
                fully_allocated = True
            else:
                allocated_milk = remaining_milk
                produced_kg = allocated_milk * line.yield_kg_per_liter
                fully_allocated = False

            total_available = produced_kg + line.current_inventory
            expected_sales = min(line.demand_mean, total_available)
            expected_leftover = max(0.0, total_available - expected_sales)

            revenue = expected_sales * line.selling_price
            cheese_cost = produced_kg * line.production_cost
            milk_cost = allocated_milk * self.milk_cost
            profit = revenue - cheese_cost - milk_cost

            lines_out.append(AllocationLine(
                cheese=line.name,
                milk_allocated_l=allocated_milk,
                cheese_produced_kg=produced_kg,
                demand_kg=line.demand_mean,
                current_inventory_kg=line.current_inventory,
                expected_sales_kg=expected_sales,
                expected_leftover_kg=expected_leftover,
                revenue=revenue,
                cost=cheese_cost + milk_cost,
                profit=profit,
                profit_per_liter=(profit / allocated_milk) if allocated_milk > 0 else 0.0,
                fully_allocated=fully_allocated,
                capacity_applied=result.capacity_applied,
            ))

            total_profit_cheese += profit
            total_produced += produced_kg
            unmet_demand += max(0.0, line.demand_mean - total_available)
            remaining_milk -= allocated_milk
            if remaining_milk <= 1e-9:
                remaining_milk = 0.0
                # NOTE: we deliberately do NOT break here anymore — a
                # capacity-capped line above may have left milk on the table
                # for a lower-priority line to use, so we keep iterating and
                # simply hand later lines zero milk_needed if none is left.

        milk_allocated = milk_available_l - remaining_milk
        leftover = remaining_milk

        raw_milk_value = leftover * self.raw_milk_price
        waste_value = -leftover * self.wastage_cost
        if raw_milk_value >= waste_value:
            disposal = "Sold as raw milk"
            milk_wasted = 0.0
            milk_sold_raw = leftover
            disposal_value = raw_milk_value
        else:
            disposal = "Wasted"
            milk_wasted = leftover
            milk_sold_raw = 0.0
            disposal_value = waste_value

        total_profit = total_profit_cheese + disposal_value

        return AllocationResult(
            milk_available_l=milk_available_l,
            milk_allocated_l=milk_allocated,
            milk_leftover_l=leftover,
            milk_wasted_l=milk_wasted,
            milk_sold_raw_l=milk_sold_raw,
            disposal_method=disposal,
            total_cheese_produced_kg=total_produced,
            total_profit=total_profit,
            profit_per_liter=(total_profit / milk_available_l) if milk_available_l > 0 else 0.0,
            utilization_rate=(milk_allocated / milk_available_l) if milk_available_l > 0 else 0.0,
            unmet_demand_kg=unmet_demand,
            lines=lines_out,
        )


# ============================================================
# SELF-TEST (run directly: python3 newsvendor_engine.py)
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("TEST 1: Fresh cheese newsvendor (Mozzarella)")
    print("=" * 60)
    model = NewsvendorModel(selling_price=300, unit_cost=180, salvage_value=54)
    r = model.solve(mean_demand=60, std_demand=18, current_inventory=10)
    print(f"Critical ratio: {r.critical_ratio:.3f}  |  Q*: {r.optimal_quantity:.1f} kg")
    print(f"Expected profit: KSh {r.expected_profit:,.0f}  |  Fill rate: {r.fill_rate:.1%}")
    assert r.production_quantity == r.optimal_quantity, "fresh case should have production==optimal"

    print("\n" + "=" * 60)
    print("TEST 2: Aged cheese newsvendor (Reserve Parmesan, 2yr aging)")
    print("=" * 60)
    aging = AgingConfig(aging_years=2.0, storage_cost_rate=0.035, aging_loss_rate=0.025,
                         financing_rate=0.06, yield_rate=0.88, overage_penalty_multiplier=1.5)
    model2 = NewsvendorModel(selling_price=800, unit_cost=450, salvage_value=450 * 0.12, aging=aging)
    r2 = model2.solve(mean_demand=20, std_demand=6)
    print(f"Effective unit cost: KSh {r2.effective_unit_cost:,.2f} (raw cost was KSh 450)")
    print(f"Q* at sale: {r2.optimal_quantity:.1f}  |  Must PRODUCE today: {r2.production_quantity:.1f}")
    print(f"Expected profit: KSh {r2.expected_profit:,.0f}")
    assert r2.production_quantity > r2.optimal_quantity, "aging loss should inflate production qty"

    print("\n" + "=" * 60)
    print("TEST 3: Daily milk allocation, no storage")
    print("=" * 60)
    lines = [
        CheeseLine("Mozzarella", yield_kg_per_liter=0.12, selling_price=650, production_cost=120,
                   demand_mean=60, demand_std=18, current_inventory=10),
        CheeseLine("Cheddar", yield_kg_per_liter=0.10, selling_price=750, production_cost=140,
                   demand_mean=50, demand_std=15, current_inventory=5),
        CheeseLine("Reserve Parmesan", yield_kg_per_liter=0.09, selling_price=1800, production_cost=250,
                   demand_mean=20, demand_std=6, salvage_rate=0.12, aging=aging),
    ]
    allocator = MilkAllocator(milk_cost_per_liter=45, raw_milk_price_per_liter=35)

    for milk_supply in [400, 1000, 2500]:
        result = allocator.allocate(milk_supply, lines)
        print(f"\n-- Milk available: {milk_supply} L --")
        for l in result.lines:
            print(f"  {l.cheese:20s} milk={l.milk_allocated_l:7.1f}L  "
                  f"produced={l.cheese_produced_kg:6.1f}kg  profit=KSh {l.profit:,.0f}  "
                  f"{'FULL' if l.fully_allocated else 'PARTIAL'}")
        print(f"  Utilization: {result.utilization_rate:.0%}  |  "
              f"Total profit: KSh {result.total_profit:,.0f}  |  "
              f"{result.disposal_method}: {result.milk_leftover_l:.0f}L  |  "
              f"Unmet demand: {result.unmet_demand_kg:.1f}kg")

    print("\n" + "=" * 60)
    print("TEST 4: Aging-room capacity constraint caps Reserve Parmesan")
    print("=" * 60)
    result_capped = allocator.allocate(2500, lines, capacity_by_cheese={"Reserve Parmesan": 15.0})
    parm_line = next(l for l in result_capped.lines if l.cheese == "Reserve Parmesan")
    print(f"Reserve Parmesan produced: {parm_line.cheese_produced_kg:.1f} kg "
          f"(capacity_applied={parm_line.capacity_applied})")
    assert parm_line.cheese_produced_kg <= 15.0 + 1e-6
    assert parm_line.capacity_applied is True

    print("\nAll checks passed.")