"""大模型推荐工作流：理解需求 → 查看家庭设置 → 分析餐品 → 生成方案。

以生成器逐步骤产出进度事件，供后端以 SSE 流式推送给前端，实时展示大模型推理进度。
事件结构：{"step": 1..4, "status": "running|done|error", "detail": "...", "result": {...}}
"""

from typing import Any

from app.core.llm_service import LLMService
from app.core.recommendation import RecommendationEngine
from app.core.today_service import TodayService

_PREF_MAP = {'low_oil': '低油', 'low_salt': '低盐', 'low_sugar': '低糖', 'soft_food': '软烂易消化'}


class RecommendWorkflow:
    def __init__(self, meal_repo, order_repo, family_repo, llm_service: LLMService | None = None):
        self._meal_repo = meal_repo
        self._order_repo = order_repo
        self._family_repo = family_repo
        self._llm = llm_service or LLMService()
        self._recommender = RecommendationEngine(self._llm)
        self._today = TodayService(meal_repo, order_repo, family_repo, llm_service=llm_service)

    def stream(self, text_input: str, family_id: str, elder_id: str,
               mode: str = 'input', lat: float | None = None, lon: float | None = None):
        # ---- Step 1 理解需求（大模型意图解析）----
        yield self._ev(1, 'running', '正在理解您说的口味、预算和偏好...')
        if mode == 'today':
            query = {'summary': '今日推荐', 'dietary_preferences': [],
                     'price_max': None, 'price_min': None, 'keywords': []}
            detail = '已理解：您想要一份贴合今日情况的推荐'
            ai_mode = 'local'
        else:
            query = self._llm.extract_meal_query(text_input or '')
            detail = self._intent_summary(query)
            ai_mode = getattr(self._llm, 'last_source', 'local') or 'local'
        yield self._ev(1, 'done', detail)

        # ---- Step 2 查看家庭设置 ----
        yield self._ev(2, 'running', '正在检查家属设定的饮食规则和预算上限...')
        rules = self._family_repo.get_family_rules(family_id, elder_id)
        yield self._ev(2, 'done', self._rules_summary(rules))

        # ---- Step 3 分析餐品 ----
        yield self._ev(3, 'running', '正在匹配符合条件的餐品，排除不符合的选项...')
        all_meals = self._meal_repo.get_all_meals()
        valid_ids = {m.id for m in all_meals}
        if mode == 'today':
            meals, summary, reasons, ai_mode = self._today.recommend_today(family_id, elder_id, lat, lon)
        else:
            results, summary, ai_mode = self._recommender.recommend_from_query(
                query, all_meals, rules, max_results=3)
            meals = [r.meal for r in results if r.meal.id in valid_ids]
            reasons = [r.reason_text for r in results if r.meal.id in valid_ids]
        if not meals:
            yield self._ev(3, 'error', '没有符合家庭规则的餐品')
            yield self._ev(4, 'error', '无可推荐餐品，请放宽条件后重试')
            return
        if '没有找到' in summary or '抱歉' in summary or '不好意思' in summary:
            yield self._ev(3, 'done', f'没有找到完全匹配的餐食，已为您挑选了 {len(meals)} 份替代餐食')
        else:
            yield self._ev(3, 'done', f'已分析 {len(all_meals)} 份餐品，{len(meals)} 份符合要求')

        # ---- Step 4 生成方案 ----
        yield self._ev(4, 'running', '综合评分中，为您生成最佳推荐方案...')
        result = {
            'meals': [m.model_dump() for m in meals],
            'query_summary': summary,
            'reasons': reasons,
            'ai_mode': ai_mode,
        }
        yield self._ev(4, 'done', '已生成推荐方案', result)

    @staticmethod
    def _ev(step: int, status: str, detail: str = '', result: Any = None) -> dict[str, Any]:
        ev: dict[str, Any] = {'step': step, 'status': status, 'detail': detail}
        if result is not None:
            ev['result'] = result
        return ev

    def _intent_summary(self, query: dict) -> str:
        parts = []
        prefs = query.get('dietary_preferences', [])
        if prefs:
            parts.append('偏好' + '、'.join(_PREF_MAP.get(p, p) for p in prefs))
        keywords = query.get('keywords', [])
        if keywords:
            parts.append('想吃' + '、'.join(keywords))
        price = query.get('price_max')
        if price is not None:
            parts.append(f'预算 {price:g} 元以内')
        return '已理解需求：' + ('、'.join(parts) if parts else str(query.get('summary') or '您的需求'))

    def _rules_summary(self, rules) -> str:
        if rules is None:
            return '未设置家属规则，默认全部通过'
        parts = [f'单餐最高 {rules.max_price:g} 元']
        if rules.allowed_dietary:
            parts.append('允许' + '、'.join(_PREF_MAP.get(p, p) for p in rules.allowed_dietary))
        if rules.blocked_items:
            parts.append('禁止' + '、'.join(rules.blocked_items))
        if rules.notes:
            parts.append('备注' + rules.notes)
        return '家属规则：' + '；'.join(parts)
