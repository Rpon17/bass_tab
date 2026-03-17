from __future__ import annotations

import sqlite3

db_path: str = r"C:\bass_project\bass_back\main_server\var\index.db"

conn: sqlite3.Connection = sqlite3.connect(db_path)
try:
    rows: list[tuple[str]] = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
        """
    ).fetchall()

    print([row[0] for row in rows])
finally:
    conn.close()