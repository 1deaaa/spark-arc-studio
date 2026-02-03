import sqlite3
import os

db_path = r"D:\0\Dev\Unity\project01\TEST\Assets\StreamingAssets\test.db"

def inspect_db():
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return

    print(f"--- Inspecting: {db_path} ---")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. List Tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables found: {[t[0] for t in tables]}")
        
        # 2. Check 'stories' table schema
        if ('stories',) in tables:
            print("\n[stories] Table Schema:")
            cursor.execute("PRAGMA table_info(stories)")
            columns = cursor.fetchall()
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")
            
            # 3. Check content count
            cursor.execute("SELECT COUNT(*) FROM stories")
            count = cursor.fetchone()[0]
            print(f"\n[stories] Row Count: {count}")
            
            # 4. Sample Data
            if count > 0:
                print("\n[stories] First Row Sample:")
                cursor.execute("SELECT * FROM stories LIMIT 1")
                row = cursor.fetchone()
                print(row)
        else:
            print("\nError: 'stories' table missing!")

        # 5. Check 'characters' table
        if ('characters',) in tables:
            print("\n[characters] Row Count:")
            cursor.execute("SELECT COUNT(*) FROM characters")
            print(cursor.fetchone()[0])
        
        conn.close()
        print("\n--- Inspection Complete ---")

    except Exception as e:
        print(f"SQLite Error: {e}")

if __name__ == "__main__":
    inspect_db()
