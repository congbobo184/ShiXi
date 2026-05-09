"""角度六：位置变现 — 石岛湾东山南路这个位置你到底用上了多少"""

from collections import defaultdict
from statistics import mean
from typing import List
from shixi.core.schema import DishSale, Finding


def diagnose(sales: List[DishSale], store_config: dict) -> List[Finding]:
    findings = []
    loc = store_config.get('location', {})
    env = store_config.get('environment', {})
    ctx = store_config.get('local_context', {})

    address = loc.get('address', '石岛湾')
    store_type = loc.get('type', 'coastal_tourist')

    # 位置基本信息
    nearby_res = env.get('nearby_residential', [])
    nearby_attr = env.get('nearby_attractions', [])
    nearby_comm = env.get('nearby_commercial', [])

    findings.append(Finding(
        level="green",
        title=f"📍 {address} — 东山南路沿街商铺",
        evidence=f"居民区: {', '.join(nearby_res)}\n"
                 f"景点: {', '.join(nearby_attr)}\n"
                 f"商业: {', '.join(nearby_comm)}",
        impact="—",
        suggestion="",
    ))

    # 商圈类型特征
    if store_type == 'coastal_tourist':
        findings.append(Finding(
            level="red" if True else "green",
            title="沿海旅游商圈：双客流模式",
            evidence="淡季(11-4月)靠本地居民，旺季(5-10月)靠游客，暑期(7-8月)爆发",
            impact="两个客群的诉求不同：本地人要'好吃不贵常来'，游客要'打卡尝鲜方便'。"
                   "你现在只服务了本地客，游客红利还没吃到",
            suggestion="①本地客: 微信群+熟客优惠，让他们冬天也来"
                       "②游客: 门口招牌要大(+'威海特色'标签)+大众点评/小红书引导"
                       "③游客口味: 暑期加海鲜味/清淡口味",
            expect="暑期每日多接20-30单游客生意",
        ))

    # 淡旺季
    by_month = defaultdict(lambda: {"orders": set(), "days": set()})
    for s in sales:
        if s.营业日期:
            m = s.营业日期.month
            by_month[m]["orders"].add(s.real_order_id)
            by_month[m]["days"].add(s.营业日期)

    if by_month:
        daily_by_month = {}
        for m in sorted(by_month):
            d = len(by_month[m]["days"])
            o = len(by_month[m]["orders"])
            daily_by_month[m] = o / d if d > 0 else 0

        off_peak_months = [m for m in daily_by_month if m <= 4]
        if off_peak_months:
            off_avg = mean(daily_by_month[m] for m in off_peak_months)

            findings.append(Finding(
                level="yellow",
                title=f"淡季(1-4月)日均 {off_avg:.0f} 单，当前以本地客为主",
                evidence="\n".join(f"  {m}月: 日均{daily_by_month[m]:.0f}单" for m in sorted(daily_by_month)),
                impact="日均单量决定了你的基本盘。如果淡季连基本开支都覆盖不了，旺季就是补窟窿",
                suggestion="淡季核心目标不是赚大钱，是养住本地客、稳住基本盘。"
                           "推月卡/周卡(比如充值100送20)，锁住周边居民的消费习惯",
                expect="月卡锁住30-50个高频本地客，淡季日均保底",
            ))

    # 周边小区渗透
    if nearby_res:
        findings.append(Finding(
            level="yellow",
            title=f"周边 {len(nearby_res)} 个小区，晚饭时段能接到更多客吗？",
            evidence="桃源街道周边多个居民小区，晚饭时段该有一波人",
            impact="周边居民没把你当'家门口食堂'，说明要么不知道你的店，要么没有'一个人吃饭也想来'的氛围",
            suggestion="①在小区门口贴/发传单(比在店门口有意义)"
                       "②推'一人食友好'定位：一个人来吃不尴尬，有单人位"
                       "③跟周边小超市/水果店互推(你在他们店放优惠券)",
        ))

    # 海水浴场距离
    attractions = nearby_attr or []
    beach_names = [a for a in attractions if '浴场' in a or '海滩' in a or '海水' in a]
    if beach_names:
        findings.append(Finding(
            level="yellow",
            title=f"距{'/'.join(beach_names)}约1km，暑期游客从海滩回来你能接住吗？",
            evidence="游客在海滩玩完(下午4-6点)→找地方吃饭→你的店在必经之路上吗？",
            impact="如果不是必经之路，1公里对走路的人来说不远不近，可能直接打车去别的地方了",
            suggestion="①在海滩附近放指引牌'往前走800米，威海最好吃的麻辣烫'"
                       "②大众点评/高德地图完善店铺信息+照片(游客先查手机)"
                       "③暑期门口摆外摆/阳伞桌椅——游客喜欢坐外面",
            expect="如果10%的浴场游客知道你并过来，暑期日均多20-50单",
        ))

    return findings
