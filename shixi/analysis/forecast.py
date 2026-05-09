"""客流预测 — 短期预测 + 暑期预估 + 异常检测"""

from collections import defaultdict
from datetime import date, timedelta
from statistics import mean
from typing import List
from shixi.core.schema import DishSale, Finding


def forecast(sales: List[DishSale], store_config: dict = None) -> List[Finding]:
    daily = _build_daily(sales)
    if not daily:
        return [Finding(module="forecast", type="prediction", priority="medium",
                        title="数据不足", detail="至少需要14天数据")]

    findings = []
    findings.extend(_next_week_forecast(daily))
    findings.extend(_summer_forecast(daily, store_config))
    findings.extend(_anomaly_check(daily))
    return findings


def _build_daily(sales: List[DishSale]) -> dict:
    daily = defaultdict(set)
    for s in sales:
        if s.营业日期:
            daily[s.营业日期].add(s.real_order_id)
    return daily


def _next_week_forecast(daily: dict) -> List[Finding]:
    findings = []
    last_date = max(daily.keys())
    all_dates = sorted(daily)
    daily_counts = {d: len(oids) for d, oids in daily.items()}

    if len(all_dates) < 14:
        return [Finding(module="forecast", type="prediction", priority="medium",
                        title="数据少于14天，预测仅供参考",
                        detail=f"当前 {len(all_dates)} 天数据")]

    # 星期因子
    weekday_counts = defaultdict(list)
    for d, cnt in daily_counts.items():
        weekday_counts[d.weekday()].append(cnt)
    weekday_avg = {wd: mean(cnts) for wd, cnts in weekday_counts.items() if cnts}
    overall_avg = mean(daily_counts.values()) if daily_counts else 1

    # 趋势
    recent = [daily_counts[d] for d in all_dates[-14:]]
    trend = mean(recent[-7:]) / mean(recent[:7]) if len(recent) >= 14 and mean(recent[:7]) > 0 else 1.0

    week_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    base = mean(recent[-7:]) if recent else 0
    predictions = []
    for i in range(1, 8):
        fd = last_date + timedelta(days=i)
        wd = fd.weekday()
        factor = weekday_avg.get(wd, overall_avg)
        pred = base * factor / overall_avg * trend
        predictions.append((fd, week_names[wd], pred))

    if predictions:
        lines = [f"{d.strftime('%m/%d')} {wn}: ~{p:.0f} 单" for d, wn, p in predictions]
        findings.append(Finding(
            module="forecast", type="prediction", priority="medium",
            title="未来7天客流预测",
            detail="\n".join(lines),
            recommendation="基于历史趋势+星期规律，实际可能受天气影响"
        ))
    return findings


def _summer_forecast(daily: dict, store_config: dict = None) -> List[Finding]:
    store_type = "coastal_tourist"
    if store_config:
        store_type = store_config.get('location', {}).get('type', 'coastal_tourist')

    multipliers = {
        "coastal_tourist": {"7": 3.0, "8": 3.5, "msg": "石岛湾暑期游客爆发，日均可达淡季3-4倍"},
    }
    mt = multipliers.get(store_type, multipliers["coastal_tourist"])

    off_peak = [len(oids) for d, oids in daily.items() if d.month <= 4]
    if not off_peak:
        return []

    base = mean(off_peak)
    jul_est = round(base * mt["7"])
    aug_est = round(base * mt["8"])
    avg_ticket = 36  # 基于现有数据

    return [Finding(
        module="forecast", type="prediction", priority="high",
        title=f"暑期客流预测: 7月日均 ~{jul_est}单, 8月日均 ~{aug_est}单（淡季 {base:.0f} 单）",
        detail=f"{mt['msg']}。预估日均营业额: 7月 ¥{jul_est * avg_ticket:.0f}, 8月 ¥{aug_est * avg_ticket:.0f}",
        recommendation="提前2周备料、确认暑期人手、门口做醒目标识",
        data={"jul_daily": jul_est, "aug_daily": aug_est, "base": round(base, 1)}
    )]


def _anomaly_check(daily: dict) -> List[Finding]:
    findings = []
    dates = sorted(daily)
    daily_counts = {d: len(oids) for d, oids in daily.items()}
    if len(dates) < 14:
        return findings

    recent = [daily_counts[d] for d in dates[-7:]]
    prev = [daily_counts[d] for d in dates[-14:-7]]
    recent_avg = mean(recent)
    prev_avg = mean(prev) if prev else 1
    change = (recent_avg - prev_avg) / prev_avg if prev_avg > 0 else 0

    if abs(change) > 0.3:
        direction = "上升" if change > 0 else "下降"
        findings.append(Finding(
            module="forecast", type="strength" if change > 0 else "problem",
            priority="medium",
            title=f"近7天客流异常{direction}: {'+' if change > 0 else ''}{change:.0%}",
            detail=f"近7天 {recent_avg:.0f} 单/天 vs 前7天 {prev_avg:.0f} 单/天",
            recommendation="持续关注" if change < 0 else "趋势向好，保持节奏"
        ))

    return findings
