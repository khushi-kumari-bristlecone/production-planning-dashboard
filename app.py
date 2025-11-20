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

def ConstrainedPlan(req_prod,capacity,production,inventory,sales,dos,pullin_desired_order, pushout_desired_order,doh_floor_ceil_df1):
    print('\n Constrained Plan pullin_desired_order ',pullin_desired_order,'and pushout_desired_order ', pushout_desired_order )
    req_prod = req_prod.drop(req_prod.columns[3:5], axis=1)
    month_list_invt = list(capacity.columns)
    capacity = capacity.drop(capacity.columns[:2], axis=1)
    production = production.drop(production.columns[3:5], axis=1)

    # Corrected index 4 to 3 for initial inventory preservation
    last_month_invt = inventory.iloc[:, [0, 1, 2, 3]]
    inventory = inventory.drop(inventory.columns[3:5], axis=1)
    # Keeping the original drop logic for consistency
    sales = sales.drop(sales.columns[3:5], axis=1)
    dos = dos.drop(dos.columns[3:5], axis=1)
    total_production = req_prod.sum(axis = 0, numeric_only = True)
    difference = capacity.subtract(total_production[capacity.columns])
    diff_dict = difference.to_dict()
    all_data = {key: value[0] for key, value in diff_dict.items()}
    all_keys = list(all_data.keys())

    def days_in_month(month_str):
        month_abbr, year = month_str.split()
        year = int(year)
        month_num = list(calendar.month_abbr).index(month_abbr)
        _, num_days = calendar.monthrange(year, month_num)
        return num_days

    def calculate_amt_of_invt(floor_doh, sales_forecast, days_per_month):
        remaining_days = floor_doh
        amt_of_invt = 0
        for sales_f, days in zip(sales_forecast, days_per_month):
            if remaining_days >= days:
                amt_of_invt += sales_f
                remaining_days -= days
            else:
                amt_of_invt += (remaining_days / days) * sales_f
                break
        return math.ceil(amt_of_invt)

    def calculate_days_of_supply(end_of_month_inventory, sales_forecast,days_per_month):
        remaining_inventory = end_of_month_inventory
        total_days_of_supply = 0
        sale_frcst = []
        for sale, days in zip(sales_forecast, days_per_month):
            if remaining_inventory >= sale and remaining_inventory!=0:
                total_days_of_supply += days
                remaining_inventory -= sale
                sale_frcst.append(sale)
            else:
                partial_days = round((remaining_inventory / sale) * days,2)
                total_days_of_supply += partial_days
                break
        if len(sale_frcst)== 2:
            if sale_frcst[0]+sale_frcst[1] == 0:
                total_days_of_supply = days_per_month[0] + days_per_month[1]
        if len(sale_frcst)> 2:
            if sale_frcst[1]+sale_frcst[2] == 0:
                total_days_of_supply = days_per_month[0] + days_per_month[1]
        return total_days_of_supply

    def update_inventory(sublist,car_model,model_year,prev_month):
        if sublist[0] == inventory.columns[3]:
            prev_month_invt = last_month_invt.loc[(last_month_invt['PRODUCT_TRIM'] == car_model) & (last_month_invt['MODEL_YEAR'] == model_year), prev_month]
        else:
            prev_month_invt = inventory.loc[(inventory['PRODUCT_TRIM'] == car_model) & (inventory['MODEL_YEAR'] == model_year), prev_month]
        i = 0
        for month in sublist:
            if i>=1:
                prev_month = sublist[i-1]
            if prev_month not in inventory.columns:
                prev_month_invt = last_month_invt.loc[(last_month_invt['PRODUCT_TRIM'] == car_model) & (last_month_invt['MODEL_YEAR'] == model_year), prev_month]
            else:
                prev_month_invt = inventory.loc[(inventory['PRODUCT_TRIM'] == car_model) & (inventory['MODEL_YEAR'] == model_year), prev_month]
            i+=1
            inventory.loc[(inventory['PRODUCT_TRIM'] == car_model) & (inventory['MODEL_YEAR'] == model_year), month] = \
                prev_month_invt + \
                production.loc[(production['PRODUCT_TRIM'] == car_model) & (production['MODEL_YEAR'] == model_year), month] - \
                sales.loc[(sales['PRODUCT_TRIM'] == car_model) & (sales['MODEL_YEAR'] == model_year), month]

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
        month_list = [f"{month} {year}" for month in months]
        return month_list

    def next_two_months(month_list):
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        last_entry = month_list[-1]
        last_month, last_year = last_entry.split()
        last_year = int(last_year)
        last_month_index = months.index(last_month)
        next_months = []
        for i in range(2):
            next_month_index = (last_month_index + 1 + i) % 12
            next_year = last_year + (last_month_index + 1 + i) // 12
            next_months.append(f"{months[next_month_index]} {next_year}")
        return next_months

    def find_common_elements_ordered(list1, list2):
        set_list2 = set(list2)
        common_elements = [item for item in list1 if item in set_list2]
        return common_elements

    def extract_years(month_year_list):
        years = set()
        for item in month_year_list:
            year = item.split()[1]
            years.add(year)
        return list(years)

    years_present = extract_years(all_keys)
    years_present = sorted(years_present)
    for year_num in years_present:
        yr_month_list = generate_month_list(year_num)
        actual_data_present = find_common_elements_ordered(yr_month_list, all_keys)
        actual_data_present_v0 = actual_data_present
        is_final_year = 0
        year_num = int(year_num)
        if year_num == int(years_present[-1]):
            is_final_year = 1
            if len(actual_data_present) >= 4:
                actual_data_present = actual_data_present[:-2]
            else:
                break

        data = {key: all_data[key] for key in actual_data_present if key in all_data}
        keys = list(data.keys())

        inv_next_two_month = next_two_months(actual_data_present)
        special_inv_month_key = actual_data_present+inv_next_two_month

        # 1st Surplus iteration (placeholder)
        for i, month in enumerate(keys):
            surplus = data[month]
            curr_month_num = i
            curr_month = keys[curr_month_num]
            if keys[i] == list(all_data.keys())[-1]:
                break
            if surplus>0:
                if ('Dec' in keys[curr_month_num]) :
                    break
                while surplus > 0:
                    break

        # 2nd Deficit iteration (placeholder core structure)
        for i, month in enumerate(keys):
            if i + 1 >= len(keys):
                break
            try:
                deficit = data[month]
                curr_month_num = i
                curr_month = keys[curr_month_num]
                if keys[i] == list(all_data.keys())[-1]:
                    break
                if curr_month == list(all_data.keys())[-1]:
                    break
                if deficit<0:
                    if ('Dec' in keys[curr_month_num]):
                        break
                    while deficit < 0:
                        if i + 1 >= len(keys):
                            break
                        if ('Dec' in keys[i]) :
                            break
                        next_month = keys[i + 1]
                        for car_model in pushout_desired_order:
                            model_rows = production[production["PRODUCT_TRIM"] == car_model].sort_values(by="MODEL_YEAR")
                            floor_doh = doh_floor_ceil_df1[doh_floor_ceil_df1["dd_Trim"] == car_model]["amt_Floor_DOS"].values[0]
                            ceil_doh = doh_floor_ceil_df1[doh_floor_ceil_df1["dd_Trim"] == car_model]["amt_Ceiling_DOS"].values[0]
                            for idx, row in model_rows.iterrows():
                                abs_deficit = abs(deficit)
                                # (logic omitted)
                                if deficit >= 0:
                                    break
                            if deficit >= 0:
                                break
                        if deficit < 0:
                            pass
                        i += 1
                        if i >= len(keys):
                            break
                        if 'Dec' in keys[i]:
                            break
            except:
                break

        # 3rd iteration scaffolding
        if is_final_year == 1:
            new_traversal_data = actual_data_present_v0
            new_traversal_data = new_traversal_data[:-2]
            data = {key: all_data[key] for key in new_traversal_data if key in all_data}
            keys = list(data.keys())
        else:
            year_num_ny = int(year_num) + 1
            yr_month_list_ny = generate_month_list(year_num_ny)
            actual_data_present_ny = find_common_elements_ordered(yr_month_list_ny, all_keys)
            year_num_ny_2 = int(year_num) + 2
            yr_month_list_ny_2 = generate_month_list(year_num_ny_2)
            actual_data_present_ny_2 = find_common_elements_ordered(yr_month_list_ny_2, all_keys)
            if year_num_ny == int(years_present[-1]):
                new_traversal_data = actual_data_present_v0 + actual_data_present_ny
                new_traversal_data = new_traversal_data[:-2]
            else:
                len_actual_data_present_ny_2 = len(actual_data_present_ny_2)
                if len_actual_data_present_ny_2 >1:
                    new_traversal_data = actual_data_present_v0 + actual_data_present_ny
                else:
                    new_traversal_data = actual_data_present_v0 + actual_data_present_ny
                    remove_month_num = 2 - len_actual_data_present_ny_2
                    new_traversal_data = actual_data_present_v0 + actual_data_present_ny[:-remove_month_num]

        if is_final_year == 0:
            year_num_ny = int(year_num) + 1
            yr_month_list_ny = generate_month_list(year_num_ny)
            actual_data_present_ny = find_common_elements_ordered(yr_month_list_ny, all_keys)
            ny_year_month = actual_data_present_ny[0]
            traversal_last_month = new_traversal_data[-1]
            special_inv_month_key_ny = new_traversal_data + next_two_months(new_traversal_data)
            data = {key: all_data[key] for key in new_traversal_data if key in all_data}
            keys = list(data.keys())
            for i, month in enumerate(keys):
                if i + 1 >= len(keys):
                    break
                surplus = data[month]
                curr_month_num = i
                curr_month = keys[curr_month_num]
                if keys[i] == list(all_data.keys())[-1]:
                    break
                if is_final_year == 0:
                    if (ny_year_month in keys[curr_month_num]) :
                        break
                if surplus>0:
                    if is_final_year == 0:
                        pass
                    while surplus > 0:
                        next_month = keys[i + 1]
                        adjustment_made = False
                        try:
                            pass
                        except:
                            pass

                        # NOTE: the variables referenced below (car_model, adjustable_invt_floor, etc)
                        # are placeholders from your original scaffold. Keep your domain logic here.
                        # This return keeps function consistent for now.
                        break

    return production, inventory, dos


####### UI CODE ###############################################################
import streamlit as st
import pandas as pd
from pathlib import Path
import numpy as np
import calendar
import math

# ---------------------------
# Load Input Data
# ---------------------------
BASE_DIR = Path(__file__).parent

# Load the Unconstrained Inventory Summary Excel file (before UI code)
unconstrained_inventory_path = BASE_DIR / 'Discovery_Unconstrained_Sales Inventory Summary_2025-11-20-11-37-09.xlsx'
try:
    unconstrained_inventory_df = pd.read_excel(unconstrained_inventory_path)
except Exception as e:
    unconstrained_inventory_df = pd.DataFrame()

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

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="Production Planning Dashboard", layout="wide")

# Initialize state for dataset_choice & click flag
if 'dataset_choice' not in st.session_state:
    st.session_state['dataset_choice'] = 'req_prod'
if 'has_clicked_dataset' not in st.session_state:
    st.session_state['has_clicked_dataset'] = False

dataset_choice = st.session_state.get('dataset_choice', 'req_prod')

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

# ---- Dynamic Title ----
if st.session_state['has_clicked_dataset']:
    st.title(f"📊 {st.session_state.get('dataset_choice', 'Production Planning Dashboard')}")
else:
    st.title("📊 Production Planning Dashboard")

# Filters below the title
col1, col2 = st.columns([1, 2])
with col1:
    filter_column = st.selectbox(
        "Filter column:",
        options=get_columns_for_choice(dataset_choice),
        key="top_filter_column"
    )
with col2:
    filter_value = st.text_input("Filter value (exact match):", "", key="top_filter_value")

# Run Balance Plan button at top
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

# ---------------------------
# Sidebar: Data Frames Viewer header + UNIFORM BUTTONS
# ---------------------------
st.sidebar.markdown("""
    <style>
    /* Sidebar background and padding */
    [data-testid="stSidebar"] {
        background-color: #23272f !important;
        padding: 1.5rem 1rem !important;
    }

    /* Sidebar header */
    .sidebar-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: #f3f6fa;
        margin-bottom: 1.2rem;
        letter-spacing: 0.5px;
    }

    /* Ensure each Streamlit button block in sidebar has uniform spacing */
    [data-testid="stSidebar"] .stButton {
        width: 100% !important;
        margin-bottom: 0.75rem !important; /* consistent vertical gap */
    }

    /* --- UNIFORM BUTTON STYLE (robust across Streamlit builds) --- */
    [data-testid="stSidebar"] .stButton > button,
    [data-testid="stSidebar"] [data-testid="baseButton-primary"],
    [data-testid="stSidebar"] [data-testid="baseButton-secondary"] {
        width: 100% !important;
        min-width: 180px !important;

        /* Force uniform height */
        height: 44px !important;
        padding: 8px 12px !important;

        /* Left alignment + single line */
        text-align: left !important;
        display: flex !important;
        align-items: center !important;
        justify-content: flex-start !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;

        /* Visuals */
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

    /* Hover */
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

# Dataset buttons (persist selection in session_state)
with st.sidebar:
    for name, key in [
        ("Required Production", "btn_req_prod"),
        ("Capacity", "btn_capacity"),
        ("Production", "btn_production"),
        ("Inventory", "btn_inventory"),
        ("Sales", "btn_sales"),
        ("DOS", "btn_dos"),
        ("Constraint Identification", "btn_constraint"),
        ("Unconstrained Inventory Summary", "btn_unconstrained_inventory"),
    ]:
        if st.button(name, key=key):
            st.session_state['dataset_choice'] = name
            st.session_state['has_clicked_dataset'] = True  # mark that a user clicked a dataset

# Read the current selection (again after possible click)
dataset_choice = st.session_state.get('dataset_choice', 'req_prod')

# Helper to filter and edit any DataFrame
from streamlit import column_config
def filter_and_edit(df, name):
    filtered_df = df
    if filter_value:
        if filter_column in df.columns:
            filtered_df = df[df[filter_column].astype(str) == filter_value]
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
elif dataset_choice == "Unconstrained Inventory Summary":
    st.subheader("📋 Unconstrained Inventory Summary")
    if not unconstrained_inventory_df.empty:
        st.data_editor(unconstrained_inventory_df, key="edit_unconstrained_inventory", num_rows="dynamic")
    else:
        st.info("No data available in Unconstrained Inventory Summary.")
        st.write("Debug: DataFrame is empty. Check file path, sheet, or file contents.")
        st.write(f"File path: {unconstrained_inventory_path}")
        try:
            test_df = pd.read_excel(unconstrained_inventory_path)
            st.write(f"Test read shape: {test_df.shape}")
        except Exception as e:
            st.write(f"Exception when reading Excel: {e}")

# After the table, show the results if the button was clicked
if run_balance_result is not None:
    production_out, inventory_out, dos_out = run_balance_result
    st.subheader("📦 Updated Production")
    st.data_editor(production_out, key="edit_production_out", num_rows="dynamic")

    st.subheader("🏭 Updated Inventory")
    st.data_editor(inventory_out, key="edit_inventory_out", num_rows="dynamic")

    st.subheader("📈 Updated DOS")
    st.data_editor(dos_out, key="edit_dos_out", num_rows="dynamic")

