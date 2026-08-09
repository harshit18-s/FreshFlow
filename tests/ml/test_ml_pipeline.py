"""
ML Pipeline & Feature Engineering Tests.
"""

import pandas as pd

from src.ml.train import preprocess_features


def test_preprocess_features():
    raw_df = pd.DataFrame([{
        'date_key': 20260805,
        'time_key': 14,
        'store_id': 101,
        'product_id': 505,
        'observed_sales': 42.0,
        'discount_factor': 0.9,
        'store_cluster': 'Cluster B',
        'volume_band': 'Medium'
    }])

    X, y = preprocess_features(raw_df)

    assert 'year' in X.columns
    assert 'month' in X.columns
    assert 'day' in X.columns
    assert 'hour' in X.columns
    assert X['year'].iloc[0] == 2026
    assert X['month'].iloc[0] == 8
    assert X['day'].iloc[0] == 5
    assert X['hour'].iloc[0] == 14
    assert y.iloc[0] == 42.0
    assert X['store_cluster'].dtype.name == 'category'
