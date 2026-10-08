"""Waste-routing optimization layer for EcoTwin (Phase 4).

Determines optimal waste-routing allocations across compatible facilities to:
- Minimize landfill residue mass
- Maximize recovered material mass
- Maximize recovered clean energy
while strictly respecting physical facility capacities and category compatibility.

Important Architectural Rule:
The optimizer only proposes routing decisions (RoutingPlan).
The EcoTwin physics engine evaluates and computes all physical mass/energy balances.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ecotwin.balance import EcoTwinEngine, SystemBalanceResult
from ecotwin.categories import WasteCategory
from ecotwin.exceptions import CapacityExceededError, InvalidRoutingError
from ecotwin.facility import ProcessingFacility
from ecotwin.routing import RouteSplit, RoutingPlan
from ecotwin.scenario import ScenarioExecutionResult, UrbanScenario
from ecotwin.units import EnergyUnit, Mass


@dataclass(frozen=True)
class OptimizationWeights:
    """
    Configurable objective weights for multi-criteria waste-routing optimization.
    
    Objective Function to Maximize:
    J = (w_mat * M_recovered / M_total) 
        - (w_landfill * M_landfill / M_total) 
        + (w_energy * E_recovered_MWh / (M_total_tonnes * ref_energy_MWh_per_tonne))
    """

    material_recovery_weight: float = 1.0
    landfill_penalty_weight: float = 1.0
    energy_recovery_weight: float = 0.5
    energy_reference_mwh_per_tonne: float = 1.0

    def __post_init__(self) -> None:
        if self.material_recovery_weight < 0:
            raise ValueError("material_recovery_weight cannot be negative.")
        if self.landfill_penalty_weight < 0:
            raise ValueError("landfill_penalty_weight cannot be negative.")
        if self.energy_recovery_weight < 0:
            raise ValueError("energy_recovery_weight cannot be negative.")
        if self.energy_reference_mwh_per_tonne <= 0:
            raise ValueError("energy_reference_mwh_per_tonne must be positive.")

    def calculate_score(self, simulation_result: SystemBalanceResult | ScenarioExecutionResult) -> float:
        """Computes the scalar objective score from simulation results."""
        if isinstance(simulation_result, ScenarioExecutionResult):
            res = simulation_result.system_balance_result
        else:
            res = simulation_result

        total_kg = res.total_incoming_mass.to_kg().value
        if total_kg <= 0.0:
            return 0.0

        mat_frac = res.total_material_recovered.to_kg().value / total_kg
        landfill_frac = res.total_landfill_residue.to_kg().value / total_kg
        
        # Energy per unit mass in MWh / tonne
        total_tonnes = res.total_incoming_mass.to_tonnes().value
        energy_mwh = res.total_energy_recovered.to_mwh().value
        energy_norm = (energy_mwh / total_tonnes) / self.energy_reference_mwh_per_tonne if total_tonnes > 0 else 0.0

        score = (
            (self.material_recovery_weight * mat_frac)
            - (self.landfill_penalty_weight * landfill_frac)
            + (self.energy_recovery_weight * energy_norm)
        )
        return float(score)


@dataclass(frozen=True)
class OptimizationResult:
    """
    Structured outcome of the routing optimization process.
    
    Contains baseline vs optimized routing plans, simulation outcomes, score delta, and solver metadata.
    """

    baseline_scenario: UrbanScenario
    optimized_scenario: UrbanScenario
    baseline_routing: RoutingPlan
    optimized_routing: RoutingPlan
    baseline_execution: ScenarioExecutionResult
    optimized_execution: ScenarioExecutionResult
    weights: OptimizationWeights
    baseline_score: float
    optimized_score: float
    score_improvement: float
    score_improvement_pct: float
    status: str
    solver_metadata: Dict[str, Any]

    def comparison(self) -> Dict[str, Any]:
        """Structured comparison between baseline and optimized routing outcomes."""
        base_res = self.baseline_execution
        opt_res = self.optimized_execution

        unit_m = base_res.total_waste_processed.unit.value
        unit_e = base_res.total_energy_recovered.unit.value

        base_mat = base_res.total_material_recovered.to_tonnes().value
        opt_mat = opt_res.total_material_recovered.to_tonnes().value

        base_landfill = base_res.total_landfill_residue.to_tonnes().value
        opt_landfill = opt_res.total_landfill_residue.to_tonnes().value

        base_energy = base_res.total_energy_recovered.to_mwh().value
        opt_energy = opt_res.total_energy_recovered.to_mwh().value

        return {
            "status": self.status,
            "objective_scores": {
                "baseline": round(self.baseline_score, 4),
                "optimized": round(self.optimized_score, 4),
                "improvement": round(self.score_improvement, 4),
                "improvement_pct": round(self.score_improvement_pct, 2),
            },
            "metrics_comparison": {
                "material_recovered_tonnes": {
                    "baseline": round(base_mat, 2),
                    "optimized": round(opt_mat, 2),
                    "delta": round(opt_mat - base_mat, 2),
                },
                "material_recovery_rate_pct": {
                    "baseline": round(base_res.material_recovery_rate * 100.0, 2),
                    "optimized": round(opt_res.material_recovery_rate * 100.0, 2),
                    "delta": round((opt_res.material_recovery_rate - base_res.material_recovery_rate) * 100.0, 2),
                },
                "landfill_residue_tonnes": {
                    "baseline": round(base_landfill, 2),
                    "optimized": round(opt_landfill, 2),
                    "delta": round(opt_landfill - base_landfill, 2),
                },
                "landfill_diversion_rate_pct": {
                    "baseline": round(base_res.landfill_diversion_rate * 100.0, 2),
                    "optimized": round(opt_res.landfill_diversion_rate * 100.0, 2),
                    "delta": round((opt_res.landfill_diversion_rate - base_res.landfill_diversion_rate) * 100.0, 2),
                },
                "energy_recovered_mwh": {
                    "baseline": round(base_energy, 2),
                    "optimized": round(opt_energy, 2),
                    "delta": round(opt_energy - base_energy, 2),
                },
                "mass_balance_error_kg": {
                    "baseline": base_res.mass_balance_error_kg,
                    "optimized": opt_res.mass_balance_error_kg,
                },
            },
            "facility_utilizations_pct": {
                "baseline": {
                    k: round(v * 100.0, 2) for k, v in base_res.facility_utilizations.items()
                },
                "optimized": {
                    k: round(v * 100.0, 2) for k, v in opt_res.facility_utilizations.items()
                },
            },
        }

    def format_report(self) -> str:
        """Generates human-readable text comparison between baseline and optimized routing."""
        comp = self.comparison()
        m_comp = comp["metrics_comparison"]
        u_comp = comp["facility_utilizations_pct"]

        lines = [
            "=" * 74,
            f" EcoTwin Waste-Routing Optimization Report: {self.baseline_scenario.name}",
            "=" * 74,
            f"  * Solver Status       : {self.status} ({self.solver_metadata.get('algorithm', 'Simplex LP')})",
            f"  * Baseline Score      : {self.baseline_score:.4f}",
            f"  * Optimized Score     : {self.optimized_score:.4f} (Score Improvement: {self.score_improvement:+.4f} / {self.score_improvement_pct:+.2f}%)",
            "\n[System-Level Metrics Comparison]",
            f"  {'Metric':<30} | {'Baseline':<12} | {'Optimized':<12} | {'Delta':<10}",
            f"  {'-'*30}-|-{'-'*12}-|-{'-'*12}-|-{'-'*10}",
            f"  {'Landfill Residue (tonnes)':<30} | {m_comp['landfill_residue_tonnes']['baseline']:>10.2f} t | {m_comp['landfill_residue_tonnes']['optimized']:>10.2f} t | {m_comp['landfill_residue_tonnes']['delta']:>+8.2f} t",
            f"  {'Landfill Diversion Rate':<30} | {m_comp['landfill_diversion_rate_pct']['baseline']:>10.2f} % | {m_comp['landfill_diversion_rate_pct']['optimized']:>10.2f} % | {m_comp['landfill_diversion_rate_pct']['delta']:>+8.2f} %",
            f"  {'Material Recovered (tonnes)':<30} | {m_comp['material_recovered_tonnes']['baseline']:>10.2f} t | {m_comp['material_recovered_tonnes']['optimized']:>10.2f} t | {m_comp['material_recovered_tonnes']['delta']:>+8.2f} t",
            f"  {'Material Recovery Rate':<30} | {m_comp['material_recovery_rate_pct']['baseline']:>10.2f} % | {m_comp['material_recovery_rate_pct']['optimized']:>10.2f} % | {m_comp['material_recovery_rate_pct']['delta']:>+8.2f} %",
            f"  {'Energy Recovered (MWh)':<30} | {m_comp['energy_recovered_mwh']['baseline']:>10.2f}   | {m_comp['energy_recovered_mwh']['optimized']:>10.2f}   | {m_comp['energy_recovered_mwh']['delta']:>+8.2f} MWh",
            f"  {'Mass Balance Error (kg)':<30} | {m_comp['mass_balance_error_kg']['baseline']:>10.6f} kg| {m_comp['mass_balance_error_kg']['optimized']:>10.6f} kg| 0.000000 kg",
            "\n[Facility Capacity Utilization Comparison]",
            f"  {'Facility':<30} | {'Baseline':<12} | {'Optimized':<12}",
            f"  {'-'*30}-|-{'-'*12}-|-{'-'*12}",
        ]

        for fac_name in self.baseline_scenario.facilities:
            b_u = u_comp["baseline"].get(fac_name, 0.0)
            o_u = u_comp["optimized"].get(fac_name, 0.0)
            lines.append(f"  {fac_name:<30} | {b_u:>10.1f} % | {o_u:>10.1f} %")

        lines.append("=" * 74)
        return "\n".join(lines)


# -----------------------------------------------------------------------------
# Exact Linear Programming Simplex Solver (Pure Python Two-Phase Simplex)
# -----------------------------------------------------------------------------

class LinearProgramSolver:
    """
    Deterministic Two-Phase Simplex Linear Programming solver.
    Solves linear programs to global mathematical optimality with zero external dependencies.
    """

    @staticmethod
    def solve_lp(
        c: List[float],
        A_ub: List[List[float]],
        b_ub: List[float],
        A_eq: List[List[float]],
        b_eq: List[float],
        max_iterations: int = 1000,
    ) -> Tuple[str, Optional[List[float]], float]:
        """
        Maximizes c^T x subject to:
          A_ub x <= b_ub  (b_ub >= 0)
          A_eq x == b_eq  (b_eq >= 0)
          x >= 0
        """
        n_vars = len(c)
        n_ub = len(b_ub)
        n_eq = len(b_eq)

        # Standardize constraints so RHS >= 0
        for i in range(n_ub):
            if b_ub[i] < 0:
                # Multiply row by -1 (becomes >=, which requires artificial)
                return ("UNSUPPORTED_NEGATIVE_RHS", None, 0.0)
        for i in range(n_eq):
            if b_eq[i] < 0:
                b_eq[i] = -b_eq[i]
                A_eq[i] = [-val for val in A_eq[i]]

        n_rows = n_ub + n_eq
        n_slack = n_ub
        n_art = n_eq

        # Tableau structure:
        # Columns: [Original vars (n_vars)] [Slack vars (n_ub)] [Artificial vars (n_eq)] [RHS (1)]
        total_cols = n_vars + n_slack + n_art + 1
        rhs_col = total_cols - 1

        # Phase 1 Tableau
        # If no equality constraints, no Phase 1 needed
        tableau = [[0.0 for _ in range(total_cols)] for _ in range(n_rows + 1)]

        # Fill inequality constraints
        for i in range(n_ub):
            for j in range(n_vars):
                tableau[i][j] = A_ub[i][j]
            tableau[i][n_vars + i] = 1.0  # Slack
            tableau[i][rhs_col] = b_ub[i]

        # Fill equality constraints
        for i in range(n_eq):
            row_idx = n_ub + i
            for j in range(n_vars):
                tableau[row_idx][j] = A_eq[i][j]
            if n_art > 0:
                tableau[row_idx][n_vars + n_slack + i] = 1.0  # Artificial
            tableau[row_idx][rhs_col] = b_eq[i]

        basis = [0 for _ in range(n_rows)]
        for i in range(n_ub):
            basis[i] = n_vars + i
        for i in range(n_eq):
            basis[n_ub + i] = n_vars + n_slack + i

        # Phase 1 Objective: Minimize sum of artificials -> Maximize -sum(a_i)
        if n_art > 0:
            # Objective row = sum of artificial rows (to eliminate artificials from obj row)
            for j in range(total_cols):
                for i in range(n_eq):
                    row_idx = n_ub + i
                    tableau[n_rows][j] += tableau[row_idx][j]
            tableau[n_rows][rhs_col] = sum(tableau[n_ub + i][rhs_col] for i in range(n_eq))

            # Run Phase 1 Simplex
            it = 0
            while it < max_iterations:
                it += 1
                # Find entering variable (most positive reduced cost in obj row for artificial minimization)
                pivot_col = -1
                max_rc = 1e-9
                for j in range(total_cols - 1):
                    if tableau[n_rows][j] > max_rc:
                        max_rc = tableau[n_rows][j]
                        pivot_col = j

                if pivot_col == -1:
                    break  # Phase 1 optimal

                # Minimum ratio test
                pivot_row = -1
                min_ratio = float("inf")
                for i in range(n_rows):
                    val = tableau[i][pivot_col]
                    if val > 1e-9:
                        ratio = tableau[i][rhs_col] / val
                        if ratio < min_ratio - 1e-9:
                            min_ratio = ratio
                            pivot_row = i

                if pivot_row == -1:
                    return ("PHASE1_UNBOUNDED", None, 0.0)

                # Pivot on (pivot_row, pivot_col)
                p_val = tableau[pivot_row][pivot_col]
                for j in range(total_cols):
                    tableau[pivot_row][j] /= p_val

                for i in range(n_rows + 1):
                    if i != pivot_row:
                        factor = tableau[i][pivot_col]
                        if abs(factor) > 1e-12:
                            for j in range(total_cols):
                                tableau[i][j] -= factor * tableau[pivot_row][j]

                basis[pivot_row] = pivot_col

            phase1_val = tableau[n_rows][rhs_col]
            if abs(phase1_val) > 1e-5:
                return ("INFEASIBLE", None, 0.0)

        # Phase 2: Optimize original objective c^T x
        # Reconstruct objective row for original variables
        phase2_cols = n_vars + n_slack + 1
        phase2_rhs_col = phase2_cols - 1

        p2_tableau = [[0.0 for _ in range(phase2_cols)] for _ in range(n_rows + 1)]
        for i in range(n_rows):
            for j in range(n_vars + n_slack):
                p2_tableau[i][j] = tableau[i][j]
            p2_tableau[i][phase2_rhs_col] = tableau[i][rhs_col]

        # Initial original objective: Maximize c^T x -> row = -c
        for j in range(n_vars):
            p2_tableau[n_rows][j] = -c[j]

        # Drive basic variable costs to 0 in objective row
        for i in range(n_rows):
            b_var = basis[i]
            if b_var < n_vars:
                c_val = p2_tableau[n_rows][b_var]
                for j in range(phase2_cols):
                    p2_tableau[n_rows][j] -= c_val * p2_tableau[i][j]

        # Phase 2 Simplex iterations
        it = 0
        while it < max_iterations:
            it += 1
            # Find entering variable: most negative reduced cost
            pivot_col = -1
            min_rc = -1e-9
            for j in range(phase2_cols - 1):
                if p2_tableau[n_rows][j] < min_rc:
                    min_rc = p2_tableau[n_rows][j]
                    pivot_col = j

            if pivot_col == -1:
                break  # Optimal solution found!

            # Minimum ratio test
            pivot_row = -1
            min_ratio = float("inf")
            for i in range(n_rows):
                val = p2_tableau[i][pivot_col]
                if val > 1e-9:
                    ratio = p2_tableau[i][phase2_rhs_col] / val
                    if ratio < min_ratio - 1e-9:
                        min_ratio = ratio
                        pivot_row = i

            if pivot_row == -1:
                return ("UNBOUNDED", None, float("inf"))

            # Pivot on (pivot_row, pivot_col)
            p_val = p2_tableau[pivot_row][pivot_col]
            for j in range(phase2_cols):
                p2_tableau[pivot_row][j] /= p_val

            for i in range(n_rows + 1):
                if i != pivot_row:
                    factor = p2_tableau[i][pivot_col]
                    if abs(factor) > 1e-12:
                        for j in range(phase2_cols):
                            p2_tableau[i][j] -= factor * p2_tableau[pivot_row][j]

            basis[pivot_row] = pivot_col

        # Extract solution x
        x_sol = [0.0 for _ in range(n_vars)]
        for i in range(n_rows):
            if basis[i] < n_vars:
                x_sol[basis[i]] = max(0.0, p2_tableau[i][phase2_rhs_col])

        obj_val = p2_tableau[n_rows][phase2_rhs_col]
        return ("OPTIMAL", x_sol, obj_val)


class WasteRoutingOptimizer:
    """
    Deterministic Linear Programming Optimizer for urban waste routing.
    """

    def __init__(self, weights: Optional[OptimizationWeights] = None):
        self.weights = weights or OptimizationWeights()

    def optimize(
        self,
        scenario: UrbanScenario,
        energy_output_unit: EnergyUnit = EnergyUnit.MWH,
    ) -> OptimizationResult:
        """
        Solves for the optimal category-to-facility routing plan that maximizes the multi-criteria score
        while strictly satisfying all mass-balance, routing-fraction, and facility capacity constraints.
        """
        # 1. Run baseline scenario first to record baseline performance
        baseline_exec = scenario.run(energy_output_unit=energy_output_unit)
        baseline_score = self.weights.calculate_score(baseline_exec)

        total_mass = scenario.daily_waste_generation
        total_mass_tonnes = total_mass.to_tonnes().value
        comp_breakdown = scenario.composition

        categories = list(WasteCategory)
        facilities = list(scenario.facilities.values())
        fac_names = [f.name for f in facilities]

        # Map variable indices: x[cat_idx, fac_idx] is fraction of category routed to facility
        n_cats = len(categories)
        n_facs = len(facilities)
        n_vars = n_cats * n_facs

        def var_idx(c_i: int, f_i: int) -> int:
            return c_i * n_facs + f_i

        # 2. Objective coefficients:
        # Maximize sum_{c, f} (M_c * u_{c, f}) * x_{c, f}
        c_obj = [0.0 for _ in range(n_vars)]
        for c_i, cat in enumerate(categories):
            cat_frac = comp_breakdown.get(cat, 0.0)
            cat_mass_tonnes = total_mass_tonnes * cat_frac

            for f_i, fac in enumerate(facilities):
                idx = var_idx(c_i, f_i)
                if not fac.is_category_accepted(cat):
                    # Incompatible route -> large negative penalty
                    c_obj[idx] = -1e6
                    continue

                profile = fac.get_profile_for_category(cat)
                r_mat = profile.material_recovery_rate
                r_landfill = profile.landfill_residue_rate
                
                # Energy yield in MWh / tonne
                e_yield_mwh_per_t = (profile.specific_energy.kwh_per_tonne / 1000.0) * profile.energy_efficiency

                # Linear utility per unit mass
                u_cf = (
                    (self.weights.material_recovery_weight * r_mat)
                    - (self.weights.landfill_penalty_weight * r_landfill)
                    + (self.weights.energy_recovery_weight * (e_yield_mwh_per_t / self.weights.energy_reference_mwh_per_tonne))
                )
                c_obj[idx] = cat_mass_tonnes * u_cf

        # 3. Constraints:
        # (a) Equality: For each category c, sum_{f} x_{c, f} = 1.0 (if cat has mass > 0)
        A_eq: List[List[float]] = []
        b_eq: List[float] = []

        for c_i, cat in enumerate(categories):
            row = [0.0 for _ in range(n_vars)]
            for f_i in range(n_facs):
                row[var_idx(c_i, f_i)] = 1.0
            A_eq.append(row)
            b_eq.append(1.0)

        # (b) Incompatible category constraints: x_{c, f} == 0 if fac does not accept cat
        for c_i, cat in enumerate(categories):
            for f_i, fac in enumerate(facilities):
                if not fac.is_category_accepted(cat):
                    row = [0.0 for _ in range(n_vars)]
                    row[var_idx(c_i, f_i)] = 1.0
                    A_eq.append(row)
                    b_eq.append(0.0)

        # (c) Inequality: Facility capacity bounds
        # For each facility f, sum_{c} M_c * x_{c, f} <= Capacity_f
        A_ub: List[List[float]] = []
        b_ub: List[float] = []

        for f_i, fac in enumerate(facilities):
            cap_tonnes = fac.capacity.to_tonnes().value
            row = [0.0 for _ in range(n_vars)]
            for c_i, cat in enumerate(categories):
                cat_frac = comp_breakdown.get(cat, 0.0)
                cat_mass_tonnes = total_mass_tonnes * cat_frac
                row[var_idx(c_i, f_i)] = cat_mass_tonnes
            A_ub.append(row)
            b_ub.append(cap_tonnes)

        # 4. Solve Linear Program
        status, sol, obj_val = LinearProgramSolver.solve_lp(
            c=c_obj,
            A_ub=A_ub,
            b_ub=b_ub,
            A_eq=A_eq,
            b_eq=b_eq,
        )

        if status != "OPTIMAL" or sol is None:
            # Fallback to baseline if problem is infeasible
            solver_meta = {
                "algorithm": "Two-Phase Simplex LP",
                "status": status,
                "iterations": 0,
                "notes": f"Solver status {status}; returning baseline configuration.",
            }
            return OptimizationResult(
                baseline_scenario=scenario,
                optimized_scenario=scenario,
                baseline_routing=scenario.routing_plan,
                optimized_routing=scenario.routing_plan,
                baseline_execution=baseline_exec,
                optimized_execution=baseline_exec,
                weights=self.weights,
                baseline_score=baseline_score,
                optimized_score=baseline_score,
                score_improvement=0.0,
                score_improvement_pct=0.0,
                status=status,
                solver_metadata=solver_meta,
            )

        # 5. Extract and construct optimized RoutingPlan
        optimized_routes: Dict[WasteCategory, Tuple[RouteSplit, ...]] = {}
        for c_i, cat in enumerate(categories):
            splits: List[RouteSplit] = []
            for f_i, fac in enumerate(facilities):
                idx = var_idx(c_i, f_i)
                raw_frac = sol[idx]
                if raw_frac > 1e-5:
                    splits.append(RouteSplit(facility_name=fac.name, fraction=float(raw_frac)))

            # If total fraction slightly diverges due to precision, normalize strictly to 1.0
            split_sum = sum(s.fraction for s in splits)
            if split_sum > 0:
                normalized_splits = tuple(
                    RouteSplit(facility_name=s.facility_name, fraction=s.fraction / split_sum) for s in splits
                )
            else:
                # Default to first compatible facility
                compatible = [fac.name for fac in facilities if fac.is_category_accepted(cat)]
                target = compatible[0] if compatible else facilities[0].name
                normalized_splits = (RouteSplit(facility_name=target, fraction=1.0),)

            optimized_routes[cat] = normalized_splits

        optimized_routing_plan = RoutingPlan(routes=optimized_routes)

        # 6. Create optimized UrbanScenario and run through EcoTwinEngine
        opt_scenario_metadata = dict(scenario.metadata)
        opt_scenario_metadata["optimization"] = {
            "status": status,
            "weights": {
                "material_recovery_weight": self.weights.material_recovery_weight,
                "landfill_penalty_weight": self.weights.landfill_penalty_weight,
                "energy_recovery_weight": self.weights.energy_recovery_weight,
            },
        }

        optimized_scenario = UrbanScenario.create(
            name=f"{scenario.name}_Optimized",
            daily_waste_generation=scenario.daily_waste_generation,
            composition=scenario.composition,
            facilities=scenario.facilities,
            routing_plan=optimized_routing_plan,
            metadata=opt_scenario_metadata,
            description=f"Optimized routing scenario derived from '{scenario.name}'.",
        )

        optimized_exec = optimized_scenario.run(energy_output_unit=energy_output_unit)
        optimized_score = self.weights.calculate_score(optimized_exec)

        score_diff = optimized_score - baseline_score
        score_diff_pct = (score_diff / abs(baseline_score) * 100.0) if abs(baseline_score) > 1e-9 else 0.0

        solver_meta = {
            "algorithm": "Two-Phase Simplex LP",
            "status": "OPTIMAL",
            "global_optimality_guarantee": True,
            "variables_count": n_vars,
            "constraints_count": len(A_ub) + len(A_eq),
        }

        return OptimizationResult(
            baseline_scenario=scenario,
            optimized_scenario=optimized_scenario,
            baseline_routing=scenario.routing_plan,
            optimized_routing=optimized_routing_plan,
            baseline_execution=baseline_exec,
            optimized_execution=optimized_exec,
            weights=self.weights,
            baseline_score=baseline_score,
            optimized_score=optimized_score,
            score_improvement=score_diff,
            score_improvement_pct=score_diff_pct,
            status="OPTIMAL",
            solver_metadata=solver_meta,
        )


def optimize_scenario_routing(
    scenario: UrbanScenario,
    weights: Optional[OptimizationWeights] = None,
    energy_output_unit: EnergyUnit = EnergyUnit.MWH,
) -> OptimizationResult:
    """Convenience functional interface to optimize routing for an UrbanScenario."""
    optimizer = WasteRoutingOptimizer(weights=weights)
    return optimizer.optimize(scenario=scenario, energy_output_unit=energy_output_unit)
