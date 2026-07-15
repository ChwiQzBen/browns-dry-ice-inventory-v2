"""
scenario_analysis.py
======================
"What if milk drops 20%?" / "What if Christmas demand jumps 40%?" answered
by re-running ProductionPlanner.build_plan() with adjusted inputs and
diffing the results against a baseline — the same pattern as the existing
Dry Ice "What-If Simulator" (sliders -> recompute -> side-by-side compare).

This is deliberately NOT:
- Monte Carlo (no random sampling of thousands of futures)
- CVaR (no worst-case-tail optimization)
- A Digital Twin (no equipment/staffing state machine)

Those need a capacity/equipment model that doesn't exist in this project
yet. "Pasteurizer fails" is approximated here as a milk-availability cut
(you can't process milk you have), which is a reasonable proxy but not a
true equipment-capacity constraint — flagged explicitly in the output
rather than silently pretending to model machinery.

CHANGE LOG
----------
- run_scenario() / compare_scenarios() now accept optional
  aging_room_capacity_kg / aging_room_used_kg and forward them into
  build_plan(). Without this, every scenario ran with the aging-room
  constraint OFF (build_plan()'s default), which could recommend
  producing aged cheese the physical room has no space for.
- compare_scenarios() now isolates per-scenario failures: one scenario
  raising an exception no longer takes down the baseline or the other
  scenarios. Failures show up as ScenarioResult.error instead.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from production_plan import ProductionPlanner, ProductionPlan
from production_tracking import RecipeBook, BatchTracker


@dataclass
class Scenario:
    name: str
    description: str = ""
    milk_multiplier: float = 1.0            # e.g. 0.8 for "milk drops 20%"
    demand_multiplier: float = 1.0          # applies to every cheese's mean+std uniformly
    per_cheese_demand_multiplier: Dict[str, float] = field(default_factory=dict)  # overrides the blanket multiplier
    equipment_note: Optional[str] = None    # e.g. "Pasteurizer down - milk treated as unusable"


@dataclass
class ScenarioResult:
    scenario: Scenario
    plan: Optional[ProductionPlan]
    profit_delta_vs_base: float
    unmet_demand_delta_vs_base: float
    utilization_delta_vs_base: float
    error: Optional[str] = None


def run_scenario(planner: ProductionPlanner,
                  base_milk_l: float,
                  base_demand: Dict[str, Tuple[float, float]],
                  selling_prices: Dict[str, float],
                  scenario: Scenario,
                  aging_room_capacity_kg: Optional[float] = None,
                  aging_room_used_kg: float = 0.0) -> ProductionPlan:
    """Applies a scenario's multipliers to the base inputs and runs one plan.
    Does not mutate planner/tracker state beyond what build_plan() already does
    (build_plan is read-only against BatchTracker; nothing is committed).

    aging_room_capacity_kg / aging_room_used_kg are forwarded to build_plan()
    exactly as the real planning tab passes them, so a scenario run reflects
    the same physical space constraint the baseline plan is subject to.
    Omit (None) to run unconstrained, matching build_plan()'s own default.
    """

    adjusted_milk = base_milk_l * scenario.milk_multiplier

    adjusted_demand = {}
    for cheese_name, (mean, std) in base_demand.items():
        mult = scenario.per_cheese_demand_multiplier.get(cheese_name, scenario.demand_multiplier)
        adjusted_demand[cheese_name] = (mean * mult, std * mult)

    kwargs = dict(
        milk_available_l=adjusted_milk,
        demand_forecast=adjusted_demand,
        selling_prices=selling_prices,
    )
    if aging_room_capacity_kg is not None:
        kwargs["aging_room_capacity_kg"] = aging_room_capacity_kg
        kwargs["aging_room_used_kg"] = aging_room_used_kg

    return planner.build_plan(**kwargs)


def _run_scenario_safely(planner: ProductionPlanner,
                          base_milk_l: float,
                          base_demand: Dict[str, Tuple[float, float]],
                          selling_prices: Dict[str, float],
                          scenario: Scenario,
                          base_plan: ProductionPlan,
                          aging_room_capacity_kg: Optional[float],
                          aging_room_used_kg: float) -> ScenarioResult:
    """Runs one scenario and catches any exception so one bad 'what if'
    doesn't take down the whole comparison. Failures are recorded on the
    returned ScenarioResult (plan=None, error=<message>) instead of
    propagating."""
    try:
        plan = run_scenario(planner, base_milk_l, base_demand, selling_prices, scenario,
                             aging_room_capacity_kg, aging_room_used_kg)
        return ScenarioResult(
            scenario=scenario, plan=plan,
            profit_delta_vs_base=plan.total_profit - base_plan.total_profit,
            unmet_demand_delta_vs_base=plan.unmet_demand_kg - base_plan.unmet_demand_kg,
            utilization_delta_vs_base=plan.allocation.utilization_rate - base_plan.allocation.utilization_rate,
        )
    except Exception as e:
        return ScenarioResult(
            scenario=scenario, plan=None,
            profit_delta_vs_base=float("nan"),
            unmet_demand_delta_vs_base=float("nan"),
            utilization_delta_vs_base=float("nan"),
            error=str(e),
        )


def compare_scenarios(planner: ProductionPlanner,
                       base_milk_l: float,
                       base_demand: Dict[str, Tuple[float, float]],
                       selling_prices: Dict[str, float],
                       scenarios: List[Scenario],
                       aging_room_capacity_kg: Optional[float] = None,
                       aging_room_used_kg: float = 0.0) -> List[ScenarioResult]:
    """Runs a baseline (multiplier 1.0, always included first) plus every
    given scenario, and returns each with deltas vs. the baseline.

    aging_room_capacity_kg / aging_room_used_kg apply to the baseline AND
    every scenario, so the comparison is apples-to-apples against the same
    physical constraint. A scenario that raises during build_plan() is
    caught and recorded on its own ScenarioResult (see
    _run_scenario_safely) rather than aborting the whole comparison — if
    the baseline itself fails, that exception is allowed to propagate,
    since there'd be nothing left to compare against.
    """

    baseline = Scenario(name="Baseline", description="Today's actual milk and forecast, unmodified")
    base_plan = run_scenario(planner, base_milk_l, base_demand, selling_prices, baseline,
                              aging_room_capacity_kg, aging_room_used_kg)

    results = [ScenarioResult(
        scenario=baseline, plan=base_plan,
        profit_delta_vs_base=0.0, unmet_demand_delta_vs_base=0.0, utilization_delta_vs_base=0.0,
    )]

    for scenario in scenarios:
        result = _run_scenario_safely(planner, base_milk_l, base_demand, selling_prices,
                                       scenario, base_plan, aging_room_capacity_kg, aging_room_used_kg)
        results.append(result)

    return results


def summarize_comparison(results: List[ScenarioResult]) -> str:
    lines = ["Scenario Comparison", "=" * 60]
    for r in results:
        lines.append(f"\n{r.scenario.name}")
        if r.scenario.description:
            lines.append(f"  {r.scenario.description}")
        if r.scenario.equipment_note:
            lines.append(f"  ⚠ Approximation: {r.scenario.equipment_note}")

        if r.error:
            lines.append(f"  ❌ Scenario failed to run: {r.error}")
            continue

        lines.append(f"  Profit: KSh {r.plan.total_profit:,.0f} "
                      f"({'+' if r.profit_delta_vs_base >= 0 else ''}{r.profit_delta_vs_base:,.0f} vs baseline)")
        lines.append(f"  Unmet demand: {r.plan.unmet_demand_kg:.1f}kg "
                      f"({'+' if r.unmet_demand_delta_vs_base >= 0 else ''}{r.unmet_demand_delta_vs_base:.1f}kg vs baseline)")
        lines.append(f"  Milk utilization: {r.plan.allocation.utilization_rate:.0%} "
                      f"({'+' if r.utilization_delta_vs_base >= 0 else ''}{r.utilization_delta_vs_base:.0%} vs baseline)")
        if r.plan.warnings:
            for w in r.plan.warnings:
                lines.append(f"  ⚠ {w}")
    return "\n".join(lines)


# ============================================================
# SELF-TEST — the three examples from the prompt, plus aging-room
# threading and failure isolation
# ============================================================

if __name__ == "__main__":
    from newsvendor_engine import AgingConfig
    from production_tracking import CheeseRecipe, BOMLineItem, OperationStep

    book = RecipeBook()
    book.add(CheeseRecipe(
        name="Mozzarella", product_code="MOZZ-5", category="Fresh Cheese",
        batch_size_kg=6.0, milk_liters_per_batch=50.0,
        shelf_life_days=30, lead_time_days=1,
        non_milk_ingredients=[BOMLineItem("Bacterial Culture", 0.3, "liters", 1200.0)],
        packaging=[BOMLineItem("Plastic Wrap", 0.5, "roll", 150.0)],
        operations=[OperationStep("Pasteurization", 0.3, "Pasteurizer", 500.0)],
    ))
    book.add(CheeseRecipe(
        name="Cheddar", product_code="CHED-10", category="Semi-Hard Cheese",
        batch_size_kg=8.5, milk_liters_per_batch=100.0,
        shelf_life_days=180, lead_time_days=14,
        non_milk_ingredients=[BOMLineItem("Bacterial Culture", 0.5, "liters", 1200.0)],
        packaging=[BOMLineItem("Wax Coating", 1, "roll", 150.0)],
        operations=[OperationStep("Pressing", 2.0, "Press", 300.0)],
    ))

    tracker = BatchTracker()
    planner = ProductionPlanner(book, tracker, milk_cost_per_liter=45.0, raw_milk_price_per_liter=35.0)

    base_milk = 900.0
    base_demand = {"Mozzarella": (60.0, 18.0), "Cheddar": (55.0, 15.0)}
    prices = {"Mozzarella": 650.0, "Cheddar": 750.0}

    scenarios = [
        Scenario(
            name="Milk drops 20%",
            description="Supplier shortfall - only 80% of usual milk arrives",
            milk_multiplier=0.8,
        ),
        Scenario(
            name="Christmas demand +40%",
            description="Holiday demand spike across all cheeses",
            demand_multiplier=1.4,
        ),
        Scenario(
            name="Pasteurizer fails",
            description="Approximated as today's milk being unusable",
            milk_multiplier=0.0,
            equipment_note=("This models 'no milk can be processed today,' not the pasteurizer "
                             "itself - there's no equipment-capacity constraint in the engine yet. "
                             "A partial failure (e.g. 50% throughput) would need that model built first."),
        ),
    ]

    print("=" * 60)
    print("compare_scenarios WITHOUT an aging-room constraint")
    print("=" * 60)
    results = compare_scenarios(planner, base_milk, base_demand, prices, scenarios)
    print(summarize_comparison(results))

    # ---- Original assertions ----
    milk_drop = next(r for r in results if r.scenario.name == "Milk drops 20%")
    assert milk_drop.profit_delta_vs_base < 0, "Less milk should reduce profit vs baseline"

    xmas = next(r for r in results if r.scenario.name == "Christmas demand +40%")
    assert xmas.unmet_demand_delta_vs_base > 0, "Higher demand on the same milk should increase shortfall"

    pasteurizer_fail = next(r for r in results if r.scenario.name == "Pasteurizer fails")
    assert pasteurizer_fail.plan.total_profit < results[0].plan.total_profit
    assert pasteurizer_fail.plan.allocation.utilization_rate == 0.0

    print("\nAll original checks passed.")

    # ---- New: aging-room capacity threads through to the scenario plans ----
    print("\n" + "=" * 60)
    print("compare_scenarios WITH a tight aging-room constraint (5kg left)")
    print("=" * 60)

    parmesan_aging = AgingConfig(aging_years=2.0, storage_cost_rate=0.035, aging_loss_rate=0.025,
                                  financing_rate=0.06, yield_rate=0.88, overage_penalty_multiplier=1.5)
    aged_book = RecipeBook()
    aged_book.add(book.get("Mozzarella"))
    aged_book.add(CheeseRecipe(
        name="Reserve Parmesan", product_code="PARM-24", category="Aged Hard Cheese",
        batch_size_kg=35.0, milk_liters_per_batch=550.0,
        shelf_life_days=365 * 3, lead_time_days=365 * 2 + 30,
        non_milk_ingredients=[BOMLineItem("Bacterial Culture", 0.8, "liters", 1500.0)],
        packaging=[BOMLineItem("Wooden Crate", 1, "unit", 350.0)],
        operations=[OperationStep("Pressing", 4.0, "Press", 300.0)],
        aging=parmesan_aging,
    ))
    aged_tracker = BatchTracker()
    aged_planner = ProductionPlanner(aged_book, aged_tracker, milk_cost_per_liter=45.0,
                                      raw_milk_price_per_liter=35.0)
    aged_demand = {"Mozzarella": (60.0, 18.0), "Reserve Parmesan": (20.0, 6.0)}
    aged_prices = {"Mozzarella": 650.0, "Reserve Parmesan": 1800.0}

    capped_results = compare_scenarios(
        aged_planner, base_milk, aged_demand, aged_prices, scenarios,
        aging_room_capacity_kg=5.0, aging_room_used_kg=0.0,
    )
    print(summarize_comparison(capped_results))

    for r in capped_results:
        if r.error:
            continue
        parm_rec = next((rec for rec in r.plan.recommendations if rec.cheese_name == "Reserve Parmesan"), None)
        if parm_rec:
            assert parm_rec.recommended_kg <= 5.0 + 1e-6, \
                f"[{r.scenario.name}] aging room cap should have capped Reserve Parmesan production"

    print("\nAging-room threading check passed.")

    # ---- New: a scenario error shouldn't kill the whole comparison ----
    print("\n" + "=" * 60)
    print("Failure isolation: one broken scenario shouldn't kill the rest")
    print("=" * 60)

    class _BrokenPlanner:
        def build_plan(self, *args, **kwargs):
            raise ValueError("simulated failure")

    bad_scenario = Scenario(name="Broken scenario")
    failed_result = _run_scenario_safely(
        _BrokenPlanner(), base_milk, base_demand, prices,
        bad_scenario, results[0].plan, None, 0.0,
    )
    assert failed_result.error is not None, "Failed scenario should carry an error message"
    assert failed_result.plan is None, "Failed scenario should not carry a partial plan"
    print(summarize_comparison([results[0], failed_result]))
    print("\nFailure isolation check passed.")

    print("\nAll checks passed.")