"""角度四：客人行为 — 怎么吃、跟谁来、还买了什么"""

from collections import defaultdict
from statistics import mean
from typing import List
from shixi.core.schema import DishSale, Finding


def diagnose(sales: List[DishSale], store_config: dict) -> List[Finding]:
    findings = []

    # 每单的称重碗数和搭配
    order_items = defaultdict(list)
    order_rev = {}
    for s in sales:
        order_items[s.real_order_id].append(s)
        if s.real_order_id not in order_rev and s.订单收入 > 0:
            order_rev[s.real_order_id] = s.订单收入

    # 每单称重菜碗数
    bowls_per_order = []
    for oid, items in order_items.items():
        bowls = sum(1 for s in items if s.菜品大类 == '称重菜')
        bowls_per_order.append(bowls)

    if bowls_per_order:
        avg_bowls = mean(bowls_per_order)
        multi_bowl = sum(1 for b in bowls_per_order if b >= 2)
        multi_pct = multi_bowl / len(bowls_per_order) * 100

        findings.append(Finding(
            level="green",
            title=f"每单平均 {avg_bowls:.1f} 碗称重菜, {multi_pct:.0f}% 的订单含2碗以上",
            evidence=f"含2碗以上说明是结伴来或者一个人吃两种口味。"
                      f"{'双人/家庭客群存在' if multi_pct > 5 else '以单人消费为主'}",
            impact="如果大多是单人一碗，套餐就要推一人食版本",
            suggestion="双人/家庭客多→推双人餐。单人客多→推一人食套餐+饮料",
            data={"avg_bowls": round(avg_bowls, 1), "multi_pct": round(multi_pct)},
        ))

    # 米饭搭售
    orders_with_rice = set()
    all_oids = set()
    for s in sales:
        all_oids.add(s.real_order_id)
        if s.菜品大类 == '主食' and '米饭' in s.菜品名称:
            orders_with_rice.add(s.real_order_id)

    rice_rate = len(orders_with_rice) / len(all_oids) * 100 if all_oids else 0
    findings.append(Finding(
        level="yellow" if rice_rate < 40 else "green",
        title=f"米饭搭售率 {rice_rate:.0f}%（{len(orders_with_rice)}/{len(all_oids)}单）",
        evidence="麻辣烫/香锅配米饭是中国人吃饭的底层逻辑",
        impact="每漏一单米饭=少赚2元(纯毛利基本是100%)。一个月漏几千块",
        suggestion="收银必问'加米饭吗？' 最省事的问答就能翻倍",
        expect="米饭搭售提到70%+，单均增收1-2元",
    ))

    # 饮料搭售
    orders_with_drink = set()
    for s in sales:
        if s.菜品大类 == '饮料':
            orders_with_drink.add(s.real_order_id)

    drink_rate = len(orders_with_drink) / len(all_oids) * 100 if all_oids else 0
    drink_rev = sum(s.菜品收入 for s in sales if s.菜品大类 == '饮料')
    total_rev = sum(s.菜品收入 for s in sales)

    findings.append(Finding(
        level="yellow" if drink_rate < 50 else "green",
        title=f"饮料搭售率 {drink_rate:.0f}%（{drink_rate:.0f}%营收），"
             f"每两单就漏一杯饮料",
        evidence=f"麻辣烫咸辣烫，配饮品是刚需不是选项。现在每3单有2单只吃不喝",
        impact="饮料毛利极高（进价2元卖6元=300%）。每天少卖20杯=少赚80元纯利",
        suggestion="①收银必问'冰镇饮料要吗？'②夏天推自制冰柠檬水/酸梅汤（成本更低）"
                   "③麻辣烫+饮料套餐减1元",
        expect="推到60%搭售率，每天多赚50-100元纯利",
    ))

    # 小食/炸品搭售
    orders_with_snack = set()
    for s in sales:
        if s.菜品大类 == '炸品（总部）':
            orders_with_snack.add(s.real_order_id)

    snack_rate = len(orders_with_snack) / len(all_oids) * 100 if all_oids else 0
    if snack_rate < 5:
        findings.append(Finding(
            level="green",
            title=f"炸品搭售率仅 {snack_rate:.1f}%",
            evidence=f"{len(orders_with_snack)}单含炸品。麻辣烫店的炸品本来就难卖",
            impact="冷冻炸品不会坏，卖不掉就是占库存。但也不亏钱",
            suggestion="考虑炸品是不是总部强制配的？如果不是，换成爆款冰粉/凉糕（夏天更搭）",
        ))

    return findings
