"""推荐引擎单元测试：家庭规则硬过滤、预算、理由与 ai_mode。"""

import pytest

from app.core.llm_service import LLMService
from app.core.recommendation import RecommendationEngine
from app.repositories.mock_repo import MockMealRepository
from app.schemas.family import FamilyRule


@pytest.fixture()
def meals():
    return MockMealRepository('data/meals.json').get_all_meals()


@pytest.fixture()
def engine():
    return RecommendationEngine(LLMService(use_remote=False))


def test_blocked_items_excluded(meals, engine):
    rules = FamilyRule(max_price=30, blocked_items=['花生'])
    results, _, mode = engine.recommend('想吃点什么', meals, rules)
    assert mode == 'local'
    for r in results:
        assert '花生' not in r.meal.name
        assert '花生' not in r.meal.description


def test_budget_enforced(meals, engine):
    rules = FamilyRule(max_price=25)
    results, _, _ = engine.recommend('想吃点什么', meals, rules)
    assert results, '应至少有一条推荐'
    assert all(r.meal.price <= 25 for r in results)


def test_budget_is_hard_filter(meals, engine):
    rules = FamilyRule(max_price=25)
    results, _, _ = engine.recommend('海参滋补一点', meals, rules)
    assert not any('海参' in r.meal.name for r in results)  # 45元葱烧海参被硬过滤


def test_eta_minutes_present(meals, engine):
    results, _, _ = engine.recommend('清淡一点', meals, None)
    assert results
    assert all(r.meal.eta_minutes >= 0 for r in results)


def test_user_price_budget(meals, engine):
    results, _, _ = engine.recommend('20元以内的饭', meals, None)
    assert results
    assert all(r.meal.price <= 20 for r in results)


def test_user_price_is_hard_filter(meals, engine):
    # 用户明确说价格上限：超预算的高分餐品（咖喱鸡肉饭 28元）必须被硬剔除
    results, _, _ = engine.recommend('咖喱鸡肉饭，20元以内', meals, None)
    assert results
    assert all(r.meal.price <= 20 for r in results)
    assert not any(r.meal.id == 'meal_030' for r in results)


def test_light_dietary_matches(meals, engine):
    results, summary, _ = engine.recommend('今天想吃清淡一点', meals, None)
    assert results
    assert '低油' in summary
    tag_set = {t.value for r in results for t in r.meal.dietary_tags}
    assert {'low_oil', 'low_salt'} & tag_set, '清淡应命中低油/低盐标签'


def test_reasons_count_matches_meals(meals, engine):
    results, _, _ = engine.recommend('清淡一点，30元以内', meals, None)
    assert 1 <= len(results) <= 3
    assert all(r.reasons for r in results)


def test_max_results_limit(meals, engine):
    results, _, _ = engine.recommend('想吃点什么', meals, None, max_results=2)
    assert len(results) <= 2


def test_rule_budget_reason_visible(meals, engine):
    rules = FamilyRule(max_price=30)
    results, _, _ = engine.recommend('清淡一点', meals, rules)
    assert results
    assert any('预算' in reason for r in results for reason in r.reasons)


def _fallback_query(summary='我想吃龙肉'):
    return {'summary': summary, 'dietary_preferences': [],
            'price_max': None, 'price_min': None, 'keywords': ['龙肉']}


def test_fallback_message_when_no_keyword_match(meals, engine):
    """老人提到具体食物词但菜单没有 → 返回替代推荐 + 说明性提示语（本地模板）。"""
    results, summary, _ = engine.recommend_from_query(_fallback_query(), meals, None)
    assert results, '应返回替代餐食'
    assert len(results) <= 3
    assert '抱歉' in summary and '龙肉' in summary


def test_fallback_respects_rules(meals, engine):
    """未命中时返回的替代餐食必须仍符合家属规则。"""
    rules = FamilyRule(max_price=30, blocked_items=['花生'])
    results, summary, _ = engine.recommend_from_query(_fallback_query(), meals, rules)
    assert results
    assert '抱歉' in summary
    for r in results:
        assert r.meal.price <= 30
        assert '花生' not in r.meal.name
        assert '花生' not in r.meal.description


def test_no_fallback_when_keyword_matched(meals, engine):
    """关键词能命中餐食时，不触发“未找到”提示语。"""
    results, summary, _ = engine.recommend_from_query(
        {'summary': '想吃鲈鱼', 'dietary_preferences': [],
         'price_max': None, 'price_min': None, 'keywords': ['鲈鱼']},
        meals, None)
    assert results
    assert '没有找到' not in summary
