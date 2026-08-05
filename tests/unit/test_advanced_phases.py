"""
Unit tests for Advanced Phases 8, 9 & 10 (Drift Monitor & Streaming).
"""

import pytest
import numpy as np
import pandas as pd
from src.ml.drift_monitor import DriftMonitor, DriftResult


def test_drift_monitor_no_drift():
    monitor = DriftMonitor()
    np.random.seed(42)
    baseline = pd.Series(np.random.normal(100, 15, 1000))
    current = pd.Series(np.random.normal(100, 15, 1000))
    
    res = monitor.evaluate_feature_drift(baseline, current, feature_name="sales")
    
    assert isinstance(res, DriftResult)
    assert res.psi_score < 0.10
    assert res.drift_status == "NO_DRIFT"
    assert res.retrain_recommended is False


def test_drift_monitor_critical_drift():
    monitor = DriftMonitor()
    np.random.seed(42)
    baseline = pd.Series(np.random.normal(100, 15, 1000))
    # Shift mean significantly to simulate concept drift
    current = pd.Series(np.random.normal(180, 25, 1000))
    
    res = monitor.evaluate_feature_drift(baseline, current, feature_name="sales")
    
    assert res.psi_score >= 0.20 or res.p_value < 0.01
    assert res.drift_status == "CRITICAL_DRIFT"
    assert res.retrain_recommended is True


def test_evaluate_dataset_drift():
    monitor = DriftMonitor()
    df1 = pd.DataFrame({'f1': np.random.normal(10, 2, 500), 'f2': np.random.normal(50, 5, 500)})
    df2 = pd.DataFrame({'f1': np.random.normal(10, 2, 500), 'f2': np.random.normal(50, 5, 500)})
    
    results = monitor.evaluate_dataset_drift(df1, df2)
    assert len(results) == 2
    assert all(r.drift_status == "NO_DRIFT" for r in results)
