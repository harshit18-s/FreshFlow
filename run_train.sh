#!/bin/bash
set -e

echo "Installing Python dependencies with retries..."
max_retries=5
count=0
success=0

while [ $count -lt $max_retries ]; do
    if pip install --no-cache-dir lightgbm mlflow shap scikit-learn; then
        echo "Successfully installed pip packages."
        success=1
        break
    else
        echo "Pip install failed. Retrying... ($((count+1))/$max_retries)"
        count=$((count+1))
        sleep 5
    fi
done

if [ $success -eq 0 ]; then
    echo "Failed to install Python dependencies after $max_retries attempts."
    exit 1
fi

echo "Running ML training script..."
python -m src.ml.train
