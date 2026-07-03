import sqlite3
conn = sqlite3.connect('backend/users.db')
rows = conn.execute('''
SELECT * FROM sessions
''').fetchall()

print(rows)
