import sqlite3

conn = sqlite3.connect(r"C:\bass_project\bass_back\main_server\var\index.db")
rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(rows)