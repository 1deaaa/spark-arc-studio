import sqlite3
conn = sqlite3.connect('data/users.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
has_feedback = any('feedback' in str(t).lower() for t in tables)
print(f"Has feedback table: {has_feedback}")
print(f"All tables: {tables}")
conn.close()
