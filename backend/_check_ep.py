import requests
BASE = "http://127.0.0.1:8000"
r = requests.post(f"{BASE}/api/v1/auth/login", json={"username":"admin","password":"admin123"})
h = {"Authorization": "Bearer "+r.json()["access_token"]}

endpoints = [
    ("member packages", "GET", "/api/v1/member-packages"),
    ("member orders",   "GET", "/api/v1/member-orders?page=1&page_size=50"),
    ("dict notice-types","GET", "/api/v1/dicts/notice-types"),
    ("admin users",     "GET", "/api/v1/admin/users?page=1&page_size=50"),
    ("admin data-clean run","POST", "/api/v1/admin/data-clean/run"),
    ("admin data-clean status","GET", "/api/v1/admin/data-clean/status"),
]
for name, method, url in endpoints:
    try:
        resp = requests.request(method, f"{BASE}{url}", headers=h, timeout=5)
        print(f"{resp.status_code:3d} {name:30s} {resp.text[:80]}")
    except Exception as e:
        print(f"ERR  {name:30s} {e}")
