"""营业节奏诊断 — 从时间维度发现经营问题"""

from collections import defaultdict
from typing import List
from statistics import mean
from shixi.core.schema import DishSale, Finding


def diagnose(sales: List[DishSale]) -> List[Finding]:
    findings = []
    if not sales:
        return [Finding(module="diagnostic", type="problem", priority="high",
                        title="无有效数据", detail="未能从数据中解析到营业日期")]
    findings.extend(_analyze_hours(sales))
    findings.extend(_analyze_peak_utilization(sales))
    findings.extend(_analyze_weekend_vs_weekday(sales))
    findings.extend(_analyze_ticket_size(sales))
    findings.extend(_analyze_monthly_trend(sales))
    return findings


def _order_revenue_map(sales: List[DishSale]) -> dict:
    """构建 real_order_id -> 订单收入 映射（去重取第一条）"""
    m = {}
    for s in sales:
        oid = s.real_order_id
        if oid not in m and s.订单收入 > 0:
            m[oid] = s.订单收入
    return m


def _analyze_hours(sales: List[DishSale]) -> List[Finding]:
    findings = []
    daily_bounds = defaultdict(lambda: {"earliest": None, "latest": None})
    for s in sales:
        if s.点菜时间 and s.营业日期:
            t = s.点菜时间
            b = daily_bounds[s.营业日期]
            if b["earliest"] is None or t < b["earliest"]:
                b["earliest"] = t
            if b["latest"] is None or t > b["latest"]:
                b["latest"] = t

    open_times = [b["earliest"] for b in daily_bounds.values() if b["earliest"]]
    close_times = [b["latest"] for b in daily_bounds.values() if b["latest"]]

    if open_times and close_times:
        avg_open = mean(t.hour + t.minute / 60 for t in open_times)
        avg_close = mean(t.hour + t.minute / 60 for t in close_times)

        findings.append(Finding(
            module="diagnostic", type="strength", priority="medium",
            title=f"日均营业 {avg_close - avg_open:.1f} 小时",
            detail=f"平均 {avg_open:.0f}:{int((avg_open % 1) * 60):02d} 开摊, "
                   f"{avg_close:.0f}:{int((avg_close % 1) * 60):02d} 收摊",
            data={"avg_open": f"{avg_open:.1f}", "avg_close": f"{avg_close:.1f}"}
        ))
        if avg_open > 10:
            findings.append(Finding(
                module="diagnostic", type="problem", priority="high",
                title=f"开门偏晚（日均 {avg_open:.0f}:{int((avg_open%1)*60):02d}）",
                detail="石岛湾周边居民+游客，上午10点后就有人流",
                recommendation="建议稳定10:00前开门。暑期游客更早出门，可提至9:30"
            ))
    return findings


def _analyze_peak_utilization(sales: List[DishSale]) -> List[Finding]:
    findings = []
    rev_map = _order_revenue_map(sales)

    lunch_oids = set()
    dinner_oids = set()
    for s in sales:
        oid = s.real_order_id
        if s.点菜时间:
            h = s.点菜时间.hour
            if 11 <= h < 13:
                lunch_oids.add(oid)
            elif 17 <= h < 19:
                dinner_oids.add(oid)

    lunch_rev = sum(rev_map.get(oid, 0) for oid in lunch_oids)
    dinner_rev = sum(rev_map.get(oid, 0) for oid in dinner_oids)
    total_rev = sum(rev_map.values())

    if total_rev > 0:
        lp = lunch_rev / total_rev * 100
        dp = dinner_rev / total_rev * 100
        findings.append(Finding(
            module="diagnostic", type="strength", priority="low",
            title=f"午高峰(11-13)贡献 {lp:.0f}% 营收, 晚高峰(17-19)贡献 {dp:.0f}%",
            detail=f"两高峰合计 {lp + dp:.0f}%。午高峰 {len(lunch_oids)} 单, 晚高峰 {len(dinner_oids)} 单",
            data={"lunch_pct": round(lp), "dinner_pct": round(dp)}
        ))
        if dp < lp * 0.8:
            findings.append(Finding(
                module="diagnostic", type="problem", priority="medium",
                title="晚高峰不如午高峰",
                detail=f"晚高峰({dp:.0f}%) vs 午高峰({lp:.0f}%)",
                recommendation="检查晚餐时段竞争情况，可推晚间特价/夜宵"
            ))
    return findings


def _analyze_weekend_vs_weekday(sales: List[DishSale]) -> List[Finding]:
    findings = []
    by_date = defaultdict(set)
    for s in sales:
        if s.营业日期:
            by_date[s.营业日期].add(s.real_order_id)

    weekend = []
    weekday = []
    for d, oids in by_date.items():
        (weekend if d.weekday() >= 5 else weekday).append(len(oids))

    if weekend and weekday:
        we_avg = mean(weekend)
        wd_avg = mean(weekday)
        ratio = we_avg / wd_avg if wd_avg > 0 else 1
        if ratio < 1.15:
            findings.append(Finding(
                module="diagnostic", type="problem", priority="medium",
                title=f"周末 {we_avg:.0f} 单 vs 工作日 {wd_avg:.0f} 单, 无周末溢价",
                detail=f"周末仅多 {ratio - 1:.0%}。石岛湾非写字楼商圈，周末理应更高",
                recommendation="周末做活动拉客流，暑期周末游客密集"
            ))
        else:
            findings.append(Finding(
                module="diagnostic", type="strength", priority="low",
                title=f"周末 {we_avg:.0f} 单, 比工作日高 {ratio - 1:.0%}",
                detail="周末客流有提升"
            ))
    return findings


def _analyze_ticket_size(sales: List[DishSale]) -> List[Finding]:
    findings = []
    rev_map = _order_revenue_map(sales)
    order_items = defaultdict(int)
    for s in sales:
        order_items[s.real_order_id] += 1

    revenues = list(rev_map.values())
    if revenues:
        avg_rev = mean(revenues)
        avg_items = mean(order_items.values()) if order_items else 0
        findings.append(Finding(
            module="diagnostic", type="strength", priority="low",
            title=f"客单价 ¥{avg_rev:.1f}, 每单约 {avg_items:.0f} 个称重条目",
            detail=f"最高 ¥{max(revenues):.0f}, 最低 ¥{min(revenues):.0f}",
            data={"avg_ticket": round(avg_rev, 1)}
        ))
        if avg_rev < 25:
            findings.append(Finding(
                module="diagnostic", type="problem", priority="medium",
                title=f"客单价偏低（¥{avg_rev:.1f}）",
                detail="建议推套餐拉高客单价",
                recommendation="麻辣烫+饮品+主食一口价套餐"
            ))
    return findings


def _analyze_monthly_trend(sales: List[DishSale]) -> List[Finding]:
    findings = []
    by_month = defaultdict(lambda: {"orders": set(), "days": set()})
    for s in sales:
        if s.营业日期:
            m = s.营业日期.month
            by_month[m]["orders"].add(s.real_order_id)
            by_month[m]["days"].add(s.营业日期)

    months = sorted(by_month)
    if len(months) < 2:
        return findings

    daily_avg = {}
    for m in months:
        d = len(by_month[m]["days"])
        o = len(by_month[m]["orders"])
        daily_avg[m] = o / d if d > 0 else 0

    avg_daily = mean(daily_avg.values())
    for m in months:
        if daily_avg[m] < avg_daily * 0.7:
            findings.append(Finding(
                module="diagnostic", type="problem", priority="medium",
                title=f"{m}月日均仅 {daily_avg[m]:.0f} 单（整体均值 {avg_daily:.0f}）",
                detail="可能是春节返乡或淡季因素",
                recommendation="春节前后可提前放假/延迟开业"
            ))

    vals = list(daily_avg.values())
    if len(vals) >= 2 and vals[-1] > vals[-2] * 1.15:
        findings.append(Finding(
            module="diagnostic", type="strength", priority="medium",
            title="近两月趋势向好，旅游季爬坡中",
            detail="5月已进入旅游旺季，趋势持续走高",
            recommendation="备足料迎接暑期高峰"
        ))
    return findings
