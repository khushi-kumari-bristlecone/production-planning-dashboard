import pandas as pd
import streamlit as st


def display_unconstrained_summary(df):
    """
    Display the unconstrained summary with collapsible regions.
    Each region is expandable/collapsible showing its delivery, production plan, and inventory data.
    """
    if df.empty:
        st.warning("No unconstrained summary data available. Please ensure the Excel file is uploaded to the repository.")
        return

    # Check if Region column exists
    if 'Region' not in df.columns:
        st.error("Region column not found in data. The data structure may be incorrect.")
        st.info("Expected columns should include 'Region' and monthly data columns.")
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
        return

    # Add filters at the top
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        regions_list = sorted(df['Region'].dropna().unique().tolist())
        selected_regions = st.multiselect("Product Region", regions_list, default=[], key="uc_filter_region")

    with col2:
        st.multiselect("Model", ["Air"], default=[], key="uc_filter_model")

    with col3:
        st.multiselect("Product Country", ["USA", "Canada", "Germany", "UK"], default=[], key="uc_filter_country")

    with col4:
        st.multiselect("Build Type", ["Standard", "Custom", "Pre-Production"], default=[], key="uc_filter_build")

    with col5:
        st.multiselect("Model Year", ["2024", "2025", "2026"], default=[], key="uc_filter_year")

    # Apply region filter if selected
    filtered_df = df.copy()
    if selected_regions and len(selected_regions) > 0:
        filtered_df = filtered_df[filtered_df['Region'].isin(selected_regions)]

    # Initialize session state for expanded regions (default: all expanded)
    if 'expanded_regions' not in st.session_state:
        st.session_state.expanded_regions = set(filtered_df['Region'].dropna().unique())

    # Get unique regions
    regions = filtered_df['Region'].dropna().unique()

    # Display each region with collapsible sections
    for region in sorted(regions):
        region_data = filtered_df[filtered_df['Region'] == region].copy()

        # Check if region is expanded
        is_expanded = region in st.session_state.expanded_regions

        # Create region header with toggle button
        cols = st.columns([0.05, 0.95])

        with cols[0]:
            if st.button("▼" if is_expanded else "▶", key=f"toggle_{region}", help=f"Expand/Collapse {region}"):
                if is_expanded:
                    st.session_state.expanded_regions.discard(region)
                else:
                    st.session_state.expanded_regions.add(region)
                st.rerun()

        with cols[1]:
            st.markdown(f"**{region}**")

        # Show region data if expanded
        if is_expanded:
            # Remove the Region column from display and show only Type + month columns
            display_data = region_data.drop('Region', axis=1).copy()

            # Display the data table for this region
            st.dataframe(
                display_data,
                use_container_width=True,
                hide_index=True,
                height=min(len(display_data) * 35 + 38, 300)
            )

        # Add separator between regions
        st.markdown("---")
