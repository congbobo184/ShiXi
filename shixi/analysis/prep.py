"""角度三：食材与备料 — 哪些品类在赚钱、哪些纯占位置"""

from collections import defaultdict
from statistics import mean
from typing import List
from shixi.core.schema import DishSale, Finding

# 生鲜类（会坏）→ 卖不动就真亏
PERISHABLE_CATEGORIES = {'称重菜', '主食'}
# 冻品/包装（不会坏）→ 卖不动只是占位
FROZEN_CATEGORIES = {'炸品（总部）', '饮料', '打包'}
# 不确定
UNKNOWN_CATEGORIES = {}


def diagnose(sales: List[DishSale], store_config: dict) -> List[Finding]:
    findings = []

    cat_rev = defaultdict(float)
    cat_count = defaultdict(int)
    cat_dates = defaultdict(set)
    for s in sales:
        cat_rev[s.菜品大类] += s.菜品收入
        cat_count[s.菜品大类] += 1
        if s.营业日期:
            cat_dates[s.菜品大类].add(s.营业日期)

    total_rev = sum(cat_rev.values())
    total_days = len(set(s.营业日期 for s in sales if s.营业日期))

    # 品类结构
    lines = []
    for cat, rev in sorted(cat_rev.items(), key=lambda x: x[1], reverse=True):
        pct = rev / total_rev * 100
        perish = "生鲜⚠️" if cat in PERISHABLE_CATEGORIES else "冻品✓"
        n_days = len(cat_dates[cat])
        lines.append(f"  {cat}({perish}): {pct:.0f}% 出现{n_days}/{total_days}天")

    findings.append(Finding(
        level="green",
        title="品类收入结构",
        evidence="\n".join(lines),
        impact="—",
        suggestion="称重菜是核心（占大头才正常），但饮料和套餐空间明显",
    ))

    # 找出真正有问题的菜品：生鲜类且几乎不卖的
    dish_counts = defaultdict(int)
    dish_dates = defaultdict(set)
    dish_cat = {}
    for s in sales:
        dish_counts[s.菜品名称] += 1
        dish_cat[s.菜品名称] = s.菜品大类
        if s.营业日期:
            dish_dates[s.菜品名称].add(s.营业日期)

    dead_perishable = []
    dead_frozen = []
    for name, cnt in dish_counts.items():
        cat = dish_cat.get(name, '')
        n_days = len(dish_dates[name])
        if n_days < total_days * 0.05 and total_days >= 30:  # 出现天数<5%
            item = (name, n_days, total_days, cat)
            if cat in PERISHABLE_CATEGORIES:
                dead_perishable.append(item)
            else:  # 冻品/包装
                dead_frozen.append(item)

    if dead_perishable:
        dead_perishable.sort(key=lambda x: x[1])
        names = [f"{n}({d}天/{t}天)" for n, d, t, _ in dead_perishable[:5]]
        findings.append(Finding(
            level="yellow" if len(dead_perishable) >= 3 else "green",
            title=f"生鲜类低动销: {', '.join(names)}",
            evidence=f"这些是生鲜品类，卖不动是真损耗。占总菜品的 {len(dead_perishable)}/{len(dish_counts)}",
            impact="每次进货卖不掉就是纯亏，而且占陈列空间",
            suggestion="生鲜类低动销品建议直接砍掉，或改为'预订制'减少损耗",
            expect="砍掉后减少备料复杂度和损耗",
        ))

    if dead_frozen:
        dead_frozen.sort(key=lambda x: x[1])
        names = [f"{n}({d}天/{t}天)" for n, d, t, _ in dead_frozen[:5]]
        findings.append(Finding(
            level="green",
            title=f"冻品/包装低动销: {', '.join(names)}",
            evidence="这些是冷冻品或包装品，不会坏，但占菜单和库存位置",
            impact="卖不动但不亏钱，只是占位",
            suggestion="总部配的SKU有些可能不适合你的客群。可跟总部沟通换品，或直接下架腾位置",
        ))

    # 套餐分析
    combo_oids = set()
    for s in sales:
        if any(kw in s.菜品名称 for kw in ['套餐', '双人', '单人']):
            combo_oids.add(s.real_order_id)

    all_oids = set(s.real_order_id for s in sales)
    combo_pct = len(combo_oids) / len(all_oids) * 100 if all_oids else 0

    if combo_pct < 10:
        findings.append(Finding(
            level="yellow",
            title=f"套餐仅占 {combo_pct:.1f}% 订单（{len(combo_oids)}/{len(all_oids)}单）",
            evidence="套餐能锁定客单价（套餐客单价比单点高30-50%），但现在几乎不存在",
            impact="没有套餐=没有价格锚点。客人每次来都'自己凑'，凑少了你就少赚",
            suggestion="「一人食」麻辣烫(1.5斤)+米饭+饮料=￥39。「双人餐」双味拼+2米饭+2饮料=￥79",
            expect="套餐占订单20%以上时，整体客单价提升10-15%",
        ))

    return findings
