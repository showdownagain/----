"""
账户路由 — 账户信息。
"""
import time
from fastapi import APIRouter
from app.mt5_client import mt5_client

router = APIRouter(tags=["账户"])


@router.get("/api/account")
def get_account():
    """获取账户信息"""
    try:
        account = mt5_client.account_info()
        return {
            "status": "ok",
            "data": {
                "login": account.get("login"),
                "server": account.get("server"),
                "name": account.get("name", ""),
                "currency": account.get("currency"),
                "leverage": account.get("leverage"),
                "balance": account.get("balance"),
                "equity": account.get("equity"),
                "margin": account.get("margin"),
                "margin_free": account.get("margin_free"),
                "margin_level": account.get("margin_level"),
                "profit": account.get("profit"),
                "credit": account.get("credit", 0),
                "trade_mode": account.get("trade_mode"),
                "trade_allowed": account.get("trade_allowed", True),
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        }
    except RuntimeError as e:
        return {"status": "error", "detail": str(e), "error_code": "MT5_ACCOUNT_FAILED"}
