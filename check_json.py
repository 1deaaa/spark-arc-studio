import sqlite3
import os

db_path = r"D:\0\Dev\Unity\project01\TEST\Assets\StreamingAssets\test.db"

def check_json():
    print(f"--- Checking JSON content in: {db_path} ---")
    if not os.path.exists(db_path):
        print("File not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check column types declared schema
    cursor.execute("PRAGMA table_info(stories)")
    cols = cursor.fetchall()
    print("Schema:")
    dlg_col_index = -1
    for i, col in enumerate(cols):
        print(f"  {col[1]}: {col[2]}")
        if col[1] == 'dlg_json':
            dlg_col_index = i

    # Fetch raw data
    print("\nRow Data Sample:")
    cursor.execute("SELECT id, dlg_json FROM stories LIMIT 1")
    row = cursor.fetchone()
    
    if row:
        id_val, json_val = row
        print(f"ID: {id_val}")
        print(f"Type of dlg_json in Python: {type(json_val)}")
        print(f"Value sample (first 100 chars): {str(json_val)[:100]}")
    else:
        print("No rows found.")

    conn.close()

if __name__ == "__main__":
    check_json()
