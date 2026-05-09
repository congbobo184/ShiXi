"""美团管家 — 菜品销售明细解析"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List
from shixi.core.schema import DishSale

# 美团导出Excel的实际列名映射
COLUMN_MAP = {
    '营业日期': '营业日期',
    '订单编号': '订单编号',
    '取餐号': '取餐号',
    '菜品名称': '菜品名称',
    '菜品大类': '菜品大类',
    '菜品小类': '菜品小类',
    '销售数量': '销售数量',
    '销售额（元）': '销售额',
    '菜品优惠（元）': '菜品优惠',
    '菜品收入（元）': '菜品收入',
    '点菜时间': '点菜时间',
    '下单时间': '下单时间',
    '订单金额(元)': '订单金额',
    '订单优惠(元)': '订单优惠',
    '订单收入(元)': '订单收入',
    '规格': '规格',
    '单位': '单位',
}


def parse(filepath: str) -> List[DishSale]:
    """解析美团菜品销售明细Excel，返回DishSale列表"""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {filepath}")

    # 美团导出的Excel，表头在第3行（0-indexed: row 2）
    df = pd.read_excel(path, header=2)

    # 去掉汇总行（营业日期为空的行）
    df = df.dropna(subset=['营业日期']).copy()

    # 类型转换
    df['营业日期'] = pd.to_datetime(df['营业日期'], errors='coerce')
    for col in ['销售数量', '销售额（元）', '菜品优惠（元）', '菜品收入（元）',
                 '订单金额(元)', '订单优惠(元)', '订单收入(元)']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    for col in ['点菜时间', '下单时间']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # 补默认值
    df['规格'] = df.get('规格', pd.Series([''] * len(df))).fillna('')
    df['单位'] = df.get('单位', pd.Series([''] * len(df))).fillna('')

    sales = []
    for _, row in df.iterrows():
        try:
            sale = DishSale(
                营业日期=row['营业日期'].date() if pd.notna(row['营业日期']) else None,
                订单编号=str(row.get('订单编号', '')),
                取餐号=str(row.get('取餐号', '')).rstrip('.0'),
                菜品名称=str(row.get('菜品名称', '')),
                菜品大类=str(row.get('菜品大类', '')),
                菜品小类=str(row.get('菜品小类', '')),
                销售数量=float(row.get('销售数量', 0)),
                销售额=float(row.get('销售额（元）', 0)),
                菜品优惠=float(row.get('菜品优惠（元）', 0)),
                菜品收入=float(row.get('菜品收入（元）', 0)),
                点菜时间=row.get('点菜时间') if pd.notna(row.get('点菜时间')) else None,
                下单时间=row.get('下单时间') if pd.notna(row.get('下单时间')) else None,
                订单金额=float(row.get('订单金额(元)', 0)),
                订单优惠=float(row.get('订单优惠(元)', 0)),
                订单收入=float(row.get('订单收入(元)', 0)),
                规格=str(row.get('规格', '')),
                单位=str(row.get('单位', '')),
            )
            sales.append(sale)
        except Exception:
            continue  # 跳过解析失败的行

    return sales
