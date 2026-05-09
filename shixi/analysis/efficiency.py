"""角度五：时段效率 — 什么时候赚钱、什么时候白烧钱"""

from collections import defaultdict
from statistics import mean
from typing import List
from shixi.core.schema import DishSale, Finding


def diagnose(sales: List[DishSale], store_config: dict) -> List[Finding]:
    findings = []

    # 每个订单归属到哪个小时（取最早的菜品时间）
    order_hour = {}
    order_rev = {}
    for s in sales:
        if s.点菜时间:
            if s.real_order_id not in order_hour:
                order_hour[s.real_order_id] = s.点菜时间.hour
        if s.real_order_id not in order_rev and s.订单收入 > 0:
            order_rev[s.real_order_id] = s.订单收入

    # 按小时汇总（每个订单只算一次）
    hour_orders = defaultdict(int)
    hour_rev = defaultdict(float)
    rev_items = defaultdict(int)
    for oid, h in order_hour.items():
        hour_orders[h] += 1
        hour_rev[h] += order_rev.get(oid, 0)
    # 也统计菜品级别的小时分布
    hour_items = defaultdict(int)
    for s in sales:
        if s.点菜时间:
            hour_items[s.点菜时间.hour] += 1

    total_rev = sum(order_rev.values())
    total_orders = len(order_hour)

    # 午晚高峰对比
    lunch_orders = sum(hour_orders.get(h, 0) for h in range(11, 14))
    dinner_orders = sum(hour_orders.get(h, 0) for h in range(17, 20))

    lunch_pct = sum(hour_rev.get(h, 0) for h in range(11, 14)) / total_rev * 100 if total_rev > 0 else 0
    dinner_pct = sum(hour_rev.get(h, 0) for h in range(17, 20)) / total_rev * 100 if total_rev > 0 else 0

    if dinner_orders < lunch_orders * 0.9:
        peak_impact = "晚高峰显著弱于午高峰，周边居民没把你当晚饭食堂"
        peak_suggestion = "推'下班一人食'定位。暑期游客上来后晚高峰自然变强"
    else:
        peak_impact = "双峰均衡，午晚都有稳定客流"
        peak_suggestion = "高峰前30分钟确保汤底滚、食材补齐"

    findings.append(Finding(
        level="green",
        title=f"午高峰(11-13) {lunch_orders}单({lunch_pct:.0f}%), 晚高峰(17-19) {dinner_orders}单({dinner_pct:.0f}%)",
        evidence=f"{'晚高峰强' if dinner_orders > lunch_orders else '午高峰强'}，差距 {abs(dinner_orders - lunch_orders)} 单",
        impact=peak_impact,
        suggestion=peak_suggestion,
    ))

    # 小时分布
    if total_orders > 0:
        hours = sorted(hour_orders)
        peak_hour = max(hour_orders, key=hour_orders.get)
        findings.append(Finding(
            level="green",
            title=f"全天高峰 {peak_hour}:00（{hour_orders[peak_hour]}单），"
                 f"午/晚双峰模式",
            evidence=" → ".join(f"{h}h:{hour_orders[h]}单" for h in [11,12,13,17,18,19] if h in hour_orders),
            impact="—",
            suggestion="高峰前30分钟确保汤底滚、食材补齐、人手到位",
        ))

    # 空窗期
    dead_hours = []
    for h in range(8, 23):
        if hour_orders.get(h, 0) < 2:
            dead_hours.append(h)

    if dead_hours:
        ranges = []
        start = dead_hours[0]
        end = dead_hours[0]
        for h in dead_hours[1:]:
            if h == end + 1:
                end = h
            else:
                ranges.append((start, end))
                start, end = h, h
        ranges.append((start, end))

        for sh, eh in ranges:
            if eh - sh >= 2 and sh >= 14:
                findings.append(Finding(
                    level="yellow",
                    title=f"下午空窗 {sh}:00-{eh}:00（{eh-sh+1}小时<2单/小时）",
                    evidence=f"几乎零单，开着门白烧人工水电",
                    impact="每天烧3小时无用功",
                    suggestion=f"{sh}:00-{eh}:00关门休息或只做备料。暑期游客下午可能来，到时候再开",
                    expect="每天省几小时人工水电",
                ))

    # 营业时长
    daily_bounds = defaultdict(lambda: {"e": None, "l": None})
    for s in sales:
        if s.点菜时间 and s.营业日期:
            t = s.点菜时间
            b = daily_bounds[s.营业日期]
            if b["e"] is None or t < b["e"]:
                b["e"] = t
            if b["l"] is None or t > b["l"]:
                b["l"] = t

    open_times = [b["e"].hour + b["e"].minute / 60 for b in daily_bounds.values() if b["e"]]
    close_times = [b["l"].hour + b["l"].minute / 60 for b in daily_bounds.values() if b["l"]]

    if open_times and close_times:
        avg_open = mean(open_times)
        avg_close = mean(close_times)
        findings.append(Finding(
            level="green",
            title=f"日均营业 {avg_close-avg_open:.1f}h "
                 f"({avg_open:.0f}:{int((avg_open%1)*60):02d}-{avg_close:.0f}:{int((avg_close%1)*60):02d})",
            evidence="—",
            impact="—",
            suggestion="暑期可早开晚收：游客上午出门，晚上海边玩完还要吃饭",
        ))

    # 周末 vs 平日
    by_date = defaultdict(set)
    for s in sales:
        if s.营业日期:
            by_date[s.营业日期].add(s.real_order_id)

    we, wd = [], []
    for d, oids in by_date.items():
        (we if d.weekday() >= 5 else wd).append(len(oids))

    if we and wd:
        we_avg = mean(we)
        wd_avg = mean(wd)
        ratio = we_avg / wd_avg if wd_avg > 0 else 1
        if ratio < 1.15:
            findings.append(Finding(
                level="yellow",
                title=f"周末 {we_avg:.0f}单 vs 平日 {wd_avg:.0f}单（仅+{ratio-1:.0%}）",
                evidence="石岛湾沿海旅游区，周末该更好",
                impact="周末红利没吃到",
                suggestion="周末黑板特价、微信群推周末限定",
                expect="周末1.3x平日以上",
            ))

    return findings
