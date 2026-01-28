import os
import time
import sqlite3
import logging
import re
import random
from urllib.parse import urljoin, urlparse

# Library imports - Requires: pip install playwright beautifulsoup4 requests
# And: playwright install chromium
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ==========================================
# CONFIGURATION
# ==========================================
# Search Parameters
NICHE = "Gym"
LOCATION = "Dubai"
MAX_LEADS = 100  # Increased limit

# Database File
DB_FILE = "leads_db.sqlite"

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("lead_generator.log"),
        logging.StreamHandler()
    ]
)

# ==========================================
# DATABASE SETUP
# ==========================================
def setup_database():
    """Creates the leads table if it does not exist."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                niche TEXT,
                location TEXT,
                business_name TEXT,
                address TEXT,
                phone TEXT,
                website TEXT,
                email TEXT,
                rating REAL,
                source_platform TEXT,
                UNIQUE(business_name)
            )
        ''')
        
        conn.commit()
        return conn
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return None

def save_lead(conn, data):
    """Saves a single lead to the database, ignoring duplicates."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO leads 
            (niche, location, business_name, address, phone, website, email, rating, source_platform)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['niche'],
            data['location'],
            data['business_name'],
            data['address'],
            data['phone'],
            data['website'],
            data['email'],
            data['rating'],
            data['source_platform']
        ))
        conn.commit()
        if cursor.rowcount > 0:
            logging.info(f"Saved lead: {data['business_name']}")
        else:
            logging.info(f"Duplicate skipped: {data['business_name']}")
    except sqlite3.Error as e:
        logging.error(f"Error saving lead: {e}")

# ==========================================
# EMAIL EXTRACTION
# ==========================================
def extract_email_from_website(url):
    """
    Visits the website and scans for email addresses on the homepage and contact page.
    Returns the first found email or None.
    """
    if not url:
        return None

    # Ensure URL has schema
    if not url.startswith("http"):
        url = "http://" + url

    emails = set()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        logging.info(f"Scraping email from: {url}")
        
        def scrape_page(target_url):
            try:
                response = requests.get(target_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 1. Mailto links
                    for a in soup.find_all('a', href=True):
                        if a['href'].startswith('mailto:'):
                            email = a['href'].replace('mailto:', '').split('?')[0]
                            if email and '@' in email:
                                emails.add(email)
                    
                    # 2. Regex
                    text_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', response.text)
                    for email in text_emails:
                        if not email.endswith(('.png', '.jpg', '.jpeg', '.gif', '.css', '.js', '.svg')):
                            emails.add(email)
            except Exception as e:
                # logging.warning(f"Failed to scrape {target_url}: {e}")
                pass

        # Scrape Homepage
        scrape_page(url)
        
        # If no email, check Contact page
        if not emails:
            try:
                response = requests.get(url, headers=headers, timeout=5)
                soup = BeautifulSoup(response.text, 'html.parser')
                contact_link = None
                
                for a in soup.find_all('a', href=True):
                    text = a.text.lower()
                    if 'contact' in text or 'about' in text:
                        contact_link = urljoin(url, a['href'])
                        break
                
                if contact_link:
                    # logging.info(f"Checking contact page: {contact_link}")
                    scrape_page(contact_link)
            except:
                pass

    except Exception as e:
        logging.error(f"Error accessing website {url}")

    if emails:
        return list(emails)[0]
    return None

# ==========================================
# PLAYWRIGHT GOOGLE MAPS SCRAPER
# ==========================================
def scrape_google_maps_links(page, niche, location, max_leads):
    """
    Searches Google Maps and scrolls to collect place Links.
    """
    search_query = f"{niche} in {location}"
    encoded_query = search_query.replace(" ", "+")
    url = f"https://www.google.com/maps/search/{encoded_query}?hl=en"
    logging.info(f"Navigating directly to: {url}")

    try:
        page.goto(url, timeout=60000)
    except Exception as e:
        logging.error(f"Error loading Google Maps: {e}")
        return []
    
    # Handle Google Consent (Cookies) if it appears
    try:
        # Common text for consent buttons
        consent_button = page.locator('form[action*="consent"] button, button[aria-label*="Accept"], button:has-text("Accept all")').first
        if consent_button.is_visible(timeout=5000):
            logging.info("Clicking consent button...")
            consent_button.click()
            time.sleep(2)
    except:
        pass

    # Wait for feed to load. 
    # The sidebar usually has role="feed".
    try:
        # Wait for the feed (search results)
        page.wait_for_selector('div[role="feed"]', timeout=30000)
        logging.info("Search results loaded.")
    except:
        # If feed not found, maybe checking if 'No results' or blocked
        logging.error("Could not find results feed. Taking screenshot...")
        page.screenshot(path="debug_feed_error.png")
        return []

    # Scroll the feed to load more results
    # The sidebar usually has role="feed".
    try:
        page.wait_for_selector('div[role="feed"]', timeout=15000)
        logging.info("Search results loaded.")
    except:
        logging.error("Could not find results feed. Checking for 'No results' messsage...")
        return []

    # Scroll the feed to load more results
    feed_selector = 'div[role="feed"]'
    links = set()
    no_new_leads_count = 0
    last_len = 0
    
    while len(links) < max_leads:
        # Get current links
        elements = page.locator('a').all()
        for el in elements:
            try:
                href = el.get_attribute("href")
                if href and "/maps/place/" in href:
                    links.add(href)
            except:
                pass
        
        current_len = len(links)
        logging.info(f"Found {current_len} leads so far...")
        
        if current_len >= max_leads:
            break
            
        if current_len == last_len:
            no_new_leads_count += 1
            if no_new_leads_count >= 5: # increased patience
                logging.info("No new leads found after scrolling. Stopping.")
                break
        else:
            no_new_leads_count = 0
            
        last_len = current_len
        
        # Scroll down
        page.hover(feed_selector)
        page.mouse.wheel(0, 5000) # Aggressive scroll
        time.sleep(3) # Wait for network load
        
    return list(links)[:max_leads]

def parse_place_details(page, url):
    """
    Visits a specific Google Maps place URL and extracts data.
    """
    try:
        page.goto(url, timeout=30000)
        
        # Data containers
        data = {
            'business_name': None,
            'address': None,
            'website': None,
            'phone': None,
            'rating': 0.0
        }
        
        # 1. Business Name (Usually h1)
        try:
            data['business_name'] = page.locator("h1").first.inner_text()
        except:
            data['business_name'] = "Unknown"

        # 2. Rating
        # aria-label="4.8 stars 123 reviews"
        try:
            rating_el = page.locator('span[role="img"]').first
            aria = rating_el.get_attribute("aria-label")
            if aria and "stars" in aria:
                 # Extract standard float
                 match = re.search(r'(\d+\.\d+)', aria)
                 if match:
                     data['rating'] = float(match.group(1))
        except:
            pass

        # 3. Address, Website, Phone
        # Google Maps details usually use buttons with aria-labels starting with "Address: ", "Website: ", "Phone: "
        # Or data-item-id attributes
        
        # Website
        try:
            # Strategies for website
            # Look for button that opens a link
            website_loc = page.locator('a[data-item-id="authority"]')
            if website_loc.count() > 0:
                data['website'] = website_loc.get_attribute("href")
            else:
                 # Fallback: Find icon with website text
                 # Or look for aria-label="Website: ..."
                 pass
        except:
            pass

        # Phone
        try:
            phone_loc = page.locator('button[data-item-id^="phone:tel:"]')
            if phone_loc.count() > 0:
                data['phone'] = phone_loc.get_attribute("aria-label").replace("Phone: ", "")
            else:
                # Try finding button with text matching phone pattern
                pass
        except:
            pass
            
        # Address
        try:
            # Address is often a button with data-item-id="address"
            addr_loc = page.locator('button[data-item-id="address"]')
            if addr_loc.count() > 0:
                 data['address'] = addr_loc.get_attribute("aria-label").replace("Address: ", "")
        except:
            pass

        return data
        
    except Exception as e:
        logging.error(f"Error parsing details for {url}: {e}")
        return None

# ==========================================
# MAIN EXECUTION
# ==========================================
import argparse

def main():
    # 1. Parse Arguments
    parser = argparse.ArgumentParser(description="Google Maps Lead Generator")
    parser.add_argument("--niche", type=str, default=NICHE, help=f"Business Niche (default: {NICHE})")
    parser.add_argument("--location", type=str, default=LOCATION, help=f"Location (default: {LOCATION})")
    parser.add_argument("--max", type=int, default=MAX_LEADS, help=f"Max leads to fetch (default: {MAX_LEADS})")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode (default: False)")  # Let's verify headless default
    
    # Actually, let's keep it simple and consistent with previous code structure
    args = parser.parse_args()
    
    current_niche = args.niche
    current_location = args.location
    current_max = args.max
    
    # 2. Setup Database
    conn = setup_database()
    if not conn:
        return

    logging.info(f"Starting Scraper for '{current_niche}' in '{current_location}' (Max: {current_max})...")
    
    with sync_playwright() as p:
        # Launch browser 
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # 3. Get Place Links
        links = scrape_google_maps_links(page, current_niche, current_location, current_max)
        logging.info(f"Collected {len(links)} potential leads. Processing details...")
        
        # 4. Process each link
        for link in links:
            details = parse_place_details(page, link)
            
            if details and details['business_name']:
                logging.info(f"Processed: {details['business_name']}")
                
                # Check website for email
                email = None
                if details['website']:
                    email = extract_email_from_website(details['website'])
                    if email:
                        logging.info(f"  -> Found Email: {email}")
                
                lead_data = {
                    'niche': current_niche,
                    'location': current_location,
                    'business_name': details['business_name'],
                    'address': details['address'],
                    'phone': details['phone'],
                    'website': details['website'],
                    'email': email,
                    'rating': details['rating'],
                    'source_platform': 'Google Maps (Playwright)'
                }
                
                save_lead(conn, lead_data)
            
            # Rate limiting
            time.sleep(random.uniform(1, 3))
            
        browser.close()

    conn.close()
    logging.info("Done.")

if __name__ == "__main__":
    main()
