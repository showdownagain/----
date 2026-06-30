"""
开发环境启动脚本。
用法:
    python run.py                # 默认 127.0.0.1:8000
    python run.py --port 9000    # 自定义端口
    python run.py --reload       # 开启热重载
"""
import sys
import argparse
from pathlib import Path

# 确保 backend/ 在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn
from app.config import get_settings

settings = get_settings()


def main():
    parser = argparse.ArgumentParser(description="MT5 Trading System Backend")
    parser.add_argument("--host", default=settings.API_HOST, help="监听地址 (默认 127.0.0.1)")
    parser.add_argument("--port", type=int, default=settings.API_PORT, help="监听端口 (默认 8000)")
    parser.add_argument("--reload", action="store_true", help="开启热重载")
    args = parser.parse_args()

    mt5_status = "Connected" if settings.MT5_LOGIN else "NOT CONFIGURED"
    trade_status = "DISABLED" if not settings.ENABLE_REAL_TRADING else "ENABLED"
    print(f"""
============================================================
        MT5 Trading System Backend v0.1.0
============================================================
  API:      http://{args.host}:{args.port}
  Docs:     http://{args.host}:{args.port}/docs
  Health:   http://{args.host}:{args.port}/api/health
------------------------------------------------------------
  MT5:      {mt5_status}
  Database: {settings.DATABASE_URL}
  Trading:  {trade_status}
============================================================
""")

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
