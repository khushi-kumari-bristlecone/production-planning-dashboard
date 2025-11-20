import pandas as pd
import streamlit as st

def calculate_constraint_identification(req_prod, capacity):
    """
    Calculate constraint identification by comparing projected production plan with available build slots.

    Args:
        req_prod: DataFrame with required production data
        capacity: DataFrame with capacity data

    Returns:
        DataFrame with constraint identification including difference slots and color coding
    """
    # Get month columns (excluding first 3 columns which are PRODUCT_TRIM, MODEL_YEAR, PRODUCT_ID)
    month_columns = [col for col in req_prod.columns if col not in ['PRODUCT_TRIM', 'MODEL_YEAR', 'PRODUCT_ID']]

    # Calculate total projected production by month
    projected_production = req_prod[month_columns].sum(axis=0)

    # Get available build slots from capacity (assuming single row)
    available_slots = capacity.iloc[0] if len(capacity) > 0 else pd.Series()

    # Create constraint identification dataframe
    constraint_data = []

    for month in month_columns:
        # Parse month and year
        month_parts = month.split()
        if len(month_parts) == 2:
            month_no = month_parts[0]
            year_no = month_parts[1]

            # Get values
            projected = projected_production.get(month, 0)
            available = available_slots.get(month, 0)
            difference = available - projected

            constraint_data.append({
                'MODEL': 'AIR',  # Based on the screenshot
                'MONTH_NO': month_no,
                'YEAR_NO': year_no,
                'PROJECTED_PRODUCTION_PLAN': int(projected),
                'AVAILABLE_BUILD_SLOT': int(available),
                'DIFFERENCE_SLOT': int(difference)
            })

    constraint_df = pd.DataFrame(constraint_data)
    return constraint_df


def apply_color_coding(val):
    """
    Apply color coding based on difference slot value:
    - Green: Perfectly balanced (0)
    - Yellow: Surplus (positive)
    - Red: Deficit (negative)
    """
    if val == 0:
        return 'background-color: #4CAF50; color: white;'  # Green
    elif val > 0:
        return 'background-color: #FFC107; color: black;'  # Yellow
    else:
        return 'background-color: #F44336; color: white;'  # Red


def display_constraint_identification(constraint_df):
    """
    Display the constraint identification table with color coding and formatting.
    """
    # Add refresh button
    if st.button("🔄 Refresh Constraint Identification", key="refresh_constraint"):
        st.rerun()

    # Use session state to store editable data
    if 'constraint_data' not in st.session_state:
        st.session_state.constraint_data = constraint_df.copy()

    # Calculate differences for KPI display
    temp_diff = st.session_state.constraint_data['AVAILABLE_BUILD_SLOT'] - st.session_state.constraint_data['PROJECTED_PRODUCTION_PLAN']

    # Display summary statistics (KPI tiles) FIRST
    col1, col2, col3 = st.columns(3)

    with col1:
        deficit_count = len(temp_diff[temp_diff < 0])
        st.metric("Deficit Months", deficit_count, delta=None, delta_color="inverse")

    with col2:
        surplus_count = len(temp_diff[temp_diff > 0])
        st.metric("Surplus Months", surplus_count)

    with col3:
        balanced_count = len(temp_diff[temp_diff == 0])
        st.metric("Balanced Months", balanced_count, delta_color="off")

    # Create two columns for side-by-side display
    col_edit, col_diff = st.columns([3, 1])

    with col_edit:
        # Editable table without DIFFERENCE_SLOT
        edit_df = st.session_state.constraint_data[['MODEL', 'MONTH_NO', 'YEAR_NO', 'PROJECTED_PRODUCTION_PLAN', 'AVAILABLE_BUILD_SLOT']].copy()

        edited_df = st.data_editor(
            edit_df,
            use_container_width=True,
            hide_index=True,
            height=600,
            key="constraint_editor",
            column_config={
                "MODEL": st.column_config.TextColumn("MODEL", disabled=True, width="small"),
                "MONTH_NO": st.column_config.TextColumn("MONTH_NO", disabled=True, width="small"),
                "YEAR_NO": st.column_config.TextColumn("YEAR_NO", disabled=True, width="small"),
                "PROJECTED_PRODUCTION_PLAN": st.column_config.NumberColumn(
                    "PROJECTED_PRODUCTION_PLAN",
                    help="Edit to adjust projected production",
                    min_value=0,
                    step=1,
                    format="%d"
                ),
                "AVAILABLE_BUILD_SLOT": st.column_config.NumberColumn(
                    "AVAILABLE_BUILD_SLOT",
                    help="Edit to adjust available capacity",
                    min_value=0,
                    step=1,
                    format="%d"
                )
            },
            disabled=["MODEL", "MONTH_NO", "YEAR_NO"]
        )

        # Update session state
        st.session_state.constraint_data[['MODEL', 'MONTH_NO', 'YEAR_NO', 'PROJECTED_PRODUCTION_PLAN', 'AVAILABLE_BUILD_SLOT']] = edited_df

    with col_diff:
        # Calculate differences in real-time
        diff_df = pd.DataFrame({
            'DIFFERENCE_SLOT': edited_df['AVAILABLE_BUILD_SLOT'] - edited_df['PROJECTED_PRODUCTION_PLAN']
        })

        # Apply color styling
        def style_difference(val):
            if val == 0:
                return 'background-color: #4CAF50; color: white; font-weight: bold;'
            elif val > 0:
                return 'background-color: #FFC107; color: black; font-weight: bold;'
            else:
                return 'background-color: #F44336; color: white; font-weight: bold;'

        styled_diff = diff_df.style.applymap(style_difference, subset=['DIFFERENCE_SLOT'])

        st.dataframe(
            styled_diff,
            use_container_width=True,
            hide_index=True,
            height=600
        )

    # Update the full dataframe with calculated differences
    st.session_state.constraint_data['DIFFERENCE_SLOT'] = diff_df['DIFFERENCE_SLOT']

    # Display legend below the table
    st.markdown("""
    **Note:**
    - <span style='color: #FFC107;'>**Surplus - YELLOW**</span>
    - <span style='color: #F44336;'>**Deficit - RED**</span>
    - <span style='color: #4CAF50;'>**Perfectly Balanced - GREEN**</span>
    """, unsafe_allow_html=True)

    return st.session_state.constraint_data
