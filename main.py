# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
from pathlib import Path
import numpy as np
import calendar
import math

app = FastAPI()

# Allow React frontend (default: localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev, restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent

# Load CSVs
def load_csv(name):
    path = BASE_DIR / f"{name}.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name}.csv not found")
    return pd.read_csv(path)

DATASETS = ["req_prod", "capacity", "production", "inventory", "sales", "dos"]

@app.get("/data/{name}")
def get_data(name: str):
    if name not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")
    df = load_csv(name)
    return {"columns": df.columns.tolist(), "data": df.fillna("").to_dict(orient="records")}

class BalanceRequest(BaseModel):
    # Optionally allow overrides, but for now just trigger the function
    pass

@app.post("/run-balance")
def run_balance(req: BalanceRequest):
    # Load all data
    req_prod = load_csv("req_prod")
    capacity = load_csv("capacity")
    capacity.columns = [col.replace('.1', '') for col in capacity.columns]
    production = load_csv("production")
    inventory = load_csv("inventory")
    sales = load_csv("sales")
    dos = load_csv("dos")

    pullin_desired_order = ['PURE', 'DREAM', 'TOURING', 'GT', 'GT-P', 'SAPPHIRE']
    pushout_desired_order = ['SAPPHIRE', 'GT-P', 'GT', 'TOURING', 'DREAM', 'PURE']

    inventory = inventory.iloc[:, [0, 1, 2, 4]]
    capacity = capacity.iloc[:, 9:36]

    dd_Trim = ['SAPPHIRE', 'GT-P', 'GT', 'TOURING', 'DREAM', 'PURE']
    amt_Floor_DOS = 60
    amt_Ceiling_DOS = 100
    doh_floor_ceil_df1 = pd.DataFrame({
        'dd_Trim': dd_Trim,
        'amt_Floor_DOS': [amt_Floor_DOS] * len(dd_Trim),
        'amt_Ceiling_DOS': [amt_Ceiling_DOS] * len(dd_Trim)
    })

    # --- Paste your full ConstrainedPlan function here ---
    def ConstrainedPlan(req_prod, capacity, production, inventory, sales, dos,
                       pullin_desired_order, pushout_desired_order, doh_floor_ceil_df1):
        # ...existing code...
        return production, inventory, dos

    # Run the function
    production_out, inventory_out, dos_out = ConstrainedPlan(
        req_prod, capacity, production, inventory, sales, dos,
        pullin_desired_order, pushout_desired_order, doh_floor_ceil_df1
    )

    # Return as JSON
    return {
        "production": {
            "columns": production_out.columns.tolist(),
            "data": production_out.fillna("").to_dict(orient="records")
        },
        "inventory": {
            "columns": inventory_out.columns.tolist(),
            "data": inventory_out.fillna("").to_dict(orient="records")
        },
        "dos": {
            "columns": dos_out.columns.tolist(),
            "data": dos_out.fillna("").to_dict(orient="records")
        }
    }