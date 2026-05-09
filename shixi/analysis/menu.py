"""菜品策略 — 卖什么、不卖什么、怎么搭"""

from collections import defaultdict
from itertools import combinations
from typing import List
from shixi.core.schema import DishSale, Finding


def analyze(sales: List[DishSale]) -> List[Finding]:
    findings = []
    findings.extend(_abc_analysis(sales))
    findings.extend(_category_structure(sales))
    findings.extend(_cross_selling(sales))
    findings.extend(_cold_items(sales))
    findings.extend(_combo_analysis(sales))
    return findings


def _abc_analysis(sales: List[DishSale]) -> List[Finding]:
    findings = []
    dish_rev = defaultdict(float)
    for s in sales:
        dish_rev[s.菜品名称] += s.菜品收入

    total = sum(dish_rev.values())
    if total == 0:
        return findings

    sorted_dishes = sorted(dish_rev.items(), key=lambda x: x[1], reverse=True)
    a_dishes, b_dishes, c_dishes = [], [], []
    cumulative = 0.0
    for name, rev in sorted_dishes:
        pct = rev / total * 100
        prev = cumulative
        cumulative += pct
        if cumulative <= 70:
            a_dishes.append((name, round(pct, 1)))
        elif prev < 70 or cumulative <= 90:
            b_dishes.append((name, round(pct, 1)))
        else:
            c_dishes.append((name, round(pct, 1)))

    if a_dishes:
        a_pct = sum(p for _, p in a_dishes)
        if len(a_dishes) <= 2 and a_pct > 60:
            findings.append(Finding(
                module="menu", type="problem", priority="high",
                title=f"过度依赖: {a_dishes[0][0]} 一个菜占 {a_dishes[0][1]}% 收入",
                detail=f"A类仅 {len(a_dishes)} 个（{', '.join(f'{n}({p}%)' for n, p in a_dishes[:3])}）贡献 {a_pct:.0f}%",
                recommendation="重点推第二个大单品，分散风险",
                data={"a_count": len(a_dishes), "b_count": len(b_dishes), "c_count": len(c_dishes)}
            ))
        else:
            findings.append(Finding(
                module="menu", type="strength", priority="low",
                title=f"A类 {len(a_dishes)} 个菜品贡献 {a_pct:.0f}% 营收",
                detail=f"B类 {len(b_dishes)} 个, C类 {len(c_dishes)} 个",
                data={"a_count": len(a_dishes), "b_count": len(b_dishes), "c_count": len(c_dishes)}
            ))
    return findings


def _category_structure(sales: List[DishSale]) -> List[Finding]:
    findings = []
    cat_rev = defaultdict(float)
    for s in sales:
        cat_rev[s.菜品大类] += s.菜品收入

    total = sum(cat_rev.values())
    if total == 0:
        return findings

    drink_rev = cat_rev.get('饮料', 0)
    drink_pct = drink_rev / total * 100

    orders_with_drink = set()
    all_orders = set()
    for s in sales:
        oid = s.real_order_id
        all_orders.add(oid)
        if s.菜品大类 == '饮料':
            orders_with_drink.add(oid)

    drink_attach = len(orders_with_drink) / len(all_orders) * 100 if all_orders else 0

    if drink_attach >= 80:
        detail = f"{len(orders_with_drink)}/{len(all_orders)} 单含饮料，搭售很好"
        rec = "保持节奏，可尝试饮料升杯/加量提价"
    elif drink_attach >= 50:
        detail = f"{len(orders_with_drink)}/{len(all_orders)} 单含饮料"
        rec = "收银时多问一句'加个饮料？'"
    else:
        detail = f"{len(orders_with_drink)}/{len(all_orders)} 单含饮料，偏低"
        rec = "收银主动推饮料，或做饮品套餐"

    findings.append(Finding(
        module="menu", type="strength" if drink_attach >= 50 else "problem",
        priority="low",
        title=f"饮料搭售率 {drink_attach:.0f}%（{drink_pct:.0f}%营收）",
        detail=detail, recommendation=rec,
        data={"drink_attach": round(drink_attach)}
    ))

    staple_pct = cat_rev.get('主食', 0) / total * 100
    if staple_pct < 5:
        findings.append(Finding(
            module="menu", type="problem", priority="low",
            title=f"主食占比仅 {staple_pct:.0f}%",
            detail="米饭定价偏低或推得不够",
            recommendation="米饭+麻辣烫套餐化"
        ))
    return findings


def _cross_selling(sales: List[DishSale]) -> List[Finding]:
    findings = []
    order_dishes = defaultdict(set)
    for s in sales:
        if s.菜品大类 not in ('打包',):
            order_dishes[s.real_order_id].add(s.菜品名称)

    pair_count = defaultdict(int)
    single_count = defaultdict(int)
    for dishes in order_dishes.values():
        for d in dishes:
            single_count[d] += 1
        for a, b in combinations(sorted(dishes), 2):
            pair_count[(a, b)] += 1

    top_pairs = sorted(pair_count.items(), key=lambda x: x[1], reverse=True)[:5]
    if top_pairs:
        lines = []
        for (a, b), cnt in top_pairs:
            rate = cnt / single_count[a] * 100 if a in single_count else 0
            lines.append(f"「{a}」+「{b}」→ {cnt}单({rate:.0f}%)")
        findings.append(Finding(
            module="menu", type="strength", priority="low",
            title="高频搭配",
            detail="\n".join(lines),
            recommendation="可做套餐锁住客单价"
        ))
    return findings


def _cold_items(sales: List[DishSale]) -> List[Finding]:
    findings = []
    dish_dates = defaultdict(set)
    all_dates = set()
    for s in sales:
        if s.营业日期:
            all_dates.add(s.营业日期)
            dish_dates[s.菜品名称].add(s.营业日期)

    if len(all_dates) < 14:
        return findings

    cold = [(d, len(dates), len(all_dates)) for d, dates in dish_dates.items()
            if len(dates) < len(all_dates) * 0.1]
    cold.sort(key=lambda x: x[1])

    if cold:
        names = [f"{n}({c}天/{t}天)" for n, c, t in cold[:5]]
        findings.append(Finding(
            module="menu", type="problem", priority="low",
            title=f"冷门预警: {', '.join(names)}",
            detail=f"在 {len(all_dates)} 天营业中仅出现寥寥数天，长期滞销占用菜单，增加备料复杂度",
            recommendation="考虑下架或改为隐藏菜单/季节限定"
        ))
    return findings


def _combo_analysis(sales: List[DishSale]) -> List[Finding]:
    findings = []
    combo_oids = set()
    for s in sales:
        oid = s.real_order_id
        if any(kw in s.菜品名称 for kw in ['套餐', '双人', '单人']):
            combo_oids.add(oid)

    all_oids = set(s.real_order_id for s in sales)
    if all_oids:
        pct = len(combo_oids) / len(all_oids) * 100
        findings.append(Finding(
            module="menu", type="problem" if pct < 5 else "strength",
            priority="medium" if pct < 5 else "low",
            title=f"套餐订单占比 {pct:.1f}%（{len(combo_oids)}/{len(all_oids)}单）",
            detail="套餐能显著拉高客单价",
            recommendation="多组合一人食/双人/家庭套餐。麻辣烫+主食+饮料一口价"
        ))
    return findings
