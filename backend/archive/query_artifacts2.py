import json
import sqlite3

conn = sqlite3.connect('data/devflow.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 获取 pipeline run 信息
cursor.execute("""
    SELECT id, status, current_stage_key, requirement_text
    FROM pipeline_run
    WHERE id = '88a6fd3796e249ef890fc46b3b0a0b5b'
""")
row = cursor.fetchone()
print(f"Pipeline Run: {row['id']}")
print(f"Status: {row['status']}")
print(f"Current Stage: {row['current_stage_key']}")
print(f"Requirement: {row['requirement_text'][:100]}...")

# 获取所有 artifacts
cursor.execute("""
    SELECT id, artifact_type, stage_key, content_summary, content
    FROM artifact
    WHERE run_id = '88a6fd3796e249ef890fc46b3b0a0b5b'
    ORDER BY created_at
""")

rows = cursor.fetchall()
print(f"\n{'='*60}")
print(f"Found {len(rows)} artifacts:")
print(f"{'='*60}")

for row in rows:
    artifact_id = row['id']
    artifact_type = row['artifact_type']
    stage_key = row['stage_key']
    summary = row['content_summary']
    content = row['content']

    print(f"\n{'-'*60}")
    print(f"Artifact: {artifact_type}")
    print(f"Stage: {stage_key}")
    print(f"ID: {artifact_id}")
    print(f"Summary: {summary}")

    if content:
        try:
            content_dict = json.loads(content)
            print(f"\nContent:")
            print(json.dumps(content_dict, ensure_ascii=False, indent=2))
        except json.JSONDecodeError:
            print(f"\nContent (raw): {content[:500]}")

conn.close()
