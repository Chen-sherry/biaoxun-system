"""API v1 路由聚合"""
from fastapi import APIRouter

from app.api.v1 import auth, bid, source, subscribe, member, member_order, dict_data, crawl, admin_user, ai, stats, portal, admin_data_clean, admin_push, admin_ai

api_v1 = APIRouter(prefix="/api/v1")

api_v1.include_router(portal.router, tags=["门户公开接口"])
api_v1.include_router(auth.router, tags=["认证"])
api_v1.include_router(bid.router, tags=["标讯"])
api_v1.include_router(source.router, tags=["采集源"])
api_v1.include_router(subscribe.router, tags=["订阅"])
api_v1.include_router(member.router, tags=["会员套餐"])
api_v1.include_router(member_order.router, tags=["会员订单"])
api_v1.include_router(dict_data.router, tags=["字典"])
api_v1.include_router(crawl.router, tags=["爬虫任务"])
api_v1.include_router(admin_user.router, tags=["后台用户管理"])
api_v1.include_router(ai.router, tags=["AI 智能匹配"])
api_v1.include_router(stats.router, tags=["统计"])
api_v1.include_router(admin_data_clean.router, tags=["后台：数据清洗"])
api_v1.include_router(admin_push.router, tags=["后台：推送管理"])
api_v1.include_router(admin_ai.router, tags=["后台：AI 设置"])
