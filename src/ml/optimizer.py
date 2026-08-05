"""
FreshFlow AI - Prescriptive Inventory & Replenishment Optimizer
===============================================================
Computes cost-optimal reorder quantities (Q*) for perishable retail goods using
asymmetric cost functions, Newsvendor critical fractile optimization, and perishability risk scores.
"""

import numpy as np
from scipy.stats import norm
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class OptimizationResult:
    """Dataclass holding replenishment optimization results."""
    forecasted_demand: float
    optimal_order_qty: int
    safety_stock: int
    critical_fractile: float
    expected_stockout_units: float
    expected_waste_units: float
    expected_net_profit: float
    spoilage_risk_score: float  # 0.0 to 100.0%
    stockout_risk_score: float  # 0.0 to 100.0%


class InventoryOptimizer:
    """
    Prescriptive Inventory Optimizer using asymmetric loss functions
    balancing stockout penalty vs spoilage waste cost.
    """

    def __init__(
        self,
        default_cost_underage_ratio: float = 2.5,
        default_salvage_ratio: float = 0.1
    ):
        self.default_cost_underage_ratio = default_cost_underage_ratio
        self.default_salvage_ratio = default_salvage_ratio

    def calculate_optimal_order(
        self,
        mean_demand: float,
        std_demand: float = None,
        unit_price: float = 10.0,
        unit_cost: float = 6.0,
        holding_cost: float = 0.5,
        shelf_life_days: int = 3,
        stockout_penalty: float = 5.0,
        salvage_value: float = 1.0
    ) -> OptimizationResult:
        """
        Calculate optimal order quantity Q* minimizing expected total cost.

        :param mean_demand: Model forecasted mean demand (units)
        :param std_demand: Forecast error standard deviation (default ~ 20% of mean)
        :param unit_price: Retail selling price per unit ($)
        :param unit_cost: Wholesale purchase cost per unit ($)
        :param holding_cost: Holding/chilling cost per unit ($)
        :param shelf_life_days: Item shelf life in days
        :param stockout_penalty: Indirect cost of customer dissatisfaction ($)
        :param salvage_value: Discount clearance recovery price per unit ($)
        """
        mean_demand = max(0.1, float(mean_demand))
        
        if std_demand is None or std_demand <= 0:
            # Default standard deviation ~ 20% coefficient of variation
            std_demand = max(1.0, mean_demand * 0.20)

        # 1. Compute Underage Cost (Cu) & Overage Cost (Co)
        # Cu = Price - Cost + Stockout Penalty
        cu = max(0.1, (unit_price - unit_cost) + stockout_penalty)

        # Co = Cost + Holding Cost - Salvage Value + Perishability Penalty
        perishability_factor = max(1.0, 7.0 / max(1, shelf_life_days))
        co = max(0.1, (unit_cost + holding_cost - salvage_value) * perishability_factor)

        # 2. Critical Fractile (Service Level SL*)
        critical_fractile = cu / (cu + co)
        critical_fractile = np.clip(critical_fractile, 0.50, 0.99)

        # 3. Optimal Quantity Q* & Safety Stock via Normal Quantile Inversion
        z_score = norm.ppf(critical_fractile)
        safety_stock = int(np.ceil(z_score * std_demand))
        optimal_order_qty = int(np.ceil(mean_demand + z_score * std_demand))
        optimal_order_qty = max(0, optimal_order_qty)

        # 4. Expected Stockout & Expected Waste Calculation
        # Standard normal distribution loss functions
        z_opt = (optimal_order_qty - mean_demand) / std_demand
        expected_waste_units = std_demand * (z_opt * norm.cdf(z_opt) + norm.pdf(z_opt))
        expected_stockout_units = std_demand * (-z_opt * (1 - norm.cdf(z_opt)) + norm.pdf(z_opt))

        # Expected Net Profit
        expected_sales = mean_demand - expected_stockout_units
        expected_revenue = expected_sales * unit_price + expected_waste_units * salvage_value
        total_cost = optimal_order_qty * unit_cost + expected_stockout_units * stockout_penalty
        expected_net_profit = expected_revenue - total_cost

        # Risk Scores (0-100%)
        spoilage_risk_score = float(norm.cdf(z_opt) * (expected_waste_units / max(1, optimal_order_qty))) * 100.0
        spoilage_risk_score = np.clip(spoilage_risk_score, 0.0, 100.0)

        stockout_risk_score = float((1.0 - norm.cdf(z_opt))) * 100.0
        stockout_risk_score = np.clip(stockout_risk_score, 0.0, 100.0)

        return OptimizationResult(
            forecasted_demand=round(mean_demand, 2),
            optimal_order_qty=optimal_order_qty,
            safety_stock=safety_stock,
            critical_fractile=round(critical_fractile, 4),
            expected_stockout_units=round(expected_stockout_units, 2),
            expected_waste_units=round(expected_waste_units, 2),
            expected_net_profit=round(expected_net_profit, 2),
            spoilage_risk_score=round(spoilage_risk_score, 2),
            stockout_risk_score=round(stockout_risk_score, 2)
        )
