# Lead Generation Automation 🚀

A robust Python script to scrape business leads from Google Maps (using Playwright) and find their email addresses by visiting their websites.

## Features
- **Free:** Does not use paid APIs (uses Playwright for scraping).
- **Flexible:** Search for ANY Niche in ANY Location.
- **Deep Scraping:** Visits business websites to find `mailto:` links and email patterns.
- **Robust:** Handles infinite scrolling to fetch up to 100+ leads per run.
- **Export:** Save data to SQLite and export to CSV.

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Muizz12/lead-generation.git
   cd lead-generation
   ```

2. **Create a Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install playwright beautifulsoup4 requests
   playwright install chromium
   ```

## Usage

Run the script using the python executable in your virtual environment.

### 1. Basic Run (Default: Gym in Dubai)
```bash
./venv/bin/python lead_generator.py
```

### 2. Custom Niche and Location
Search for Real Estate in USA:
```bash
./venv/bin/python lead_generator.py --niche "Real Estate" --location "USA"
```

### 3. Change Fetch Limit
Fetch only 50 leads (Default is 100):
```bash
./venv/bin/python lead_generator.py --niche "Dentist" --location "London" --max 50
```

### 4. See the Browser (Debug Mode)
By default, the browser is **visible** so you can see the scraping in action.

To run in **headless mode** (invisible, faster):
```bash
./venv/bin/python lead_generator.py --headless
```

## Exporting Data

The script saves data to `leads_db.sqlite`. To export it to a CSV file (readable by Excel):

```bash
./venv/bin/python export_leads.py
```

This will create **`leads_export.csv`** in the same folder.