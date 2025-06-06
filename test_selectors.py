# test_selectors.py - Tool to test and validate your CSS selectors

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import re
from config import WATCH_SITES, USER_AGENT


class SelectorTester:
    """
    This class helps you test and validate CSS selectors before running the main script.
    Think of it as a rehearsal before the main performance.
    """

    def __init__(self):
        self.driver = None
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

    def setup_browser(self):
        """Create a browser instance for testing dynamic content."""
        if self.driver is None:
            chrome_options = Options()
            chrome_options.add_argument(f'--user-agent={USER_AGENT}')
            # Don't use headless mode for testing - you want to see what's happening
            chrome_options.add_argument('--window-size=1920,1080')

            self.driver = webdriver.Chrome(options=chrome_options)

        return self.driver

    def extract_price_from_text(self, price_text):
        """
        Test version of price extraction - same logic as main script.
        This helps you see if your selector is finding the right text.
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
                    print(f"    ⚠️  Price {price} seems outside expected range for G-Shock")
                    return price  # Return anyway, but warn about it

            except ValueError:
                print(f"    ❌ Could not convert '{number_patterns[0]}' to float")
                return None

        print(f"    ❌ No valid price found in text: '{price_text}'")
        return None

    def test_static_selector(self, site_name, site_config):
        """
        Test a CSS selector on a static website.
        This shows you exactly what text the selector finds.
        """
        url = site_config['url']
        primary_selector = site_config['price_selector']
        backup_selector = site_config.get('backup_selector', primary_selector)

        print(f"\n🧪 Testing STATIC selectors for {site_name}")
        print(f"URL: {url}")
        print(f"Primary selector: {primary_selector}")

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Test primary selector
            primary_elements = soup.select(primary_selector)
            print(f"\nPrimary selector found {len(primary_elements)} elements:")

            for i, element in enumerate(primary_elements[:3]):  # Show first 3 matches
                text = element.get_text(strip=True)
                print(f"  Element {i + 1}: '{text}'")

                # Try to extract price from this text
                price = self.extract_price_from_text(text)
                if price:
                    print(f"    ✅ Extracted price: ₹{price}")
                else:
                    print(f"    ❌ Could not extract valid price")

            # Test backup selector if different
            if backup_selector != primary_selector:
                backup_elements = soup.select(backup_selector)
                print(f"\nBackup selector found {len(backup_elements)} elements:")

                for i, element in enumerate(backup_elements[:3]):
                    text = element.get_text(strip=True)
                    print(f"  Element {i + 1}: '{text}'")

                    # Try to extract price from this text
                    price = self.extract_price_from_text(text)
                    if price:
                        print(f"    ✅ Extracted price: ₹{price}")
                    else:
                        print(f"    ❌ Could not extract valid price")

            # Analyze the results
            if primary_elements:
                best_element = primary_elements[0]
                price_text = best_element.get_text(strip=True)
                extracted_price = self.extract_price_from_text(price_text)

                if extracted_price:
                    print(f"\n✅ PRIMARY SELECTOR WORKS PERFECTLY")
                    print(f"Best match: '{price_text}' → ₹{extracted_price}")
                    return True
                else:
                    print(f"\n⚠️  PRIMARY SELECTOR FINDS ELEMENTS BUT PRICE EXTRACTION FAILS")
                    return False
            elif backup_selector != primary_selector and backup_elements:
                print(f"\n⚠️  PRIMARY FAILED, BUT BACKUP SELECTOR WORKS")
                return True
            else:
                print(f"\n❌ BOTH SELECTORS FAILED TO FIND ELEMENTS")
                return False

        except Exception as e:
            print(f"❌ Error testing {site_name}: {e}")
            return False

    def test_dynamic_selector(self, site_name, site_config):
        """
        Test a CSS selector on a dynamic website using browser automation.
        This is more thorough but slower than static testing.
        """
        url = site_config['url']
        primary_selector = site_config['price_selector']
        backup_selector = site_config.get('backup_selector', primary_selector)

        print(f"\n🧪 Testing DYNAMIC selectors for {site_name}")
        print(f"URL: {url}")
        print(f"Primary selector: {primary_selector}")

        try:
            driver = self.setup_browser()
            print("Opening browser and loading page...")
            driver.get(url)

            # Wait a moment for initial page load
            time.sleep(3)

            # Create a wait object for explicit waits
            wait = WebDriverWait(driver, 15)

            # Test primary selector
            primary_success = False
            try:
                print("Waiting for primary selector to appear...")
                primary_element = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, primary_selector))
                )

                price_text = primary_element.text.strip()
                print(f"✅ Primary selector found element")
                print(f"Text content: '{price_text}'")

                # Try to extract price
                extracted_price = self.extract_price_from_text(price_text)
                if extracted_price:
                    print(f"✅ Successfully extracted price: ₹{extracted_price}")
                    primary_success = True
                else:
                    print(f"❌ Could not extract valid price from: '{price_text}'")

            except TimeoutException:
                print(f"❌ Primary selector timed out after 15 seconds")
            except Exception as e:
                print(f"❌ Error with primary selector: {e}")

            # Test backup selector if different and primary failed
            backup_success = False
            if backup_selector != primary_selector and not primary_success:
                try:
                    print(f"\nTrying backup selector: {backup_selector}")
                    backup_element = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, backup_selector))
                    )

                    price_text = backup_element.text.strip()
                    print(f"✅ Backup selector found element")
                    print(f"Text content: '{price_text}'")

                    # Try to extract price
                    extracted_price = self.extract_price_from_text(price_text)
                    if extracted_price:
                        print(f"✅ Successfully extracted price: ₹{extracted_price}")
                        backup_success = True
                    else:
                        print(f"❌ Could not extract valid price from: '{price_text}'")

                except TimeoutException:
                    print(f"❌ Backup selector also timed out")
                except Exception as e:
                    print(f"❌ Error with backup selector: {e}")

            # Final evaluation
            if primary_success:
                print(f"\n✅ DYNAMIC TEST PASSED - Primary selector works perfectly")
                return True
            elif backup_success:
                print(f"\n⚠️  DYNAMIC TEST PARTIAL - Only backup selector works")
                return True
            else:
                print(f"\n❌ DYNAMIC TEST FAILED - Neither selector works")

                # Provide debugging help
                print("\n🔍 DEBUGGING SUGGESTIONS:")
                print("1. Check if the page loaded completely")
                print("2. Try inspecting the page manually to verify selectors")
                print("3. The element might be inside an iframe")
                print("4. The site might be blocking automated browsers")

                return False

        except Exception as e:
            print(f"❌ Unexpected error during dynamic testing: {e}")
            return False

    def test_single_site(self, site_name):
        """
        Test selectors for a single specific site.
        This is useful when you're troubleshooting one particular site.
        """
        if site_name not in WATCH_SITES:
            print(f"❌ Site '{site_name}' not found in configuration")
            print(f"Available sites: {', '.join(WATCH_SITES.keys())}")
            return False

        site_config = WATCH_SITES[site_name]
        method = site_config.get('method', 'static')

        print(f"\n{'=' * 60}")
        print(f"🎯 TESTING SINGLE SITE: {site_name}")
        print(f"Method: {method.upper()}")
        print(f"{'=' * 60}")

        if method == 'static':
            success = self.test_static_selector(site_name, site_config)
        else:
            success = self.test_dynamic_selector(site_name, site_config)

        if success:
            print(f"\n🎉 SUCCESS: {site_name} selectors are working correctly!")
        else:
            print(f"\n💔 FAILURE: {site_name} selectors need adjustment")

        return success

    def test_all_sites(self):
        """
        Test selectors for all configured sites.
        This gives you a complete overview of which sites are working.
        """
        print(f"\n{'=' * 60}")
        print(f"🔍 TESTING ALL CONFIGURED SITES")
        print(f"Total sites to test: {len(WATCH_SITES)}")
        print(f"{'=' * 60}")

        results = {}
        successful_sites = 0

        for site_name, site_config in WATCH_SITES.items():
            method = site_config.get('method', 'static')

            print(f"\n[{list(WATCH_SITES.keys()).index(site_name) + 1}/{len(WATCH_SITES)}] Testing {site_name}...")

            if method == 'static':
                success = self.test_static_selector(site_name, site_config)
            else:
                success = self.test_dynamic_selector(site_name, site_config)

            results[site_name] = success
            if success:
                successful_sites += 1

            # Wait between tests to be respectful to servers
            wait_time = site_config.get('wait_time', 3)
            if site_name != list(WATCH_SITES.keys())[-1]:  # Don't wait after last site
                print(f"Waiting {wait_time} seconds before next test...")
                time.sleep(wait_time)

        # Generate summary report
        self.generate_test_summary(results, successful_sites)

        return results

    def generate_test_summary(self, results, successful_sites):
        """
        Create a comprehensive summary of all testing results.
        This helps you quickly see which sites need attention.
        """
        total_sites = len(results)
        failed_sites = total_sites - successful_sites
        success_rate = (successful_sites / total_sites) * 100

        print(f"\n{'=' * 60}")
        print(f"📊 COMPREHENSIVE TEST SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total sites tested: {total_sites}")
        print(f"Successful: {successful_sites} ✅")
        print(f"Failed: {failed_sites} ❌")
        print(f"Success rate: {success_rate:.1f}%")

        if successful_sites > 0:
            print(f"\n✅ WORKING SITES:")
            for site_name, success in results.items():
                if success:
                    method = WATCH_SITES[site_name].get('method', 'static')
                    print(f"  • {site_name} ({method})")

        if failed_sites > 0:
            print(f"\n❌ SITES NEEDING ATTENTION:")
            for site_name, success in results.items():
                if not success:
                    method = WATCH_SITES[site_name].get('method', 'static')
                    print(f"  • {site_name} ({method})")

            print(f"\n💡 TROUBLESHOOTING TIPS FOR FAILED SITES:")
            print(f"1. Check if the website has changed its layout")
            print(f"2. Verify CSS selectors using browser developer tools")
            print(f"3. Consider if the site blocks automated browsers")
            print(f"4. Try adjusting wait times for dynamic sites")
            print(f"5. Check if backup selectors are more reliable")

        print(f"\n🎯 RECOMMENDATION:")
        if success_rate >= 80:
            print(f"Excellent! Your price tracker should work reliably.")
        elif success_rate >= 60:
            print(f"Good coverage, but consider fixing failed sites for better results.")
        else:
            print(f"Many sites are failing. Review and update selectors before running main tracker.")

    def cleanup(self):
        """
        Clean up browser resources.
        Always call this when you're done testing.
        """
        if self.driver:
            self.driver.quit()
            print("\n🧹 Browser closed and resources cleaned up")


def main():
    """
    Interactive testing interface.
    This gives you options for different types of testing.
    """
    tester = SelectorTester()

    try:
        print("🔧 G-SHOCK SELECTOR TESTING TOOL")
        print("This tool helps you verify that your CSS selectors work correctly.")
        print("\nWhat would you like to test?")
        print("1. Test all sites (comprehensive)")
        print("2. Test a specific site")
        print("3. List all configured sites")

        choice = input("\nEnter your choice (1-3): ").strip()

        if choice == '1':
            print("\n🚀 Starting comprehensive test of all sites...")
            print("This may take several minutes depending on your sites...")
            results = tester.test_all_sites()

        elif choice == '2':
            print(f"\nAvailable sites:")
            for i, site_name in enumerate(WATCH_SITES.keys(), 1):
                method = WATCH_SITES[site_name].get('method', 'static')
                print(f"  {i}. {site_name} ({method})")

            site_choice = input(f"\nEnter site name or number: ").strip()

            # Handle both name and number input
            if site_choice.isdigit():
                site_index = int(site_choice) - 1
                site_names = list(WATCH_SITES.keys())
                if 0 <= site_index < len(site_names):
                    site_name = site_names[site_index]
                else:
                    print("❌ Invalid site number")
                    return
            else:
                site_name = site_choice

            tester.test_single_site(site_name)

        elif choice == '3':
            print(f"\n📋 CONFIGURED SITES ({len(WATCH_SITES)} total):")
            for site_name, config in WATCH_SITES.items():
                method = config.get('method', 'static')
                print(f"  • {site_name}")
                print(f"    Method: {method}")
                print(f"    URL: {config['url']}")
                print(f"    Selector: {config['price_selector']}")
                print()

        else:
            print("❌ Invalid choice. Please run the script again.")

    except KeyboardInterrupt:
        print("\n\n⏹️  Testing interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

    finally:
        # Always clean up, even if something goes wrong
        tester.cleanup()


if __name__ == "__main__":
    main()