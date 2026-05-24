import sqlite3
conn = sqlite3.connect('backend/cricket.db')
rows = conn.execute('''
SELECT d.bowler, COUNT(DISTINCT d.match_id) AS finals,
  ROUND(SUM(d.runs_total) * 6.0 / COUNT(CASE WHEN d.extras_type IS NULL OR d.extras_type != 'wides' THEN 1 END), 2) AS economy
FROM deliveries d
JOIN matches m ON d.match_id = m.match_id
WHERE m.match_number = (SELECT MAX(match_number) FROM matches m2 WHERE m2.season = m.season)
GROUP BY d.bowler
HAVING COUNT(DISTINCT d.match_id) >= 2
ORDER BY economy ASC LIMIT 10
''').fetchall()

print(rows)
