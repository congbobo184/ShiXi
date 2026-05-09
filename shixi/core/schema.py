"""统一数据模型"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class DishSale:
    """一条菜品销售记录"""
    营业日期: date
    订单编号: str = ""
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
        return f"{self.营业日期}_{self.取餐号}"


@dataclass
class Finding:
    """一条诊断发现"""
    level: str             # red(高优) / yellow(中优) / green(低优)
    title: str             # 问题标题
    evidence: str          # 数据证据
    impact: str            # 如果不改会怎样
    suggestion: str        # 具体怎么做
    expect: str = ""       # 改了预期效果
    data: dict = field(default_factory=dict)
