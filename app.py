import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import threading
import queue
from datetime import datetime, timedelta
import time
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from main import PriceTracker  # Import your existing tracker
from config import EMAIL_CONFIG, PRICE_THRESHOLD  # Import email config and threshold

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        background-color: #d4edda;
        color: #000000;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e1e5e9;
    }
    .price-alert {
        background-color: #d4edda;
        color: #000000;
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
    .countdown-display {
        background-color: #e3f2fd;
        padding: 0.5rem;
        border-radius: 0.25rem;
        text-align: center;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'auto_refresh_active' not in st.session_state:
    st.session_state.auto_refresh_active = False
if 'last_refresh_time' not in st.session_state:
    st.session_state.last_refresh_time = None
if 'price_update_queue' not in st.session_state:
    st.session_state.price_update_queue = queue.Queue()
if 'background_thread' not in st.session_state:
    st.session_state.background_thread = None

# Title and description
st.title("🔍 G-Shock GA-2100-1A1 Price Tracker")
st.markdown("Real-time price monitoring across multiple e-commerce platforms")

# Sidebar controls
st.sidebar.header("⚙️ Controls")

# Display current threshold info (read-only from config)
st.sidebar.markdown(f"🎯 **Price Alert Threshold:** ₹{PRICE_THRESHOLD:,}")
st.sidebar.markdown("*Threshold is managed in config.py*")


# Email alert functionality
def send_email_alert(alert_info):
    """
    Sends email notifications when good deals are found.
    This is like having a friend call you when they spot a great sale.
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['email']
        msg['To'] = EMAIL_CONFIG['email']
        msg['Subject'] = f"🎯 G-Shock Deal Alert: {alert_info['site']}"

        # Create a detailed email body
        body = f"""
Great news! Your G-Shock GA-2100-1A1 watch has hit a great price!

🏪 Store: {alert_info['site']}
💰 Current Price: ₹{alert_info['price']:,.2f}
🎯 Your Target: ₹{PRICE_THRESHOLD:,.2f}
📈 Historical Low: ₹{alert_info['historical_low']:,.2f}

🔥 Alert Reason: {alert_info['reason']}

⏰ Detected at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🛒 Ready to buy? Here's the link:
{alert_info['url']}

Happy shopping! 🎉

---
This alert was sent by your automated G-Shock price tracker via Streamlit Dashboard.
        """

        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
            server.starttls()
            server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
            server.send_message(msg)

        logger.info(f"Email alert sent successfully for {alert_info['site']}")
        st.success(f"📧 Email alert sent: {alert_info['site']} - ₹{alert_info['price']:,.2f}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")
        st.error(f"❌ Failed to send email alert: {e}")
        return False


# Check for deals and send alerts
def check_for_deals_and_alert(current_prices):
    """
    Analyzes current prices and determines if any warrant an alert.
    Sends email notifications for good deals.
    """
    if not current_prices:
        return 0

    # Load historical data to get lowest ever price
    df = load_price_data()
    historical_low = df['price'].min() if not df.empty else float('inf')

    alerts_sent = 0

    for site_name, price in current_prices.items():
        alert_reasons = []

        # Check if price is at or below threshold
        if price <= PRICE_THRESHOLD:
            alert_reasons.append(f"At/below your target of ₹{PRICE_THRESHOLD:,.2f}")

        # Check if this is a new historical low
        if price < historical_low:
            alert_reasons.append("New historical low!")

        # Check for significant drops (10% below historical average)
        if historical_low != float('inf'):
            if price < historical_low * 0.9:
                alert_reasons.append("Significant price drop detected")

        # If we have reasons to alert, send the notification
        if alert_reasons:
            from config import WATCH_SITES  # Import here to avoid circular imports

            alert_info = {
                'site': site_name,
                'price': price,
                'historical_low': historical_low,
                'reason': ' | '.join(alert_reasons),
                'url': WATCH_SITES.get(site_name, {}).get('url', 'N/A')
            }

            if send_email_alert(alert_info):
                alerts_sent += 1

    return alerts_sent


# Background price fetching function
def background_price_fetch():
    """
    Background function to fetch prices without blocking the UI.
    Runs in a separate thread.
    """
    tracker = PriceTracker()
    try:
        logger.info("Background price fetch started")
        current_prices = tracker.get_all_current_prices()

        if current_prices:
            tracker.save_price_data(current_prices)

            # Check for deals and send alerts
            alerts_sent = check_for_deals_and_alert(current_prices)

            # Put results in queue for main thread to pick up
            st.session_state.price_update_queue.put({
                'success': True,
                'prices': current_prices,
                'alerts_sent': alerts_sent,
                'timestamp': datetime.now()
            })
            logger.info(f"Background fetch completed: {len(current_prices)} prices, {alerts_sent} alerts")
        else:
            st.session_state.price_update_queue.put({
                'success': False,
                'error': 'No prices retrieved',
                'timestamp': datetime.now()
            })

    except Exception as e:
        logger.error(f"Background price fetch error: {e}")
        st.session_state.price_update_queue.put({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now()
        })
    finally:
        tracker.cleanup()


# Load historical data with proper error handling
@st.cache_data(ttl=30)  # Cache for 30 seconds
def load_price_data():
    """Load price data from CSV file with comprehensive error handling."""
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


# Manual refresh function - refactored for better UX
def manual_price_refresh():
    """
    Manually refresh prices with better user feedback and error handling.
    """
    progress_placeholder = st.empty()
    status_placeholder = st.empty()

    try:
        with progress_placeholder:
            progress_bar = st.progress(0)
            status_placeholder.info("🔄 Initializing price tracker...")

        tracker = PriceTracker()

        with progress_placeholder:
            progress_bar.progress(20)
            status_placeholder.info("🌐 Fetching prices from all sites...")

        current_prices = tracker.get_all_current_prices()

        with progress_placeholder:
            progress_bar.progress(60)
            status_placeholder.info("💾 Saving price data...")

        if current_prices:
            tracker.save_price_data(current_prices)

            with progress_placeholder:
                progress_bar.progress(80)
                status_placeholder.info("🔍 Checking for price alerts...")

            # Check for deals and send alerts
            alerts_sent = check_for_deals_and_alert(current_prices)

            with progress_placeholder:
                progress_bar.progress(100)
                status_placeholder.success(f"✅ Successfully updated {len(current_prices)} prices!")

            if alerts_sent > 0:
                st.success(f"🎉 {alerts_sent} price alert(s) sent to your email!")

            # Update session state
            st.session_state.last_refresh_time = datetime.now()

            # Clear cache to force reload
            load_price_data.clear()

            # Show summary of fetched prices
            st.subheader("📋 Latest Prices Retrieved:")
            sorted_prices = sorted(current_prices.items(), key=lambda x: x[1])

            cols = st.columns(min(3, len(sorted_prices)))
            for idx, (site, price) in enumerate(sorted_prices):
                with cols[idx % len(cols)]:
                    alert_emoji = "🚨" if price <= PRICE_THRESHOLD else "💰"
                    st.metric(
                        label=f"{alert_emoji} {site}",
                        value=f"₹{price:,.0f}",
                        delta=f"₹{price - PRICE_THRESHOLD:,.0f}" if price > PRICE_THRESHOLD else "Below target!"
                    )

        else:
            progress_placeholder.empty()
            status_placeholder.error("⚠️ No prices could be retrieved. Check your internet connection.")

    except Exception as e:
        progress_placeholder.empty()
        status_placeholder.error(f"❌ Error during price refresh: {str(e)}")
        logger.error(f"Manual refresh error: {e}")
    finally:
        tracker.cleanup()
        # Clear progress indicators after 3 seconds
        time.sleep(3)
        progress_placeholder.empty()


# Manual refresh button with improved feedback
if st.sidebar.button("🔄 Refresh Prices Now", type="primary"):
    manual_price_refresh()

# Auto-refresh controls
st.sidebar.markdown("---")
st.sidebar.subheader("🤖 Auto-Refresh Settings")

# Auto-refresh toggle
auto_refresh_enabled = st.sidebar.checkbox(
    "🔄 Enable Auto-refresh",
    value=st.session_state.auto_refresh_active,
    help="Automatically refresh prices every hour"
)

# Auto-refresh interval
refresh_interval_minutes = st.sidebar.selectbox(
    "⏰ Refresh Interval:",
    options=[30, 60, 120, 180, 360],  # 30 min, 1h, 2h, 3h, 6h
    index=1,  # Default to 60 minutes
    format_func=lambda x: f"{x} minutes" if x < 60 else f"{x // 60} hour{'s' if x // 60 > 1 else ''}",
    help="How often to automatically refresh prices"
)

# Update session state
st.session_state.auto_refresh_active = auto_refresh_enabled

# Auto-refresh logic with proper thread management
if auto_refresh_enabled:
    if st.session_state.last_refresh_time is None:
        st.session_state.last_refresh_time = datetime.now()

    # Calculate time until next refresh
    next_refresh_time = st.session_state.last_refresh_time + timedelta(minutes=refresh_interval_minutes)
    time_until_refresh = next_refresh_time - datetime.now()

    # Display countdown
    if time_until_refresh.total_seconds() > 0:
        hours, remainder = divmod(int(time_until_refresh.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        st.sidebar.markdown(f"""
        <div class="countdown-display">
            🕒 Next refresh in:<br>
            <strong>{hours:02d}:{minutes:02d}:{seconds:02d}</strong>
        </div>
        """, unsafe_allow_html=True)

        # Check if we have queued results from background thread
        try:
            if not st.session_state.price_update_queue.empty():
                result = st.session_state.price_update_queue.get_nowait()
                if result['success']:
                    st.sidebar.success(f"🔄 Auto-updated {len(result['prices'])} prices!")
                    if result['alerts_sent'] > 0:
                        st.sidebar.success(f"📧 {result['alerts_sent']} alert(s) sent!")
                    st.session_state.last_refresh_time = result['timestamp']
                    load_price_data.clear()  # Clear cache
                else:
                    st.sidebar.error(f"Auto-refresh failed: {result['error']}")
        except queue.Empty:
            pass

    else:
        # Time to refresh
        if (st.session_state.background_thread is None or
                not st.session_state.background_thread.is_alive()):
            st.sidebar.info("🔄 Starting background price fetch...")
            st.session_state.background_thread = threading.Thread(
                target=background_price_fetch,
                daemon=True
            )
            st.session_state.background_thread.start()

        # Auto-rerun every 5 seconds to update countdown and check for results
        time.sleep(5)
        st.rerun()

else:
    # Auto-refresh is disabled
    if st.session_state.last_refresh_time:
        last_refresh_str = st.session_state.last_refresh_time.strftime('%Y-%m-%d %H:%M:%S')
        st.sidebar.info(f"🕒 Last refresh: {last_refresh_str}")

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
                price_color = "🟢" if row['price'] <= PRICE_THRESHOLD else "🔴"
                delta_text = f"vs ₹{PRICE_THRESHOLD:,}" if row[
                                                               'price'] <= PRICE_THRESHOLD else f"+₹{row['price'] - PRICE_THRESHOLD:,.0f} over target"

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
                <p>{'🚨 Below your target!' if best_deal['price'] <= PRICE_THRESHOLD else '⏳ Still above target'}</p>
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
                y=PRICE_THRESHOLD,
                line_dash="dash",
                line_color="red",
                annotation_text=f"Target: ₹{PRICE_THRESHOLD:,}",
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
            below_threshold = len(latest_prices[latest_prices['price'] <= PRICE_THRESHOLD])
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

        alert_sites = latest_prices[latest_prices['price'] <= PRICE_THRESHOLD]
        if not alert_sites.empty:
            st.success(f"🎉 {len(alert_sites)} site(s) currently below your target price!")
            for _, site in alert_sites.iterrows():
                st.write(f"• **{site['site']}**: ₹{site['price']:,.0f} (Save ₹{PRICE_THRESHOLD - site['price']:,.0f})")
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

# Footer with status information
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown("🤖 **Automated Price Tracker**")
with col2:
    st.markdown(f"🎯 **Target:** ₹{PRICE_THRESHOLD:,}")
with col3:
    refresh_status = "🟢 Active" if auto_refresh_enabled else "🔴 Inactive"
    st.markdown(f"🔄 **Auto-refresh:** {refresh_status}")
with col4:
    st.markdown(f"🕒 **Current Time:** {datetime.now().strftime('%H:%M:%S')}")

# Important note about closing the browser
st.markdown("""
---
### ❓ Frequently Asked Questions

**Q: What happens if I close this browser tab/window?**  
**A:** If you close this Streamlit app, the auto-refresh will stop working. The app only runs while the browser is open. For continuous monitoring even when you're away, you should:
- Use the standalone `main.py` script with a cron job (Linux/Mac) or Task Scheduler (Windows)
- Keep this browser tab open if you want the web-based auto-refresh feature

**Q: How do I set up continuous background monitoring?**  
**A:** Set up a scheduled task to run `python main.py` every few hours using your operating system's task scheduler.
""")