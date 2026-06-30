# MT5 自动交易与看盘系统 — 产品需求文档 (PRD)

> **版本:** v1.0  
> **日期:** 2026-06-30  
> **状态:** 草案  
> **作者:** —  
> **关联文档:** `方案.md`（技术实施方案）、`MT5 Trading Dashboard.html`（前端原型）

---

## 目录

1. [产品概述](#1-产品概述)
2. [用户角色](#2-用户角色)
3. [功能需求](#3-功能需求)
4. [API 接口定义](#4-api-接口定义)
5. [WebSocket 实时推送](#5-websocket-实时推送)
6. [数据库设计](#6-数据库设计)
7. [后端架构与模块设计](#7-后端架构与模块设计)
8. [策略引擎](#8-策略引擎)
9. [风控模块](#9-风控模块)
10. [告警与消息推送](#10-告警与消息推送)
11. [非功能需求](#11-非功能需求)
12. [开发阶段规划](#12-开发阶段规划)
13. [附录](#13-附录)

---

## 1. 产品概述

### 1.1 产品定位

MT5 自动交易与看盘系统是一套运行于 Windows 11 本地环境的交易辅助工具。系统以 **MetaTrader 5 Terminal** 为桥梁，通过 Python 官方库获取实时行情与账户数据，经 FastAPI 后端分发至前端看盘控制台，并内置策略引擎、风控模块和消息告警能力。

### 1.2 核心价值

| 痛点 | 解决方案 |
|------|---------|
| MT5 自带界面信息分散、无法定制 | 统一 Dashboard 汇总行情/账户/持仓/策略/告警 |
| 手动盯盘效率低 | 策略引擎自动扫描多品种、多周期，生成交易信号 |
| 手动下单易出错 | 风控模块 9 道检查 + 一键停止保护 |
| 无法及时获知交易动态 | Telegram/飞书/钉钉多渠道实时告警 |
| 策略回测与实盘脱节 | 同一套代码从 Demo→模拟→小资金→实盘渐进式上线 |

### 1.3 系统架构总览

```text
┌──────────────────────────────────────────────────────────┐
│                    Windows 11 / Windows Server            │
│                                                          │
│  ┌──────────────────┐    ┌─────────────────────────┐     │
│  │ MetaTrader 5     │◄──►│ Python MT5 Bridge       │     │
│  │ Terminal         │    │ (MetaTrader5 官方库)     │     │
│  │ (券商账户登录)    │    └───────────┬─────────────┘     │
│  └──────────────────┘                │                   │
│                                      ▼                   │
│  ┌──────────────────────────────────────────────────┐    │
│  │              FastAPI 后端 (:8000)                  │    │
│  │  ┌─────────┐ ┌──────────┐ ┌──────────────────┐   │    │
│  │  │ REST API│ │WebSocket │ │ 策略引擎 + 风控   │   │    │
│  │  └─────────┘ └──────────┘ └──────────────────┘   │    │
│  │  ┌──────────────────────────────────────────┐    │    │
│  │  │         SQLite 数据库 (trading.db)        │    │    │
│  │  └──────────────────────────────────────────┘    │    │
│  └───────────────────┬──────────────────────────────┘    │
│                      │                                   │
│  ┌───────────────────▼──────────────────────────────┐    │
│  │      Vue 3 / React 前端 (:5173)                   │    │
│  │      Lightweight Charts · 实时看盘控制台           │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │  外部通知: Telegram · 飞书 · 钉钉 · Email         │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

### 1.4 技术选型

| 层级 | 技术 | 版本要求 | 说明 |
|------|------|---------|------|
| 交易接口 | MetaTrader5 Python | ≥5.0.45 | MT5 官方 Python 库，进程间通信 |
| 后端框架 | FastAPI | ≥0.110 | REST API + WebSocket |
| ASGI 服务器 | Uvicorn | ≥0.29 | 生产级 ASGI |
| 前端框架 | Vue 3 + Vite（或 React + Vite） | Vue≥3.4 / React≥18 | SPA 单页应用 |
| 图表库 | Lightweight Charts | ≥4.2 | TradingView 官方开源 |
| HTTP 客户端 | Axios | ≥1.7 | 前端 API 请求 |
| 数据库 | SQLite（可升级至 PostgreSQL） | — | 本地嵌入式 |
| ORM | SQLAlchemy | ≥2.0 | Python 数据库抽象 |
| 任务调度 | APScheduler | ≥3.10 | 策略定时扫描 |
| 数据科学 | Pandas / NumPy | ≥2.0 / ≥1.26 | K线数据处理 |
| 技术指标 | ta (optional) | ≥0.11 | 内置指标计算库 |
| 消息推送 | requests (HTTP) | ≥2.31 | 调用飞书/钉钉/Telegram Webhook |
| 运行环境 | Python + Node.js | 3.11/3.12 + LTS | Windows 11 |

---

## 2. 用户角色

| 角色 | 描述 | 核心需求 |
|------|------|---------|
| **交易员（唯一用户）** | 本地单用户，管理自有资金 | 看盘、策略信号、手动/半自动下单、风控保护 |

> 第一版不做多用户权限系统。所有功能面向单一交易员，运行于 `127.0.0.1` 本地环境。

---

## 3. 功能需求

### 3.1 功能模块总览

```text
MT5 Trading System
│
├── M1. 系统连接
│   ├── MT5 Terminal 初始化与登录状态检测
│   ├── 连接健康检查 (Health Check)
│   └── 断线自动重连（含退避策略）
│
├── M2. 行情数据
│   ├── 实时 Tick 数据获取
│   ├── 历史 K 线数据获取（支持多周期）
│   ├── 品种信息查询（点差、合约规格）
│   └── Market Watch 品种列表
│
├── M3. 账户信息
│   ├── 账户基本信息（余额/净值/保证金/可用保证金）
│   ├── 保证金水平百分比
│   └── 浮动盈亏汇总
│
├── M4. 持仓管理
│   ├── 当前持仓列表（含止损止盈）
│   ├── 持仓盈亏实时计算
│   └── 持仓快照历史
│
├── M5. 订单管理
│   ├── 订单预检 (Order Check)
│   ├── 市价单发送
│   ├── 挂单发送（Limit/Stop）
│   ├── 订单修改（SL/TP 调整）
│   ├── 平仓（全部/部分）
│   └── 历史订单查询
│
├── M6. 策略引擎
│   ├── 策略注册与生命周期管理（启动/停止）
│   ├── 多策略并行运行
│   ├── 多品种/多周期扫描
│   ├── 统一信号格式输出
│   └── 策略参数热更新
│
├── M7. 风控模块
│   ├── 9 道风控检查链
│   ├── 真实交易开关
│   └── 一键紧急停止
│
├── M8. 消息告警
│   ├── Telegram Bot 推送
│   ├── 飞书 Webhook 推送
│   ├── 钉钉 Webhook 推送
│   └── Email 推送（可选）
│
├── M9. 数据持久化
│   ├── 策略信号记录
│   ├── 订单记录
│   ├── 持仓快照
│   ├── 告警日志
│   └── 系统运行日志
│
└── M10. 前端看盘控制台
    ├── 顶部状态栏（连接状态/账户/服务器/时间/延迟）
    ├── K 线图（蜡烛图 + MA + 成交量 + 周期切换）
    ├── 账户面板（余额/净值/保证金/浮动盈亏）
    ├── 持仓列表（品种/方向/手数/价格/盈亏）
    ├── 策略信号页（信号历史表）
    ├── 策略引擎页（策略卡片 + 启停控制）
    ├── 订单记录页（历史订单表）
    └── 告警日志页（告警时间线）
```

### 3.2 前端页面布局

参见原型文件 `MT5 Trading Dashboard.html`，布局规范如下：

```text
┌─────────────────────────────────────────────────────────┐
│  顶部状态栏 (48px)                                [⟳] [⚙] │
│  ● MT5 Trading │ 账户 88609174 │ ICMarkets-Demo │ 已连接  │
├────────────────────────────┬────────────────────────────┤
│                            │  账户概况                    │
│                            │  余额      $10,245.80       │
│    K 线图 (XAUUSD)         │  净值      $10,378.25       │
│    ┌─ MA20 (橙)           │  保证金    $512.30          │
│    ┌─ MA60 (紫)           │  可用      $9,865.95        │
│    ██ 成交量               │  浮动盈亏  +$132.45         │
│                            ├────────────────────────────┤
│  [1m][5m][15m][1H][4H][日] │  当前持仓 (2)               │
│                            │  品种  方向 手数  开仓  盈亏  │
│                            │  XAUUSD BUY 0.05  ... +61  │
│                            │  EURUSD SELL 0.10 ... +74  │
├────────────────────────────┴────────────────────────────┤
│  [策略信号] [策略引擎] [订单记录] [告警日志]              │
│  ┌─────────────────────────────────────────────────────┐│
│  │ 时间  品种  周期 策略  信号  价格  置信度  原因       ││
│  │ 15:28 XAUUSD M5 MACross BUY 2350 82%  MA20上穿MA60 ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
                                    [⏹ 一键停止]
```

### 3.3 前端状态管理

| 状态 | 来源 | 更新频率 | 显示位置 |
|------|------|---------|---------|
| MT5 连接状态 | `GET /api/health` | 每 5s 轮询 | 顶部状态栏 |
| 实时报价 | `WS /ws/ticks/{symbol}` | ≤1s 推送 | 图表工具栏 |
| K 线数据 | `GET /api/rates/{symbol}` | 周期结束更新 | 图表区 |
| 账户信息 | `GET /api/account` | 每 3s 轮询 | 右侧账户面板 |
| 持仓列表 | `GET /api/positions` | 每 3s 轮询 | 右侧持仓面板 |
| 策略状态 | `GET /api/strategies` | 每 10s 轮询 | 策略引擎页 |
| 信号列表 | `GET /api/signals` | 每 5s 轮询 | 策略信号页 |
| 订单记录 | `GET /api/orders` | 每 5s 轮询 | 订单记录页 |
| 告警日志 | `WS /ws/events` | 事件驱动 | 告警日志页 |
| 当前时间 | 客户端 `Date` | 每秒 | 顶部状态栏 |

---

## 4. API 接口定义

### 4.1 通用约定

#### Base URL

```text
http://127.0.0.1:8000
```

#### 通用响应格式

所有成功响应包裹在 `data` 字段中：

```json
{
  "status": "ok",
  "data": { ... },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

所有错误响应返回 `detail` 字段：

```json
{
  "status": "error",
  "detail": "MT5 connection failed: Initialize error",
  "error_code": "MT5_CONNECT_FAILED",
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

#### HTTP 状态码

| 状态码 | 含义 |
|--------|------|
| 200 | 请求成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 422 | 请求体验证失败（Pydantic） |
| 500 | 服务器内部错误 |
| 503 | MT5 连接不可用 |

#### 通用请求头

```http
Content-Type: application/json
Accept: application/json
```

---

### 4.2 系统接口

#### 4.2.1 健康检查

```http
GET /api/health
```

**响应示例：**

```json
{
  "status": "ok",
  "data": {
    "mt5_connected": true,
    "mt5_account": "88609174",
    "mt5_server": "ICMarkets-Demo",
    "uptime_seconds": 3724,
    "python_version": "3.12.0",
    "active_strategies": 3,
    "open_positions": 2,
    "pending_orders": 0,
    "last_tick_time": "2026-06-30T15:29:58.000Z"
  },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

#### 4.2.2 获取系统配置

```http
GET /api/config
```

**响应：**

```json
{
  "status": "ok",
  "data": {
    "default_symbol": "XAUUSD",
    "default_lot": 0.01,
    "max_lot": 0.05,
    "max_positions": 3,
    "max_daily_loss": 100.0,
    "enable_real_trading": false,
    "allowed_symbols": ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"],
    "trading_hours": { "start": "00:00", "end": "23:59" },
    "max_spread_pips": { "XAUUSD": 5.0, "EURUSD": 2.0 }
  },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

---

### 4.3 行情接口

#### 4.3.1 获取实时 Tick

```http
GET /api/tick/{symbol}
```

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| symbol | string | 是 | 品种代码，如 `XAUUSD` |

**响应示例：**

```json
{
  "status": "ok",
  "data": {
    "symbol": "XAUUSD",
    "bid": 2350.05,
    "ask": 2350.19,
    "spread": 0.14,
    "last": 2350.12,
    "volume": 125,
    "time": "2026-06-30T15:30:00.000Z",
    "digits": 2,
    "spread_pips": 1.4
  },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

**错误响应：**

```json
{
  "status": "error",
  "detail": "Symbol 'INVALID' not found in Market Watch",
  "error_code": "SYMBOL_NOT_FOUND",
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

#### 4.3.2 获取多品种 Tick（批量）

```http
GET /api/ticks?symbols=XAUUSD,EURUSD,GBPUSD
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| symbols | string | 是 | 逗号分隔的品种列表，最多 20 个 |

**响应：**

```json
{
  "status": "ok",
  "data": [
    { "symbol": "XAUUSD", "bid": 2350.05, "ask": 2350.19, "spread": 0.14, "time": "..." },
    { "symbol": "EURUSD", "bid": 1.0781, "ask": 1.0783, "spread": 0.00002, "time": "..." }
  ],
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

#### 4.3.3 获取历史 K 线

```http
GET /api/rates/{symbol}?timeframe=M5&count=200&from=2026-06-29T00:00:00&to=2026-06-30T15:30:00
```

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| symbol | string | 是 | 品种代码 |

**查询参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| timeframe | string | 否 | M5 | K线周期：`M1`/`M5`/`M15`/`M30`/`H1`/`H4`/`D1`/`W1`/`MN1` |
| count | int | 否 | 200 | 返回 K 线数量（最大 5000） |
| from | string(ISO 8601) | 否 | — | 起始时间 |
| to | string(ISO 8601) | 否 | — | 结束时间 |

> `count` 与 `from`/`to` 互斥：传 `from`/`to` 时忽略 `count`。

**响应示例：**

```json
{
  "status": "ok",
  "data": {
    "symbol": "XAUUSD",
    "timeframe": "M5",
    "count": 200,
    "rates": [
      {
        "time": "2026-06-30T15:25:00",
        "open": 2349.50,
        "high": 2351.20,
        "low": 2348.80,
        "close": 2350.10,
        "tick_volume": 342,
        "spread": 2,
        "real_volume": 0
      },
      {
        "time": "2026-06-30T15:30:00",
        "open": 2350.10,
        "high": 2351.80,
        "low": 2349.60,
        "close": 2350.12,
        "tick_volume": 287,
        "spread": 2,
        "real_volume": 0
      }
    ]
  },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

#### 4.3.4 获取品种信息

```http
GET /api/symbol/{symbol}
```

**响应：**

```json
{
  "status": "ok",
  "data": {
    "symbol": "XAUUSD",
    "description": "Gold vs US Dollar",
    "digits": 2,
    "point": 0.01,
    "trade_contract_size": 100,
    "volume_min": 0.01,
    "volume_max": 50,
    "volume_step": 0.01,
    "swap_long": -3.5,
    "swap_short": 1.2,
    "spread": 2,
    "trade_mode": 4
  },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

---

### 4.4 账户接口

#### 4.4.1 获取账户信息

```http
GET /api/account
```

**响应：**

```json
{
  "status": "ok",
  "data": {
    "login": 88609174,
    "server": "ICMarkets-Demo",
    "name": "Demo Account",
    "currency": "USD",
    "leverage": 500,
    "balance": 10245.80,
    "equity": 10378.25,
    "margin": 512.30,
    "margin_free": 9865.95,
    "margin_level": 2025.48,
    "profit": 132.45,
    "credit": 0.0,
    "trade_mode": 0,
    "trade_allowed": true
  },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| balance | float | 账户余额（不含浮动盈亏） |
| equity | float | 净值 = balance + floating P&L |
| margin | float | 已用保证金 |
| margin_free | float | 可用保证金 = equity - margin |
| margin_level | float | 保证金水平百分比 = (equity / margin) × 100 |
| profit | float | 当前浮动盈亏 |

---

### 4.5 持仓接口

#### 4.5.1 获取当前持仓

```http
GET /api/positions
GET /api/positions?symbol=XAUUSD
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| symbol | string | 否 | 按品种筛选 |

**响应：**

```json
{
  "status": "ok",
  "data": {
    "count": 2,
    "total_profit": 135.60,
    "positions": [
      {
        "ticket": 12345678,
        "symbol": "XAUUSD",
        "type": "BUY",
        "volume": 0.05,
        "price_open": 2337.80,
        "price_current": 2350.12,
        "sl": 2330.00,
        "tp": 2365.00,
        "profit": 61.60,
        "swap": -0.15,
        "commission": 0.0,
        "comment": "python strategy buy",
        "time_open": "2026-06-30T14:55:00",
        "magic": 20260101
      },
      {
        "ticket": 12345679,
        "symbol": "EURUSD",
        "type": "SELL",
        "volume": 0.10,
        "price_open": 1.0856,
        "price_current": 1.0782,
        "sl": 1.0900,
        "tp": 1.0720,
        "profit": 74.00,
        "swap": -0.30,
        "commission": 0.0,
        "comment": "macd strategy sell",
        "time_open": "2026-06-30T14:30:00",
        "magic": 20260102
      }
    ]
  },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

---

### 4.6 订单接口

#### 4.6.1 订单预检

```http
POST /api/orders/check
```

**请求体：**

```json
{
  "symbol": "XAUUSD",
  "action": "BUY",
  "volume": 0.05,
  "order_type": "MARKET",
  "price": 0.0,
  "sl": 2330.00,
  "tp": 2365.00,
  "deviation": 20,
  "comment": "python strategy buy"
}
```

**字段说明：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| symbol | string | 是 | 品种代码 |
| action | string | 是 | `BUY` / `SELL` / `CLOSE_BUY` / `CLOSE_SELL` |
| volume | float | 是 | 手数（须为品种 `volume_step` 的整数倍） |
| order_type | string | 是 | `MARKET` / `LIMIT` / `STOP` |
| price | float | 条件 | 挂单价格（市价单填 0） |
| sl | float | 否 | 止损价 |
| tp | float | 否 | 止盈价 |
| deviation | int | 否 | 最大滑点（默认 20） |
| comment | string | 否 | 订单备注 |

**成功响应：**

```json
{
  "status": "ok",
  "data": {
    "check_passed": true,
    "order_check_result": {
      "retcode": 0,
      "balance": 10245.80,
      "equity": 10378.25,
      "margin": 512.30,
      "margin_free": 9865.95,
      "margin_level": 2025.48,
      "volume": 0.05,
      "price": 2350.12,
      "bid": 2350.05,
      "ask": 2350.19,
      "profit": 0.0,
      "margin_initial": 235.01,
      "margin_maintenance": 117.51
    },
    "risk_check": {
      "passed": true,
      "checks": [
        { "rule": "real_trading_enabled", "passed": true, "message": "ok" },
        { "rule": "lot_within_limit", "passed": true, "message": "0.05 ≤ 0.05" },
        { "rule": "positions_within_limit", "passed": true, "message": "2 < 3" },
        { "rule": "symbol_no_duplicate", "passed": false, "message": "XAUUSD already has a BUY position" },
        { "rule": "spread_check", "passed": true, "message": "spread 1.4 ≤ 5.0" },
        { "rule": "daily_loss_check", "passed": true, "message": "daily loss $12.50 ≤ $100.00" },
        { "rule": "trading_hours_check", "passed": true, "message": "within trading hours" },
        { "rule": "duplicate_signal_check", "passed": true, "message": "no duplicate signal" }
      ],
      "failed_rules": ["symbol_no_duplicate"]
    }
  },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

**风控拒绝响应（200 OK，但 `check_passed: false`）：**

```json
{
  "status": "ok",
  "data": {
    "check_passed": false,
    "order_check_result": null,
    "risk_check": {
      "passed": false,
      "checks": [
        { "rule": "real_trading_enabled", "passed": false, "message": "ENABLE_REAL_TRADING=false" }
      ],
      "failed_rules": ["real_trading_enabled"]
    }
  },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

#### 4.6.2 发送订单

```http
POST /api/orders/send
```

**请求体：**（同 4.6.1 订单预检）

**执行流程：**

```text
接收到请求
  → 构建 MT5 request
  → 调用 risk_service.validate_order()  // 风控 9 道检查
  → 调用 mt5.order_check(request)        // MT5 预检
  → 调用 mt5.order_send(request)         // 真实下单
  → 保存 orders 表
  → WebSocket 广播 ORDER_UPDATE
  → 触发告警（Telegram/飞书/钉钉）
  → 返回 ticket
```

**成功响应：**

```json
{
  "status": "ok",
  "data": {
    "ticket": 12345680,
    "symbol": "XAUUSD",
    "type": "BUY",
    "volume": 0.05,
    "price": 2350.19,
    "sl": 2330.00,
    "tp": 2365.00,
    "comment": "python strategy buy",
    "retcode": 10009,
    "retcode_description": "DONE",
    "time": "2026-06-30T15:30:01.000Z"
  },
  "timestamp": "2026-06-30T15:30:01.000Z"
}
```

**错误响应：**

```json
{
  "status": "error",
  "detail": "Risk check failed",
  "error_code": "RISK_CHECK_FAILED",
  "data": {
    "failed_rules": ["symbol_no_duplicate"],
    "checks": [
      { "rule": "symbol_no_duplicate", "passed": false, "message": "XAUUSD already has a BUY position" }
    ]
  },
  "timestamp": "2026-06-30T15:30:01.000Z"
}
```

#### 4.6.3 获取订单历史

```http
GET /api/orders?limit=50&symbol=XAUUSD
```

**查询参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| limit | int | 否 | 50 | 返回数量（最大 500） |
| symbol | string | 否 | — | 按品种筛选 |
| status | string | 否 | — | `FILLED` / `CANCELED` / `REJECTED` |

**响应：**

```json
{
  "status": "ok",
  "data": {
    "count": 5,
    "orders": [
      {
        "id": 1,
        "symbol": "XAUUSD",
        "order_type": "BUY",
        "volume": 0.05,
        "price": 2337.80,
        "sl": 2330.00,
        "tp": 2365.00,
        "status": "FILLED",
        "mt5_order_id": 12345678,
        "comment": "MA Cross 信号",
        "created_at": "2026-06-30T14:55:00"
      }
    ]
  },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

#### 4.6.4 平仓

```http
POST /api/orders/close
```

**请求体：**

```json
{
  "ticket": 12345678,
  "volume": 0.05,
  "deviation": 20
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ticket | int | 是 | 持仓 ticket |
| volume | float | 否 | 平仓手数（默认全部平仓） |
| deviation | int | 否 | 最大滑点 |

---

### 4.7 策略接口

#### 4.7.1 获取所有策略

```http
GET /api/strategies
```

**响应：**

```json
{
  "status": "ok",
  "data": {
    "strategies": [
      {
        "name": "MA Cross",
        "display_name": "均线交叉策略",
        "symbol": "XAUUSD",
        "timeframe": "M5",
        "status": "running",
        "last_signal": "BUY",
        "last_signal_time": "2026-06-30T15:28:00",
        "params": { "fast": 20, "slow": 60 },
        "stats": {
          "signals_generated": 142,
          "buy_signals": 48,
          "sell_signals": 36,
          "hold_signals": 58,
          "uptime_minutes": 3724
        }
      }
    ]
  },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

#### 4.7.2 启动策略

```http
POST /api/strategies/{name}/start
```

**请求体（可选参数覆盖）：**

```json
{
  "params": {
    "fast": 20,
    "slow": 60
  }
}
```

**响应：**

```json
{
  "status": "ok",
  "data": {
    "name": "MA Cross",
    "status": "running",
    "started_at": "2026-06-30T15:30:00"
  },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

#### 4.7.3 停止策略

```http
POST /api/strategies/{name}/stop
```

**响应：**

```json
{
  "status": "ok",
  "data": {
    "name": "MA Cross",
    "status": "stopped",
    "stopped_at": "2026-06-30T15:30:00"
  },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

#### 4.7.4 更新策略参数（热更新）

```http
PATCH /api/strategies/{name}/params
```

**请求体：**

```json
{
  "params": { "fast": 10, "slow": 30 }
}
```

#### 4.7.5 获取策略信号历史

```http
GET /api/signals?limit=100&symbol=XAUUSD&strategy=MACross
```

**查询参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| limit | int | 否 | 100 | 返回数量（最大 1000） |
| symbol | string | 否 | — | 按品种筛选 |
| strategy | string | 否 | — | 按策略名称筛选 |
| signal | string | 否 | — | `BUY` / `SELL` / `HOLD` |

**响应：**

```json
{
  "status": "ok",
  "data": {
    "count": 7,
    "signals": [
      {
        "id": 142,
        "symbol": "XAUUSD",
        "timeframe": "M5",
        "strategy_name": "MA Cross",
        "signal": "BUY",
        "reason": "MA20 crossed above MA60",
        "price": 2350.12,
        "confidence": 0.82,
        "created_at": "2026-06-30T15:28:02"
      }
    ]
  },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

---

### 4.8 告警接口

#### 4.8.1 获取告警历史

```http
GET /api/alerts?limit=50&level=warn
```

**查询参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| limit | int | 否 | 50 | 返回数量 |
| level | string | 否 | — | `info` / `warn` / `error` / `success` |

**响应：**

```json
{
  "status": "ok",
  "data": {
    "count": 8,
    "alerts": [
      {
        "id": 8,
        "level": "success",
        "title": "策略信号",
        "message": "【MA Cross】XAUUSD M5 产生买入信号 @ 2350.12",
        "channel": "telegram,feishu",
        "status": "sent",
        "created_at": "2026-06-30T15:28:05"
      }
    ]
  },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

---

### 4.9 系统控制接口

#### 4.9.1 一键紧急停止

```http
POST /api/system/emergency-stop
```

**行为：**
1. 停止所有运行中的策略
2. 设置 `enable_real_trading = false`（内存级，重启恢复读取 `.env`）
3. 关闭所有 WebSocket 连接
4. 记录告警日志 `level=error`

**响应：**

```json
{
  "status": "ok",
  "data": {
    "strategies_stopped": 3,
    "real_trading_disabled": true,
    "websocket_connections_closed": 2,
    "mode": "SAFE_MODE"
  },
  "timestamp": "2026-06-30T15:30:00.000Z"
}
```

---

### 4.10 API 接口总览表

| 方法 | 路径 | 说明 | 模块 |
|------|------|------|------|
| `GET` | `/api/health` | 系统健康检查 | M1 |
| `GET` | `/api/config` | 获取系统配置 | M1 |
| `GET` | `/api/tick/{symbol}` | 获取实时 Tick | M2 |
| `GET` | `/api/ticks?symbols=` | 批量获取 Tick | M2 |
| `GET` | `/api/rates/{symbol}` | 获取历史 K 线 | M2 |
| `GET` | `/api/symbol/{symbol}` | 获取品种信息 | M2 |
| `GET` | `/api/account` | 获取账户信息 | M3 |
| `GET` | `/api/positions` | 获取当前持仓 | M4 |
| `POST` | `/api/orders/check` | 订单预检 | M5 |
| `POST` | `/api/orders/send` | 发送订单 | M5 |
| `POST` | `/api/orders/close` | 平仓 | M5 |
| `GET` | `/api/orders` | 获取订单历史 | M5 |
| `GET` | `/api/strategies` | 获取所有策略 | M6 |
| `POST` | `/api/strategies/{name}/start` | 启动策略 | M6 |
| `POST` | `/api/strategies/{name}/stop` | 停止策略 | M6 |
| `PATCH` | `/api/strategies/{name}/params` | 更新策略参数 | M6 |
| `GET` | `/api/signals` | 获取策略信号历史 | M6 |
| `GET` | `/api/alerts` | 获取告警历史 | M8 |
| `POST` | `/api/system/emergency-stop` | 一键紧急停止 | M7 |
| `WS` | `/ws/ticks/{symbol}` | Tick 实时推送 | M2 |
| `WS` | `/ws/events` | 事件实时推送 | M8 |
| `WS` | `/ws/ticks?symbols=XAUUSD,EURUSD` | 多品种 Tick 推送 | M2 |

---

## 5. WebSocket 实时推送

### 5.1 Tick 推送

```text
WS /ws/ticks/{symbol}
WS /ws/ticks?symbols=XAUUSD,EURUSD
```

**连接生命周期：**

```text
Client → Server: WebSocket 握手
Server → Client: { "type": "connected", "symbols": ["XAUUSD"], "timestamp": "..." }
Server → Client: { "type": "tick", "data": { ... } }   // 每 500ms-1s
Server → Client: { "type": "tick", "data": { ... } }   // 持续推送
Client → Server: { "type": "subscribe", "symbols": ["EURUSD"] }  // 动态订阅
Server → Client: { "type": "subscribed", "symbols": ["XAUUSD","EURUSD"] }
Client → Server: Close (1000)
```

**消息格式：**

```json
{
  "type": "tick",
  "data": {
    "symbol": "XAUUSD",
    "bid": 2350.05,
    "ask": 2350.19,
    "spread": 0.14,
    "last": 2350.12,
    "volume": 125,
    "time": "2026-06-30T15:30:00.500Z"
  }
}
```

**优化策略（第二版）：**
- 只在价格变化时推送（减少无效推送）
- 前端心跳检测（30s 无消息 → 自动重连）
- 指数退避重连（1s → 2s → 4s → 8s → 最大 30s）

### 5.2 事件推送

```text
WS /ws/events
```

**推送事件类型：**

| 事件类型 | 触发条件 | 优先级 |
|---------|---------|--------|
| `MT5_CONNECTED` | MT5 连接成功 | info |
| `MT5_DISCONNECTED` | MT5 断开 | error |
| `MT5_RECONNECTING` | MT5 重连中 | warn |
| `ORDER_CHECK_RESULT` | 订单预检完成 | info |
| `ORDER_SEND_RESULT` | 订单发送完成 | success/error |
| `ORDER_FILLED` | 订单成交 | success |
| `ORDER_REJECTED` | 订单被拒绝 | error |
| `STRATEGY_SIGNAL` | 策略产生信号 | info |
| `STRATEGY_STARTED` | 策略启动 | info |
| `STRATEGY_STOPPED` | 策略停止 | warn |
| `POSITION_UPDATED` | 持仓变化 | info |
| `ACCOUNT_UPDATED` | 账户变化 | info |
| `RISK_ALERT` | 风控告警 | error |
| `SYSTEM_ERROR` | 系统异常 | error |

**消息格式：**

```json
{
  "type": "STRATEGY_SIGNAL",
  "data": {
    "symbol": "XAUUSD",
    "timeframe": "M5",
    "strategy": "MA Cross",
    "signal": "BUY",
    "reason": "MA20 crossed above MA60",
    "price": 2350.12,
    "confidence": 0.82
  },
  "timestamp": "2026-06-30T15:28:02.000Z"
}
```

---

## 6. 数据库设计

### 6.1 数据库信息

| 属性 | 值 |
|------|-----|
| 引擎 | SQLite 3 |
| 文件路径 | `backend/data/trading.db` |
| ORM | SQLAlchemy 2.0 |
| 迁移工具 | Alembic（第二版引入） |
| 字符集 | UTF-8 |

### 6.2 ER 图

```text
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│ strategy_signals│     │     orders       │     │  positions_snapshot │
├─────────────────┤     ├──────────────────┤     ├─────────────────────┤
│ id (PK)         │     │ id (PK)          │     │ id (PK)             │
│ symbol          │     │ symbol           │     │ symbol              │
│ timeframe       │     │ order_type       │     │ ticket (UQ)         │
│ strategy_name   │     │ action           │     │ type (BUY/SELL)     │
│ signal          │     │ volume           │     │ volume              │
│ reason          │     │ price            │     │ price_open          │
│ price           │     │ sl               │     │ price_current       │
│ confidence      │     │ tp               │     │ sl                  │
│ created_at (IX) │     │ status           │     │ tp                  │
└─────────────────┘     │ mt5_order_id     │     │ profit              │
                        │ comment          │     │ swap                │
┌─────────────────┐     │ risk_check_json  │     │ commission          │
│    alerts       │     │ created_at (IX)  │     │ snapshot_at (IX)    │
├─────────────────┤     └──────────────────┘     └─────────────────────┘
│ id (PK)         │
│ level           │     ┌──────────────────┐
│ title           │     │  system_logs     │
│ message         │     ├──────────────────┤
│ channel         │     │ id (PK)          │
│ status          │     │ level            │
│ created_at (IX) │     │ module           │
└─────────────────┘     │ message          │
                        │ traceback        │
                        │ created_at (IX)  │
                        └──────────────────┘
```

### 6.3 建表 SQL

#### 6.3.1 strategy_signals

```sql
CREATE TABLE strategy_signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT    NOT NULL,               -- 品种代码，如 XAUUSD
    timeframe       TEXT    NOT NULL,               -- K线周期 M1/M5/M15/H1/H4/D1
    strategy_name   TEXT    NOT NULL,               -- 策略名称
    signal          TEXT    NOT NULL CHECK(signal IN ('BUY','SELL','CLOSE_BUY','CLOSE_SELL','HOLD')),
    reason          TEXT,                           -- 信号原因描述
    price           REAL,                           -- 产生信号时的价格
    confidence      REAL    DEFAULT 0.5,            -- 置信度 0.0-1.0
    extra_data      TEXT,                           -- JSON 扩展字段
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX idx_signals_symbol    ON strategy_signals(symbol);
CREATE INDEX idx_signals_strategy  ON strategy_signals(strategy_name);
CREATE INDEX idx_signals_time      ON strategy_signals(created_at);
CREATE INDEX idx_signals_signal    ON strategy_signals(signal);
```

#### 6.3.2 orders

```sql
CREATE TABLE orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT    NOT NULL,
    action          TEXT    NOT NULL CHECK(action IN ('BUY','SELL','CLOSE_BUY','CLOSE_SELL')),
    order_type      TEXT    NOT NULL CHECK(order_type IN ('MARKET','LIMIT','STOP')),
    volume          REAL    NOT NULL,
    price           REAL,
    sl              REAL,
    tp              REAL,
    deviation       INTEGER DEFAULT 20,
    status          TEXT    NOT NULL DEFAULT 'PENDING'
                           CHECK(status IN ('PENDING','CHECK_PASSED','CHECK_FAILED',
                                            'SENT','FILLED','PARTIALLY_FILLED',
                                            'CANCELED','REJECTED','EXPIRED')),
    mt5_order_id    INTEGER,                        -- MT5 返回的 ticket
    mt5_retcode     INTEGER,                        -- MT5 返回码
    comment         TEXT,
    risk_check_json TEXT,                           -- 风控检查结果 JSON
    request_json    TEXT,                           -- 原始请求 JSON
    response_json   TEXT,                           -- MT5 响应 JSON
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at      TEXT
);

CREATE INDEX idx_orders_symbol  ON orders(symbol);
CREATE INDEX idx_orders_status  ON orders(status);
CREATE INDEX idx_orders_time    ON orders(created_at);
```

#### 6.3.3 positions_snapshot

```sql
CREATE TABLE positions_snapshot (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT    NOT NULL,
    ticket          INTEGER NOT NULL,               -- MT5 持仓 ticket
    type            TEXT    NOT NULL CHECK(type IN ('BUY','SELL')),
    volume          REAL    NOT NULL,
    price_open      REAL    NOT NULL,
    price_current   REAL    NOT NULL,
    sl              REAL,
    tp              REAL,
    profit          REAL    NOT NULL DEFAULT 0,
    swap            REAL    DEFAULT 0,
    commission      REAL    DEFAULT 0,
    comment         TEXT,
    magic           INTEGER,
    snapshot_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX idx_pos_snapshot_ticket ON positions_snapshot(ticket);
CREATE INDEX idx_pos_snapshot_time   ON positions_snapshot(snapshot_at);
```

#### 6.3.4 alerts

```sql
CREATE TABLE alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    level           TEXT    NOT NULL CHECK(level IN ('info','warn','error','success')),
    title           TEXT    NOT NULL,
    message         TEXT    NOT NULL,
    channel         TEXT    DEFAULT 'system',       -- telegram,feishu,dingtalk,email (逗号分隔)
    status          TEXT    NOT NULL DEFAULT 'pending'
                           CHECK(status IN ('pending','sent','failed','skipped')),
    error_detail    TEXT,                           -- 发送失败的详细错误
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX idx_alerts_level ON alerts(level);
CREATE INDEX idx_alerts_time  ON alerts(created_at);
```

#### 6.3.5 system_logs

```sql
CREATE TABLE system_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    level           TEXT    NOT NULL CHECK(level IN ('DEBUG','INFO','WARNING','ERROR','CRITICAL')),
    module          TEXT    NOT NULL,               -- 模块名: mt5_client, risk_service, strategy_engine 等
    message         TEXT    NOT NULL,
    traceback       TEXT,                           -- 异常堆栈（仅 ERROR/CRITICAL）
    extra_data      TEXT,                           -- JSON 扩展字段
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX idx_logs_level  ON system_logs(level);
CREATE INDEX idx_logs_module ON system_logs(module);
CREATE INDEX idx_logs_time   ON system_logs(created_at);
```

---

## 7. 后端架构与模块设计

### 7.1 目录结构

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 应用入口 + 路由注册
│   ├── config.py                # 配置管理（读取 .env）
│   ├── dependencies.py          # FastAPI 依赖注入
│   │
│   ├── mt5_client.py            # [M1] MT5 连接封装
│   ├── market_service.py        # [M2] 行情数据服务
│   ├── account_service.py       # [M3] 账户信息服务
│   ├── position_service.py      # [M4] 持仓管理服务
│   ├── order_service.py         # [M5] 订单管理服务
│   ├── risk_service.py          # [M7] 风控模块
│   ├── strategy_engine.py       # [M6] 策略引擎（调度器）
│   ├── alert_service.py         # [M8] 告警服务
│   ├── websocket_manager.py     # WebSocket 连接管理
│   │
│   ├── database.py              # SQLAlchemy 引擎 + Session
│   ├── models.py                # ORM 模型定义
│   ├── schemas.py               # Pydantic 请求/响应模型
│   │
│   └── routers/
│       ├── __init__.py
│       ├── health.py            # /api/health
│       ├── market.py            # /api/tick, /api/rates, /api/symbol
│       ├── account.py           # /api/account
│       ├── positions.py         # /api/positions
│       ├── orders.py            # /api/orders/*
│       ├── strategies.py        # /api/strategies/*
│       ├── signals.py           # /api/signals
│       ├── alerts.py            # /api/alerts
│       ├── system.py            # /api/system/*
│       └── ws.py                # /ws/* WebSocket 路由
│
├── strategies/                  # 策略插件目录
│   ├── __init__.py
│   ├── base_strategy.py         # 策略基类
│   ├── ma_cross.py              # 均线交叉策略
│   ├── rsi_strategy.py          # RSI 策略
│   ├── macd_strategy.py         # MACD 策略
│   ├── breakout_strategy.py     # 突破策略
│   ├── bollinger_strategy.py    # 布林带策略
│   └── multi_scan.py            # 多品种扫描策略
│
├── alerts/                      # 告警通道插件
│   ├── __init__.py
│   ├── base_channel.py          # 通道基类
│   ├── telegram_channel.py      # Telegram Bot
│   ├── feishu_channel.py        # 飞书 Webhook
│   ├── dingtalk_channel.py      # 钉钉 Webhook
│   └── email_channel.py         # Email
│
├── data/
│   └── trading.db               # SQLite 数据库文件
│
├── logs/
│   ├── app.log                  # 应用日志
│   └── trading.log              # 交易日志
│
├── tests/
│   ├── test_mt5_client.py
│   ├── test_risk_service.py
│   └── test_order_service.py
│
├── requirements.txt
├── .env                         # 环境变量配置
└── .env.example                 # 配置模板
```

### 7.2 模块依赖关系

```text
main.py (FastAPI App)
  ├── config.py (全局配置单例)
  ├── database.py (SQLAlchemy)
  │   └── models.py (ORM)
  ├── mt5_client.py (单例)
  │   ├── market_service.py
  │   ├── account_service.py
  │   └── position_service.py
  ├── strategy_engine.py
  │   ├── mt5_client.py
  │   ├── risk_service.py
  │   └── strategies/*.py (插件)
  ├── order_service.py
  │   ├── mt5_client.py
  │   └── risk_service.py
  ├── alert_service.py
  │   └── alerts/*.py (插件)
  └── websocket_manager.py
```

### 7.3 核心模块规范

#### 7.3.1 MT5 Client (mt5_client.py)

```python
class MT5Client:
    """
    MT5 连接单例。
    线程安全：所有对 mt5.* 的调用必须在同一线程（主线程）。
    若需多线程访问，使用 queue.Queue 将请求序列化到主线程。
    """

    # ---- 生命周期 ----
    def __init__(self, config: Config)
    def connect() -> bool                    # 初始化 MT5 连接
    def shutdown() -> None                   # 关闭 MT5 连接
    def reconnect() -> bool                  # 断线重连（指数退避: 1s→2s→4s→8s→max 30s）
    def is_connected() -> bool               # 检查连接状态

    # ---- 账户 ----
    def account_info() -> dict               # 获取账户信息

    # ---- 行情 ----
    def symbol_tick(symbol: str) -> dict     # 获取实时 Tick
    def symbol_info(symbol: str) -> dict     # 获取品种信息
    def get_rates(symbol: str, timeframe: int, count: int) -> pd.DataFrame  # 获取K线
    def get_symbols() -> list[dict]          # 获取 Market Watch 品种列表

    # ---- 持仓 ----
    def positions_get(symbol: str | None) -> list[dict]  # 获取持仓

    # ---- 订单 ----
    def order_check(request: dict) -> dict   # 订单预检
    def order_send(request: dict) -> dict    # 发送订单
    def positions_close(ticket: int, lot: float, deviation: int) -> dict  # 平仓

    # ---- 错误处理 ----
    def last_error() -> tuple[int, str]      # 获取最后错误码和描述
```

**关键约束：**
- `mt5.initialize()` 必须在主线程调用
- 所有 MT5 调用必须检查返回值是否为 `None`（`None` 表示失败）
- 每次调用后检查 `mt5.last_error()`
- 重连时必须先 `shutdown()` 再 `initialize()`

#### 7.3.2 配置管理 (config.py)

```python
class Config:
    """从 .env 文件加载配置，支持运行时热更新部分字段"""

    # MT5 连接
    MT5_LOGIN: str
    MT5_PASSWORD: str
    MT5_SERVER: str

    # 交易参数
    DEFAULT_SYMBOL: str = "XAUUSD"
    DEFAULT_LOT: float = 0.01
    MAX_LOT: float = 0.05
    MAX_POSITIONS: int = 3
    MAX_DAILY_LOSS: float = 100.0
    MAX_LOSS_PER_TRADE: float = 20.0
    MAX_SYMBOL_POSITIONS: int = 1

    # 安全开关
    ENABLE_REAL_TRADING: bool = False

    # 风控参数
    MAX_SPREAD_PIPS: dict = {"XAUUSD": 5.0, "EURUSD": 2.0, "default": 3.0}
    TRADING_HOURS_START: str = "00:00"
    TRADING_HOURS_END: str = "23:59"
    SIGNAL_COOLDOWN_SECONDS: int = 60

    # 告警
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    FEISHU_WEBHOOK_URL: str = ""
    DINGTALK_WEBHOOK_URL: str = ""

    # 系统
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
```

---

## 8. 策略引擎

### 8.1 架构原则

> **策略只产生信号，不下单。**

```text
策略引擎 (策略调度 + 执行)
    │
    ├── 定时扫描（APScheduler，每 1 分钟）
    │   ├── MA Cross Strategy  → 生成 BUY/SELL/HOLD 信号
    │   ├── RSI Strategy       → 生成 BUY/SELL/HOLD 信号
    │   ├── MACD Strategy      → 生成 BUY/SELL/HOLD 信号
    │   └── ...
    │
    ├── 信号输出 → 统一格式
    │   ├── 保存 strategy_signals 表
    │   ├── WebSocket 广播 STRATEGY_SIGNAL
    │   └── 触发 alert_service（若信号为 BUY/SELL）
    │
    └── （可选）信号 → 自动下单
        但必须经过 risk_service.validate_order() 全部 9 道检查
```

### 8.2 策略基类

```python
from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    """所有策略的基类"""

    def __init__(self, symbol: str, timeframe: str, mt5_client, config: dict):
        self.name: str = self.__class__.__name__
        self.symbol = symbol
        self.timeframe = timeframe
        self.mt5 = mt5_client
        self.params = config
        self.status = "stopped"
        self.last_signal_time = None

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> dict:
        """
        子类必须实现此方法。
        输入: K线 DataFrame (columns: time, open, high, low, close, tick_volume)
        输出: {
            "signal": "BUY" | "SELL" | "CLOSE_BUY" | "CLOSE_SELL" | "HOLD",
            "reason": "信号原因描述",
            "confidence": 0.0-1.0,
            "price": float
        }
        """
        pass

    def run(self) -> dict:
        """框架调用: 获取K线 → 生成信号 → 返回"""
        timeframe_map = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 16385, "H4": 16388, "D1": 16392}
        tf = timeframe_map.get(self.timeframe, 5)

        df = self.mt5.get_rates(self.symbol, tf, count=200)
        if df is None or len(df) < 50:
            return {"signal": "HOLD", "reason": "insufficient data"}

        signal = self.generate_signal(df)
        signal["symbol"] = self.symbol
        signal["timeframe"] = self.timeframe
        signal["strategy_name"] = self.name
        return signal
```

### 8.3 统一信号格式

```python
{
    "symbol": "XAUUSD",
    "timeframe": "M5",
    "strategy_name": "MACross",
    "signal": "BUY",                    # BUY | SELL | CLOSE_BUY | CLOSE_SELL | HOLD
    "reason": "MA20 crossed above MA60",
    "confidence": 0.82,                 # 0.0 (最低) → 1.0 (最高)
    "price": 2350.12,
    "timestamp": "2026-06-30T15:28:02"
}
```

### 8.4 内置策略清单

| 策略名称 | 文件名 | 品种 | 默认周期 | 参数 | 说明 |
|---------|--------|------|---------|------|------|
| MA Cross | `ma_cross.py` | XAUUSD | M5 | fast=20, slow=60 | 双均线金叉/死叉 |
| RSI | `rsi_strategy.py` | XAUUSD | M15 | period=14, oversold=30, overbought=70 | RSI 超买超卖 |
| MACD | `macd_strategy.py` | EURUSD | M5 | fast=12, slow=26, signal=9 | MACD 柱状图转向 |
| Breakout | `breakout_strategy.py` | XAUUSD | M15 | period=20, threshold=0.5 | 支撑阻力突破 |
| Bollinger | `bollinger_strategy.py` | XAUUSD | M30 | period=20, stddev=2 | 布林带回归 |
| Multi-Scan | `multi_scan.py` | — | H1 | symbols=["XAUUSD","EURUSD","GBPUSD"] | 多品种扫描汇总 |

### 8.5 策略调度器

```python
class StrategyEngine:
    """策略调度器：管理所有策略实例的生命周期与定时执行"""

    def __init__(self, mt5_client, db_session, ws_manager, alert_service):
        self.strategies: dict[str, BaseStrategy] = {}
        self.scheduler = AsyncIOScheduler()

    def register(self, strategy: BaseStrategy) -> None
    def unregister(self, name: str) -> None
    def start(self, name: str, params: dict = None) -> bool
    def stop(self, name: str) -> bool
    def stop_all(self) -> int
    def get_status(self, name: str = None) -> dict
    def update_params(self, name: str, params: dict) -> bool

    async def _scan_loop(self):
        """每分钟执行：遍历所有 running 策略 → run() → 保存信号 → 推送"""
```

---

## 9. 风控模块

### 9.1 风控检查链

风控模块是下单前的**最后一道防线**。每次下单必须依次通过以下 9 道检查：

```text
策略信号 / 手动下单
    │
    ▼
┌─────────────────────────────┐
│ 检查 1: ENABLE_REAL_TRADING │  ← 全局交易开关
│ 通过 → 继续                │
│ 拒绝 → "真实交易未启用"      │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 检查 2: 品种是否允许交易     │  ← allowed_symbols 白名单
│ 通过 → 继续                │
│ 拒绝 → "品种不在允许列表"    │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 检查 3: 手数是否超限         │  ← lot ≤ MAX_LOT
│ 通过 → 继续                │
│ 拒绝 → "手数超过最大限制"    │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 检查 4: 持仓数量是否超限     │  ← len(positions) < MAX_POSITIONS
│ 通过 → 继续                │
│ 拒绝 → "持仓数量已达上限"    │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 检查 5: 同品种是否已有持仓   │  ← 同 symbol 同方向
│ 通过 → 继续                │
│ 拒绝 → "同品种已有同向持仓"   │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 检查 6: 点差是否过大         │  ← spread ≤ MAX_SPREAD_PIPS[symbol]
│ 通过 → 继续                │
│ 拒绝 → "点差超过阈值"        │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 检查 7: 今日亏损是否超限     │  ← daily_loss ≤ MAX_DAILY_LOSS
│ 通过 → 继续                │
│ 拒绝 → "今日亏损已达上限"    │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 检查 8: 是否重复信号         │  ← 同一根K线内不再下单
│ 通过 → 继续                │
│ 拒绝 → "重复信号，冷却中"    │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 检查 9: MT5 order_check    │  ← mt5.order_check(request)
│ 通过 → 允许下单            │
│ 拒绝 → MT5 返回的拒绝原因    │
└─────────────────────────────┘
```

### 9.2 风控模块接口

```python
class RiskService:
    def __init__(self, config: Config, mt5_client):
        self.max_lot = config.MAX_LOT
        self.max_positions = config.MAX_POSITIONS
        self.max_daily_loss = config.MAX_DAILY_LOSS
        self.enable_real_trading = config.ENABLE_REAL_TRADING

    def validate_order(
        self,
        symbol: str,
        action: str,
        lot: float,
        positions: list[dict],
        last_signal: dict | None
    ) -> tuple[bool, str, list[dict]]:
        """
        返回: (通过?, 汇总消息, 逐项检查结果列表)
        """
        pass

    def get_daily_loss(self) -> float:
        """查询今日已实现亏损总额"""
        pass

    def disable_trading(self) -> None:
        """紧急关闭交易（内存级，重启恢复）"""
        self.enable_real_trading = False

    def enable_trading(self) -> None:
        """重新启用交易"""
        self.enable_real_trading = True
```

---

## 10. 告警与消息推送

### 10.1 告警场景与级别

| 场景 | 级别 | 推送渠道 | 触发条件 |
|------|------|---------|---------|
| MT5 连接成功 | info | 无（仅日志） | `mt5.initialize()` 成功 |
| MT5 连接失败 | **error** | Telegram + 飞书 + 钉钉 | `initialize()` 失败或断线 |
| MT5 重连成功 | success | Telegram | 重连成功 |
| 策略 BUY/SELL 信号 | success | Telegram + 飞书 | 信号置信度 ≥ 0.6 |
| 策略 HOLD 信号 | info | 无（仅记录） | 每次策略扫描 |
| 订单预检失败 | **error** | Telegram + 飞书 | `check_passed = false` |
| 订单发送成功 | success | Telegram + 飞书 | `order_send` retcode=DONE |
| 订单发送失败 | **error** | Telegram + 飞书 + 钉钉 | `order_send` retcode≠DONE |
| 止损触发 | **error** | Telegram + 飞书 + 钉钉 | 持仓被止损平仓 |
| 止盈触发 | success | Telegram + 飞书 | 持仓被止盈平仓 |
| 日亏损达到 80% 限制 | **warn** | Telegram + 飞书 | `daily_loss ≥ max_daily_loss × 0.8` |
| 日亏损达到 100% 限制 | **error** | Telegram + 飞书 + 钉钉 | `daily_loss ≥ max_daily_loss` |
| 一键停止触发 | **error** | Telegram + 飞书 + 钉钉 | 用户点击一键停止 |
| 系统异常退出 | **error** | Telegram + 飞书 + 钉钉 | 未捕获异常 |

### 10.2 消息格式

#### Telegram / 飞书 / 钉钉 通用模板

```text
【MT5 策略提醒】
品种：{symbol}
周期：{timeframe}
策略：{strategy_name}
信号：{signal_cn}
价格：{price}
原因：{reason}
时间：{timestamp}

---
账户：{account}
服务器：{server}
```

#### 订单提醒模板

```text
【MT5 订单通知】
状态：{status_cn}
品种：{symbol}
方向：{action_cn}
手数：{volume}
价格：{price}
止损：{sl}
止盈：{tp}
Ticket：{mt5_order_id}
时间：{timestamp}

---
账户：{account} | 净值：${equity}
```

### 10.3 告警通道实现

```python
class BaseAlertChannel(ABC):
    @abstractmethod
    async def send(self, title: str, message: str) -> bool:
        """发送消息，返回是否成功"""
        pass

class TelegramChannel(BaseAlertChannel):
    """通过 Telegram Bot API 发送消息"""
    async def send(self, title: str, message: str) -> bool:
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": f"*{title}*\n\n{message}", "parse_mode": "Markdown"}
        # HTTP POST
        pass

class FeishuChannel(BaseAlertChannel):
    """通过飞书 Webhook 发送消息"""
    async def send(self, title: str, message: str) -> bool:
        payload = {"msg_type": "interactive", "card": {"header": {"title": {"content": title}}, ...}}
        # HTTP POST
        pass

class DingTalkChannel(BaseAlertChannel):
    """通过钉钉 Webhook 发送消息"""
    async def send(self, title: str, message: str) -> bool:
        payload = {"msgtype": "markdown", "markdown": {"title": title, "text": message}}
        # HTTP POST
        pass
```

---

## 11. 非功能需求

### 11.1 性能要求

| 指标 | 目标值 | 说明 |
|------|--------|------|
| API 响应时间 (P95) | < 200ms | 不含 MT5 调用延迟 |
| Tick 推送延迟 | < 1s | WebSocket 推送到前端 |
| K 线查询 (200 根) | < 500ms | `copy_rates_from_pos` 调用 |
| 策略扫描间隔 | 60s（可配置） | 所有策略同步执行 |
| 前端首屏加载 | < 3s | 含 Lightweight Charts 初始化 |
| 数据库写入 | < 50ms | SQLite 单条写入 |
| WebSocket 并发连接 | ≥ 5 | 支持多 Tab 同时打开 |

### 11.2 可靠性要求

| 要求 | 说明 |
|------|------|
| MT5 断线自动重连 | 指数退避策略：1s → 2s → 4s → 8s → 30s（最大） |
| 重连后恢复策略 | 重连成功后自动恢复策略扫描 + WebSocket 推送 |
| 优雅关闭 | 收到 SIGTERM/SIGINT 时：停止策略 → 平仓检查 → 关闭 MT5 → 关闭 DB |
| 防重复下单 | 同一 signal + 同一根 K 线内最多下单一次 |
| 异常隔离 | 单个策略异常不影响其他策略运行 |
| 数据完整性 | 所有写操作使用事务；订单状态变更必须原子 |

### 11.3 安全性要求

| 要求 | 说明 |
|------|------|
| **仅监听 127.0.0.1** | 开发阶段绝不可绑定 `0.0.0.0` |
| **`.env` 不入 Git** | MT5 密码、Bot Token 等敏感信息均在 `.env` |
| **ENABLE_REAL_TRADING 默认 false** | 首次启动不可自动进入实盘模式 |
| **一键停止** | 前端常驻红色按钮，一键停止所有策略和自动交易 |
| **无公网暴露** | MVP 阶段不对外暴露任何端口 |
| **最小权限** | MT5 账户建议使用 Demo 账户或只读权限实盘账户 |

### 11.4 可维护性要求

| 要求 | 说明 |
|------|------|
| 结构化日志 | 所有模块使用 `logging` 标准库，输出到文件 + 控制台 |
| 日志轮转 | 单文件最大 10MB，保留最近 30 天 |
| 策略可插拔 | 新增策略只需继承 `BaseStrategy` + 放入 `strategies/` 目录 |
| 告警通道可插拔 | 新增通道只需继承 `BaseAlertChannel` + 放入 `alerts/` 目录 |
| 配置外部化 | 所有可变参数在 `.env` 文件，代码中不留硬编码 |
| 数据库备份 | SQLite 单文件，备份 = 复制 `trading.db` |

---

## 12. 开发阶段规划

### 阶段总览

```text
阶段 1  阶段 2   阶段 3   阶段 4   阶段 5   阶段 6   阶段 7   阶段 8
只读    前端     策略     消息     模拟     Demo    小资金   自动
连接    看盘     信号     提醒     下单     下单     实盘     交易
  │       │       │       │       │       │       │       │
  ▼       ▼       ▼       ▼       ▼       ▼       ▼       ▼
Day1-2  Day3-5  Day6   Day7   Day8-9  Day10+  Week3+  Week6+
```

### 阶段 1：只读连接 MT5（Day 1-2）

**目标：** 确认 Python ↔ MT5 通信正常

**交付物：**

| API | 预期结果 |
|-----|---------|
| `GET /api/health` | `mt5_connected: true` |
| `GET /api/account` | 返回账户余额、净值等 |
| `GET /api/positions` | 返回当前持仓列表（可能为空） |
| `GET /api/tick/XAUUSD` | 返回实时 bid/ask |
| `GET /api/rates/XAUUSD?timeframe=M5&count=200` | 返回 200 根 M5 K线 |

**不做：** 下单、策略、告警

### 阶段 2：前端看盘（Day 3-5）

**目标：** 浏览器可看到实时行情和账户信息

**交付物：**
- 前端加载 K 线图（Lightweight Charts 蜡烛图）
- 顶部状态栏显示连接状态/账户/服务器
- 账户面板显示余额/净值/保证金/浮动盈亏
- 持仓列表（如有）
- WebSocket 实时推送价格至前端

**参考原型：** `MT5 Trading Dashboard.html`

### 阶段 3：策略信号（Day 6）

**目标：** 策略运行并生成信号（不下单）

**交付物：**
- MA Cross 策略每 1 分钟执行一次
- 信号保存至 `strategy_signals` 表
- 前端策略信号页可查看信号历史
- 策略引擎页可启动/停止策略

### 阶段 4：消息提醒（Day 7）

**目标：** 策略信号和异常事件推送到手机

**交付物：**
- Telegram 收到策略信号提醒
- 飞书/钉钉收到异常告警
- 告警日志页可查看历史

### 阶段 5：模拟下单（Day 8-9）

**目标：** 验证订单流程但不真实下单

**交付物：**
- 前端可发起买入/卖出请求
- 风控模块 9 道检查全部运行
- `order_check` 通过并返回结果
- **不调用 `order_send`**

### 阶段 6：Demo 账户下单（Day 10+）

**目标：** Demo 账户完成真实交易

**前置条件：**
- 阶段 1-5 全部通过
- `ENABLE_REAL_TRADING=true`
- MT5 登录 Demo 账户

**交付物：**
- Demo 账户可买入/卖出/平仓
- 所有订单写入 `orders` 表
- 订单状态变化推送 Telegram/飞书

### 阶段 7：小资金实盘（Week 3+）

**目标：** 极小仓位辅助交易

**约束：**
- 极小手数（0.01 lot）
- 半自动模式（人工确认后下单）
- **不启用全自动交易**

### 阶段 8：自动交易（Week 6+）

**前置条件（全部必须满足）：**

- [ ] Demo 稳定运行 ≥ 2 周
- [ ] 所有异常均有日志
- [ ] 所有交易均有记录
- [ ] 风控规则已充分验证
- [ ] 断线不会重复下单
- [ ] 策略不会连续刷单
- [ ] 日亏损限制已验证
- [ ] 一键停止按钮功能正常

---

## 13. 附录

### 13.1 环境变量完整模板 (.env.example)

```env
# ===== MT5 连接 =====
MT5_LOGIN=你的MT5账号
MT5_PASSWORD=你的MT5密码
MT5_SERVER=ICMarkets-Demo

# ===== 交易品种 =====
DEFAULT_SYMBOL=XAUUSD
ALLOWED_SYMBOLS=XAUUSD,EURUSD,GBPUSD,USDJPY

# ===== 交易参数 =====
DEFAULT_LOT=0.01
MAX_LOT=0.05
MAX_POSITIONS=3
MAX_SYMBOL_POSITIONS=1
MAX_DAILY_LOSS=100
MAX_LOSS_PER_TRADE=20

# ===== 安全开关（第一版必须为 false）=====
ENABLE_REAL_TRADING=false

# ===== 风控参数 =====
MAX_SPREAD_XAUUSD=5.0
MAX_SPREAD_FOREX=2.0
TRADING_HOURS_START=00:00
TRADING_HOURS_END=23:59
SIGNAL_COOLDOWN_SECONDS=60

# ===== 策略配置 =====
STRATEGY_SCAN_INTERVAL_SECONDS=60

# ===== Telegram =====
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# ===== 飞书 =====
FEISHU_WEBHOOK_URL=

# ===== 钉钉 =====
DINGTALK_WEBHOOK_URL=

# ===== Email（可选）=====
EMAIL_SMTP_HOST=
EMAIL_SMTP_PORT=587
EMAIL_USER=
EMAIL_PASSWORD=
EMAIL_TO=

# ===== 系统 =====
API_HOST=127.0.0.1
API_PORT=8000
LOG_LEVEL=INFO
```

### 13.2 Python 依赖 (requirements.txt)

```text
MetaTrader5>=5.0.45
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
pandas>=2.0.0
numpy>=1.26.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-dotenv>=1.0.0
sqlalchemy>=2.0.0
apscheduler>=3.10.0
requests>=2.31.0
ta>=0.11.0
websockets>=12.0
```

### 13.3 错误码定义

| 错误码 | HTTP 状态码 | 说明 |
|--------|-----------|------|
| `MT5_NOT_INITIALIZED` | 503 | MT5 未初始化 |
| `MT5_CONNECT_FAILED` | 503 | MT5 连接失败 |
| `MT5_ACCOUNT_FAILED` | 500 | 获取账户信息失败 |
| `MT5_TICK_FAILED` | 500 | 获取 Tick 失败 |
| `MT5_RATES_FAILED` | 500 | 获取 K 线失败 |
| `MT5_ORDER_CHECK_FAILED` | 500 | 订单预检失败 |
| `MT5_ORDER_SEND_FAILED` | 500 | 订单发送失败 |
| `RISK_CHECK_FAILED` | 400 | 风控检查未通过 |
| `SYMBOL_NOT_FOUND` | 404 | 品种不存在 |
| `STRATEGY_NOT_FOUND` | 404 | 策略不存在 |
| `STRATEGY_ALREADY_RUNNING` | 400 | 策略已在运行 |
| `STRATEGY_NOT_RUNNING` | 400 | 策略未在运行 |
| `POSITION_NOT_FOUND` | 404 | 持仓不存在 |
| `ORDER_NOT_FOUND` | 404 | 订单不存在 |
| `INVALID_PARAMS` | 422 | 参数验证失败 |
| `EMERGENCY_STOP_ACTIVE` | 403 | 系统处于安全模式 |

### 13.4 前端路由规划（Vue Router）

```javascript
const routes = [
  { path: '/',           name: 'Dashboard',  component: Dashboard },   // 主看盘页
  { path: '/strategies', name: 'Strategies', component: Strategies },  // 策略管理页
  { path: '/orders',     name: 'Orders',     component: Orders },      // 订单历史页
  { path: '/alerts',     name: 'Alerts',     component: Alerts },      // 告警日志页
  { path: '/settings',   name: 'Settings',   component: Settings },    // 系统设置页
];
```

> 第一版建议单页 Dashboard 包含所有面板（如原型所示），路由在第二版引入。

### 13.5 变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-06-30 | 初始版本，覆盖 MVP 全部功能 | — |
| v1.1 | 2026-07-01 | Dashboard 布局重构 + ATR 多周期统计模块 | — |

### v1.1 变更详情 (2026-07-01)

#### 后端新增
- **品种名称自动解析** (`mt5_client.py`)：支持 `XAUUSD`/`XAUUSD.c` 等两种写法，自动匹配券商实际品种名
- **ATR 多周期统计服务** (`services/atr_service.py`)：12 周期 × 3 个 ATR(1/5/50) + 3 比率 + 7 种市场状态分类，与 MQL5 `ATR_统计交易辅助面板` 逻辑一致
- **ATR API** (`routers/atr.py`)：`GET /api/atr-stats/{symbol}?tf=M5`
- **挂单 API** (`routers/positions.py`)：`GET /api/pending-orders`
- 时间周期映射扩展：新增 M3/H2/H8
- Tick 时间存储统一为 UTC（`utcfromtimestamp`），与 K 线图时区一致

#### 前端重构 (`MT5 Dashboard Live.html`)

**顶部状态栏精简：**
- 保留：MT5 连接状态、账户号、服务器、连接状态指示、最新消息、本地时钟
- 移除：Tick 计数、DB 模式标签、账户余额/净值/保证金等字段

**图表标题栏扩展：**
- 新增服务器时间显示（YYYY-MM-DD 星期 HH:MM:SS，芝加哥时间）
- 账户信息移至此处：余额、净值、可用、已用、保证金率、杠杆、浮动盈亏
- K 线横轴改为英文 `YYYY-MM-DD HH:MM` 格式

**ATR 可折叠面板（K 线图左上角）：**
- 折叠状态：显示选中周期的核心指标（周期/ATR1/ATR5/ATR50/1:5/5:50/状态）
- 悬停展开：完整 12 周期表格，含方向箭头(↗↘→)
- 点击行切换顶部显示，`width: fit-content` 自适应宽度

**右侧交易面板（持仓面板下方）：**
- 交易参数：单笔风险%/金额、止损止盈 ATR5 倍数
- 自动计算：止损点数、止盈点数、以损定仓手数
- BUY/SELL/平仓/应用参数 按钮
- 推保护开关（启动点+赢利点）、追踪止损开关（启动点+距离）
- 保证金比例条（薄条）

**底部面板：**
- "交易"标签页：当前持仓（含止损止盈列）+ 当前挂单（品种/类型/手数/挂单价/止损/止盈/状态）
- "系统日志"标签页：保留历史消息
- 移除"数据状态"标签页，最新消息已移至顶部栏

**移除：**
- 右侧面板的持仓列表
- 右下角一键停止按钮
- 图表工具栏的 ATR 状态标签

---

> **下一行动：** 按第十二节阶段规划，从阶段 1 "只读连接 MT5" 开始实施。  
> **关联文档：** `方案.md`（实施细节） · `MT5 Dashboard Live.html`（实时 Dashboard）
