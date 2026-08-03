"""LLMService 单元测试：本地降级 + 远程 JSON 解析 + 失败回退。"""

import pytest

from app.core.llm_service import LLMService


def test_local_extract_light_and_budget():
    llm = LLMService(use_remote=False)
    q = llm.extract_meal_query('今天想吃清淡一点，30元以内')
    assert llm.last_source == 'local'
    assert 'low_oil' in q['dietary_preferences']
    assert 'low_salt' in q['dietary_preferences']
    assert q['price_max'] == 30.0
    assert q['price_min'] is None


def test_local_extract_soft_food():
    llm = LLMService(use_remote=False)
    q = llm.extract_meal_query('想吃点软和好消化的')
    assert 'soft_food' in q['dietary_preferences']
    assert q['price_max'] is None


def test_local_extract_price_range():
    llm = LLMService(use_remote=False)
    q = llm.extract_meal_query('15到20元的粥')
    assert q['price_min'] == 15.0
    assert q['price_max'] == 20.0
    assert '粥' in q['keywords']


def test_no_key_falls_back_to_local(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    llm = LLMService()
    q = llm.extract_meal_query('想吃清淡的')
    assert llm.last_source == 'local'
    assert 'low_oil' in q['dietary_preferences']


def test_remote_failure_falls_back_to_local(monkeypatch):
    def boom(self, user_input):
        raise RuntimeError('network down')
    monkeypatch.setattr(LLMService, '_remote_extract', boom)
    llm = LLMService(use_remote=True, api_key='sk-test')
    q = llm.extract_meal_query('想吃清淡的')
    assert llm.last_source == 'local'
    assert 'low_salt' in q['dietary_preferences']


def test_parse_remote_json_plain():
    llm = LLMService()
    data = llm._parse_remote_json('{"summary":"原话","dietary_preferences":["low_oil","low_salt"],"price_max":30,"price_min":null,"keywords":["粥"]}')
    assert data is not None
    assert data['dietary_preferences'] == ['low_oil', 'low_salt']
    assert data['price_max'] == 30.0
    assert data['keywords'] == ['粥']


def test_parse_remote_json_with_code_fence():
    llm = LLMService()
    content = '```json\n{"dietary_preferences":["low_sugar"],"price_max":null,"price_min":null,"keywords":[]}\n```'
    data = llm._parse_remote_json(content)
    assert data['dietary_preferences'] == ['low_sugar']


def test_parse_remote_json_filters_invalid_prefs():
    llm = LLMService()
    content = '{"dietary_preferences":["low_salt","magic_tag","辣"],"price_max":"28元","keywords":"notalist"}'
    data = llm._parse_remote_json(content)
    assert data['dietary_preferences'] == ['low_salt']
    assert data['price_max'] == 28.0
    assert data['keywords'] == []


def test_parse_remote_json_garbage_returns_none():
    llm = LLMService()
    assert llm._parse_remote_json('完全不是 JSON') is None
    assert llm._parse_remote_json('{}') is not None


def test_remote_success_sets_source(monkeypatch):
    class FakeContent:
        content = '{"summary":"s","dietary_preferences":["low_oil"],"price_max":30,"price_min":null,"keywords":[]}'

    class FakeChoice:
        message = FakeContent()

    class FakeResp:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            return FakeResp()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, *a, **k):
            self.chat = FakeChat()

    import openai
    monkeypatch.setattr(openai, 'OpenAI', FakeClient)
    llm = LLMService(use_remote=True, api_key='sk-test', timeout=0.5)
    q = llm.extract_meal_query('清淡的')
    assert llm.last_source == 'remote'
    assert q['price_max'] == 30.0
