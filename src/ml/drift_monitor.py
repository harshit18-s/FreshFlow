"""
FreshFlow AI — MLOps Drift Detection & Governance Engine
=========================================================
Monitors statistical distribution shift (Data Drift) and prediction shift (Concept Drift)
between baseline training distributions and live production inference streams.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp


@dataclass
class DriftResult:
    """Dataclass holding statistical drift evaluation results."""
    feature_name: str
    ks_statistic: float
    p_value: float
    psi_score: float
    drift_status: str  # 'NO_DRIFT', 'MODERATE_DRIFT', 'CRITICAL_DRIFT'
    retrain_recommended: bool


class DriftMonitor:
    """
    Computes statistical distribution shift metrics (PSI & KS-test)
    for model feature drift and performance degradation monitoring.
    """

    def __init__(self, psi_warning_threshold: float = 0.10, psi_critical_threshold: float = 0.20):
        self.psi_warning_threshold = psi_warning_threshold
        self.psi_critical_threshold = psi_critical_threshold

    def calculate_psi(self, baseline: np.ndarray, current: np.ndarray, num_buckets: int = 10) -> float:
        """
        Calculate Population Stability Index (PSI) between baseline and current data distribution.
        """
        baseline = np.asarray(baseline, dtype=float)
        current = np.asarray(current, dtype=float)

        # Remove NaNs
        baseline = baseline[~np.isnan(baseline)]
        current = current[~np.isnan(current)]

        if len(baseline) == 0 or len(current) == 0:
            return 0.0

        # Define quantile bin edges from baseline
        percentiles = np.linspace(0, 100, num_buckets + 1)
        bin_edges = np.percentile(baseline, percentiles)
        bin_edges[0] -= 1e-5
        bin_edges[-1] += 1e-5

        # Compute bucket proportions
        b_counts, _ = np.histogram(baseline, bins=bin_edges)
        c_counts, _ = np.histogram(current, bins=bin_edges)

        b_props = b_counts / float(len(baseline))
        c_props = c_counts / float(len(current))

        # Add small epsilon to prevent division by zero or log(0)
        eps = 1e-4
        b_props = np.where(b_props == 0, eps, b_props)
        c_props = np.where(c_props == 0, eps, c_props)

        # PSI formula
        psi_value = np.sum((c_props - b_props) * np.log(c_props / b_props))
        return float(np.round(psi_value, 4))

    def evaluate_feature_drift(
        self,
        baseline_data: pd.Series,
        current_data: pd.Series,
        feature_name: str = "feature"
    ) -> DriftResult:
        """
        Evaluate feature drift using both 2-sample KS-test and PSI.
        """
        # Numeric conversion for categorical data
        if baseline_data.dtype.name == 'category' or baseline_data.dtype == object:
            b_vals = baseline_data.astype('category').cat.codes.values
            c_vals = current_data.astype('category').cat.codes.values
        else:
            b_vals = baseline_data.values
            c_vals = current_data.values

        # KS Test
        ks_stat, p_val = ks_2samp(b_vals, c_vals)
        ks_stat = float(np.round(ks_stat, 4))
        p_val = float(np.round(p_val, 4))

        # PSI Metric
        psi_score = self.calculate_psi(b_vals, c_vals)

        # Determine drift status
        if psi_score >= self.psi_critical_threshold or p_val < 0.01:
            drift_status = "CRITICAL_DRIFT"
            retrain = True
        elif psi_score >= self.psi_warning_threshold:
            drift_status = "MODERATE_DRIFT"
            retrain = False
        else:
            drift_status = "NO_DRIFT"
            retrain = False

        return DriftResult(
            feature_name=feature_name,
            ks_statistic=ks_stat,
            p_value=p_val,
            psi_score=psi_score,
            drift_status=drift_status,
            retrain_recommended=retrain
        )

    def evaluate_dataset_drift(
        self,
        baseline_df: pd.DataFrame,
        current_df: pd.DataFrame
    ) -> list[DriftResult]:
        """
        Evaluate drift across all matching columns in the dataset.
        """
        common_cols = [c for c in baseline_df.columns if c in current_df.columns]
        results = []
        for col in common_cols:
            res = self.evaluate_feature_drift(baseline_df[col], current_df[col], feature_name=col)
            results.append(res)
        return results
