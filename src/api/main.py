import os

import mlflow
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from prometheus_fastapi_instrumentator import Instrumentator
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

app = FastAPI(title="FreshFlow Demand Forecasting API")

if HAS_PROMETHEUS:
    Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load MLflow configurations
MLFLOW_DB = os.getenv("MLFLOW_DB", "sqlite:///opt/airflow/data/mlruns.db")
mlflow.set_tracking_uri(MLFLOW_DB)

model = None

def load_latest_model():
    global model
    try:
        experiment = mlflow.get_experiment_by_name("freshflow_demand_forecasting")
        if not experiment:
            print("Experiment not found.")
            return False

        runs = mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            order_by=["metrics.rmse ASC"],
            max_results=1
        )

        if runs.empty:
            print("No runs found.")
            return False

        best_run_id = runs.iloc[0].run_id
        model_uri = f"runs:/{best_run_id}/model"

        print(f"Loading model from {model_uri}...")
        model = mlflow.lightgbm.load_model(model_uri)
        return True
    except Exception as e:
        print(f"Error loading model: {e}")
        return False

class ForecastRequest(BaseModel):
    store_id: int
    product_id: int
    store_cluster: str
    volume_band: str
    discount_factor: float
    year: int
    month: int
    day: int
    hour: int

class ForecastResponse(BaseModel):
    forecasted_demand: float

@app.on_event("startup")
def startup_event():
    success = load_latest_model()
    if not success:
        print("Warning: Model could not be loaded at startup.")

@app.get("/health")
def health_check():
    return {"status": "healthy", "model_loaded": model is not None}

@app.post("/predict", response_model=ForecastResponse)
def predict(request: ForecastRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model is not loaded.")

    input_data = pd.DataFrame([{
        "store_id": request.store_id,
        "product_id": request.product_id,
        "discount_factor": request.discount_factor,
        "store_cluster": request.store_cluster,
        "volume_band": request.volume_band,
        "year": request.year,
        "month": request.month,
        "day": request.day,
        "hour": request.hour
    }])

    # Apply categorical types for LightGBM
    categorical_cols = ['store_id', 'product_id', 'store_cluster', 'volume_band']
    for col in categorical_cols:
        input_data[col] = input_data[col].astype('category')

    try:
        prediction = model.predict(input_data)[0]
        # Demand cannot be negative
        prediction = max(0.0, float(prediction))
        return ForecastResponse(forecasted_demand=prediction)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

class OptimizeRequest(BaseModel):
    mean_demand: float
    std_demand: float = 0.0
    unit_price: float = 10.0
    unit_cost: float = 6.0
    holding_cost: float = 0.5
    shelf_life_days: int = 3
    stockout_penalty: float = 5.0
    salvage_value: float = 1.0

@app.post("/optimize-order")
def optimize_order(request: OptimizeRequest):
    from src.ml.optimizer import InventoryOptimizer
    optimizer = InventoryOptimizer()
    res = optimizer.calculate_optimal_order(
        mean_demand=request.mean_demand,
        std_demand=request.std_demand,
        unit_price=request.unit_price,
        unit_cost=request.unit_cost,
        holding_cost=request.holding_cost,
        shelf_life_days=request.shelf_life_days,
        stockout_penalty=request.stockout_penalty,
        salvage_value=request.salvage_value
    )
    return res.__dict__


@app.post("/reload-model")
def reload_model():
    """Hot-reload the latest trained model from MLflow without restarting the server."""
    success = load_latest_model()
    return {
        "success": success,
        "model_loaded": model is not None,
        "message": "Model reloaded successfully" if success else "Reload failed — check MLflow"
    }

