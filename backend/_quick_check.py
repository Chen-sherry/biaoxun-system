import pymysql, requests

# 1) bid_subscribe 表是否存在
conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='12345', database='bid_info', charset='utf8mb4')
cur = conn.cursor()
cur.execute("SHOW TABLES LIKE 'bid_subscribe'")
exists = cur.fetchone()
print(f"bid_subscribe 表: {'存在' if exists else '不存在'}")
if not exists:
    print("需要 CREATE TABLE！")
    cur.close(); conn.close()
    raise SystemExit

# 2) 字段
cur.execute("DESCRIBE bid_subscribe")
for r in cur.fetchall(): print(f"  {r[0]:20s} {r[1]}")
cur.close(); conn.close()

# 3) register 接口
BASE = "http://127.0.0.1:8000"
try:
    r = requests.post(f"{BASE}/api/v1/auth/register", json={"username": "test_user_01", "password": "123456", "nickname": "测试"}, timeout=5)
    print(f"\nregister test_user_01: {r.status_code} {r.json()}")
except Exception as e:
    print(f"\nregister fail: {e}")

# 4) subscribe 接口（需登录）
try:
    r2 = requests.post(f"{BASE}/api/v1/auth/login", json={"username": "test_user_01", "password": "123456"}, timeout=5)
    token = r2.json()["access_token"]
    h = {"Authorization": "Bearer " + token}
    r3 = requests.post(f"{BASE}/api/v1/subscribes", json={"keyword": "培训 团建", "frequency": "daily"}, headers=h, timeout=5)
    print(f"subscribe create: {r3.status_code} {r3.json()}")
    r4 = requests.get(f"{BASE}/api/v1/subscribes", headers=h, timeout=5)
    print(f"subscribe list:   {r4.status_code} {r4.json()}")
except Exception as e:
    print(f"subscribe test fail: {e}")
