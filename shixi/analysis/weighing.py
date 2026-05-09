"""角度一：称重结构 — 客人拿多少、拿什么"""

from collections import defaultdict
from statistics import mean, median
from typing import List
from shixi.core.schema import DishSale, Finding


def diagnose(sales: List[DishSale], store_config: dict) -> List[Finding]:
    findings = []

    # 称重菜按口味分析
    flavor_qty = defaultdict(list)
    for s in sales:
        if s.菜品大类 == '称重菜' and s.单位 in ('斤', '公斤') and s.销售数量 > 0:
            qty = s.销售数量 * 2 if s.单位 == '公斤' else s.销售数量  # 统一换算为斤
            flavor_qty[s.菜品名称].append(qty)

    if not flavor_qty:
        return findings

    # 每个口味的称重统计
    flavor_stats = {}
    for name, quantities in flavor_qty.items():
        flavor_stats[name] = {
            "avg": mean(quantities),
            "median": median(quantities),
            "count": len(quantities),
            "total": sum(quantities),
        }

    # 排序看哪个口味称重最高
    ranked = sorted(flavor_stats.items(), key=lambda x: x[1]["avg"], reverse=True)
    lines = []
    for name, stats in ranked[:5]:
        lines.append(f"  {name}: 均{stats['avg']:.1f}斤/碗, 共{stats['count']}碗, 中位{stats['median']:.1f}斤")

    if lines:
        findings.append(Finding(
            level="green",
            title="称重结构一览",
            evidence="\n".join(lines),
            impact="香锅称重最高说明客人拿得多——炒着吃更像一顿饭。低称重的口味可以研究为什么拿得少",
            suggestion="把称重最低的口味（通常番茄/冒菜偏汤）做套餐搭配，用饮料/小食补客单价",
            expect="推套餐后低称重口味的客单价可追平均值",
        ))

    # 所有称重菜的分布
    all_qtys = []
    for qs in flavor_qty.values():
        all_qtys.extend(qs)

    if all_qtys:
        # 分段
        q25 = sorted(all_qtys)[len(all_qtys) // 4]
        q50 = median(all_qtys)
        q75 = sorted(all_qtys)[len(all_qtys) * 3 // 4]
        q90 = sorted(all_qtys)[int(len(all_qtys) * 0.9)]

        findings.append(Finding(
            level="green",
            title=f"称重分布: 25%≤{q25:.1f}斤 中位{q50:.1f}斤 75%≤{q75:.1f}斤 90%≤{q90:.1f}斤",
            evidence=f"基于 {len(all_qtys)} 碗称重菜统计，均重 {mean(all_qtys):.1f} 斤",
            impact="称重数据是客单价的核心驱动力，持续追踪看有没有往下掉",
            suggestion="每月对比一次称重分布。如果中位数下移了，说明客人拿得少了，要排查食材陈列/新鲜度",
            data={"p25": round(q25, 1), "p50": round(q50, 1), "p75": round(q75, 1),
                   "p90": round(q90, 1), "mean": round(mean(all_qtys), 1)},
        ))

    return findings
