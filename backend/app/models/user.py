"""用户、角色、权限 RBAC 模型"""
from sqlalchemy import (
    Column, Integer, String, Boolean, Text, DateTime, ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import TimestampMixin


class SysUser(TimestampMixin, Base):
    __tablename__ = "sys_user"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    username = Column(String(64), nullable=False, unique=True, comment="登录账号")
    password_hash = Column(String(255), nullable=False, comment="bcrypt 密码")
    nickname = Column(String(64), nullable=True, comment="昵称")
    real_name = Column(String(64), nullable=True, comment="真实姓名")
    phone = Column(String(20), nullable=True, index=True, comment="手机号")
    email = Column(String(128), nullable=True, index=True, comment="邮箱")
    avatar = Column(String(255), nullable=True, comment="头像 URL")
    company = Column(String(128), nullable=True, comment="所属企业")
    is_admin = Column(Boolean, nullable=False, default=False, comment="是否超级管理员")
    status = Column(Integer, nullable=False, default=1, comment="1 启用 0 禁用")
    last_login_at = Column(DateTime, nullable=True, comment="最后登录时间")
    remark = Column(Text, nullable=True, comment="备注")

    roles = relationship("SysRole", secondary="sys_user_role", back_populates="users")


class SysRole(TimestampMixin, Base):
    __tablename__ = "sys_role"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, unique=True, comment="角色名称")
    code = Column(String(64), nullable=False, unique=True, comment="角色编码")
    description = Column(String(255), nullable=True, comment="描述")
    status = Column(Integer, nullable=False, default=1, comment="1 启用 0 禁用")

    users = relationship("SysUser", secondary="sys_user_role", back_populates="roles")
    permissions = relationship(
        "SysPermission", secondary="sys_role_permission", back_populates="roles"
    )


class SysPermission(TimestampMixin, Base):
    """权限节点：菜单、按钮、接口统一管理"""
    __tablename__ = "sys_permission"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_id = Column(Integer, ForeignKey("sys_permission.id"), nullable=True, comment="父级")
    name = Column(String(64), nullable=False, comment="权限名称")
    code = Column(String(128), nullable=False, comment="权限编码，如 bid:info:add")
    type = Column(Integer, nullable=False, default=1, comment="1 菜单 2 按钮 3 接口")
    path = Column(String(255), nullable=True, comment="前端路由或接口路径")
    icon = Column(String(64), nullable=True, comment="菜单图标")
    sort = Column(Integer, nullable=False, default=0, comment="排序")
    status = Column(Integer, nullable=False, default=1, comment="1 启用 0 禁用")

    roles = relationship(
        "SysRole", secondary="sys_role_permission", back_populates="permissions"
    )


class SysUserRole(Base):
    """用户-角色关联"""
    __tablename__ = "sys_user_role"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uk_user_role"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("sys_role.id"), nullable=False)


class SysRolePermission(Base):
    """角色-权限关联"""
    __tablename__ = "sys_role_permission"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uk_role_perm"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("sys_role.id"), nullable=False)
    permission_id = Column(Integer, ForeignKey("sys_permission.id"), nullable=False)
