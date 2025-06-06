import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
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
            tracker.save_price_data(current_prices)
            st.sidebar.success("✅ Prices updated!")
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


# Load historical data
@st.cache_data(ttl=30)  # Cache for 30 seconds
def load_price_data():
    try:
        df = pd.read_csv('price_history.csv')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except FileNotFoundError:
        return pd.DataFrame()


# Main dashboard
if not load_price_data().empty:
    df = load_price_data()

    # Current prices section
    st.header("📊 Current Prices")

    # Get latest prices for each site
    latest_prices = df.groupby('site').last().reset_index()
    latest_prices = latest_prices.sort_values('price')

    # Display current prices in columns
    cols = st.columns(4)
    for idx, row in latest_prices.iterrows():
        with cols[idx % 4]:
            price_color = "🟢" if row['price'] <= threshold else "🔴"
            st.metric(
                label=f"{price_color} {row['site']}",
                value=f"₹{row['price']:,.0f}",
                delta=f"Target: ₹{threshold:,}"
            )

    # Best deal highlight
    best_deal = latest_prices.iloc[0]
    st.markdown(f"""
    <div class="price-alert">
        <h4>🎯 Best Current Deal</h4>
        <p><strong>{best_deal['site']}</strong> - ₹{best_deal['price']:,.0f}</p>
        <p>{'🚨 Below threshold!' if best_deal['price'] <= threshold else '⏳ Waiting for better price'}</p>
    </div>
    """, unsafe_allow_html=True)

    # Price history chart
    st.header("📈 Price History")

    # Create interactive plot
    fig = px.line(
        df,
        x='timestamp',
        y='price',
        color='site',
        title="Price Trends Over Time",
        labels={'price': 'Price (₹)', 'timestamp': 'Date & Time'}
    )

    # Add threshold line
    fig.add_hline(
        y=threshold,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Target Price: ₹{threshold:,}"
    )

    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

    # Summary statistics
    st.header("📋 Summary Statistics")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("💰 Price Analysis")
        st.write(f"**Lowest Price:** ₹{df['price'].min():,.0f}")
        st.write(f"**Highest Price:** ₹{df['price'].max():,.0f}")
        st.write(f"**Average Price:** ₹{df['price'].mean():,.0f}")

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
        st.write(f"**Days Tracked:** {(df['timestamp'].max() - df['timestamp'].min()).days + 1}")

    # Raw data table (expandable)
    with st.expander("🗂️ View Raw Data"):
        st.dataframe(df.sort_values('timestamp', ascending=False), use_container_width=True)

else:
    st.warning("📝 No price data found. Click 'Refresh Prices Now' to start tracking!")

# Auto-refresh functionality
if auto_refresh:
    time.sleep(30)
    st.rerun()

# Footer
st.markdown("---")
st.markdown("🤖 Automated by Python Price Tracker | Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


# Add this to your main.py
class StreamlitPriceTracker(PriceTracker):
    def __init__(self):
        super().__init__()

    def get_dashboard_data(self):
        """Get data formatted for dashboard"""
        try:
            df = pd.read_csv('price_history.csv')
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        except FileNotFoundError:
            return pd.DataFrame()

    def get_current_summary(self):
        """Get current price summary"""
        df = self.get_dashboard_data()
        if df.empty:
            return None

        latest_prices = df.groupby('site').last().reset_index()
        return {
            'best_price': latest_prices['price'].min(),
            'best_site': latest_prices.loc[latest_prices['price'].idxmin(), 'site'],
            'total_sites': len(latest_prices),
            'below_threshold': len(latest_prices[latest_prices['price'] <= 10000])
        }