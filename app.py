import streamlit as st
import pandas as pd
from pathlib import Path
import numpy as np
import calendar
import math

# -----------------------------
# Load Input Data
# -----------------------------
BASE_DIR = Path(__file__).parent

req_prod = pd.read_csv(BASE_DIR / 'req_prod.csv')
capacity = pd.read_csv(BASE_DIR / 'capacity.csv')
capacity.columns = [col.replace('.1', '') for col in capacity.columns]
production = pd.read_csv(BASE_DIR / 'production.csv')
inventory = pd.read_csv(BASE_DIR / 'inventory.csv')
sales = pd.read_csv(BASE_DIR / 'sales.csv')
dos = pd.read_csv(BASE_DIR / 'dos.csv')

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

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Production Planning Dashboard", layout="wide")
st.title("📊 Production Planning Dashboard")

# Move Run Balance Plan button to the top
run_balance_clicked = st.button("⚖️ Run Balance Plan", key="run_balance_top")
run_balance_result = None
if run_balance_clicked:
    with st.spinner("Running Constrained Plan..."):
        production_out, inventory_out, dos_out = ConstrainedPlan(
            req_prod, capacity, production, inventory, sales, dos,
            pullin_desired_order, pushout_desired_order, doh_floor_ceil_df1
        )
    st.success("✅ Constrained Plan executed successfully!")
    run_balance_result = (production_out, inventory_out, dos_out)

st.sidebar.header("⚙️ Data Frames Viewer")
dataset_choice = st.sidebar.selectbox(
    "Select a dataset to view:",
    ["req_prod", "capacity", "production", "inventory", "sales", "dos"]
)

# Add filter controls
def get_columns_for_choice(choice):
    if choice == "req_prod":
        return req_prod.columns.tolist()
    elif choice == "capacity":
        return capacity.columns.tolist()
    elif choice == "production":
        return production.columns.tolist()
    elif choice == "inventory":
        return inventory.columns.tolist()
    elif choice == "sales":
        return sales.columns.tolist()
    elif choice == "dos":
        return dos.columns.tolist()
    else:
        return []

filter_column = st.sidebar.selectbox(
    "Filter column:",
    options=get_columns_for_choice(dataset_choice)
)
filter_value = st.sidebar.text_input("Filter value (exact match):", "")

# Helper to filter and edit any DataFrame
from streamlit import column_config

def filter_and_edit(df, name):
    filtered_df = df
    if filter_value:
        if filter_column in df.columns:
            filtered_df = df[df[filter_column].astype(str) == filter_value]
    # All columns editable by default
    edited_df = st.data_editor(
        filtered_df,
        key=f"edit_{name}",
        num_rows="dynamic",
        column_config={col: column_config.Column() for col in filtered_df.columns}
    )
    return edited_df

# Show and edit the selected dataset
if dataset_choice == "req_prod":
    req_prod = filter_and_edit(req_prod, "req_prod")
elif dataset_choice == "capacity":
    capacity = filter_and_edit(capacity, "capacity")
elif dataset_choice == "production":
    production = filter_and_edit(production, "production")
elif dataset_choice == "inventory":
    inventory = filter_and_edit(inventory, "inventory")
elif dataset_choice == "sales":
    sales = filter_and_edit(sales, "sales")
elif dataset_choice == "dos":
    dos = filter_and_edit(dos, "dos")

# After the table, show the results if the button was clicked
if run_balance_result is not None:
    production_out, inventory_out, dos_out = run_balance_result
    st.subheader("📦 Updated Production")
    st.data_editor(production_out, key="edit_production_out", num_rows="dynamic")

    st.subheader("🏭 Updated Inventory")
    st.data_editor(inventory_out, key="edit_inventory_out", num_rows="dynamic")

    st.subheader("📈 Updated DOS")
    st.data_editor(dos_out, key="edit_dos_out", num_rows="dynamic")