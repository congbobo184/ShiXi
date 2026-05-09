"""营业节奏诊断 — 从时间维度发现经营问题"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import List
from statistics import mean, median
from shixi.core.schema import DishSale, Finding


def diagnose(sales: List[DishSale]) -> List[Finding]:
    """诊断营业节奏，返回发现列表"""
    findings = []

    # 按日期、订单分组
    orders_by_date = defaultdict(list)
    for s in sales:
        if s.营业日期:
            orders_by_date[s.营业日期].append(s)

    if not orders_by_date:
        return [Finding(module="diagnostic", type="problem", priority="high",
                        title="无有效数据", detail="未能从数据中解析到营业日期")]

    findings.extend(_analyze_hours(sales))
    findings.extend(_analyze_peak_utilization(sales))
    findings.extend(_analyze_weekend_vs_weekday(sales))
    findings.extend(_analyze_ticket_size(sales))
    findings.extend(_analyze_monthly_trend(sales))

    return findings


def _analyze_hours(sales: List[DishSale]) -> List[Finding]:
    """分析出摊收摊时间与空窗期"""
    findings = []

    # 每日最早、最晚点菜时间
    daily_bounds = defaultdict(lambda: {"earliest": None, "latest": None})
    for s in sales:
        if s.点菜时间 and s.营业日期:
            t = s.点菜时间
            if daily_bounds[s.营业日期]["earliest"] is None or t < daily_bounds[s.营业日期]["earliest"]:
                daily_bounds[s.营业日期]["earliest"] = t
            if daily_bounds[s.营业日期]["latest"] is None or t > daily_bounds[s.营业日期]["latest"]:
                daily_bounds[s.营业日期]["latest"] = t

    open_times = [b["earliest"] for b in daily_bounds.values() if b["earliest"]]
    close_times = [b["latest"] for b in daily_bounds.values() if b["latest"]]

    if open_times and close_times:
        avg_open_hour = mean(t.hour + t.minute / 60 for t in open_times)
        avg_close_hour = mean(t.hour + t.minute / 60 for t in close_times)
        earliest_open = min(open_times)
        latest_close = max(close_times)

        findings.append(Finding(
            module="diagnostic", type="strength", priority="medium",
            title=f"日均营业时长约 {avg_close_hour - avg_open_hour:.1f} 小时",
            detail=f"平均 {avg_open_hour:.0f}:{int((avg_open_hour % 1) * 60):02d} 开摊, "
                   f"{avg_close_hour:.0f}:{int((avg_close_hour % 1) * 60):02d} 收摊",
            data={"avg_open": f"{avg_open_hour:.1f}", "avg_close": f"{avg_close_hour:.1f}"}
        ))

        # 开门时间是否偏晚？
        if avg_open_hour > 10:
            findings.append(Finding(
                module="diagnostic", type="problem", priority="high",
                title=f"开门偏晚（日均 {avg_open_hour:.0f}:{int((avg_open_hour%1)*60):02d}），可能错失早间客流",
                detail=f"最早记录 {earliest_open.strftime('%H:%M')}，但日均开门在 {avg_open_hour:.0f}:{int((avg_open_hour%1)*60):02d}，"
                       f"说明多数日子开得晚。石岛湾周边居民+游客，上午10点后就有人流",
                recommendation="建议稳定10:00前开门。暑期游客更早出门，可提至9:30"
            ))

        # 空窗期分析
        hour_counts = defaultdict(int)
        for s in sales:
            if s.点菜时间:
                hour_counts[s.点菜时间.hour] += 1

        dead_hours = []
        for h in range(8, 23):
            if hour_counts.get(h, 0) < 10:  # 少于10条菜品记录算空窗
                dead_hours.append(h)

        if dead_hours:
            # 合并连续空窗时段
            ranges = []
            start = dead_hours[0]
            end = dead_hours[0]
            for h in dead_hours[1:]:
                if h == end + 1:
                    end = h
                else:
                    ranges.append((start, end))
                    start = h
                    end = h
            ranges.append((start, end))

            for s_h, e_h in ranges:
                if e_h - s_h >= 2:  # 连续2小时以上空窗
                    findings.append(Finding(
                        module="diagnostic", type="problem", priority="medium",
                        title=f"空窗期: {s_h}:00-{e_h}:00（连续 {e_h - s_h + 1} 小时几乎无单）",
                        detail=f"该时段累计菜品记录不足10条，客流极低",
                        recommendation=f"考虑 {s_h}:00 前后暂时休息或做备料，把人手集中到高峰期"
                    ))

    return findings


def _analyze_peak_utilization(sales: List[DishSale]) -> List[Finding]:
    """分析午晚高峰利用率"""
    findings = []

    # 午高峰 11:00-13:00, 晚高峰 17:00-19:00
    lunch_rev = 0.0
    dinner_rev = 0.0
    total_rev = 0.0
    lunch_orders = set()
    dinner_orders = set()
    all_orders = set()

    for s in sales:
        if s.订单收入 > 0:
            total_rev += s.订单收入
            all_orders.add(s.订单编号)
            if s.点菜时间:
                h = s.点菜时间.hour
                if 11 <= h < 13:
                    lunch_rev += s.订单收入
                    lunch_orders.add(s.订单编号)
                elif 17 <= h < 19:
                    dinner_rev += s.订单收入
                    dinner_orders.add(s.订单编号)

    if total_rev > 0:
        lunch_pct = lunch_rev / total_rev * 100
        dinner_pct = dinner_rev / total_rev * 100

        findings.append(Finding(
            module="diagnostic", type="strength", priority="low",
            title=f"午高峰(11-13点)贡献 {lunch_pct:.0f}% 营收, 晚高峰(17-19点)贡献 {dinner_pct:.0f}%",
            detail=f"两高峰合计 {lunch_pct + dinner_pct:.0f}%。午高峰 {len(lunch_orders)} 单, 晚高峰 {len(dinner_orders)} 单",
            data={"lunch_pct": round(lunch_pct), "dinner_pct": round(dinner_pct)}
        ))

        if dinner_pct < lunch_pct * 0.8:
            findings.append(Finding(
                module="diagnostic", type="problem", priority="medium",
                title="晚高峰不如午高峰，晚餐客流未充分捕获",
                detail=f"晚高峰营收占比 ({dinner_pct:.0f}%) 明显低于午高峰 ({lunch_pct:.0f}%)",
                recommendation="检查晚餐时段是否有周边竞争？或者石岛湾居民习惯在家吃晚饭？可推晚间特价/夜宵场景"
            ))

    return findings


def _analyze_weekend_vs_weekday(sales: List[DishSale]) -> List[Finding]:
    """工作日与周末对比"""
    findings = []

    by_date = defaultdict(lambda: {"orders": set(), "revenue": 0.0})
    for s in sales:
        if s.营业日期:
            d = s.营业日期
            by_date[d]["orders"].add(s.订单编号)
            by_date[d]["revenue"] += s.订单收入

    weekend = []
    weekday = []
    for d, v in by_date.items():
        # 去重：用订单首行收入
        if d.weekday() >= 5:
            weekend.append(len(v["orders"]))
        else:
            weekday.append(len(v["orders"]))

    if weekend and weekday:
        we_avg = mean(weekend)
        wd_avg = mean(weekday)
        ratio = we_avg / wd_avg if wd_avg > 0 else 1

        if ratio < 1.1:
            findings.append(Finding(
                module="diagnostic", type="problem", priority="medium",
                title=f"周末日均 {we_avg:.1f} 单 vs 工作日 {wd_avg:.1f} 单，几乎无周末溢价",
                detail=f"周末仅比工作日多 {ratio - 1:.0%}。石岛湾非写字楼商圈，周末客流理应更高",
                recommendation="周末有没有特别活动？暑期周末应加大宣传，游客周末集中出行"
            ))
        else:
            findings.append(Finding(
                module="diagnostic", type="strength", priority="low",
                title=f"周末日均 {we_avg:.1f} 单, 比工作日高 {ratio - 1:.0%}",
                detail="周末客流有提升，合理"
            ))

    return findings


def _analyze_ticket_size(sales: List[DishSale]) -> List[Finding]:
    """客单价分析"""
    findings = []

    order_revenue = {}
    order_items = defaultdict(int)
    for s in sales:
        if s.订单收入 > 0:
            order_revenue[s.订单编号] = s.订单收入
        order_items[s.订单编号] += 1

    revenues = list(order_revenue.values())
    items_per_order = [order_items[oid] for oid in order_revenue]

    if revenues:
        avg_rev = mean(revenues)
        avg_items = mean(items_per_order) if items_per_order else 0

        findings.append(Finding(
            module="diagnostic", type="strength", priority="low",
            title=f"客单价 ¥{avg_rev:.1f}（最高 ¥{max(revenues):.1f}, 最低 ¥{min(revenues):.1f}）",
            detail=f"麻辣烫称重计价，每单含约 {avg_items:.0f} 个称重条目",
            data={"avg_ticket": round(avg_rev, 1)}
        ))

        # 客单价偏低？
        if avg_rev < 30:
            findings.append(Finding(
                module="diagnostic", type="problem", priority="medium",
                title=f"客单价偏低（¥{avg_rev:.1f}），有提升空间",
                detail=f"平均每单仅 {avg_items:.0f} 个菜品，饮料/小食搭售不足",
                recommendation="尝试套餐组合（麻辣烫+饮品+主食一口价），提升客单价"
            ))

    return findings


def _analyze_monthly_trend(sales: List[DishSale]) -> List[Finding]:
    """月度趋势分析"""
    findings = []

    by_month = defaultdict(lambda: {"orders": set(), "revenue": 0.0, "days": set()})
    for s in sales:
        if s.营业日期:
            m = s.营业日期.month
            by_month[m]["orders"].add(s.订单编号)
            by_month[m]["revenue"] += s.订单收入
            by_month[m]["days"].add(s.营业日期)

    months = sorted(by_month)
    if len(months) >= 2:
        # 用日均单数做比较，规避天数不同的问题
        daily_avg_by_month = {}
        for m in months:
            days = len(by_month[m]["days"])
            orders = len(by_month[m]["orders"])
            daily_avg_by_month[m] = orders / days if days > 0 else 0

        all_daily_avgs = list(daily_avg_by_month.values())
        avg_daily = mean(all_daily_avgs)

        for i, m in enumerate(months):
            d_avg = daily_avg_by_month[m]
            if d_avg < avg_daily * 0.7:
                findings.append(Finding(
                    module="diagnostic", type="problem", priority="medium",
                    title=f"{m}月日均仅 {d_avg:.1f} 单，明显低于整体均值 {avg_daily:.1f} 单",
                    detail=f"{m}月共 {len(by_month[m]['orders'])} 单/{len(by_month[m]['days'])} 天。可能是春节返乡或淡季因素",
                    recommendation="春节前后可考虑提前放假/延迟开业，减少无效营业天数"
                ))

        # 趋势方向
        recent_vals = all_daily_avgs[-2:]
        if len(recent_vals) >= 2 and recent_vals[-1] > recent_vals[-2] * 1.2:
            findings.append(Finding(
                module="diagnostic", type="strength", priority="medium",
                title=f"近两个月趋势向好（{months[-2]}月→{months[-1]}月：{recent_vals[0]:.1f}→{recent_vals[1]:.1f}单/天）",
                detail=f"5月进入旅游爬坡期，趋势应持续走高",
                recommendation="5月开始备足料，准备迎接暑期高峰"
            ))

    return findings
