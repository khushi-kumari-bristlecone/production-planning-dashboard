import json
# from loguru import logger
# from aera import session
from datetime import datetime
import warnings
import pandas as pd
import math
import calendar
import requests
from dateutil.relativedelta import relativedelta
warnings.filterwarnings("ignore")


# ======================================================================
#  ConstrainedPlan — preserved (scaffold/logic as in your file)
# ======================================================================
def ConstrainedPlan(req_prod, capacity, production, inventory, sales, dos,
                    pullin_desired_order, pushout_desired_order, doh_floor_ceil_df1):
    print('\n Constrained Plan pullin_desired_order ', pullin_desired_order,
          'and pushout_desired_order ', pushout_desired_order)

    # Drops / setup
    req_prod = req_prod.drop(req_prod.columns[3:5], axis=1)
    month_list_invt = list(capacity.columns)
    capacity = capacity.drop(capacity.columns[:2], axis=1)
    production = production.drop(production.columns[3:5], axis=1)

    # Preserve initial inventory month
    last_month_invt = inventory.iloc[:, [0, 1, 2, 3]]
    inventory = inventory.drop(inventory.columns[3:5], axis=1)
    sales = sales.drop(sales.columns[3:5], axis=1)
    dos = dos.drop(dos.columns[3:5], axis=1)

    # Surplus/deficit base calc
    total_production = req_prod.sum(axis=0, numeric_only=True)
    difference = capacity.subtract(total_production[capacity.columns])
    diff_dict = difference.to_dict()
    all_data = {key: value[0] for key, value in diff_dict.items()}
    all_keys = list(all_data.keys())

    # ---------------- helpers (preserved) ----------------
    def days_in_month(month_str):
        month_abbr, year = month_str.split()
        year = int(year)
        month_num = list(calendar.month_abbr).index(month_abbr)
        _, num_days = calendar.monthrange(year, month_num)
        return num_days

    def calculate_amt_of_invt(floor_doh, sales_forecast, days_per_month):
        remaining_days = floor_doh
        amt_of_invt = 0
        for sale_val, days in zip(sales_forecast, days_per_month):
            if remaining_days >= days:
                amt_of_invt += sale_val
                remaining_days -= days
            else:
                amt_of_invt += (remaining_days / days) * sale_val
                break
        return math.ceil(amt_of_invt)

    def calculate_days_of_supply(end_of_month_inventory, sales_forecast, days_per_month):
        remaining_inventory = end_of_month_inventory
        total_days_of_supply = 0
        sale_frcst = []
        for sale_val, days in zip(sales_forecast, days_per_month):
            if remaining_inventory >= sale_val and remaining_inventory != 0:
                total_days_of_supply += days
                remaining_inventory -= sale_val
                sale_frcst.append(sale_val)
            else:
                partial_days = round((remaining_inventory / sale_val) * days, 2) if sale_val != 0 else 0
                total_days_of_supply += partial_days
                break
        # handle consecutive zeros (your original rules)
        if len(sale_frcst) == 2 and (sale_frcst[0] + sale_frcst[1] == 0):
            total_days_of_supply = days_per_month[0] + days_per_month[1]
        if len(sale_frcst) > 2 and (sale_frcst[1] + sale_frcst[2] == 0):
            total_days_of_supply = days_per_month[0] + days_per_month[1]
        return total_days_of_supply

    def update_inventory(sublist, car_model, model_year, prev_month):
        if sublist[0] == inventory.columns[3]:
            prev_month_invt = last_month_invt.loc[
                (last_month_invt['PRODUCT_TRIM'] == car_model) & (last_month_invt['MODEL_YEAR'] == model_year),
                prev_month
            ]
        else:
            prev_month_invt = inventory.loc[
                (inventory['PRODUCT_TRIM'] == car_model) & (inventory['MODEL_YEAR'] == model_year),
                prev_month
            ]
        i = 0
        for month in sublist:
            if i >= 1:
                prev_month = sublist[i - 1]
            if prev_month not in inventory.columns:
                prev_month_invt = last_month_invt.loc[
                    (last_month_invt['PRODUCT_TRIM'] == car_model) & (last_month_invt['MODEL_YEAR'] == model_year),
                    prev_month
                ]
            else:
                prev_month_invt = inventory.loc[
                    (inventory['PRODUCT_TRIM'] == car_model) & (inventory['MODEL_YEAR'] == model_year),
                    prev_month
                ]
            i += 1
            inventory.loc[
                (inventory['PRODUCT_TRIM'] == car_model) & (inventory['MODEL_YEAR'] == model_year), month
            ] = (
                prev_month_invt
                + production.loc[
                    (production['PRODUCT_TRIM'] == car_model) & (production['MODEL_YEAR'] == model_year), month
                ]
                - sales.loc[
                    (sales['PRODUCT_TRIM'] == car_model) & (sales['MODEL_YEAR'] == model_year), month
                ]
            )

    def update_value_pull(pull_value, car_model, add_month, sub_month, model_year):
        def update_data(df, model_col, year_col):
            if pull_value > 0:
                df.loc[(df[model_col] == car_model) & (df[year_col] == model_year), add_month] += pull_value
                df.loc[(df[model_col] == car_model) & (df[year_col] == model_year), sub_month] -= pull_value
        update_data(production, "PRODUCT_TRIM", "MODEL_YEAR")

    def update_value_push(push_value, car_model, add_month, sub_month, model_year):
        def update_data(df, model_col, year_col):
            if push_value > 0:
                df.loc[(df[model_col] == car_model) & (df[year_col] == model_year), add_month] += push_value
                df.loc[(df[model_col] == car_model) & (df[year_col] == model_year), sub_month] -= push_value
        update_data(production, "PRODUCT_TRIM", "MODEL_YEAR")

    def generate_month_list(year):
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return [f"{m} {year}" for m in months]

    def next_two_months(month_list):
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        last_entry = month_list[-1]
        last_month, last_year = last_entry.split()
        last_year = int(last_year)
        last_month_index = months.index(last_month)
        nxt = []
        for i in range(2):
            idx = (last_month_index + 1 + i) % 12
            ny = last_year + (last_month_index + 1 + i) // 12
            nxt.append(f"{months[idx]} {ny}")
        return nxt

    def find_common_elements_ordered(list1, list2):
        set2 = set(list2)
        return [x for x in list1 if x in set2]

    def extract_years(month_year_list):
        years = set()
        for item in month_year_list:
            years.add(item.split()[1])
        return list(years)

    years_present = sorted(extract_years(all_keys))
    for year_num in years_present:
        yr_month_list = generate_month_list(year_num)
        actual_data_present = find_common_elements_ordered(yr_month_list, all_keys)
        actual_data_present_v0 = actual_data_present[:]
        is_final_year = 0
        ynum = int(year_num)

        if ynum == int(years_present[-1]):
            is_final_year = 1
            if len(actual_data_present) >= 4:
                actual_data_present = actual_data_present[:-2]
            else:
                break

        data = {key: all_data[key] for key in actual_data_present if key in all_data}
        keys = list(data.keys())

        # Allow referencing next months for inventory checks
        inv_next_two = next_two_months(actual_data_present)
        special_inv_month_key = actual_data_present + inv_next_two

        # ----------------------------- 1) Surplus sweep (scaffold retained) -----------------------------
        for i, month in enumerate(keys):
            surplus = data[month]
            if keys[i] == list(all_data.keys())[-1]:
                break
            if surplus > 0:
                if 'Dec' in keys[i]:
                    break
                while surplus > 0:
                    break  # TODO: your surplus resolve logic

        # ----------------------------- 2) Deficit/Conflict sweep (scaffold retained) -----------------------------
        for i, month in enumerate(keys):
            if i + 1 >= len(keys):
                break
            try:
                deficit = data[month]
                if keys[i] == list(all_data.keys())[-1]:
                    break
                if deficit < 0:
                    if 'Dec' in keys[i]:
                        break
                    while deficit < 0:
                        if i + 1 >= len(keys):
                            break
                        if 'Dec' in keys[i]:
                            break
                        next_month = keys[i + 1]
                        for car_model in pushout_desired_order:
                            model_rows = production[production["PRODUCT_TRIM"] == car_model].sort_values(by="MODEL_YEAR")
                            floor_doh = doh_floor_ceil_df1[doh_floor_ceil_df1["dd_Trim"] == car_model]["amt_Floor_DOS"].values[0]
                            ceil_doh = doh_floor_ceil_df1[doh_floor_ceil_df1["dd_Trim"] == car_model]["amt_Ceiling_DOS"].values[0]
                            for idx, row in model_rows.iterrows():
                                abs_deficit = abs(deficit)
                                # your placeholder calculations
                                total_days_of_supply_ith = 0
                                total_days_of_supply = 0
                                if (total_days_of_supply_ith < floor_doh) or (total_days_of_supply_ith > ceil_doh) or \
                                   (total_days_of_supply < floor_doh) or (total_days_of_supply > ceil_doh):
                                    pass
                                if deficit >= 0:
                                    break
                            if deficit >= 0:
                                break
                        # move to next month, boundary checks retained
                        i += 1
                        if i >= len(keys):
                            break
                        if 'Dec' in keys[i]:
                            break
            except Exception:
                break

        # ----------------------------- 3) Final sweep (scaffold retained) -----------------------------
        if is_final_year == 1:
            new_traversal_data = actual_data_present_v0[:-2]
            data = {key: all_data[key] for key in new_traversal_data if key in all_data}
            keys = list(data.keys())
        else:
            year_num_ny = ynum + 1
            yr_month_list_ny = generate_month_list(year_num_ny)
            actual_data_present_ny = find_common_elements_ordered(yr_month_list_ny, all_keys)

            year_num_ny_2 = ynum + 2
            yr_month_list_ny_2 = generate_month_list(year_num_ny_2)
            actual_data_present_ny_2 = find_common_elements_ordered(yr_month_list_ny_2, all_keys)

            if year_num_ny == int(years_present[-1]):
                new_traversal_data = (actual_data_present_v0 + actual_data_present_ny)[:-2]
            else:
                if len(actual_data_present_ny_2) > 1:
                    new_traversal_data = actual_data_present_v0 + actual_data_present_ny
                else:
                    remove_month_num = 2 - len(actual_data_present_ny_2)
                    new_traversal_data = actual_data_present_v0 + actual_data_present_ny[:-remove_month_num]

            if len(new_traversal_data) > 0:
                ny_year_month = (find_common_elements_ordered(generate_month_list(year_num_ny), all_keys) or [""])[0]
                special_inv_month_key_ny = new_traversal_data + next_two_months(new_traversal_data)
                data = {key: all_data[key] for key in new_traversal_data if key in all_data}
                keys = list(data.keys())
                for i, month in enumerate(keys):
                    if i + 1 >= len(keys):
                        break
                    surplus = data[month]
                    if keys[i] == list(all_data.keys())[-1]:
                        break
                    if (ny_year_month in keys[i]) and (is_final_year == 0):
                        break
                    if surplus > 0:
                        while surplus > 0:
                            # placeholder for your final sweep logic
                            break

    # return full frames (unchanged)
    return production, inventory, dos


# ======================================================================
#                          UI CODE (updated)
# ======================================================================
import streamlit as st
from pathlib import Path
import numpy as np

# 1) Page setup + state
st.set_page_config(page_title="Production Planning Dashboard", layout="wide")

if 'dataset_choice' not in st.session_state:
    st.session_state['dataset_choice'] = 'req_prod'  # internal key
if 'has_clicked_dataset' not in st.session_state:
    st.session_state['has_clicked_dataset'] = False

BASE_DIR = Path(__file__).parent

# 2) Cached loaders to remove lag
@st.cache_data(show_spinner=False)
def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)

@st.cache_data(show_spinner=False)
def load_excel(path: Path) -> pd.DataFrame:
    try:
        return pd.read_excel(path, engine="openpyxl")
    except Exception:
        return pd.read_excel(path)

# 3) Load data (cached)
req_prod = load_csv(BASE_DIR / 'req_prod.csv')
capacity = load_csv(BASE_DIR / 'capacity.csv')
production = load_csv(BASE_DIR / 'production.csv')
inventory = load_csv(BASE_DIR / 'inventory.csv')
sales = load_csv(BASE_DIR / 'sales.csv')
dos = load_csv(BASE_DIR / 'dos.csv')

# keep your transforms
capacity.columns = [col.replace('.1', '') for col in capacity.columns]
inventory = inventory.iloc[:, [0, 1, 2, 4]]
capacity = capacity.iloc[:, 9:36]

# optional Excel summary (cached)
unconstrained_inventory_path = BASE_DIR / 'Discovery_Unconstrained_Sales Inventory Summary_2025-11-20-11-37-09.xlsx'
try:
    unconstrained_inventory_df = load_excel(unconstrained_inventory_path)
except Exception:
    unconstrained_inventory_df = pd.DataFrame()

# domain constants
pullin_desired_order = ['PURE', 'DREAM', 'TOURING', 'GT', 'GT-P', 'SAPPHIRE']
pushout_desired_order = ['SAPPHIRE', 'GT-P', 'GT', 'TOURING', 'DREAM', 'PURE']
dd_Trim = ['SAPPHIRE', 'GT-P', 'GT', 'TOURING', 'DREAM', 'PURE']
amt_Floor_DOS = 60
amt_Ceiling_DOS = 100
doh_floor_ceil_df1 = pd.DataFrame({
    'dd_Trim': dd_Trim,
    'amt_Floor_DOS': [amt_Floor_DOS] * len(dd_Trim),
    'amt_Ceiling_DOS': [amt_Ceiling_DOS] * len(dd_Trim)
})

# ---------------------------
# Label ↔ key mapping (FIX for your screenshot)
# ---------------------------
# Internal keys (use these throughout the logic)
DATASETS = [
    ("Required Production", "req_prod"),
    ("Capacity", "capacity"),
    ("Production", "production"),
    ("Inventory", "inventory"),
    ("Sales", "sales"),
    ("DOS", "dos"),
    ("Constraint Identification", "constraint"),
    ("Unconstrained Inventory Summary", "unconstrained_inventory"),
]

# Pretty display names for the title
DISPLAY_NAMES = {
    "req_prod": "Required Production",
    "capacity": "Capacity",
    "production": "Production",
    "inventory": "Inventory",
    "sales": "Sales",
    "dos": "DOS",
    "constraint": "Constraint Identification",
    "unconstrained_inventory": "Unconstrained Inventory Summary",
}

# 4) Sidebar first: robust CSS + buttons (so state updates precede rendering)
st.sidebar.markdown("""
    <style>
    [data-testid="stSidebar"] {
        background-color: #23272f !important;
        padding: 1.5rem 1rem !important;
    }
    .sidebar-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: #f3f6fa;
        margin-bottom: 1.2rem;
        letter-spacing: 0.5px;
    }
    [data-testid="stSidebar"] .stButton {
        width: 100% !important;
        margin-bottom: 0.75rem !important;
    }
    [data-testid="stSidebar"] .stButton > button,
    [data-testid="stSidebar"] [data-testid="baseButton-primary"],
    [data-testid="stSidebar"] [data-testid="baseButton-secondary"] {
        width: 100% !important;
        min-width: 180px !important;
        height: 44px !important;
        padding: 8px 12px !important;

        text-align: left !important;
        display: flex !important;
        align-items: center !important;
        justify-content: flex-start !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;

        background: linear-gradient(90deg, #3a3f4b 0%, #23272f 100%) !important;
        color: #f3f6fa !important;
        border: 1.5px solid #6c6f7a !important;
        border-radius: 10px !important;
        font-size: 1.08rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.2px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.10) !important;
        transition: background 0.2s, color 0.2s, border 0.2s, box-shadow 0.2s !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover,
    [data-testid="stSidebar"] [data-testid="baseButton-primary"]:hover,
    [data-testid="stSidebar"] [data-testid="baseButton-secondary"]:hover {
        background: #444857 !important;
        color: #ffe082 !important;
        border: 1.5px solid #ffe082 !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.12) !important;
    }
    </style>
""", unsafe_allow_html=True)

st.sidebar.markdown('<div class="sidebar-title">⚙️ Data Frames Viewer</div>', unsafe_allow_html=True)

with st.sidebar:
    for label, key in DATASETS:
        # Use internal key in session_state; label is just the button text
        if st.button(label, key=f"btn_{key}"):
            st.session_state['dataset_choice'] = key
            st.session_state['has_clicked_dataset'] = True

# current internal key after click
dataset_choice = st.session_state['dataset_choice']

# 5) Dynamic title (first load vs after click)
if st.session_state['has_clicked_dataset']:
    st.title(f"📊 {DISPLAY_NAMES.get(dataset_choice, dataset_choice)}")
else:
    st.title("📊 Production Planning Dashboard")

# 6) Top controls (filter options driven by internal key)
def get_columns_for_choice(choice_key: str):
    if choice_key == "req_prod":
        return req_prod.columns.tolist()
    elif choice_key == "capacity":
        return capacity.columns.tolist()
    elif choice_key == "production":
        return production.columns.tolist()
    elif choice_key == "inventory":
        return inventory.columns.tolist()
    elif choice_key == "sales":
        return sales.columns.tolist()
    elif choice_key == "dos":
        return dos.columns.tolist()
    elif choice_key == "unconstrained_inventory":
        return unconstrained_inventory_df.columns.tolist()
    else:
        return []

col1, col2 = st.columns([1, 2])
with col1:
    filter_column = st.selectbox(
        "Filter column:",
        options=get_columns_for_choice(dataset_choice),
        key="top_filter_column"
    )
with col2:
    filter_value = st.text_input("Filter value (exact match):", "", key="top_filter_value")

# Run Balance Plan at top (unchanged behavior)
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

# 7) Helper to filter & edit
from streamlit import column_config
def filter_and_edit(df: pd.DataFrame, name: str) -> pd.DataFrame:
    filtered_df = df
    if filter_value and (filter_column in df.columns):
        filtered_df = df[df[filter_column].astype(str) == filter_value]
    return st.data_editor(
        filtered_df,
        key=f"edit_{name}",
        num_rows="dynamic",
        column_config={col: column_config.Column() for col in filtered_df.columns}
    )

# 8) Render the selected dataset (internal keys drive the branches)
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

elif dataset_choice == "constraint":
    st.subheader("📋 Constraint Identification")
    st.info("This view is under development.")

elif dataset_choice == "unconstrained_inventory":
    st.subheader("📋 Unconstrained Inventory Summary")
    if not unconstrained_inventory_df.empty:
        st.data_editor(unconstrained_inventory_df, key="edit_unconstrained_inventory", num_rows="dynamic")
    else:
        st.warning("No data available in Unconstrained Inventory Summary.")
        st.write("Debug: DataFrame is empty. Check file path, sheet, or file contents.")
        st.write(f"File path: {unconstrained_inventory_path}")
        try:
            test_df = load_excel(unconstrained_inventory_path)
            st.write(f"Test read shape: {test_df.shape}")
        except Exception as e:
            st.write(f"Exception when reading Excel: {e}")

# 9) Results after plan run (unchanged)
if run_balance_result is not None:
    production_out, inventory_out, dos_out = run_balance_result
    st.subheader("📦 Updated Production")
    st.data_editor(production_out, key="edit_production_out", num_rows="dynamic")

    st.subheader("🏭 Updated Inventory")
    st.data_editor(inventory_out, key="edit_inventory_out", num_rows="dynamic")

    st.subheader("📈 Updated DOS")
    st.data_editor(dos_out, key="edit_dos_out", num_rows="dynamic")
