"""家属端 AI 分析服务：由大模型分析家属饮食规则与推荐餐食的匹配，并给出综合适合度。

综合适合度 = 推荐餐食对家属规则的满足度（0~100）。
规则匹配分析优先由大模型生成；大模型不可用时降级为本地规则分析。
结果缓存 60 秒，避免重复调用慢速大模型。
"""

import time

from app.core.llm_service import LLMService
from app.core.recommendation import RecommendationEngine

_PREF_MAP = {
    'low_oil': '低油', 'low_salt': '低盐', 'low_sugar': '低糖', 'soft_food': '软烂易消化',
    'vegetarian': '素食', 'high_protein': '高蛋白', 'low_carb': '低碳水', 'gluten_free': '无麸质',
    'halal': '清真', 'no_pork': '无猪肉', 'no_seafood': '无海鲜', 'low_purine': '低嘌呤',
}


class AnalysisService:
    def __init__(self, meal_repo, order_repo, family_repo, llm_service: LLMService | None = None):
        self._meal_repo = meal_repo
        self._order_repo = order_repo
        self._family_repo = family_repo
        self._llm = llm_service or LLMService()
        self._recommender = RecommendationEngine(self._llm)
        self._cache_key = None
        self._cache_time = 0.0

    def analyze(self, family_id: str, elder_id: str) -> dict:
        rules = self._family_repo.get_family_rules(family_id, elder_id)
        cache_key = self._rules_text(rules) if rules else 'none'

        # 60 秒内同规则直接返回缓存，避免重复调用慢速大模型
        now = time.time()
        if now - self._cache_time < 60 and self._cache_key == cache_key:
            return self._cached_result

        result = self._compute_analysis(family_id, elder_id, rules)
        self._cached_result = result
        self._cache_key = cache_key
        self._cache_time = now
        return result

    def _compute_analysis(self, family_id: str, elder_id: str, rules) -> dict:
        all_meals = self._meal_repo.get_all_meals()

        # 用家属规则过滤 + 本地评分，取评分最高的餐食作为分析对象
        neutral_query = {'summary': '今天想吃一顿合适的', 'dietary_preferences': [],
                         'price_max': None, 'price_min': None, 'keywords': []}
        results, _, _ = self._recommender.recommend_from_query(neutral_query, all_meals, rules, max_results=3)
        top = results[0] if results else None
        meal = top.meal if top else None

        # 综合适合度 = 该餐食对家属规则的满足度（0~100）
        suitability = self._compute_suitability(rules, meal)

        rules_text = self._rules_text(rules)
        meal_text = self._meal_text(meal) if meal else '暂无推荐餐食'

        # 大模型生成分析（失败降级为本地规则分析）
        llm_result = self._llm.generate_analysis(rules_text, meal_text) if meal else None
        if llm_result:
            summary = llm_result['summary']
            matches = llm_result['matches']
            ai_mode = 'remote'
        else:
            summary = self._local_summary(rules)
            matches = self._local_matches(rules, meal, top)
            ai_mode = 'local'

        return {
            'summary': summary,
            'matches': matches,
            'suitability': suitability,
            'meal': meal_text,
            'ai_mode': ai_mode,
        }

    def _rules_text(self, rules) -> str:
        if rules is None:
            return '未设定家属规则'
        parts = [f'单餐最高{rules.max_price:g}元']
        if rules.allowed_dietary:
            parts.append('允许' + '、'.join(_PREF_MAP.get(p, p) for p in rules.allowed_dietary))
        if rules.blocked_items:
            parts.append('禁止' + '、'.join(rules.blocked_items))
        if rules.notes:
            parts.append('备注' + rules.notes)
        return '；'.join(parts)

    def _compute_suitability(self, rules, meal) -> int:
        """综合适合度 = 推荐餐食对家属规则的满足度（0~100）。"""
        if meal is None:
            return 60
        score = 100
        tags = [t.value for t in meal.dietary_tags]
        if rules:
            if meal.price > rules.max_price:
                score -= 30
            for pref in rules.allowed_dietary:
                if pref not in tags:
                    score -= 15
            if rules.blocked_items:
                hits = [b for b in rules.blocked_items if b in meal.name or b in meal.description]
                if hits:
                    score -= 40
        return max(30, min(100, score))

    def _meal_text(self, meal) -> str:
        tags = '、'.join(_PREF_MAP.get(t.value, t.value) for t in meal.dietary_tags) or '无标签'
        return f'{meal.name}：{meal.description}，价格{meal.price:g}元，标签：{tags}'

    def _local_summary(self, rules) -> str:
        if rules:
            prefs = '、'.join(_PREF_MAP.get(p, p) for p in rules.allowed_dietary) if rules.allowed_dietary else '无'
            return (f'根据家属设定的饮食规则（预算¥{rules.max_price:g}、偏好{prefs}），'
                    f'AI 综合评估后推荐了最适合的餐品。')
        return '根据老人的口味需求，AI 综合评估后推荐了最适合的餐品。'

    def _local_matches(self, rules, meal, top) -> list[dict]:
        matches = []
        if rules is None:
            matches.append({'label': '家属规则', 'desc': '未设定家属规则，默认全部通过', 'status': 'info'})
        else:
            if meal:
                tags = [t.value for t in meal.dietary_tags]
                if meal.price <= rules.max_price:
                    matches.append({'label': f'预算上限 ¥{rules.max_price:g}',
                                    'desc': f'餐品价格 ¥{meal.price:g} 在预算内', 'status': 'match'})
                else:
                    matches.append({'label': f'预算上限 ¥{rules.max_price:g}',
                                    'desc': f'餐品价格 ¥{meal.price:g} 超出预算', 'status': 'warn'})
                for pref in rules.allowed_dietary:
                    lbl = _PREF_MAP.get(pref, pref)
                    if pref in tags:
                        matches.append({'label': f'{lbl}偏好', 'desc': f'餐品含{lbl}标签，已匹配', 'status': 'match'})
                    else:
                        matches.append({'label': f'{lbl}偏好', 'desc': f'餐品不含{lbl}标签', 'status': 'info'})
                if rules.blocked_items:
                    hits = [b for b in rules.blocked_items if b in meal.name or b in meal.description]
                    if hits:
                        matches.append({'label': '禁忌食材', 'desc': '包含' + '、'.join(hits), 'status': 'warn'})
                    else:
                        matches.append({'label': '禁忌食材', 'desc': '未含禁止食材，已确认', 'status': 'match'})
                if rules.notes:
                    matches.append({'label': '备注', 'desc': rules.notes, 'status': 'info'})
        if top and top.reasons:
            matches.append({'label': '推荐理由', 'desc': '；'.join(top.reasons), 'status': 'info'})
        return matches
