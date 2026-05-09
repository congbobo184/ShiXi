"""菜品策略 — 卖什么、不卖什么、怎么搭"""

from collections import defaultdict
from itertools import combinations
from typing import List
from shixi.core.schema import DishSale, Finding


def analyze(sales: List[DishSale]) -> List[Finding]:
    """菜品全面分析"""
    findings = []
    findings.extend(_abc_analysis(sales))
    findings.extend(_category_structure(sales))
    findings.extend(_cross_selling(sales))
    findings.extend(_cold_items(sales))
    findings.extend(_combo_analysis(sales))
    return findings


def _abc_analysis(sales: List[DishSale]) -> List[Finding]:
    """ABC分类（帕累托分析）"""
    findings = []

    dish_rev = defaultdict(float)
    dish_qty = defaultdict(float)
    for s in sales:
        dish_rev[s.菜品名称] += s.菜品收入
        dish_qty[s.菜品名称] += s.销售数量

    total_rev = sum(dish_rev.values())
    if total_rev == 0:
        return findings

    sorted_dishes = sorted(dish_rev.items(), key=lambda x: x[1], reverse=True)

    a_dishes = []
    b_dishes = []
    c_dishes = []
    cumulative = 0.0
    for name, rev in sorted_dishes:
        pct = rev / total_rev * 100
        prev_cum = cumulative
        cumulative += pct
        if cumulative <= 70:
            a_dishes.append((name, round(pct, 1)))
        elif prev_cum < 70 or cumulative <= 90:
            b_dishes.append((name, round(pct, 1)))
        else:
            c_dishes.append((name, round(pct, 1)))

    if a_dishes:
        a_names = [f"{n}({p}%)" for n, p in a_dishes[:3]]
        a_pct = sum(p for _, p in a_dishes)

        if len(a_dishes) <= 2 and a_pct > 60:
            findings.append(Finding(
                module="menu", type="problem", priority="high",
                title=f"过度依赖: {a_dishes[0][0]} 一个菜占 {a_dishes[0][1]}% 收入",
                detail=f"A类菜品仅 {len(a_dishes)} 个（{', '.join(a_names)}），贡献了 {a_pct:.0f}% 营收。"
                       f"一旦口味过气或供应链出问题，营收直接腰斩",
                recommendation="重点推第二个大单品，分散风险。B类菜品里有潜力的加大推广",
                data={"a_count": len(a_dishes), "b_count": len(b_dishes), "c_count": len(c_dishes),
                       "a_pct": round(a_pct), "top1": a_dishes[0][0], "top1_pct": a_dishes[0][1]}
            ))
        else:
            findings.append(Finding(
                module="menu", type="strength", priority="low",
                title=f"A类 {len(a_dishes)} 个菜品贡献 {a_pct:.0f}% 营收（{', '.join(a_names)}）",
                detail=f"B类 {len(b_dishes)} 个菜品, C类 {len(c_dishes)} 个",
                data={"a_count": len(a_dishes), "b_count": len(b_dishes), "c_count": len(c_dishes)}
            ))

    return findings


def _category_structure(sales: List[DishSale]) -> List[Finding]:
    """品类结构分析"""
    findings = []

    cat_rev = defaultdict(float)
    for s in sales:
        cat_rev[s.菜品大类] += s.菜品收入

    total = sum(cat_rev.values())
    if total == 0:
        return findings

    # 饮料搭售率
    drink_rev = cat_rev.get('饮料', 0)
    drink_pct = drink_rev / total * 100

    orders_with_drink = set()
    all_orders = set()
    for s in sales:
        all_orders.add(s.订单编号)
        if s.菜品大类 == '饮料':
            orders_with_drink.add(s.订单编号)

    drink_attach = len(orders_with_drink) / len(all_orders) * 100 if all_orders else 0

    if drink_attach >= 95:
        drink_msg = f"{len(orders_with_drink)}/{len(all_orders)} 单含饮料，几乎每单都搭。饮品是纯利品类"
        drink_rec = "保持现有搭售节奏，可尝试饮料升杯/加量，小幅提价"
    elif drink_attach >= 50:
        drink_msg = f"{len(orders_with_drink)}/{len(all_orders)} 单含饮料，还有提升空间"
        drink_rec = "麻辣烫偏咸偏辣，天然搭饮品。收银时多问一句'加个饮料？'，每多卖一杯净利润率极高"
    else:
        drink_msg = f"{len(orders_with_drink)}/{len(all_orders)} 单含饮料，搭售偏低"
        drink_rec = "收银时主动推饮料，或做麻辣烫+饮品小套餐，拉高搭售率"

    findings.append(Finding(
        module="menu", type="strength" if drink_attach >= 50 else "problem",
        priority="medium" if drink_attach < 50 else "low",
        title=f"饮料搭售率 {drink_attach:.0f}%（{drink_pct:.0f}%营收）",
        detail=drink_msg,
        recommendation=drink_rec,
        data={"drink_attach": round(drink_attach), "drink_rev_pct": round(drink_pct)}
    ))

    # 主食占比
    staple_rev = cat_rev.get('主食', 0)
    staple_pct = staple_rev / total * 100
    if staple_pct < 5:
        findings.append(Finding(
            module="menu", type="problem", priority="low",
            title=f"主食占比仅 {staple_pct:.0f}%，可能漏掉'吃饱'需求",
            detail="米饭销量不错但收入占比低，说明定价可能偏低或没推够",
            recommendation="米饭+麻辣烫套餐化，或者推'加1元换米饭'的连带策略"
        ))

    return findings


def _cross_selling(sales: List[DishSale]) -> List[Finding]:
    """连带销售分析 — 哪些菜品经常一起出现"""
    findings = []

    order_dishes = defaultdict(set)
    for s in sales:
        if s.菜品大类 not in ('打包',):
            order_dishes[s.订单编号].add(s.菜品名称)

    # 统计菜品对共现
    pair_count = defaultdict(int)
    single_count = defaultdict(int)
    for dishes in order_dishes.values():
        for d in dishes:
            single_count[d] += 1
        for a, b in combinations(sorted(dishes), 2):
            pair_count[(a, b)] += 1

    # 找强关联对
    top_pairs = sorted(pair_count.items(), key=lambda x: x[1], reverse=True)[:5]
    if top_pairs:
        lines = []
        for (a, b), cnt in top_pairs:
            a_total = single_count[a]
            rate = cnt / a_total * 100 if a_total else 0
            lines.append(f"「{a}」+「{b}」→ {cnt}单({rate:.0f}%)")

        if lines:
            findings.append(Finding(
                module="menu", type="strength", priority="low",
                title="连带销售Top组合",
                detail="\n".join(lines),
                recommendation="这些高频搭配可以做套餐，锁住客单价",
                data={"top_pairs": [{"a": a, "b": b, "count": c} for (a, b), c in top_pairs]}
            ))

    return findings


def _cold_items(sales: List[DishSale]) -> List[Finding]:
    """冷门预警 — 长期没人点的菜"""
    findings = []

    dish_dates = defaultdict(set)
    all_dates = set()
    for s in sales:
        if s.营业日期:
            all_dates.add(s.营业日期)
            dish_dates[s.菜品名称].add(s.营业日期)

    total_days = len(all_dates)
    if total_days < 14:
        return findings

    cold = []
    for dish, dates in dish_dates.items():
        if len(dates) < total_days * 0.1:  # 出现天数少于10%
            cold.append((dish, len(dates), total_days))

    if cold:
        cold.sort(key=lambda x: x[1])
        names = [f"{n}({d}天/{t}天)" for n, d, t in cold[:5]]
        findings.append(Finding(
            module="menu", type="problem", priority="low",
            title=f"冷门预警: {', '.join(names)}",
            detail=f"以上菜品在 {total_days} 天中仅出现寥寥数天，长期滞销占用菜单",
            recommendation="考虑下架替换，或改为'隐藏菜单'/季节限定，减少备料复杂度"
        ))

    return findings


def _combo_analysis(sales: List[DishSale]) -> List[Finding]:
    """套餐分析"""
    findings = []

    combo_rev = 0.0
    combo_orders = set()
    total_rev = 0.0
    all_orders = set()

    for s in sales:
        total_rev += s.菜品收入
        all_orders.add(s.订单编号)
        if '套餐' in s.菜品名称 or '双人' in s.菜品名称 or '单人' in s.菜品名称:
            combo_rev += s.菜品收入
            combo_orders.add(s.订单编号)

    if total_rev > 0 and combo_rev > 0:
        pct = combo_rev / total_rev * 100
        findings.append(Finding(
            module="menu", type="strength" if pct > 5 else "problem",
            priority="medium",
            title=f"套餐贡献 {pct:.1f}% 营收（{len(combo_orders)} 单）",
            detail=f"「肥牛大虾双人餐」「精品肥牛单人餐」有一定销量。套餐能显著拉高客单价",
            recommendation="多组合几个套餐：一人食、双人、家庭装。尤其是麻辣烫+主食+饮料的一人食套餐"
        ))

    return findings
