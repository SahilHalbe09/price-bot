# main.py - The heart of your price tracking system

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import csv
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import re
import logging
from config import *

# Set up logging to track what your script is doing
logging.basicConfig(
    level=logging.INFO if VERBOSE_LOGGING else logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()  # This also prints to console
    ]
)

logger = logging.getLogger(__name__)


class PriceTracker:
    """
    This class encapsulates all the price tracking functionality.
    Think of it as your personal shopping assistant that you can give instructions to.
    """

    def __init__(self):
        self.driver = None
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

    def setup_browser(self):
        """
        Creates a controlled browser instance for dynamic content scraping.
        This is like hiring a robot to operate a web browser for you.
        """
        if self.driver is None:
            chrome_options = Options()
            chrome_options.add_argument(f'--user-agent={USER_AGENT}')
            chrome_options.add_argument('--headless')  # Run without showing browser window
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')

            try:
                self.driver = webdriver.Chrome(options=chrome_options)
                logger.info("Browser driver initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize browser driver: {e}")
                raise

        return self.driver

    def extract_price_from_text(self, price_text):
        """
        Converts messy price text like "₹8,999.00" into clean numbers like 8999.0
        This handles Indian currency formatting with commas and various symbols.
        """
        if not price_text:
            return None

        # Remove common currency symbols and clean the text
        cleaned_text = price_text.replace('₹', '').replace(',', '').replace('Rs', '').replace('INR', '')

        # Find all number patterns in the text
        number_patterns = re.findall(r'\d+\.?\d*', cleaned_text)

        if number_patterns:
            try:
                # Take the first number found (usually the price)
                price = float(number_patterns[0])

                # Sanity check: G-Shock watches typically cost between ₹5,000 and ₹15,000
                if 5000 <= price <= 15000:
                    return price
                else:
                    logger.warning(f"Price {price} seems outside expected range for G-Shock")
                    return price  # Return anyway, but log the concern

            except ValueError:
                logger.error(f"Could not convert '{number_patterns[0]}' to float")
                return None

        logger.warning(f"No valid price found in text: '{price_text}'")
        return None

    def scrape_price_static(self, site_name, site_config):
        """
        Scrapes prices from websites that load content immediately (no JavaScript needed).
        This is like reading a printed newspaper - all the information is already there.
        """
        url = site_config['url']
        primary_selector = site_config['price_selector']
        backup_selector = site_config.get('backup_selector', primary_selector)

        try:
            logger.info(f"Scraping {site_name} using static method")

            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Try primary selector first
            price_element = soup.select_one(primary_selector)

            # If primary fails, try backup selector
            if not price_element and backup_selector != primary_selector:
                logger.info(f"Primary selector failed for {site_name}, trying backup")
                price_element = soup.select_one(backup_selector)

            if price_element:
                price_text = price_element.get_text(strip=True)
                logger.info(f"Found price text for {site_name}: '{price_text}'")

                price = self.extract_price_from_text(price_text)
                if price:
                    logger.info(f"Successfully extracted price from {site_name}: ₹{price}")
                    return price
                else:
                    logger.warning(f"Could not extract valid price from text: '{price_text}'")
            else:
                logger.warning(f"Price element not found on {site_name}")

        except requests.RequestException as e:
            logger.error(f"Network error while scraping {site_name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error while scraping {site_name}: {e}")

        return None

    def scrape_price_dynamic(self, site_name, site_config):
        """
        Scrapes prices from websites that load content with JavaScript after page loads.
        This is like waiting for someone to write information on a board after you arrive.
        """
        url = site_config['url']
        primary_selector = site_config['price_selector']
        backup_selector = site_config.get('backup_selector', primary_selector)

        try:
            logger.info(f"Scraping {site_name} using dynamic method")

            driver = self.setup_browser()
            driver.get(url)

            # Wait for the page to load completely
            wait = WebDriverWait(driver, 15)

            # Try to find the price element
            price_element = None

            try:
                # Try primary selector first
                price_element = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, primary_selector))
                )
            except TimeoutException:
                if backup_selector != primary_selector:
                    logger.info(f"Primary selector timed out for {site_name}, trying backup")
                    try:
                        price_element = wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, backup_selector))
                        )
                    except TimeoutException:
                        logger.warning(f"Both selectors timed out for {site_name}")

            if price_element:
                price_text = price_element.text.strip()
                logger.info(f"Found price text for {site_name}: '{price_text}'")

                price = self.extract_price_from_text(price_text)
                if price:
                    logger.info(f"Successfully extracted price from {site_name}: ₹{price}")
                    return price
                else:
                    logger.warning(f"Could not extract valid price from text: '{price_text}'")
            else:
                logger.warning(f"Price element not found on {site_name}")

        except Exception as e:
            logger.error(f"Error while scraping {site_name}: {e}")

        return None

    def get_all_current_prices(self):
        """
        Coordinates the scraping of all websites and returns a dictionary of current prices.
        This is like sending scouts to different markets to gather intelligence.
        """
        current_prices = {}

        logger.info("Starting comprehensive price check across all sites")

        for site_name, site_config in WATCH_SITES.items():
            logger.info(f"Checking {site_name}...")

            # Determine which scraping method to use
            if site_config['method'] == 'static':
                price = self.scrape_price_static(site_name, site_config)
            else:
                price = self.scrape_price_dynamic(site_name, site_config)

            if price:
                current_prices[site_name] = price
                print(f"✓ {site_name}: ₹{price:,.2f}")
            else:
                print(f"✗ {site_name}: Could not retrieve price")

            # Be respectful - wait between requests
            wait_time = site_config.get('wait_time', 3)
            time.sleep(wait_time)

        logger.info(f"Price check completed. Retrieved {len(current_prices)} prices.")
        return current_prices

    def get_historical_data(self):
        """
        Reads the price history file and returns useful statistics.
        This is like looking through old receipts to understand price trends.
        """
        try:
            import os

            # Check if file exists and has content
            if not os.path.exists(HISTORY_FILE) or os.path.getsize(HISTORY_FILE) == 0:
                logger.info("No price history file found or file is empty. This appears to be the first run.")
                return {'lowest_ever': float('inf'), 'records': []}

            with open(HISTORY_FILE, 'r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)

                # Check if the required columns exist
                if reader.fieldnames is None:
                    logger.warning("CSV file appears to be empty or malformed")
                    return {'lowest_ever': float('inf'), 'records': []}

                required_columns = ['timestamp', 'site', 'price']
                missing_columns = [col for col in required_columns if col not in reader.fieldnames]

                if missing_columns:
                    logger.error(f"Missing columns in CSV: {missing_columns}")
                    logger.info("Consider deleting the CSV file to recreate it with proper headers")
                    return {'lowest_ever': float('inf'), 'records': []}

                records = list(reader)

                if not records:
                    return {'lowest_ever': float('inf'), 'records': []}

                # Find the lowest price ever recorded
                prices = []
                for record in records:
                    try:
                        if record.get('price'):
                            prices.append(float(record['price']))
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid price value found: {record.get('price')}")
                        continue

                lowest_ever = min(prices) if prices else float('inf')

                return {
                    'lowest_ever': lowest_ever,
                    'records': records,
                    'total_checks': len(records)
                }

        except FileNotFoundError:
            logger.info("No price history file found. This appears to be the first run.")
            return {'lowest_ever': float('inf'), 'records': []}
        except Exception as e:
            logger.error(f"Error reading price history: {e}")
            return {'lowest_ever': float('inf'), 'records': []}

    def save_price_data(self, current_prices):
        """
        Saves current price data to the history file.
        This is like keeping a detailed diary of all prices you've encountered.
        """
        try:
            import os

            # Check if file exists and has content
            file_exists = os.path.exists(HISTORY_FILE) and os.path.getsize(HISTORY_FILE) > 0

            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            historical_data = self.get_historical_data()

            with open(HISTORY_FILE, 'a', newline='', encoding='utf-8') as file:
                fieldnames = ['timestamp', 'site', 'price', 'is_new_low', 'below_threshold']
                writer = csv.DictWriter(file, fieldnames=fieldnames)

                # Write headers if file doesn't exist or is empty
                if not file_exists:
                    writer.writeheader()
                    logger.info("Created new price history file with headers")

                for site_name, price in current_prices.items():
                    is_new_low = price < historical_data['lowest_ever']
                    below_threshold = price <= PRICE_THRESHOLD

                    writer.writerow({
                        'timestamp': current_time,
                        'site': site_name,
                        'price': price,
                        'is_new_low': is_new_low,
                        'below_threshold': below_threshold
                    })

                logger.info(f"Saved {len(current_prices)} price records to history")

        except Exception as e:
            logger.error(f"Error saving price data: {e}")
            # If there's an error and the file might be corrupted, let's ensure headers exist
            try:
                import os
                if os.path.exists(HISTORY_FILE):
                    with open(HISTORY_FILE, 'r', newline='', encoding='utf-8') as file:
                        first_line = file.readline().strip()
                        if first_line and 'timestamp' not in first_line:
                            logger.warning(
                                "CSV file exists but appears to be missing headers. Consider deleting it to recreate with proper headers.")
            except:
                pass

    def send_email_alert(self, alert_info):
        """
        Sends email notifications when good deals are found.
        This is like having a friend call you when they spot a great sale.
        """
        if TEST_MODE:
            logger.info(f"TEST MODE: Would send alert for {alert_info}")
            return

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
This alert was sent by your automated G-Shock price tracker.
            """

            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
                server.starttls()
                server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
                server.send_message(msg)

            logger.info(f"Email alert sent successfully for {alert_info['site']}")
            print(f"📧 Alert sent: {alert_info['site']} - ₹{alert_info['price']:,.2f}")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            print(f"❌ Failed to send email alert: {e}")

    def check_for_deals(self, current_prices):
        """
        Analyzes current prices and determines if any warrant an alert.
        This is your smart shopping assistant making decisions about what's worth your attention.
        """
        historical_data = self.get_historical_data()
        alerts_sent = 0

        for site_name, price in current_prices.items():
            alert_reasons = []

            # Check if price is at or below your threshold
            if price <= PRICE_THRESHOLD:
                alert_reasons.append(f"At/below your target of ₹{PRICE_THRESHOLD:,.2f}")

            # Check if this is a new historical low
            if price < historical_data['lowest_ever']:
                alert_reasons.append("New historical low!")

            # Check for significant drops (10% below historical average)
            if historical_data['lowest_ever'] != float('inf'):
                if price < historical_data['lowest_ever'] * 0.9:
                    alert_reasons.append("Significant price drop detected")

            # If we have reasons to alert, send the notification
            if alert_reasons:
                alert_info = {
                    'site': site_name,
                    'price': price,
                    'historical_low': historical_data['lowest_ever'],
                    'reason': ' | '.join(alert_reasons),
                    'url': WATCH_SITES[site_name]['url']
                }

                self.send_email_alert(alert_info)
                alerts_sent += 1

        return alerts_sent

    def generate_summary_report(self, current_prices):
        """
        Creates a comprehensive summary of the current price check.
        This is like getting a briefing from your shopping assistant about the market situation.
        """
        if not current_prices:
            print("❌ No prices were successfully retrieved.")
            return

        historical_data = self.get_historical_data()

        print("\n" + "=" * 60)
        print("🔍 G-SHOCK GA-2100-1A1 PRICE SUMMARY")
        print("=" * 60)

        # Find the best current deal
        best_price = min(current_prices.values())
        best_site = min(current_prices, key=current_prices.get)

        print(f"🏆 Best current price: ₹{best_price:,.2f} at {best_site}")
        print(f"🎯 Your target price: ₹{PRICE_THRESHOLD:,.2f}")

        if historical_data['lowest_ever'] != float('inf'):
            print(f"📊 Historical low: ₹{historical_data['lowest_ever']:,.2f}")
        else:
            print("📊 Historical low: No previous data")

        print(f"🕒 Check completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        print("\n📋 All current prices (sorted by price):")
        sorted_prices = sorted(current_prices.items(), key=lambda x: x[1])

        for site, price in sorted_prices:
            status = "🔥" if price <= PRICE_THRESHOLD else "💰"
            print(f"  {status} {site}: ₹{price:,.2f}")

        print("=" * 60)

    def cleanup(self):
        """
        Properly closes browser and cleans up resources.
        This is like putting away your tools after finishing work.
        """
        if self.driver:
            self.driver.quit()
            logger.info("Browser driver closed")


def main():
    """
    The main function that orchestrates the entire price checking process.
    This is the conductor of your price tracking orchestra.
    """
    tracker = PriceTracker()

    try:
        logger.info("Starting G-Shock price tracking session")
        print("🚀 Starting G-Shock GA-2100-1A1 price check...")

        # Get current prices from all configured sites
        current_prices = tracker.get_all_current_prices()

        if not current_prices:
            print("❌ No prices could be retrieved. Check your internet connection and site configurations.")
            return

        # Save the data to our history file
        tracker.save_price_data(current_prices)

        # Check if any prices warrant alerts
        alerts_sent = tracker.check_for_deals(current_prices)

        # Generate and display summary
        tracker.generate_summary_report(current_prices)

        if alerts_sent > 0:
            print(f"\n🎉 {alerts_sent} price alert(s) sent to your email!")
        else:
            print("\n😌 No alerts triggered this time. Your tracker is still watching...")

        logger.info("Price tracking session completed successfully")

    except Exception as e:
        logger.error(f"Error during main execution: {e}")
        print(f"❌ Error occurred: {e}")

    finally:
        # Always clean up, even if something goes wrong
        tracker.cleanup()


if __name__ == "__main__":
    main()