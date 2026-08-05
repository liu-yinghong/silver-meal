"""今日推荐服务：综合三份餐食 —— 评分最高 + 大模型天气推荐 + 历史下单最多。

评分最高由现有推荐引擎决定（含大模型意图解析）；
天气推荐由大模型按用户所在位置的实时天气挑选，失败降级为本地规则；
历史下单最多由订单数据统计得出。
"""

from typing import Any

from app.schemas.meal import Meal
from app.core.llm_service import LLMService
from app.core.rule_engine import RuleEngine
from app.core.recommendation import RecommendationEngine
from app.core.weather_service import WeatherService


class TodayService:
    def __init__(self, meal_repo, order_repo, family_repo, llm_service: LLMService | None = None):
        self._meal_repo = meal_repo
        self._order_repo = order_repo
        self._family_repo = family_repo
        self._llm = llm_service or LLMService()
        self._rule_engine = RuleEngine()
        self._recommender = RecommendationEngine(self._llm)
        self._weather = WeatherService()
        self._cache_key = None
        self._cache_time = 0.0
        self._cached_result = None

    def recommend_today(self, family_id: str, elder_id: str,
                        lat: float | None = None, lon: float | None = None
                        ) -> tuple[list[Meal], str, list[str], str]:
        import time
        rules = self._family_repo.get_family_rules(family_id, elder_id)
        cache_key = f'{family_id}:{elder_id}:{(rules.max_price if rules else "")}:{(rules.allowed_dietary if rules else "")}'
        # 60 秒内同规则直接返回缓存，避免重复调用慢速大模型
        now = time.time()
        if now - self._cache_time < 60 and self._cache_key == cache_key and self._cached_result:
            return self._cached_result
        result = self._compute_today(rules, family_id, elder_id, lat, lon)
        self._cached_result = result
        self._cache_key = cache_key
        self._cache_time = now
        return result

    def _compute_today(self, rules, family_id, elder_id,
                       lat=None, lon=None) -> tuple[list[Meal], str, list[str], str]:
        all_meals = self._meal_repo.get_all_meals()
        candidates = self._rule_engine.filter_meals_by_rules(all_meals, rules) if rules else list(all_meals)
        if not candidates:
            return [], '今天没有符合家庭规则的餐品，请联系家人调整规则后重试', [], 'local'

        # 预取 Top5 评分结果，用于“评分最高”与补齐（走本地规则评分，避免重复大模型调用）
        neutral_query = {'summary': '今天想吃一顿合适的', 'dietary_preferences': [],
                         'price_max': None, 'price_min': None, 'keywords': []}
        top_results = self._recommender.recommend_from_query(neutral_query, candidates, rules, max_results=5)
        top_rank = [r for r in (top_results[0] if top_results else [])]
        ai_mode = 'local'

        meals: list[Meal] = []
        reasons: list[str] = []
        used: set[str] = set()

        # 1. 评分最高
        if top_rank:
            r0 = top_rank[0]
            meals.append(r0.meal)
            used.add(r0.meal.id)
            reasons.append('综合评分最高：' + r0.reason_text)

        # 2. 大模型按天气推荐
        weather = self._weather.get_weather(lat, lon)
        w = self._pick_by_weather(candidates, used, weather)
        if w:
            meal, reason = w
            meals.append(meal)
            used.add(meal.id)
            reasons.append(reason)
            if getattr(self._llm, 'last_source', 'local') == 'remote':
                ai_mode = 'remote'

        # 3. 历史下单最多
        h = self._pick_most_ordered(candidates, used)
        if h:
            meal, reason = h
            meals.append(meal)
            used.add(meal.id)
            reasons.append(reason)

        # 补齐不足 3 个
        if len(meals) < 3:
            for r in top_rank:
                if len(meals) >= 3:
                    break
                if r.meal.id not in used:
                    meals.append(r.meal)
                    used.add(r.meal.id)
                    reasons.append('综合推荐：' + r.reason_text)

        # 显式检索校验：仅返回 meals.json 中真实存在的餐食
        valid_ids = {m.id for m in self._meal_repo.get_all_meals()}
        final_meals = []
        final_reasons = []
        for m, r in zip(meals, reasons):
            if m.id in valid_ids:
                final_meals.append(m)
                final_reasons.append(r)

        summary = '今日为您精心挑选 3 份餐食：首选综合评分最高，其次贴合今日天气，第三是您常点的口味'
        return final_meals, summary, final_reasons, ai_mode

    def _pick_by_weather(self, candidates: list[Meal], used: set[str], weather: dict[str, Any]
                         ) -> tuple[Meal, str] | None:
        valid = [m for m in candidates if m.id not in used]
        if not valid:
            return None
        cond = weather.get('condition', '') or ''
        # 优先由大模型挑选（结果必须回查 meals 文件，防止模型虚构不存在的餐食）
        # 候选只取前 5 份，避免提示词过长导致大模型超时降级
        try:
            lines = '\n'.join(f'{m.id}|{m.name}|{m.description}|{m.price:g}' for m in valid[:5])
            pick = self._llm.pick_meal_for_weather(weather, lines)
            if pick and pick.get('meal_id'):
                meal = self._meal_repo.get_meal_by_id(pick['meal_id'])
                if meal and meal.id not in used:
                    reason = pick.get('reason') or f'今日{cond}，这份正合适'
                    return meal, '天气推荐：' + reason
        except Exception:
            pass
        # 本地降级：按天气映射偏好标签
        pref = self._weather_pref_tags(weather)
        for m in valid:
            tags = [t.value for t in m.dietary_tags]
            if pref and any(p in tags for p in pref):
                return m, f'今日{cond or "天气"}，推荐清淡易消化的「{m.name}」'
        return valid[0], f'今日{cond or "天气"}，为您推荐「{valid[0].name}」'

    def _pick_most_ordered(self, candidates: list[Meal], used: set[str]) -> tuple[Meal, str] | None:
        counts = self._order_repo.get_meal_order_counts()
        valid = [m for m in candidates if m.id not in used]
        if not valid:
            return None
        best = max(valid, key=lambda m: counts.get(m.id, 0))
        if counts.get(best.id, 0) <= 0:
            return None
        return best, f'您最常点的「{best.name}」，已下单 {counts[best.id]} 次'

    def _weather_pref_tags(self, weather: dict[str, Any]) -> list[str]:
        cond = weather.get('condition', '') or ''
        if any(k in cond for k in ('晴', '热', '高温', '炎热')):
            return ['low_oil', 'low_salt', 'low_sugar']
        if any(k in cond for k in ('雨', '雪', '雷', '阴', '降温', '冷', '雾')):
            return ['soft_food', 'low_oil']
        return ['low_salt', 'low_oil']
