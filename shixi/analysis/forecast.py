"""客流预测 — 短期预测 + 暑期预估 + 异常检测"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean
from typing import List
from shixi.core.schema import DishSale, Finding


def forecast(sales: List[DishSale], store_config: dict = None) -> List[Finding]:
    """生成客流预测"""
    findings = []

    # 构建日级别数据
    daily = _build_daily(sales)
    if not daily:
        return [Finding(module="forecast", type="prediction", priority="medium",
                        title="数据不足，无法预测", detail="至少需要14天数据")]

    findings.extend(_next_week_forecast(daily))
    findings.extend(_summer_forecast(daily, store_config))
    findings.extend(_anomaly_check(daily))

    return findings


def _build_daily(sales: List[DishSale]) -> dict:
    """构建日级别数据 {date: orders}"""
    daily = defaultdict(lambda: {"orders": set(), "revenue": 0.0})
    for s in sales:
        if s.营业日期:
            daily[s.营业日期]["orders"].add(s.订单编号)
            daily[s.营业日期]["revenue"] += s.订单收入
    return daily


def _next_week_forecast(daily: dict) -> List[Finding]:
    """未来7天预测（简单移动平均 + 星期因子）"""
    findings = []

    last_date = max(daily.keys())
    all_dates = sorted(daily)

    if len(all_dates) < 14:
        findings.append(Finding(
            module="forecast", type="prediction", priority="medium",
            title="数据量不足14天，预测仅供参考",
            detail=f"当前可用 {len(all_dates)} 天数据"
        ))
        return findings

    # 计算星期系数
    weekday_counts = defaultdict(list)
    for d, v in daily.items():
        weekday_counts[d.weekday()].append(len(v["orders"]))

    weekday_factor = {wd: mean(cnts) for wd, cnts in weekday_counts.items() if cnts}
    all_daily_counts = [len(v["orders"]) for v in daily.values()]
    overall_avg = mean(all_daily_counts) if all_daily_counts else 1

    def factor_for(wd):
        return weekday_factor.get(wd, overall_avg)

    # 7日移动平均
    recent = [len(daily[d]["orders"]) for d in sorted(daily) if d > last_date - timedelta(days=14)]
    trend = mean(recent[-7:]) / mean(recent[:7]) if len(recent) >= 14 and mean(recent[:7]) > 0 else 1.0

    # 预测未来7天
    week_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    base = mean(recent[-7:]) if recent else 0
    predictions = []
    for i in range(1, 8):
        future_date = last_date + timedelta(days=i)
        wd = future_date.weekday()
        predicted = base * factor_for(wd) / overall_avg * trend
        predictions.append((future_date, week_names[wd], predicted))

    if predictions:
        lines = [f"{d.strftime('%m/%d')} {wn}: 预计 {p:.0f} 单" for d, wn, p in predictions]
        findings.append(Finding(
            module="forecast", type="prediction", priority="medium",
            title="未来7天客流预测",
            detail="\n".join(lines),
            recommendation="预测基于历史趋势+星期规律，实际可能受天气、周边活动影响",
            data={"predictions": [{"date": str(d), "orders": round(p)} for d, _, p in predictions]}
        ))

    return findings


def _summer_forecast(daily: dict, store_config: dict = None) -> List[Finding]:
    """暑期高峰预测"""

    store_type = "coastal_tourist"
    if store_config:
        store_type = store_config.get('location', {}).get('type', 'coastal_tourist')

    # 沿海旅游商圈系数
    multipliers = {
        "coastal_tourist": {"7": 3.5, "8": 4.0, "peak_msg": "石岛湾暑期游客爆发，日均可达淡季3-5倍"},
        "urban_residential": {"7": 1.2, "8": 1.3, "peak_msg": "居民区暑期稳定增长"},
        "campus": {"7": 0.3, "8": 0.2, "peak_msg": "学校商圈暑期断崖下跌"},
    }
    mt = multipliers.get(store_type, multipliers["coastal_tourist"])

    # 计算淡季基线（排除5月以后）
    off_peak_orders = []
    for d, v in daily.items():
        if d.month <= 4:
            off_peak_orders.append(len(v["orders"]))

    if not off_peak_orders:
        return []

    base = mean(off_peak_orders)
    jul_est = base * mt["7"]
    aug_est = base * mt["8"]

    findings = []

    # 简化预测
    today = date.today()
    if today.month < 7:
        findings.append(Finding(
            module="forecast", type="prediction", priority="high",
            title=f"暑期客流预测: 7月日均约 {jul_est:.0f} 单, 8月日均约 {aug_est:.0f} 单",
            detail=f"{mt['peak_msg']}。当前淡季日均 {base:.1f} 单。"
                   f"日均营业额预估: 7月约 ¥{jul_est * 30:.0f}-{jul_est * 40:.0f}, "
                   f"8月约 ¥{aug_est * 30:.0f}-{aug_est * 40:.0f}",
            recommendation="7-8月营收窗口期，建议：1)提前2周备料 2)确认暑期人手 3)门口做醒目标识吸引游客",
            data={"jul_daily_est": round(jul_est), "aug_daily_est": round(aug_est),
                   "base_daily": round(base, 1), "multiplier_7": mt["7"], "multiplier_8": mt["8"]}
        ))
    else:
        findings.append(Finding(
            module="forecast", type="prediction", priority="high",
            title=f"8月预计: 日均约 {aug_est:.0f} 单 (淡季 {base:.1f} 单的 {mt['8']}x)",
            detail=f"{mt['peak_msg']}",
            data={"aug_daily_est": round(aug_est), "base_daily": round(base, 1)}
        ))

    return findings


def _anomaly_check(daily: dict) -> List[Finding]:
    """异常检测 — 最近几天是否偏离预期"""

    dates = sorted(daily)
    if len(dates) < 14:
        return []

    # 最近7天 vs 前7天
    recent_dates = dates[-7:]
    prev_dates = dates[-14:-7]

    recent_avg = mean(len(daily[d]["orders"]) for d in recent_dates)
    prev_avg = mean(len(daily[d]["orders"]) for d in prev_dates) if prev_dates else 1

    change = (recent_avg - prev_avg) / prev_avg if prev_avg > 0 else 0

    findings = []
    if abs(change) > 0.3:
        direction = "上升" if change > 0 else "下降"
        level = "strength" if change > 0 else "problem"

        findings.append(Finding(
            module="forecast", type=level, priority="medium",
            title=f"近7天客流异常{direction}: {'+' if change > 0 else ''}{change:.0%}",
            detail=f"近7天日均 {recent_avg:.1f} 单 vs 前7天 {prev_avg:.1f} 单",
            recommendation="持续关注，如果连续2周异常建议排查原因（天气？周边竞争？节日？）" if change < 0 else "趋势向好，保持现有节奏"
        ))

    # 单日异常检测
    for d in recent_dates:
        orders = len(daily[d]["orders"])
        if orders < recent_avg * 0.3 and orders > 0:
            findings.append(Finding(
                module="forecast", type="problem", priority="low",
                title=f"{d.strftime('%m/%d')} 异常低单量: 仅 {orders} 单（均值的 {orders/recent_avg:.0%}）",
                detail="可能是天气、节假日或周边临时因素导致",
                recommendation="回顾当日是否有特殊原因（大雨？停电？提前关门？）"
            ))

    return findings
