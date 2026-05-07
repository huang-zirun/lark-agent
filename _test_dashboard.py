import subprocess
import time

time.sleep(2)

# Test the API endpoints that the dashboard calls
endpoints = [
    "/api/v1/metrics/overview",
    "/api/v1/metrics/recent-runs?limit=20",
    "/api/v1/metrics/active-run",
    "/api/v1/metrics/stage-stats",
    "/api/v1/metrics/token-usage",
]

for ep in endpoints:
    result = subprocess.run(
        ["curl", "-s", "-m", "10", "-w", "\nHTTP_STATUS:%{http_code}", f"http://127.0.0.1:8080{ep}"],
        capture_output=True, text=True, timeout=15
    )
    # Find HTTP status
    lines = result.stdout.rsplit("\nHTTP_STATUS:", 1)
    status = lines[1] if len(lines) > 1 else "unknown"
    body = lines[0][:200]
    print(f"{ep}: HTTP {status}")
    print(f"  {body}\n")
