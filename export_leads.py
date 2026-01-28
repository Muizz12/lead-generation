import sqlite3
import csv
import os

DB_FILE = "leads_db.sqlite"
CSV_FILE = "leads_export.csv"

def export_to_csv():
    if not os.path.exists(DB_FILE):
        print(f"Error: Database file '{DB_FILE}' not found.")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Select all columns
        cursor.execute("SELECT * FROM leads")
        rows = cursor.fetchall()
        
        # Get column names
        column_names = [description[0] for description in cursor.description]
        
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(column_names)  # Write header
            writer.writerows(rows)         # Write data
            
        print(f"✅ Successfully exported {len(rows)} leads to '{CSV_FILE}'")
        print("You can now open this file in Excel, Numbers, or Google Sheets.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    export_to_csv()
