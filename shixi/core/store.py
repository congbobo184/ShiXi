"""数据存储 — Parquet读写 + SQLite元数据"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List
from shixi.core.schema import DishSale


def get_warehouse_dir() -> Path:
    return Path(__file__).parent.parent.parent / "data" / "warehouse"


def get_meta_db() -> Path:
    return get_warehouse_dir() / "meta.db"


def sales_to_df(sales: List[DishSale]) -> pd.DataFrame:
    """DishSale列表 → DataFrame"""
    records = []
    for s in sales:
        records.append({
            '营业日期': s.营业日期,
            '订单编号': s.订单编号,
            '取餐号': s.取餐号,
            '菜品名称': s.菜品名称,
            '菜品大类': s.菜品大类,
            '菜品小类': s.菜品小类,
            '销售数量': s.销售数量,
            '销售额': s.销售额,
            '菜品优惠': s.菜品优惠,
            '菜品收入': s.菜品收入,
            '点菜时间': s.点菜时间,
            '下单时间': s.下单时间,
            '订单金额': s.订单金额,
            '订单优惠': s.订单优惠,
            '订单收入': s.订单收入,
            '规格': s.规格,
            '单位': s.单位,
        })
    return pd.DataFrame(records)


def df_to_sales(df: pd.DataFrame) -> List[DishSale]:
    """DataFrame → DishSale列表"""
    sales = []
    for _, row in df.iterrows():
        sales.append(DishSale(
            营业日期=row['营业日期'].date() if hasattr(row['营业日期'], 'date') else row['营业日期'],
            订单编号=str(row['订单编号']),
            取餐号=str(row.get('取餐号', '')),
            菜品名称=str(row['菜品名称']),
            菜品大类=str(row['菜品大类']),
            菜品小类=str(row['菜品小类']),
            销售数量=float(row['销售数量']),
            销售额=float(row['销售额']),
            菜品优惠=float(row['菜品优惠']),
            菜品收入=float(row['菜品收入']),
            点菜时间=row['点菜时间'].to_pydatetime() if pd.notna(row.get('点菜时间')) else None,
            下单时间=row['下单时间'].to_pydatetime() if pd.notna(row.get('下单时间')) else None,
            订单金额=float(row['订单金额']),
            订单优惠=float(row['订单优惠']),
            订单收入=float(row['订单收入']),
            规格=str(row.get('规格', '')),
            单位=str(row.get('单位', '')),
        ))
    return sales


def save(sales: List[DishSale], source_file: str):
    """保存到Parquet并记录元数据"""
    warehouse = get_warehouse_dir()
    warehouse.mkdir(parents=True, exist_ok=True)

    df = sales_to_df(sales)

    # 按月份分Parquet文件
    df['月份'] = pd.to_datetime(df['营业日期']).dt.to_period('M').astype(str)
    for month, group in df.groupby('月份'):
        parquet_path = warehouse / f"sales_{month}.parquet"
        if parquet_path.exists():
            existing = pd.read_parquet(parquet_path)
            group = pd.concat([existing, group]).drop_duplicates(subset=['订单编号', '菜品名称', '销售数量'])
        group.drop(columns=['月份']).to_parquet(parquet_path, index=False)

    # SQLite元数据
    db = get_meta_db()
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT,
            record_count INTEGER,
            date_from TEXT,
            date_to TEXT,
            imported_at TEXT
        )
    """)
    conn.execute(
        "INSERT INTO imports (source_file, record_count, date_from, date_to, imported_at) VALUES (?, ?, ?, ?, ?)",
        (source_file, len(sales),
         str(df['营业日期'].min()), str(df['营业日期'].max()),
         datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def load(date_from: str = None, date_to: str = None) -> List[DishSale]:
    """从Parquet加载数据"""
    warehouse = get_warehouse_dir()
    if not warehouse.exists():
        return []

    frames = []
    for f in sorted(warehouse.glob("sales_*.parquet")):
        df = pd.read_parquet(f)
        if date_from:
            df = df[df['营业日期'] >= date_from]
        if date_to:
            df = df[df['营业日期'] <= date_to]
        if not df.empty:
            frames.append(df)

    if not frames:
        return []

    return df_to_sales(pd.concat(frames, ignore_index=True))


def get_date_range():
    """获取数据日期范围"""
    sales = load()
    if not sales:
        return None, None
    dates = [s.营业日期 for s in sales if s.营业日期]
    return min(dates), max(dates)


def get_import_history():
    """获取导入历史"""
    db = get_meta_db()
    if not db.exists():
        return []
    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT * FROM imports ORDER BY imported_at DESC").fetchall()
    conn.close()
    return rows
