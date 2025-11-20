import pandas as pd
import streamlit as st


def display_unconstrained_summary(df):
    """
    Display the unconstrained summary with collapsible regions.
    Each region is expandable/collapsible showing its delivery, production plan, and inventory data.
    """
    st.subheader("📊 Unconstrained Summary")

    if df.empty:
        st.warning("No unconstrained summary data available.")
        return

    # Check if Region column exists
    if 'Region' not in df.columns:
        st.error("Region column not found in data.")
        st.dataframe(df, use_container_width=True, hide_index=True)
        return

    # Initialize session state for expanded regions (default: all expanded)
    if 'expanded_regions' not in st.session_state:
        st.session_state.expanded_regions = set(df['Region'].dropna().unique())

    # Get unique regions
    regions = df['Region'].dropna().unique()

    # Display each region with collapsible sections
    for region in sorted(regions):
        region_data = df[df['Region'] == region].copy()

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
