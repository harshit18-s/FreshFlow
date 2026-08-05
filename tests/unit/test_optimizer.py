"""
Unit tests for Prescriptive Inventory Optimizer.
"""

import pytest
from src.ml.optimizer import InventoryOptimizer, OptimizationResult

def test_inventory_optimizer_basic():
    optimizer = InventoryOptimizer()
    res = optimizer.calculate_optimal_order(
        mean_demand=100.0,
        std_demand=20.0,
        unit_price=10.0,
        unit_cost=6.0,
        shelf_life_days=3
    )
    
    assert isinstance(res, OptimizationResult)
    assert res.forecasted_demand == 100.0
    assert res.optimal_order_qty >= 100
    assert res.safety_stock >= 0
    assert 0.5 <= res.critical_fractile <= 0.99
    assert 0.0 <= res.spoilage_risk_score <= 100.0
    assert 0.0 <= res.stockout_risk_score <= 100.0


def test_inventory_optimizer_short_shelf_life():
    optimizer = InventoryOptimizer()
    # Very short shelf life (1 day) should increase overage penalty and lower critical fractile vs 7 day shelf life
    res_short = optimizer.calculate_optimal_order(mean_demand=100.0, shelf_life_days=1)
    res_long = optimizer.calculate_optimal_order(mean_demand=100.0, shelf_life_days=7)
    
    assert res_short.critical_fractile <= res_long.critical_fractile
    assert res_short.optimal_order_qty <= res_long.optimal_order_qty
