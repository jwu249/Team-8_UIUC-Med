import requests
from collections import Counter

url = "https://uiucmed.pythonanywhere.com/api/services/"
payload = requests.get(url, timeout=10).json()
rows = payload.get("results", [])

print("total rows:", len(rows))
print("top locations:")
for loc, n in Counter(r["location"] for r in rows).most_common(5):
    print(f"  {loc}: {n}")

required = sum(1 for r in rows if r["appointments_required"])
optional = len(rows) - required
print("appointments required:", required)
print("walk-in/optional:", optional)