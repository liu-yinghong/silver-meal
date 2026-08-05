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

        # 用户明确说的价格上限也是硬约束：超预算餐食直接剔除，防止高分超预算餐品混入推荐
        if price_max is not None:
            candidates = [m for m in candidates if m.price <= price_max]

        scored = []
        for meal in candidates:
            score, reasons = self._score_meal(meal, keywords, prefs, price_max, family_rules)
            if score < 0:
                continue  # 硬约束不通过，跳过
            scored.append(RecommendResult(meal, score, reasons))

        scored.sort(key=lambda r: r.score, reverse=True)

        # 完全没有符合规则的候选 → 交由上游按“无合适餐食”处理
        if not scored:
            return [], f'抱歉，暂时没有找到符合您需求和家属规则的餐食，请放宽条件或联系家人调整规则', ai_mode

        # 老人明确提到了具体食物词，但没有任何一份餐食命中 → 生成“未找到+替代推荐”提示语
        matched = not keywords or any(
            any(kw in r.meal.name or kw in r.meal.description for kw in keywords)
            for r in scored
        )
        if not matched:
            return self._fallback_recommend(summary, candidates, scored, family_rules, max_results)

        top = scored[:max_results]

        query_summary = f'您说：{summary or "您的需求"}，为您推荐以下餐食'
        if prefs:
            pref_names = [self._tag_map.get(p, p) for p in prefs]
            query_summary += f'（偏好：{"、".join(pref_names)}）'

        return top, query_summary, ai_mode

    def _fallback_recommend(
        self,
        summary: str,
        candidates: list[Meal],
        scored: list[RecommendResult],
        family_rules: FamilyRule | None,
        max_results: int,
    ) -> tuple[list[RecommendResult], str, str]:
        """未命中老人需求时的兜底：优先让大模型挑选替代餐食并生成解释提示语；
        大模型不可用时，用评分最高的候选 + 本地模板提示语。"""
        by_id = {r.meal.id: r for r in scored}
        rules_text = self._rules_hint(family_rules)
        meal_lines = '\n'.join(f'{m.id}|{m.name}|{m.price:g}元' for m in candidates)
        pick = self._llm.generate_fallback_recommendation(summary, meal_lines, rules_text=rules_text)

        if pick and pick.get('meal_ids'):
            picked: list[RecommendResult] = []
            for mid in pick['meal_ids']:
                if len(picked) >= max_results:
                    break
                if mid in by_id and not any(r.meal.id == mid for r in picked):
                    picked.append(by_id[mid])
            if picked:
                return picked, pick.get('message') or self._fallback_message(summary), self._llm.last_source or 'remote'

        return scored[:max_results], self._fallback_message(summary, family_rules), self._llm.last_source or 'local'

    @staticmethod
    def _fallback_message(summary: str, family_rules: FamilyRule | None = None) -> str:
        want = (summary or '').strip() or '您想吃的'
        if family_rules:
            return f'抱歉，暂时没有找到与「{want}」完全匹配的餐食，已按家属规则为您挑选了下面几份比较合适的，您可以看看。'
        return f'抱歉，暂时没有找到与「{want}」完全匹配的餐食，为您挑选了下面几份比较合适的，您可以看看。'

    def _rules_hint(self, family_rules: FamilyRule | None) -> str | None:
        if family_rules is None:
            return None
        parts = [f'家属规则：单餐最高{family_rules.max_price:g}元']
        if family_rules.allowed_dietary:
            parts.append('偏好' + '、'.join(self._tag_map.get(p, p) for p in family_rules.allowed_dietary))
        if family_rules.blocked_items:
            parts.append('禁食' + '、'.join(family_rules.blocked_items))
        return '；'.join(parts)

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
