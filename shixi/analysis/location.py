"""位置洞察 — 基于商圈类型的客群推断与季节分析"""

from collections import defaultdict
from datetime import date
from typing import List, Optional
from shixi.core.schema import DishSale, Finding

# 商圈类型系数
STORE_TYPE_PROFILES = {
    "coastal_tourist": {
        "name": "沿海旅游商圈",
        "tourist_months": [5, 6, 7, 8, 9, 10],
        "peak_months": [7, 8],
        "peak_multiplier": 4.0,       # 暑期高峰是淡季的倍数
        "shoulder_multiplier": 1.5,    # 5/6/9/10月是淡季的倍数
        "traits": [
            "暑期(7-8月)爆发式增长，游客为主",
            "淡季(11-4月)以本地居民为主",
            "周末效应应该比写字楼商圈更明显",
            "游客就餐时间更集中(12点午饭、18点晚饭)",
            "游客客单价通常高于本地居民",
        ],
        "recommendations": [
            "5月开始逐步备料，7-8月备足2-3倍食材",
            "暑期可延长晚间营业时间，游客夜宵需求强",
            "淡季侧重本地客维护（微信群、熟客优惠）",
            "暑期门口立牌/引导牌，游客靠视觉决策",
        ]
    },
    "urban_residential": {
        "name": "城市居民商圈",
        "traits": ["以周边小区居民为主", "周末效应明显", "晚餐和夜宵时段重要"],
    },
    "campus": {
        "name": "学校商圈",
        "traits": ["寒暑假断崖式下跌", "学生客单价低但频次高", "外卖占比通常较高"],
    },
    "business_district": {
        "name": "写字楼商圈",
        "traits": ["工作日午高峰是绝对主力", "周末惨淡", "客单价中等偏上", "外卖占比高"],
    },
}


def analyze(sales: List[DishSale], store_config: dict) -> List[Finding]:
    """位置洞察分析"""
    findings = []

    store_type = store_config.get('location', {}).get('type', 'urban_residential')
    profile = STORE_TYPE_PROFILES.get(store_type, STORE_TYPE_PROFILES['urban_residential'])

    findings.extend(_seasonal_analysis(sales, profile))
    findings.extend(_local_vs_tourist_inference(sales, profile))
    findings.extend(_store_type_recommendations(profile, store_config))

    return findings


def _seasonal_analysis(sales: List[DishSale], profile: dict) -> List[Finding]:
    """淡旺季分析"""
    findings = []

    by_month = defaultdict(lambda: {"orders": set(), "revenue": 0.0, "days": set()})
    for s in sales:
        if s.营业日期:
            m = s.营业日期.month
            by_month[m]["orders"].add(s.订单编号)
            by_month[m]["revenue"] += s.订单收入
            by_month[m]["days"].add(s.营业日期)

    tourist_months = profile.get('tourist_months', [])
    peak_months = profile.get('peak_months', [])
    peak_mult = profile.get('peak_multiplier', 3.0)
    shoulder_mult = profile.get('shoulder_multiplier', 1.5)

    # 用非旅游月(11-4月)做淡季基线
    off_peak = [m for m in by_month if m not in tourist_months]
    if off_peak and tourist_months:
        off_avg_rev = sum(len(by_month[m]["orders"]) / len(by_month[m]["days"])
                          for m in off_peak if by_month[m]["days"])
        off_avg_rev /= len(off_peak) if off_peak else 1

        # 检查5月表现
        if 5 in by_month:
            may_daily = len(by_month[5]["orders"]) / len(by_month[5]["days"]) if by_month[5]["days"] else 0
            if may_daily > off_avg_rev * 1.2:
                findings.append(Finding(
                    module="location", type="strength", priority="medium",
                    title="5月客流已开始爬坡，验证旅游季效应",
                    detail=f"淡季日均约 {off_avg_rev:.1f} 单, 5月日均 {may_daily:.1f} 单 (+{may_daily/off_avg_rev-1:.0%})",
                    recommendation="趋势向好，暑期高峰（7-8月）预计日均可达 "
                                  f"{off_avg_rev * peak_mult:.0f}-{off_avg_rev * peak_mult * 1.2:.0f} 单"
                ))

        # 暑期预测
        findings.append(Finding(
            module="location", type="prediction", priority="high",
            title=f"暑期(7-8月)客流预测：日均可达淡季 {peak_mult:.0f}x",
            detail=f"当前淡季日均约 {off_avg_rev:.1f} 单，参照沿海旅游商圈系数，"
                   f"暑期高峰预计日均 {off_avg_rev * peak_mult:.0f}-{off_avg_rev * peak_mult * 1.5:.0f} 单",
            recommendation=f"7-8月需提前备足食材（建议淡季的{peak_mult:.0f}倍起），适当增加人手",
            data={"off_peak_daily": round(off_avg_rev, 1),
                   "peak_estimate_low": round(off_avg_rev * peak_mult),
                   "peak_estimate_high": round(off_avg_rev * peak_mult * 1.5)}
        ))

    return findings


def _local_vs_tourist_inference(sales: List[DishSale], profile: dict) -> List[Finding]:
    """从数据推断本地/游客客群特征"""
    findings = []

    tourist_months = set(profile.get('tourist_months', [7, 8]))

    # 时段分布: 游客就餐时间更集中
    by_hour_tourist = defaultdict(int)
    by_hour_local = defaultdict(int)
    tourist_total = 0
    local_total = 0

    for s in sales:
        if s.点菜时间 and s.营业日期:
            h = s.点菜时间.hour
            if s.营业日期.month in tourist_months:
                by_hour_tourist[h] += 1
                tourist_total += 1
            else:
                by_hour_local[h] += 1
                local_total += 1

    if local_total > 0:
        # 本地客时段特征
        lunch_local = sum(by_hour_local.get(h, 0) for h in range(11, 14))
        dinner_local = sum(by_hour_local.get(h, 0) for h in range(17, 20))
        evening_local = sum(by_hour_local.get(h, 0) for h in range(20, 24))

        # 推断
        if dinner_local > lunch_local * 1.3:
            findings.append(Finding(
                module="location", type="strength", priority="low",
                title="本地客偏爱晚餐时段（晚高峰 > 午高峰）",
                detail=f"淡季晚餐时段({dinner_local}条)明显多于午餐({lunch_local}条)，"
                       f"符合居民区消费习惯",
                recommendation="晚餐时段重点服务本地熟客，推'下班一人食'场景"
            ))

        if evening_local > local_total * 0.1:
            findings.append(Finding(
                module="location", type="strength", priority="low",
                title=f"夜宵时段(20-24点)占淡季 {evening_local / local_total * 100:.0f}%，本地夜宵需求明显",
                detail="石岛湾居民有夜间消费习惯",
                recommendation="暑期可延长至24点，兼顾本地夜宵+游客夜间觅食"
            ))

    # 客单价推断
    dish_rev = defaultdict(float)
    for s in sales:
        dish_rev[s.菜品名称] += s.菜品收入

    if len(dish_rev) >= 10:
        top_rev = sorted(dish_rev.values(), reverse=True)[:3]
        findings.append(Finding(
            module="location", type="suggestion", priority="low",
            title="石岛湾游客推理：暑期口味可能不同于本地",
            detail=f"当前最受欢迎: {list(dish_rev.keys())[:3]}。"
                   "暑期游客可能偏好更清淡的口味（番茄、酸甜）或更本地化的体验（海鲜味）",
            recommendation="暑期可考虑增加1-2款'游客专属'口味：海鲜味麻辣烫、威海特色的海鲜拼盘"
        ))

    return findings


def _store_type_recommendations(profile: dict, store_config: dict) -> List[Finding]:
    """基于商圈类型给出针对性建议"""
    findings = []

    store_name = store_config.get('name', '本店')
    traits = profile.get('traits', [])
    recs = profile.get('recommendations', [])

    # 输出商圈特征
    detail_lines = [f"· {t}" for t in traits]
    findings.append(Finding(
        module="location", type="strength", priority="low",
        title=f"商圈类型: {profile.get('name', '未知')}",
        detail="\n".join(detail_lines),
        data={"store_type": profile.get('name', '')}
    ))

    # 操作建议
    if recs:
        rec_lines = [f"{i + 1}. {r}" for i, r in enumerate(recs)]
        findings.append(Finding(
            module="location", type="suggestion", priority="high",
            title=f"{store_name} — 基于商圈特征的行动建议",
            detail="\n".join(rec_lines),
            recommendation="以上建议基于沿海旅游商圈特征，具体执行根据实际情况调整"
        ))

    return findings
