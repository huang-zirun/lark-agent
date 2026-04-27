import json
import sqlite3

conn = sqlite3.connect('data/devflow.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT id, artifact_type, content_summary, content
    FROM artifact
    WHERE run_id = '88a6fd3796e249ef890fc46b3b0a0b5b'
""")

rows = cursor.fetchall()
print(f"Found {len(rows)} artifacts:")
for row in rows:
    artifact_id, artifact_type, summary, content = row
    print(f"\n--- {artifact_type} ({artifact_id}) ---")
    print(f"Summary: {summary}")
    if content:
        content_dict = json.loads(content)
        print(f"Content keys: {content_dict.keys()}")
        print(f"Content preview: {json.dumps(content_dict, indent=2)[:500]}...")

conn.close()
