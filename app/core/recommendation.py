import re
from typing import Any
from app.schemas.meal import Meal, DietaryPreference
from app.schemas.family import FamilyRule
from app.core.llm_service import LLMService
from app.core.rule_engine import RuleEngine


class RecommendResult:
    """单个推荐结果"""
    def __init__(self, meal: Meal, score: int, reasons: list[str]):
        self.meal = meal
        self.score = score
        self.reasons = reasons

    @property
    def reason_text(self) -> str:
        return '；'.join(self.reasons) if self.reasons else '常规推荐'


class RecommendationEngine:
    """餐食推荐引擎：结合用户输入 + 家属规则进行智能推荐"""

    def __init__(self, llm_service: LLMService | None = None):
        self._llm = llm_service or LLMService()
        self._rule_engine = RuleEngine()
        self._tag_map = {
            'low_oil': '低油', 'low_salt': '低盐',
            'low_sugar': '低糖', 'soft_food': '软烂易消化',
            'vegetarian': '素食', 'high_protein': '高蛋白',
            'low_carb': '低碳水', 'gluten_free': '无麸质',
            'halal': '清真', 'no_pork': '无猪肉',
            'no_seafood': '无海鲜', 'low_purine': '低嘌呤',
        }

    def recommend(
        self,
        text_input: str,
        all_meals: list[Meal],
        family_rules: FamilyRule | None = None,
        max_results: int = 3,
    ) -> tuple[list[RecommendResult], str, str]:
        """
        综合评分推荐：
        1. 解析用户输入 → 关键词、饮食偏好、价格约束
        2. 应用家属规则进行硬过滤
        3. 对每个候选餐食评分（关键词匹配 + 标签匹配 + 规则符合度）
        4. 按总分降序，返回 top N
        返回 (推荐结果, 需求摘要, ai_mode)。ai_mode 为 'remote' 表示真实大模型解析，'local' 表示本地降级。
        """
        query = self._llm.extract_meal_query(text_input)
        return self.recommend_from_query(query, all_meals, family_rules, max_results)

    def recommend_from_query(
        self,
        query: dict,
        all_meals: list[Meal],
        family_rules: FamilyRule | None = None,
        max_results: int = 3,
    ) -> tuple[list[RecommendResult], str, str]:
        """基于已解析的意图 query 直接评分推荐（工作流中复用，避免重复调用大模型）。"""
        ai_mode = getattr(self._llm, 'last_source', 'local') or 'local'
        keywords = query.get('keywords', [])
        prefs = query.get('dietary_preferences', [])
        price_max = query.get('price_max')
        summary = query.get('summary', '')

        candidates = self._rule_engine.filter_meals_by_rules(all_meals, family_rules) if family_rules else all_meals

        scored = []
        for meal in candidates:
            score, reasons = self._score_meal(meal, keywords, prefs, price_max, family_rules)
            if score < 0:
                continue  # 硬约束不通过，跳过
            scored.append(RecommendResult(meal, score, reasons))

        scored.sort(key=lambda r: r.score, reverse=True)
        top = scored[:max_results]

        query_summary = f'您说：{summary or "您的需求"}，为您推荐以下餐食'
        if prefs:
            pref_names = [self._tag_map.get(p, p) for p in prefs]
            query_summary += f'（偏好：{"、".join(pref_names)}）'

        return top, query_summary, ai_mode

    def _score_meal(
        self,
        meal: Meal,
        keywords: list[str],
        prefs: list[str],
        price_max: float | None,
        rules: FamilyRule | None,
    ) -> tuple[int, list[str]]:
        """对单个餐食进行评分，返回 (score, reasons)"""
        score = 0
        reasons = []

        # ---------- 硬约束：家属禁止食材 ----------
        if rules and rules.blocked_items:
            for item in rules.blocked_items:
                if item in meal.name or item in meal.description:
                    return -1, []

        # ---------- 1. 名称关键词匹配（最高 50 分） ----------
        meal_tags_str = [t.value for t in meal.dietary_tags]
        for kw in keywords:
            if kw in meal.name:
                score += 50
                reasons.append(f'名称包含"{kw}"')
                break

        # ---------- 2. 描述关键词匹配（最高 30 分） ----------
        for kw in keywords:
            if kw in meal.description:
                score += 30
                reasons.append(f'描述提及"{kw}"')
                break

        # ---------- 3. 饮食偏好标签匹配（每个匹配 +20 分） ----------
        matched_prefs = []
        for pref in prefs:
            if pref in meal_tags_str:
                score += 20
                matched_prefs.append(self._tag_map.get(pref, pref))
        if matched_prefs:
            reasons.append(f'符合{"、".join(matched_prefs)}')

        # ---------- 4. 家属规则价格上限 ----------
        if rules:
            if meal.price <= rules.max_price:
                score += 20
                reasons.append(f'价格{meal.price}元在预算内')
            else:
                score -= 10
                reasons.append(f'超出预算上限{rules.max_price}元')

        # ---------- 5. 用户主动输入价格上限 ----------
        if price_max is not None and meal.price <= price_max:
            score += 15

        # ---------- 6. 家属规则饮食偏好 ----------
        if rules and rules.allowed_dietary:
            if any(tag in meal_tags_str for tag in rules.allowed_dietary):
                score += 15
            else:
                score -= 5

        # ---------- 默认保底分 ----------
        if score == 0:
            score = 10
            reasons.append('基础推荐')

        return score, reasons
