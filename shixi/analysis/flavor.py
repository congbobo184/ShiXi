"""角度二：口味格局 — 几种口味的此消彼长"""

from collections import defaultdict
from statistics import mean
from typing import List
from shixi.core.schema import DishSale, Finding


def diagnose(sales: List[DishSale], store_config: dict) -> List[Finding]:
    findings = []

    # 称重菜各口味收入
    flavor_rev = defaultdict(float)
    flavor_count = defaultdict(int)
    for s in sales:
        if s.菜品大类 == '称重菜' and s.菜品收入 > 0:
            flavor_rev[s.菜品名称] += s.菜品收入
            flavor_count[s.菜品名称] += 1

    if not flavor_rev:
        return findings

    total = sum(flavor_rev.values())
    ranked = sorted(flavor_rev.items(), key=lambda x: x[1], reverse=True)

    # 口味集中度
    top1_pct = ranked[0][1] / total * 100 if ranked else 0
    top2_pct = (ranked[0][1] + ranked[1][1]) / total * 100 if len(ranked) >= 2 else top1_pct

    if top1_pct > 40:
        findings.append(Finding(
            level="red",
            title=f"口味过度集中: 「{ranked[0][0]}」一个味占称重菜收入的 {top1_pct:.0f}%",
            evidence=f"前两名合计 {top2_pct:.0f}%。客人每次来都点同一个味，口味疲劳风险高",
            impact="万一口味审美疲劳或出现更强的竞品口味，营收直接腰斩",
            suggestion=f"①重点推第二口味「{ranked[1][0]}」，门口海报/收银推荐\n"
                       f"②暑期前测试一个新口味（藤椒/酸菜/海鲜），降低口味风险",
            expect="第二口味推起来后，口味集中度降到40%以下，抗风险能力翻倍"
        ))
    elif top1_pct > 30:
        findings.append(Finding(
            level="yellow",
            title=f"「{ranked[0][0]}」占 {top1_pct:.0f}%，口味偏集中",
            evidence=f"前两名合计 {top2_pct:.0f}%。还在健康范围但要注意",
            impact="持续下去可能口味疲劳",
            suggestion="逐步推第二口味，不要让一个口味一家独大",
        ))

    # 口味排行
    lines = []
    for name, rev in ranked:
        pct = rev / total * 100
        cnt = flavor_count[name]
        lines.append(f"  {name}: {pct:.0f}% ({cnt}碗)")

    findings.append(Finding(
        level="green",
        title="口味收入格局",
        evidence="\n".join(lines),
        impact="—",
        suggestion="品牌叫'小谷姐姐麻辣拌'，但店里麻辣拌才排第几？品牌特色没打出来",
        expect="突出麻辣拌后，这个品牌特色口味的占比应提升",
    ))

    # 按月度看口味趋势（用日均收入，避免月份天数不同不可比）
    by_month = defaultdict(lambda: defaultdict(float))
    month_days = defaultdict(set)
    for s in sales:
        if s.菜品大类 == '称重菜' and s.营业日期 and s.菜品收入 > 0:
            by_month[s.营业日期.month][s.菜品名称] += s.菜品收入
            month_days[s.营业日期.month].add(s.营业日期)

    months = sorted(by_month)
    if len(months) >= 3:
        first_month = months[0]
        last_month = months[-1]

        # 日均收入
        fdays = len(month_days[first_month])
        ldays = len(month_days[last_month])
        if fdays > 0 and ldays > 0:
            growth = {}
            for name in flavor_rev:
                fm_daily = by_month[first_month].get(name, 0) / fdays
                lm_daily = by_month[last_month].get(name, 0) / ldays
                if fm_daily > 0:
                    growth[name] = (lm_daily - fm_daily) / fm_daily

        growing = [(n, g) for n, g in growth.items() if g > 0.2]
        if growing:
            growing.sort(key=lambda x: x[1], reverse=True)
            names = [f"{n}(+{g:.0%})" for n, g in growing[:3]]
            findings.append(Finding(
                level="green",
                title=f"增长中的口味: {', '.join(names)}",
                evidence=f"对比{first_month}月→{last_month}月",
                impact="这些口味在涨，值得重点投入",
                suggestion="增长快的口味加大推广，可能成为第二增长点",
            ))

        declining = [(n, g) for n, g in growth.items() if g < -0.2]
        if declining:
            declining.sort(key=lambda x: x[1])
            names = [f"{n}({g:.0%})" for n, g in declining[:3]]
            findings.append(Finding(
                level="yellow",
                title=f"下滑中的口味: {', '.join(names)}",
                evidence=f"对比{first_month}月→{last_month}月",
                impact="持续下滑可能需要换掉或改进",
                suggestion="排查原因：口味本身不好吃？还是推广不够？",
            ))

    return findings
