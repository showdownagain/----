"""
FastAPI 应用入口 — MT5 Trading System Backend.
启动: uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 确保项目根目录在 Python Path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.database import init_db
from app.mt5_client import mt5_client
from app.services.tick_sync import tick_sync_service
from app.services.websocket_manager import ws_manager

# ═══════════════════════════════════════════════════════════════
# 日志
# ═══════════════════════════════════════════════════════════════
settings = get_settings()

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# 生命周期
# ═══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的初始化与清理"""
    # ---- STARTUP ----
    logger.info("=" * 50)
    logger.info("MT5 Trading System starting...")

    # 1. 初始化数据库（创建表）
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database init failed: {e}")

    # 2. 连接 MT5
    mt5_ok = mt5_client.connect()
    if mt5_ok:
        logger.info("MT5 connected successfully")
    else:
        logger.warning("MT5 NOT connected — open MT5 Terminal, log in, then restart backend")
        logger.warning("API will start but market endpoints will return errors")

    # 3. 设置 tick_sync 的 ws_manager 引用
    tick_sync_service.ws_manager = ws_manager

    # 4. 启动 Tick 同步（如果 MT5 已连接）
    if mt5_ok:
        await tick_sync_service.start(settings.allowed_symbols_list)
    else:
        logger.info("Tick sync skipped (MT5 not connected)")

    logger.info(f"MT5 Trading System ready — http://{settings.API_HOST}:{settings.API_PORT}")
    logger.info(f"API docs — http://{settings.API_HOST}:{settings.API_PORT}/docs")
    logger.info("=" * 50)

    yield  # ← 应用运行中

    # ---- SHUTDOWN ----
    logger.info("MT5 Trading System shutting down...")
    await tick_sync_service.stop()
    mt5_client.shutdown()
    logger.info("Shutdown complete")


# ═══════════════════════════════════════════════════════════════
# FastAPI App
# ═══════════════════════════════════════════════════════════════

app = FastAPI(
    title="MT5 Trading System",
    description="MetaTrader 5 自动交易与看盘系统 — REST API + WebSocket",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — 开发阶段允许所有来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════
# 注册路由
# ═══════════════════════════════════════════════════════════════

from fastapi.responses import HTMLResponse

from app.routers import health, market, account, positions, ws, atr

app.include_router(health.router)
app.include_router(market.router)
app.include_router(account.router)
app.include_router(positions.router)
app.include_router(ws.router)
app.include_router(atr.router)


# ═══════════════════════════════════════════════════════════════
# 根路径
# ═══════════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {
        "name": "MT5 Trading System",
        "version": "0.1.0",
        "docs": "/docs",
        "dashboard": "/dashboard",
        "health": "/api/health",
        "mt5_connected": mt5_client.is_connected,
        "tick_sync_running": tick_sync_service.is_running,
    }


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """直接返回看盘前端页面"""
    from pathlib import Path
    dashboard_path = Path(__file__).resolve().parent.parent.parent / "MT5 Dashboard Live.html"
    if dashboard_path.exists():
        return dashboard_path.read_text(encoding="utf-8")
    return HTMLResponse("<h1>Dashboard file not found</h1>", status_code=404)
