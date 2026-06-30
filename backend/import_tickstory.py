"""
Tickstory 历史 Tick 数据导入脚本
=================================
从 Tickstory Lite 导出的 .bi5 文件批量导入 XAUUSD 历史 Tick 到 SQLite 数据库。

用法:
    python import_tickstory.py                           # 导入所有年份
    python import_tickstory.py --year 2026               # 只导入指定年份
    python import_tickstory.py --year 2026 --dry-run     # 预览模式（不写入数据库）
    python import_tickstory.py --limit 100000            # 限制导入条数（测试用）

数据格式:
    .bi5 文件 = LZMA 压缩，解压后每条记录 20 字节 (Big-Endian):
        - int32: 从该小时 00:00:00 起的毫秒偏移量
        - int32: Ask 价格 (×1000，如 2064562 → 2064.562)
        - int32: Bid 价格 (×1000)
        - float32: Ask 成交量
        - float32: Bid 成交量

目录结构:
    XAUUSD/{year}/{month}/{day}/{hour}h_ticks.bi5
    month: 00-11 (0索引), day: 01-31, hour: 00-23
"""

import os
import sys
import io
import struct
import lzma
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# 确保 backend/ 在 Python Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text
from app.database import SessionLocal, engine
from app.models import TickDatum

# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

TICKSTORY_BASE = Path.home() / "AppData/Roaming/Tickstory/Tickstory Lite/Data/XAUUSD"
SYMBOL = "XAUUSD"
PRICE_DIVISOR = 1000.0  # XAUUSD: raw_value / 1000 = actual price
RECORD_SIZE = 20        # bytes per tick record
BATCH_SIZE = 5000       # records per DB commit
PROGRESS_INTERVAL = 50  # print progress every N files


def parse_bi5_file(filepath: Path) -> list[dict] | None:
    """
    解析单个 .bi5 文件，返回 Tick 记录列表。

    目录结构: XAUUSD/2024/00/01/23h_ticks.bi5
                             年   月  日  时(文件内偏移)
    返回: [{"time": "2024-01-01 23:00:00.312", "bid": 2062.598, "ask": 2064.562, ...}, ...]
    """
    # 从路径提取时间信息
    parts = filepath.parts
    try:
        year = int(parts[-4])
        month = int(parts[-3]) + 1   # 0-indexed → 1-indexed
        day = int(parts[-2])
        filename = parts[-1]          # "23h_ticks.bi5"
        hour = int(filename.split("h")[0])
    except (ValueError, IndexError):
        print(f"  [WARN] Cannot parse path: {filepath}")
        return None

    # 读取并解压
    try:
        with open(filepath, "rb") as f:
            raw = f.read()
    except Exception as e:
        print(f"  [WARN] Read error {filepath}: {e}")
        return None

    if len(raw) == 0:
        return []  # 空文件

    try:
        decompressed = lzma.decompress(raw)
    except Exception as e:
        print(f"  [WARN] Decompress error {filepath}: {e}")
        return None

    if len(decompressed) == 0 or len(decompressed) % RECORD_SIZE != 0:
        print(f"  [WARN] Unexpected decompressed size {len(decompressed)} in {filepath}")
        return None

    # 解析记录
    n_records = len(decompressed) // RECORD_SIZE
    base_time = datetime(year, month, day, hour, 0, 0)
    records = []

    for i in range(n_records):
        offset = i * RECORD_SIZE
        try:
            t_ms, ask_raw, bid_raw, ask_vol, bid_vol = struct.unpack(
                ">IIIff", decompressed[offset:offset + RECORD_SIZE]
            )
        except struct.error:
            continue

        tick_time = base_time + timedelta(milliseconds=t_ms)
        bid = round(bid_raw / PRICE_DIVISOR, 3)
        ask = round(ask_raw / PRICE_DIVISOR, 3)
        spread = round(ask - bid, 3)

        records.append({
            "symbol": SYMBOL,
            "bid": bid,
            "ask": ask,
            "spread": max(spread, 0),
            "last": None,
            "volume": int(ask_vol * 100) if ask_vol > 0 else 0,
            "time": tick_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],  # 毫秒精度
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    return records


def import_year(base_dir: Path, year: int, dry_run: bool = False, limit: int = 0) -> dict:
    """
    导入指定年份的所有 Tick 数据。
    返回: {"files": N, "records": N, "errors": N}
    """
    year_dir = base_dir / str(year)
    if not year_dir.exists():
        print(f"  Directory not found: {year_dir}")
        return {"files": 0, "records": 0, "errors": 0}

    bi5_files = sorted(
        [f for f in year_dir.rglob("*.bi5") if f.stat().st_size > 0],
        key=lambda x: str(x)
    )

    if not bi5_files:
        print(f"  No non-empty .bi5 files found in {year}")
        return {"files": 0, "records": 0, "errors": 0}

    total_files = len(bi5_files)
    total_records = 0
    total_errors = 0
    batch = []
    first_time = None
    last_time = None
    start_time = time.time()

    print(f"  Found {total_files} non-empty .bi5 files")
    if limit > 0:
        print(f"  [LIMIT] Will stop after importing {limit:,} records")

    db = SessionLocal()

    try:
        for idx, filepath in enumerate(bi5_files):
            records = parse_bi5_file(filepath)

            if records is None:
                total_errors += 1
                continue

            if records:
                if first_time is None:
                    first_time = records[0]["time"]
                last_time = records[-1]["time"]

                if not dry_run:
                    batch.extend(records)

                    # 批量写入
                    if len(batch) >= BATCH_SIZE:
                        db.execute(
                            text("""INSERT INTO tick_data (symbol, bid, ask, spread, last, volume, time, created_at)
                                    VALUES (:symbol, :bid, :ask, :spread, :last, :volume, :time, :created_at)"""),
                            batch,
                        )
                        db.commit()
                        total_records += len(batch)
                        batch = []

                        # 检查 limit
                        if limit > 0 and total_records >= limit:
                            print(f"  [LIMIT] Reached {total_records:,} records, stopping")
                            break
                else:
                    total_records += len(records)

            # 进度输出
            if (idx + 1) % PROGRESS_INTERVAL == 0:
                elapsed = time.time() - start_time
                rate = total_records / elapsed if elapsed > 0 else 0
                pct = (idx + 1) / total_files * 100
                print(f"  [{idx+1:5d}/{total_files}] {pct:5.1f}% | {total_records:>10,} ticks | {rate:>8,.0f} rec/s")

        # 写入剩余批次
        if batch and not dry_run:
            db.execute(
                text("""INSERT INTO tick_data (symbol, bid, ask, spread, last, volume, time, created_at)
                        VALUES (:symbol, :bid, :ask, :spread, :last, :volume, :time, :created_at)"""),
                batch,
            )
            db.commit()
            total_records += len(batch)

    except Exception as e:
        db.rollback()
        print(f"  [ERROR] {e}")
        total_errors += 1
    finally:
        db.close()

    elapsed = time.time() - start_time
    rate = total_records / elapsed if elapsed > 0 else 0

    print(f"  {'[DRY RUN] ' if dry_run else ''}Done in {elapsed:.1f}s")
    print(f"  Files: {total_files} | Records: {total_records:,} | Errors: {total_errors}")
    print(f"  Rate: {rate:,.0f} rec/s")
    if first_time and last_time:
        print(f"  Range: {first_time} → {last_time}")

    return {"files": total_files, "records": total_records, "errors": total_errors}


def show_stats():
    """显示当前数据库中已有的 Tick 统计"""
    db = SessionLocal()
    try:
        total = db.query(TickDatum).count()
        if total == 0:
            print("  Database: empty (no tick data yet)")
            return

        # 按年份统计
        rows = db.execute(text(
            "SELECT substr(time,1,4) as yr, COUNT(*) as cnt, MIN(time), MAX(time) "
            "FROM tick_data GROUP BY yr ORDER BY yr"
        )).fetchall()
        print(f"  Total: {total:,} tick records")
        for row in rows:
            print(f"    {row[0]}: {row[1]:,} records ({row[2]} → {row[3]})")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Import Tickstory .bi5 tick data to SQLite")
    parser.add_argument("--year", type=int, help="Import specific year only (e.g. 2026)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    parser.add_argument("--limit", type=int, default=0, help="Max records to import (0 = unlimited)")
    parser.add_argument("--stats", action="store_true", help="Show current DB stats and exit")
    args = parser.parse_args()

    print("=" * 60)
    print("Tickstory → SQLite Import Tool")
    print(f"Source: {TICKSTORY_BASE}")
    print(f"Symbol: {SYMBOL} (price / {PRICE_DIVISOR})")
    print(f"Mode: {'DRY RUN (no writes)' if args.dry_run else 'IMPORT'}")
    print("=" * 60)

    if args.stats:
        show_stats()
        return

    years = [args.year] if args.year else [2024, 2025, 2026]
    grand_total = {"files": 0, "records": 0, "errors": 0}

    for year in years:
        print(f"\n--- {year} ---")
        result = import_year(TICKSTORY_BASE, year, dry_run=args.dry_run, limit=args.limit)
        for k in grand_total:
            grand_total[k] += result[k]
        if args.limit > 0 and result["records"] >= args.limit:
            break

    print(f"\n{'=' * 60}")
    print(f"TOTAL: {grand_total['files']} files, {grand_total['records']:,} records, {grand_total['errors']} errors")
    print(f"{'=' * 60}")

    if not args.dry_run and grand_total["records"] > 0:
        show_stats()


if __name__ == "__main__":
    main()
