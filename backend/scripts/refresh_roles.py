# -*- coding: utf-8 -*-
"""
角色体系调整脚本：合并旧 editor/auditor/ops → admin_role，新增 bidder
member / guest 已在表里，直接用。

执行前先备份：mysqldump -u root -p12345 bid_info > bid_info_backup.sql
"""
import pymysql

conn = pymysql.connect(
    host="127.0.0.1", port=3306, user="root", password="12345",
    database="bid_info", charset="utf8mb4",
)
cur = conn.cursor()

# ---- 1) editor(id=2) 改名为 admin_role ----
cur.execute("UPDATE sys_role SET code='admin_role', name='管理员', description='标讯编辑/审核/运营' WHERE id=2")

# ---- 2) 合并 auditor(id=3) + ops(id=4) 的权限到 admin_role(id=2) ----
cur.execute(
    "INSERT IGNORE INTO sys_role_permission (role_id, permission_id) "
    "SELECT 2, permission_id FROM sys_role_permission WHERE role_id IN (3, 4)"
)
merged = cur.rowcount

# ---- 3) 删除 auditor / ops ----
cur.execute("DELETE FROM sys_role_permission WHERE role_id IN (3, 4)")
cur.execute("DELETE FROM sys_role WHERE id IN (3, 4)")

# ---- 4) 新增 bidder ----
cur.execute(
    "INSERT INTO sys_role (code, name, description, created_at) "
    "VALUES (%s, %s, %s, NOW()) "
    "ON DUPLICATE KEY UPDATE name=VALUES(name)",
    ("bidder", "投标用户", "企业投标方：订阅标讯、使用AI匹配、收藏")
)

conn.commit()

# ---- 5) 打印结果 ----
cur.execute(
    "SELECT r.code, r.name, COUNT(rp.permission_id) AS perm_count "
    "FROM sys_role r LEFT JOIN sys_role_permission rp ON r.id=rp.role_id "
    "GROUP BY r.id ORDER BY perm_count DESC"
)
print("\n=== 角色体系调整完成 ===")
print(f"合并权限数: {merged}")
for row in cur.fetchall():
    print(f"  {row[0]:15s} {row[1]:15s} 权限={row[2]}")

cur.close()
conn.close()
print("\n✅ 完成！")
