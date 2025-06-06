import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import os
from main import PriceTracker  # Import your existing tracker

# Page configuration
st.set_page_config(
    page_title="G-Shock Price Tracker",
    page_icon="⌚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e1e5e9;
    }
    .price-alert {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.25rem;
        padding: 0.75rem;
        margin: 1rem 0;
    }
    .error-alert {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 0.25rem;
        padding: 0.75rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Title and description
st.title("🔍 G-Shock GA-2100-1A1 Price Tracker")
st.markdown("Real-time price monitoring across multiple e-commerce platforms")

# Sidebar controls
st.sidebar.header("⚙️ Controls")

# Manual refresh button
if st.sidebar.button("🔄 Refresh Prices Now", type="primary"):
    with st.spinner("Fetching latest prices..."):
        tracker = PriceTracker()
        try:
            current_prices = tracker.get_all_current_prices()
            if current_prices:
                tracker.save_price_data(current_prices)
                st.sidebar.success(f"✅ Updated {len(current_prices)} prices!")
                # Clear cache to force reload
                load_price_data.clear()
            else:
                st.sidebar.warning("⚠️ No prices could be retrieved")
        except Exception as e:
            st.sidebar.error(f"❌ Error: {str(e)}")
        finally:
            tracker.cleanup()

# Auto-refresh toggle
auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh (30 seconds)")

# Price threshold setting
threshold = st.sidebar.number_input(
    "💰 Price Alert Threshold (₹)",
    min_value=5000,
    max_value=15000,
    value=10000,
    step=100
)

# Display current threshold info
st.sidebar.markdown(f"🎯 **Current Target:** ₹{threshold:,}")


# Load historical data with proper error handling
@st.cache_data(ttl=30)  # Cache for 30 seconds
def load_price_data():
    try:
        # Check if file exists
        if not os.path.exists('price_history.csv'):
            return pd.DataFrame()

        # Read the CSV file
        df = pd.read_csv('price_history.csv')

        # Check if dataframe is empty
        if df.empty:
            return pd.DataFrame()

        # Check if required columns exist
        required_columns = ['timestamp', 'site', 'price']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            st.error(f"Missing columns in CSV: {missing_columns}")
            return pd.DataFrame()

        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Ensure price is numeric
        df['price'] = pd.to_numeric(df['price'], errors='coerce')

        # Remove rows with invalid prices
        df = df.dropna(subset=['price'])

        return df

    except Exception as e:
        st.error(f"Error loading price data: {str(e)}")
        return pd.DataFrame()


# Load the data
df = load_price_data()

# Main dashboard
if not df.empty:
    st.header("📊 Current Prices")

    # Get latest prices for each site
    try:
        latest_prices = df.groupby('site').last().reset_index()
        latest_prices = latest_prices.sort_values('price')

        # Display current prices in columns
        cols = st.columns(min(4, len(latest_prices)))
        for idx, row in latest_prices.iterrows():
            with cols[idx % len(cols)]:
                price_color = "🟢" if row['price'] <= threshold else "🔴"
                delta_text = f"vs ₹{threshold:,}" if row[
                                                         'price'] <= threshold else f"+₹{row['price'] - threshold:,.0f} over target"

                st.metric(
                    label=f"{price_color} {row['site']}",
                    value=f"₹{row['price']:,.0f}",
                    delta=delta_text
                )

        # Best deal highlight
        best_deal = latest_prices.iloc[0]
        worst_deal = latest_prices.iloc[-1]

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"""
            <div class="price-alert">
                <h4>🏆 Best Current Deal</h4>
                <p><strong>{best_deal['site']}</strong> - ₹{best_deal['price']:,.0f}</p>
                <p>{'🚨 Below your target!' if best_deal['price'] <= threshold else '⏳ Still above target'}</p>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            savings = worst_deal['price'] - best_deal['price']
            st.markdown(f"""
            <div class="metric-card">
                <h4>💰 Price Spread</h4>
                <p><strong>Highest:</strong> ₹{worst_deal['price']:,.0f} ({worst_deal['site']})</p>
                <p><strong>Potential Savings:</strong> ₹{savings:,.0f}</p>
            </div>
            """, unsafe_allow_html=True)

        # Price history chart
        st.header("📈 Price History")

        # Date range selector
        col1, col2 = st.columns(2)
        with col1:
            days_back = st.selectbox(
                "📅 View last:",
                options=[7, 14, 30, 90, 365, 0],
                format_func=lambda x: f"{x} days" if x > 0 else "All time",
                index=2  # Default to 30 days
            )

        # Filter data based on selection
        if days_back > 0:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            chart_df = df[df['timestamp'] >= cutoff_date]
        else:
            chart_df = df

        if not chart_df.empty:
            # Create interactive plot
            fig = px.line(
                chart_df,
                x='timestamp',
                y='price',
                color='site',
                title=f"Price Trends {'(Last ' + str(days_back) + ' days)' if days_back > 0 else '(All Time)'}",
                labels={'price': 'Price (₹)', 'timestamp': 'Date & Time'},
                hover_data={'price': ':,.0f'}
            )

            # Add threshold line
            fig.add_hline(
                y=threshold,
                line_dash="dash",
                line_color="red",
                annotation_text=f"Target: ₹{threshold:,}",
                annotation_position="bottom right"
            )

            # Customize layout
            fig.update_layout(
                height=500,
                hovermode='x unified',
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available for the selected time period.")

        # Summary statistics
        st.header("📋 Summary Statistics")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("💰 Price Analysis")
            st.write(f"**Lowest Ever:** ₹{df['price'].min():,.0f}")
            st.write(f"**Highest Ever:** ₹{df['price'].max():,.0f}")
            st.write(f"**Current Average:** ₹{latest_prices['price'].mean():,.0f}")

            # Show how many sites are below threshold
            below_threshold = len(latest_prices[latest_prices['price'] <= threshold])
            st.write(f"**Below Target:** {below_threshold}/{len(latest_prices)} sites")

        with col2:
            st.subheader("🏪 Site Performance")
            avg_by_site = df.groupby('site')['price'].mean().sort_values()
            st.write("**Best Average Prices:**")
            for site, price in avg_by_site.head(3).items():
                st.write(f"• {site}: ₹{price:,.0f}")

        with col3:
            st.subheader("📊 Tracking Stats")
            st.write(f"**Total Records:** {len(df):,}")
            st.write(f"**Sites Monitored:** {df['site'].nunique()}")
            days_tracked = (df['timestamp'].max() - df['timestamp'].min()).days + 1
            st.write(f"**Days Tracked:** {days_tracked}")
            st.write(f"**Last Updated:** {df['timestamp'].max().strftime('%Y-%m-%d %H:%M')}")

        # Alerts section
        st.header("🚨 Current Alerts")

        alert_sites = latest_prices[latest_prices['price'] <= threshold]
        if not alert_sites.empty:
            st.success(f"🎉 {len(alert_sites)} site(s) currently below your target price!")
            for _, site in alert_sites.iterrows():
                st.write(f"• **{site['site']}**: ₹{site['price']:,.0f} (Save ₹{threshold - site['price']:,.0f})")
        else:
            st.info("😔 No sites currently below your target price. Keep watching!")

        # Raw data table (expandable)
        with st.expander("🗂️ View Raw Data"):
            # Show most recent data first
            display_df = df.sort_values('timestamp', ascending=False)
            st.dataframe(display_df, use_container_width=True)

    except Exception as e:
        st.error(f"Error processing price data: {str(e)}")

else:
    # No data available - show getting started guide
    st.markdown("""
    <div class="error-alert">
        <h4>📝 No Price Data Found</h4>
        <p>It looks like you haven't collected any price data yet. Here's how to get started:</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    ### 🚀 Getting Started:

    1. **Click the "Refresh Prices Now" button** in the sidebar to fetch current prices
    2. **Run your main.py script** from the command line to start automated tracking
    3. **Set up a scheduled task** to run the script regularly (every few hours)

    ### 📁 Expected Files:
    - `price_history.csv` - This will be created automatically when you first run the tracker
    - `main.py` - Your price tracking script
    - `config.py` - Configuration settings

    ### 🔧 Quick Test:
    Try clicking the refresh button above to test if your tracker is working properly.
    """)

# Auto-refresh functionality
if auto_refresh:
    # Show countdown
    placeholder = st.empty()
    for i in range(30, 0, -1):
        placeholder.text(f"🔄 Auto-refreshing in {i} seconds...")
        time.sleep(1)
    placeholder.empty()
    st.rerun()

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("🤖 **Automated Price Tracker**")
with col2:
    st.markdown(f"🎯 **Target:** ₹{threshold:,}")
with col3:
    st.markdown(f"🕒 **Updated:** {datetime.now().strftime('%H:%M:%S')}")