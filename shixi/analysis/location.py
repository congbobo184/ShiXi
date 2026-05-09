"""位置洞察 — 商圈类型、淡旺季、本地/游客推断"""

from collections import defaultdict
from typing import List
from shixi.core.schema import DishSale, Finding

STORE_TYPE_PROFILES = {
    "coastal_tourist": {
        "name": "沿海旅游商圈",
        "tourist_months": [5, 6, 7, 8, 9, 10],
        "peak_months": [7, 8],
        "peak_multiplier": 3.5,
        "shoulder_multiplier": 1.5,
        "traits": [
            "暑期(7-8月)爆发式增长，游客为主",
            "淡季(11-4月)以本地居民为主",
            "游客就餐时间更集中(12点午饭、18点晚饭)",
            "游客客单价通常高于本地居民",
        ],
        "recommendations": [
            "5月开始逐步备料，7-8月备足2-3倍食材",
            "暑期延长晚间营业时间，游客夜宵需求强",
            "淡季侧重本地客维护（微信群、熟客优惠）",
            "暑期门口立牌/引导牌，游客靠视觉决策",
        ]
    },
}


def analyze(sales: List[DishSale], store_config: dict) -> List[Finding]:
    findings = []
    store_type = store_config.get('location', {}).get('type', 'coastal_tourist')
    profile = STORE_TYPE_PROFILES.get(store_type, STORE_TYPE_PROFILES['coastal_tourist'])

    findings.extend(_seasonal_analysis(sales, profile))
    findings.extend(_local_vs_tourist_inference(sales, profile))
    findings.extend(_store_type_info(profile, store_config))

    return findings


def _seasonal_analysis(sales: List[DishSale], profile: dict) -> List[Finding]:
    findings = []
    by_month = defaultdict(lambda: {"orders": set(), "days": set()})
    for s in sales:
        if s.营业日期:
            m = s.营业日期.month
            by_month[m]["orders"].add(s.real_order_id)
            by_month[m]["days"].add(s.营业日期)

    tourist_months = set(profile.get('tourist_months', [7, 8]))
    peak_mult = profile.get('peak_multiplier', 3.0)

    off_peak = [m for m in by_month if m not in tourist_months]
    if off_peak:
        off_daily = sum(len(by_month[m]["orders"]) / len(by_month[m]["days"])
                        for m in off_peak if by_month[m]["days"]) / len(off_peak)

        if 5 in by_month and off_daily > 0:
            may_daily = len(by_month[5]["orders"]) / len(by_month[5]["days"]) if by_month[5]["days"] else 0
            if may_daily > off_daily * 1.2:
                findings.append(Finding(
                    module="location", type="strength", priority="medium",
                    title=f"5月日均 {may_daily:.0f} 单, 比淡季 {off_daily:.0f} 单高 {may_daily/off_daily-1:.0%}",
                    detail="旅游季已开始爬坡，趋势向好",
                    recommendation="暑期(7-8月)预计日均 {off_daily * peak_mult:.0f}-{off_daily * peak_mult * 1.5:.0f} 单，提前备料"
                ))

        findings.append(Finding(
            module="location", type="prediction", priority="high",
            title=f"暑期(7-8月)客流预测: 日均约淡季的 {peak_mult:.0f}x",
            detail=f"淡季日均 {off_daily:.0f} 单, 暑期预计 {off_daily * peak_mult:.0f}-{off_daily * peak_mult * 1.5:.0f} 单",
            recommendation=f"7-8月提前备料（建议淡季{peak_mult:.0f}倍起），适当增加人手",
            data={"off_peak_daily": round(off_daily, 1),
                   "peak_low": round(off_daily * peak_mult),
                   "peak_high": round(off_daily * peak_mult * 1.5)}
        ))
    return findings


def _local_vs_tourist_inference(sales: List[DishSale], profile: dict) -> List[Finding]:
    findings = []
    tourist_months = set(profile.get('tourist_months', [7, 8]))

    by_hour = {"local": defaultdict(int), "tourist": defaultdict(int)}
    for s in sales:
        if s.点菜时间 and s.营业日期:
            h = s.点菜时间.hour
            key = "tourist" if s.营业日期.month in tourist_months else "local"
            by_hour[key][h] += 1

    local_total = sum(by_hour["local"].values())
    tourist_total = sum(by_hour["tourist"].values())

    if local_total > 0:
        # 夜宵时段
        evening = sum(by_hour["local"].get(h, 0) for h in range(20, 24))
        if evening > local_total * 0.08:
            findings.append(Finding(
                module="location", type="strength", priority="low",
                title=f"夜宵时段(20-24点)占淡季 {evening/local_total*100:.0f}%，本地夜宵需求明显",
                detail="石岛湾居民有夜间消费习惯",
                recommendation="暑期延长至24点，兼顾本地夜宵+游客"
            ))

    findings.append(Finding(
        module="location", type="suggestion", priority="low",
        title="暑期口味建议",
        detail="当前以麻辣烫/香锅为主。暑期游客可能偏好更清淡口味（番茄、酸甜）或本地化体验（海鲜味）",
        recommendation="暑期可增加1-2款'游客专属'口味：海鲜味麻辣烫、威海特色海鲜拼盘"
    ))
    return findings


def _store_type_info(profile: dict, store_config: dict) -> List[Finding]:
    findings = []
    traits = profile.get('traits', [])
    recs = profile.get('recommendations', [])

    findings.append(Finding(
        module="location", type="strength", priority="low",
        title=f"商圈类型: {profile.get('name', '未知')}",
        detail="\n".join(f"· {t}" for t in traits),
        data={"store_type": profile.get('name', '')}
    ))

    if recs:
        findings.append(Finding(
            module="location", type="suggestion", priority="high",
            title=f"{store_config.get('name', '本店')} — 商圈行动建议",
            detail="\n".join(f"{i+1}. {r}" for i, r in enumerate(recs)),
            recommendation="以上基于沿海旅游商圈特征，根据实际情况调整"
        ))
    return findings
