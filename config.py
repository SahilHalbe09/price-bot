# config.py - Your control center for all settings and site information

# Personal Settings - Adjust these to your preferences
PRICE_THRESHOLD = 10000  # The price point where you want to be alerted
CHECK_INTERVAL_HOURS = 6  # How often to check prices

# Email Configuration for Alerts
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'email': 'sahilyhalbe@gmail.com',  # Replace with your actual email
    'password': 'kbbk hepn wljv xqfc'  # Use Gmail app password, not regular password
}

# File Settings
HISTORY_FILE = 'price_history.csv'
LOG_FILE = 'price_tracker.log'

# Browser Settings
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# Website Configuration
# Each site has: URL, CSS selector, and scraping method (static or dynamic)
WATCH_SITES = {
    'Amazon India': {
        'url': 'https://www.amazon.in/Casio-Analog-Digital-Black-Watch-GA-2100-1A1DR-G987/dp/B07YCTCMFK/',
        'price_selector': '.a-price-whole',  # Simplified selector - more stable than your long one
        'backup_selector': '#corePriceDisplay_desktop_feature_div .a-price-whole',  # Fallback option
        'method': 'static',  # Amazon usually loads prices immediately
        'wait_time': 3  # Seconds to wait between requests to be respectful
    },

    'Flipkart': {
        'url': 'https://www.flipkart.com/casio-ga-2100-1a1dr-g-shock-black-dial-resin-strap-analog-digital-watch-men/p/itm734eb8e33cc5b',
        'price_selector': '._30jeq3',  # Shorter, more stable selector
        'backup_selector': '.UOCQB1 div',  # Alternative if main fails
        'method': 'dynamic',  # Flipkart often needs JavaScript to load prices
        'wait_time': 4
    },

    'Myntra': {
        'url': 'https://www.myntra.com/watches/casio/casio-men-g-shock-ga-2100-1a1dr-black-analog-digital-dial-black-resin-strap-watch-g987/10761810/buy',
        'price_selector': '.pdp-price strong',  # Simplified from your complex selector
        'backup_selector': '.pdp-discount-container strong',
        'method': 'dynamic',  # Myntra loads content dynamically
        'wait_time': 3
    },

    'Casio Official': {
        'url': 'https://www.casio.com/in/watches/gshock/product.GA-2100-1A1/',
        'price_selector': '.p-product_detail-price',  # Your selector looks good for this one
        'backup_selector': '.price',
        'method': 'static',
        'wait_time': 2
    },

    'Swiss Time House': {
        'url': 'https://www.swisstimehouse.com/casio-g987-ga-2100-1a1dr-g-shock-mens-watch',
        'price_selector': '.ce-product-price span',  # Simplified version
        'backup_selector': '.price-item',
        'method': 'static',
        'wait_time': 3
    },

    'Just In Time': {
        'url': 'https://justintime.in/products/casio-resin-black-digital-mens-watch-g987',
        'price_selector': '.price-item--sale',  # Clean selector from your data
        'backup_selector': '.price__sale span',
        'method': 'static',
        'wait_time': 3
    },

    'Tata Cliq': {
        'url': 'https://luxury.tatacliq.com/casio-g-shock-ga-2100-1a1dr-black-analog-digital-dial-black-resin-strap-mens-watch-g987/p-mp000000016123909',
        'price_selector': '.pdp-module__flxRgtIconColLft div',  # Simplified
        'backup_selector': '[data-testid="price"]',  # Common pattern for luxury sites
        'method': 'dynamic',  # Luxury sites often load prices dynamically
        'wait_time': 4
    },

    'Ajio': {
        'url': 'https://www.ajio.com/casio-ga-2100-1a1dr-analog-digital-watch-with-resin-strap/p/460813061_black',
        'price_selector': '.prod-price-section div',  # From your selector
        'backup_selector': '.price',
        'method': 'dynamic',  # Ajio typically needs JavaScript
        'wait_time': 3
    },

    'Helios': {
        'url': 'https://www.helioswatchstore.com/g-shock-g-shock-men-round-black-watches-g987',
        'price_selector': '.product-info-price span',  # Cleaned up version
        'backup_selector': '.price',
        'method': 'static',
        'wait_time': 2
    }
}

# Debugging Settings - Turn these on when testing
DEBUG_MODE = True  # Set to False when running automatically
VERBOSE_LOGGING = True  # Detailed output for troubleshooting
TEST_MODE = False  # Set to True to test without sending real alerts