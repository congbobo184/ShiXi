"""统一数据模型"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class DishSale:
    """一条菜品销售记录"""
    营业日期: date
    订单编号: str
    取餐号: str = ""
    菜品名称: str = ""
    菜品大类: str = ""
    菜品小类: str = ""
    销售数量: float = 0.0
    销售额: float = 0.0
    菜品优惠: float = 0.0
    菜品收入: float = 0.0
    点菜时间: Optional[datetime] = None
    下单时间: Optional[datetime] = None
    订单金额: float = 0.0
    订单优惠: float = 0.0
    订单收入: float = 0.0
    规格: str = ""
    单位: str = ""

    @property
    def real_order_id(self) -> str:
        """真正的订单标识 = 日期 + 取餐号（美团按天重置取餐号）"""
        return f"{self.营业日期}_{self.取餐号}"


@dataclass
class Finding:
    """分析发现 — 系统的核心输出"""
    module: str                # diagnostic / menu / location / forecast
    type: str                  # problem / strength / suggestion / prediction
    priority: str              # high / medium / low
    title: str                 # 一句话结论
    detail: str                # 数据支撑
    recommendation: str = ""   # 行动建议
    data: dict = field(default_factory=dict)  # 附数据 {label: value}
