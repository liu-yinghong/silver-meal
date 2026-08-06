"""API 冒烟测试：推荐契约、稳定错误码、消息校验与 Demo Reset。"""

import pytest
from fastapi.testclient import TestClient

from app.core.llm_service import LLMService


@pytest.fixture()
def client(monkeypatch):
    from app.main import app
    import app.adapters.web_api as web_api
    # 推荐链路固定走本地解析，避免测试依赖网络
    web_api.meal_service._recommender._llm = LLMService(use_remote=False)
    # 今日推荐 / 分析 / SSE 工作流也用本地大模型，保证测试快速、可离线
    for _svc in (web_api.today_service, web_api.analysis_service, web_api.workflow):
        if getattr(_svc, '_llm', None):
            _svc._llm._use_remote = False
        if getattr(_svc, '_recommender', None) and getattr(_svc._recommender, '_llm', None):
            _svc._recommender._llm._use_remote = False
        if getattr(_svc, '_today', None) and getattr(_svc._today, '_llm', None):
            _svc._today._llm._use_remote = False
    # 每个用例重置持久化状态，保证隔离
    web_api.order_repo.reset()
    web_api.family_repo.reset()
    web_api.message_repo.reset()
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'


def test_recommend_contract(client):
    r = client.post('/api/meals/recommend', json={
        'text_input': '今天想吃清淡一点，30元以内',
        'family_id': 'family_001',
    })
    assert r.status_code == 200
    data = r.json()
    assert data['ai_mode'] in ('remote', 'local')
    assert 1 <= len(data['meals']) <= 3
    assert len(data['reasons']) == len(data['meals'])
    assert all(m['price'] <= 30 for m in data['meals'])


def test_recommend_respects_family_rules(client):
    client.post('/api/family/settings', json={
        'family_id': 'family_001', 'elder_id': 'elder_001',
        'rules': {'max_price': 30, 'blocked_items': ['花生']},
    })
    r = client.post('/api/meals/recommend', json={
        'text_input': '给我来点吃的', 'family_id': 'family_001',
    })
    data = r.json()
    for meal in data['meals']:
        assert '花生' not in meal['name']
        assert meal['price'] <= 30


def test_create_order_meal_not_found(client):
    r = client.post('/api/orders', json={
        'meal_id': 'meal_not_exist', 'elder_id': 'elder_001', 'family_id': 'family_001',
    })
    assert r.status_code == 404
    assert r.headers.get('X-Error-Code') == 'MEAL_NOT_FOUND'


def test_order_state_machine_via_api(client):
    created = client.post('/api/orders', json={
        'meal_id': 'meal_001', 'elder_id': 'elder_001', 'family_id': 'family_001',
    }).json()
    oid = created['order_id']

    early = client.post('/api/orders/confirm', json={'order_id': oid, 'action': 'confirm'})
    assert early.status_code == 409
    assert early.headers.get('X-Error-Code') == 'INVALID_ORDER_TRANSITION'

    status = None
    for _ in range(5):
        status = client.post(f'/api/orders/{oid}/advance').json()['status']
    assert status == 'delivered'

    confirmed = client.post('/api/orders/confirm', json={'order_id': oid, 'action': 'confirm'})
    assert confirmed.status_code == 200
    assert confirmed.json()['status'] == 'confirmed'

    cancel = client.post(f'/api/orders/{oid}/cancel')
    assert cancel.status_code == 409
    assert cancel.headers.get('X-Error-Code') == 'INVALID_ORDER_TRANSITION'


def test_empty_message_rejected(client):
    r = client.post('/api/messages', json={
        'elder_id': 'elder_001', 'family_id': 'family_001', 'content': '   ',
    })
    assert r.status_code == 422
    assert r.headers.get('X-Error-Code') == 'EMPTY_MESSAGE'


def test_message_roundtrip_and_reset(client):
    r = client.post('/api/messages', json={
        'elder_id': 'elder_001', 'family_id': 'family_001', 'content': '记得喝水',
    })
    assert r.status_code == 200
    unread = client.get('/api/messages/elder_001/unread').json()
    assert len(unread) == 1
    assert unread[0]['content'] == '记得喝水'

    reset = client.post('/api/demo/reset')
    assert reset.status_code == 200
    body = reset.json()
    assert body['status'] == 'ok'
    assert body['cleared']['messages'] == 1
    assert client.get('/api/messages/elder_001/unread').json() == []


def test_message_sender_field(client):
    r = client.post('/api/messages', json={
        'elder_id': 'elder_001', 'family_id': 'family_001', 'sender': '女儿', 'content': '注意休息',
    })
    assert r.status_code == 200
    msgs = client.get('/api/messages/elder_001').json()
    assert len(msgs) == 1
    assert msgs[0]['sender'] == '女儿'


def test_family_orders_after_create(client):
    oid = client.post('/api/orders', json={
        'meal_id': 'meal_001', 'elder_id': 'elder_001', 'family_id': 'family_001',
    }).json()['order_id']
    orders = client.get('/api/family/family_001/orders').json()
    assert any(o['order_id'] == oid for o in orders)


def test_no_eligible_meal_returns_422(client):
    client.post('/api/family/settings', json={
        'family_id': 'family_002', 'elder_id': 'elder_001',
        'rules': {'max_price': 1},  # 所有餐品都超预算 → 无合格餐品
    })
    r = client.post('/api/meals/recommend', json={'text_input': '来点吃的', 'family_id': 'family_002'})
    assert r.status_code == 422
    assert r.headers.get('X-Error-Code') == 'NO_ELIGIBLE_MEAL'
    assert '放宽' in r.json()['detail']


def test_eta_in_recommend_and_order(client):
    r = client.post('/api/meals/recommend', json={'text_input': '清淡一点', 'family_id': 'family_001'})
    assert r.status_code == 200
    meal = r.json()['meals'][0]
    assert 'eta_minutes' in meal
    created = client.post('/api/orders', json={
        'meal_id': meal['id'], 'elder_id': 'elder_001', 'family_id': 'family_001',
    }).json()
    assert created['eta_minutes'] == meal['eta_minutes']
    status = client.get('/api/orders/' + created['order_id']).json()
    assert status['eta_minutes'] == meal['eta_minutes']


def test_double_create_order_is_idempotent(client):
    body = {'meal_id': 'meal_003', 'elder_id': 'elder_001', 'family_id': 'family_001'}
    first = client.post('/api/orders', json=body).json()
    second = client.post('/api/orders', json=body).json()
    assert first['order_id'] == second['order_id']


def test_weather_endpoint_success(client, monkeypatch):
    from app.core.weather_service import WeatherService
    WeatherService._cache.clear(); WeatherService._cache_time = 0
    monkeypatch.setattr(WeatherService, '_fetch_open_meteo', lambda self, lat, lon: {
        'temp': 32, 'condition': '多云', 'icon': '⛅', 'source': 'open-meteo',
    })
    r = client.get('/api/weather?lat=31.23&lon=121.47')
    assert r.status_code == 200
    data = r.json()
    assert data['source'] == 'open-meteo'
    assert data['temp'] == 32
    assert data['condition'] == '多云'
    assert 'date' in data


def test_weather_endpoint_fallback(client, monkeypatch):
    from app.core.weather_service import WeatherService
    WeatherService._cache.clear(); WeatherService._cache_time = 0
    monkeypatch.setattr(WeatherService, '_fetch_open_meteo', lambda self, lat, lon: (_ for _ in ()).throw(RuntimeError('network down')))
    r = client.get('/api/weather')
    assert r.status_code == 200
    data = r.json()
    assert data['source'] == 'fallback'
    assert 'date' in data


def test_asr_endpoint_success(client, monkeypatch):
    from app.core.asr_service import ASRService
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test')  # 确保走 ASR 调用路径
    monkeypatch.setattr(ASRService, 'transcribe', lambda self, wav, sample_rate=16000: '想吃清淡的')
    r = client.post('/api/asr', files={'file': ('audio.wav', b'fake-wav-bytes', 'audio/wav')})
    assert r.status_code == 200
    assert r.json()['text'] == '想吃清淡的'


def test_asr_endpoint_failed(client, monkeypatch):
    from app.core.asr_service import ASRService
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test')
    monkeypatch.setattr(ASRService, 'transcribe', lambda self, wav, sample_rate=16000: None)
    r = client.post('/api/asr', files={'file': ('audio.wav', b'fake-wav-bytes', 'audio/wav')})
    assert r.status_code == 422
    assert r.headers.get('X-Error-Code') == 'ASR_FAILED'


def test_asr_no_key_reports_clear_error(client, monkeypatch):
    """未配置 OPENAI_API_KEY 时，ASR 返回明确的可排查错误码。"""
    from app.core.asr_service import ASRService
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr(ASRService, 'transcribe', lambda self, wav, sample_rate=16000: '想吃清淡的')
    r = client.post('/api/asr', files={'file': ('audio.wav', b'fake-wav-bytes', 'audio/wav')})
    assert r.status_code == 422
    assert r.headers.get('X-Error-Code') == 'ASR_NO_KEY'
    assert 'OPENAI_API_KEY' in r.json()['detail']


def test_api_status_reports_key(client, monkeypatch):
    """/api/status 反映后端是否已读取 OPENAI_API_KEY。"""
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test')
    r = client.get('/api/status')
    assert r.status_code == 200
    body = r.json()
    assert body['status'] == 'ok'
    assert body['llm']['configured'] is True
    assert body['asr']['configured'] is True


def test_today_service_three_dimensions(monkeypatch):
    """今日推荐：三份餐食各不相同，含历史下单最多的一份。"""
    from app.core.today_service import TodayService
    from app.core.llm_service import LLMService
    from app.repositories.mock_repo import MockMealRepository, MockOrderRepository, MockFamilyRepository
    meal_repo = MockMealRepository('data/meals.json')
    order_repo = MockOrderRepository()
    family_repo = MockFamilyRepository()
    monkeypatch.setattr(order_repo, 'get_meal_order_counts', lambda: {'meal_004': 5})
    svc = TodayService(meal_repo, order_repo, family_repo, llm_service=LLMService(use_remote=False))
    monkeypatch.setattr(svc._weather, 'get_weather', lambda *a, **k: {'temp': 30, 'condition': '晴朗', 'icon': '☀️'})
    meals, summary, reasons, mode = svc.recommend_today('family_001', 'elder_001')
    assert len(meals) == 3
    assert len(reasons) == len(meals)
    assert len({m.id for m in meals}) == 3
    assert any(m.id == 'meal_004' for m in meals)  # 历史下单最多进入推荐
    assert any('常点' in r for r in reasons)


def test_today_endpoint_returns_three(client, monkeypatch):
    from app.core.weather_service import WeatherService
    from app.core.llm_service import LLMService
    import app.adapters.web_api as web_api
    WeatherService._cache.clear(); WeatherService._cache_time = 0
    monkeypatch.setattr(WeatherService, '_fetch_open_meteo', lambda self, lat, lon: {
        'temp': 26, 'condition': '多云', 'icon': '⛅', 'source': 'open-meteo'})
    web_api.today_service._llm = LLMService(use_remote=False)
    r = client.post('/api/meals/today', json={'family_id': 'family_001', 'elder_id': 'elder_001'})
    assert r.status_code == 200
    data = r.json()
    assert 1 <= len(data['meals']) <= 3
    assert len(data['reasons']) == len(data['meals'])
    assert data['ai_mode'] in ('remote', 'local')


def test_recommendations_only_from_meals_file(client, monkeypatch):
    """推荐结果（今日推荐 + 文本输入）必须全部来自 meals.json 文件。"""
    import json
    from pathlib import Path
    from app.core.weather_service import WeatherService
    from app.core.llm_service import LLMService
    import app.adapters.web_api as web_api
    WeatherService._cache.clear(); WeatherService._cache_time = 0
    monkeypatch.setattr(WeatherService, '_fetch_open_meteo', lambda self, lat, lon: {
        'temp': 25, 'condition': '多云', 'icon': '⛅', 'source': 'open-meteo'})
    web_api.today_service._llm = LLMService(use_remote=False)
    root = Path(__file__).resolve().parent.parent
    with open(root / 'data' / 'meals.json', 'r', encoding='utf-8-sig') as f:
        file_ids = {m['id'] for m in json.load(f)}
    assert len(file_ids) >= 3
    # 文本输入推荐
    r = client.post('/api/meals/recommend', json={'text_input': '想吃清淡的', 'family_id': 'family_001'})
    for m in r.json()['meals']:
        assert m['id'] in file_ids
    # 今日推荐
    r = client.post('/api/meals/today', json={'family_id': 'family_001', 'elder_id': 'elder_001'})
    for m in r.json()['meals']:
        assert m['id'] in file_ids


def test_recommend_stream_four_steps(client, monkeypatch):
    """SSE 工作流：依次产出 理解需求→查看家庭设置→分析餐品→生成方案 四步，末步含结果。"""
    from app.core.llm_service import LLMService
    import app.adapters.web_api as web_api
    web_api.workflow._llm = LLMService(use_remote=False)
    r = client.post('/api/meals/recommend/stream', json={
        'text_input': '想吃清淡的', 'family_id': 'family_001', 'elder_id': 'elder_001', 'mode': 'input'})
    assert r.status_code == 200
    assert 'text/event-stream' in r.headers.get('content-type', '')
    text = r.text
    for step in (1, 2, 3, 4):
        assert f'"step": {step}' in text
        assert f'"step": {step}, "status": "running"' in text
        assert f'"step": {step}, "status": "done"' in text
    assert '"result"' in text


def test_meal_detail_endpoint(client):
    r = client.get('/api/meals/meal_001')
    assert r.status_code == 200
    assert r.json()['id'] == 'meal_001'
    r = client.get('/api/meals/meal_not_exist')
    assert r.status_code == 404
    assert r.headers.get('X-Error-Code') == 'MEAL_NOT_FOUND'


def test_family_order_contains_meal_id(client):
    """家庭订单列表包含 meal_id（供再来一份直接展示上次下单餐食）。"""
    oid = client.post('/api/orders', json={
        'meal_id': 'meal_001', 'elder_id': 'elder_001', 'family_id': 'family_001'}).json()['order_id']
    orders = client.get('/api/family/family_001/orders').json()
    o = next(x for x in orders if x['order_id'] == oid)
    assert o['meal_id'] == 'meal_001'


def test_recommend_local_no_llm(client):
    """本地传统检索：ai_mode=local、不调用大模型，且满足家属规则（预算/禁止食材）。"""
    client.post('/api/family/settings', json={
        'family_id': 'family_001', 'elder_id': 'elder_001',
        'rules': {'max_price': 30, 'allowed_dietary': ['low_oil', 'low_salt'],
                  'blocked_items': ['花生'], 'notify_on_unconfirm': True,
                  'unconfirm_timeout_minutes': 30, 'notes': ''}})
    r = client.post('/api/meals/recommend/local', json={
        'text_input': '想吃清淡的', 'family_id': 'family_001'})
    assert r.status_code == 200
    d = r.json()
    assert d['ai_mode'] == 'local'
    assert 1 <= len(d['meals']) <= 3
    for m in d['meals']:
        assert m['price'] <= 30
        assert '花生' not in m['name']


def test_order_repo_persists(tmp_path):
    """历史订单库：订单持久化到文件后，重新加载仓库仍能读取历史订单。"""
    from app.repositories.mock_repo import MockOrderRepository
    path = str(tmp_path / 'orders.json')
    repo = MockOrderRepository(path)
    repo.create_order('meal_001', 'elder_001', 'family_001', '清蒸鲈鱼套餐', 28.0, 35)
    repo2 = MockOrderRepository(path)
    counts = repo2.get_meal_order_counts()
    assert counts.get('meal_001', 0) >= 1


def test_analysis_endpoint(client, monkeypatch):
    """家属端 AI 分析接口：返回摘要、规则匹配项与综合适合度（0~100）。"""
    from app.core.llm_service import LLMService
    import app.adapters.web_api as web_api
    # 禁用大模型分析，走确定性本地降级
    web_api.analysis_service._llm = LLMService(use_remote=False)
    client.post('/api/family/settings', json={
        'family_id': 'family_001', 'elder_id': 'elder_001',
        'rules': {'max_price': 25, 'allowed_dietary': ['low_oil', 'low_salt'],
                  'blocked_items': ['花生'], 'notify_on_unconfirm': True,
                  'unconfirm_timeout_minutes': 30, 'notes': '少盐'}})
    r = client.post('/api/analysis')
    assert r.status_code == 200
    d = r.json()
    assert 'summary' in d and d['summary']
    assert 'matches' in d and len(d['matches']) > 0
    assert 0 <= d['suitability'] <= 100
    labels = ' '.join(m['label'] for m in d['matches'])
    assert '预算' in labels


def test_recommend_user_budget_hard_filter_api(client):
    """接口级验证：用户明确说价格上限，超预算餐品被硬剔除（咖喱鸡肉饭 28 元不应出现）。"""
    r = client.post('/api/meals/recommend', json={
        'text_input': '咖喱鸡肉饭，20元以内', 'family_id': 'family_001',
    })
    assert r.status_code == 200
    data = r.json()
    assert data['meals'], '应有推荐结果'
    assert all(m['price'] <= 20 for m in data['meals'])
    assert not any(m['id'] == 'meal_030' for m in data['meals'])


def test_today_recommend_api(client):
    """今日推荐：返回 1~3 份符合家属规则的餐食，reasons 与 meals 一一对应。"""
    r = client.post('/api/meals/today', json={
        'family_id': 'family_001', 'elder_id': 'elder_001',
    })
    assert r.status_code == 200
    data = r.json()
    assert 1 <= len(data['meals']) <= 3
    assert len(data['reasons']) == len(data['meals'])
    assert data['ai_mode'] in ('remote', 'local')


def test_order_timeout_api(client):
    """送达后未确认 → 可标记为超时未确认。"""
    oid = client.post('/api/orders', json={
        'meal_id': 'meal_001', 'elder_id': 'elder_001', 'family_id': 'family_001',
    }).json()['order_id']
    for _ in range(5):
        client.post(f'/api/orders/{oid}/advance')
    r = client.post(f'/api/orders/{oid}/timeout')
    assert r.status_code == 200
    assert r.json()['status'] == 'unconfirmed_timeout'


def test_order_cancel_api(client):
    """进行中的订单可取消。"""
    oid = client.post('/api/orders', json={
        'meal_id': 'meal_001', 'elder_id': 'elder_001', 'family_id': 'family_001',
    }).json()['order_id']
    r = client.post(f'/api/orders/{oid}/cancel')
    assert r.status_code == 200
    assert r.json()['status'] == 'cancelled'


def test_family_rules_roundtrip_api(client):
    """家属规则保存后读取一致。"""
    client.post('/api/family/settings', json={
        'family_id': 'family_003', 'elder_id': 'elder_001',
        'rules': {'max_price': 25, 'allowed_dietary': ['low_oil'], 'blocked_items': ['海鲜'],
                  'notify_on_unconfirm': True, 'unconfirm_timeout_minutes': 45, 'notes': '少放盐'},
    })
    r = client.get('/api/family/family_003/rules?elder_id=elder_001')
    assert r.status_code == 200
    rules = r.json()
    assert rules['max_price'] == 25
    assert rules['allowed_dietary'] == ['low_oil']
    assert rules['blocked_items'] == ['海鲜']
    assert rules['unconfirm_timeout_minutes'] == 45
    assert rules['notes'] == '少放盐'


def test_weather_endpoint_fallback(client, monkeypatch):
    """天气接口：获取失败时返回降级结构，不抛错。"""
    def fake_weather(self, lat=None, lon=None):
        return {'temp': None, 'condition': '获取失败', 'icon': '🌤️', 'source': 'fallback', 'date': '', 'location': '上海'}
    monkeypatch.setattr('app.core.weather_service.WeatherService.get_weather', fake_weather)
    r = client.get('/api/weather')
    assert r.status_code == 200
    data = r.json()
    assert 'condition' in data and 'temp' in data and 'icon' in data


def test_recommend_stream_api(client):
    """SSE 工作流：逐步推送事件，最终生成推荐方案。"""
    with client.stream('POST', '/api/meals/recommend/stream', json={
        'text_input': '清淡一点', 'family_id': 'family_001', 'elder_id': 'elder_001', 'mode': 'input',
    }) as resp:
        assert resp.status_code == 200
        assert resp.headers.get('content-type', '').startswith('text/event-stream')
        body = ''.join(resp.iter_text())
    assert 'data:' in body
    assert '"step"' in body
    assert '"status"' in body
    assert '"result"' in body or '生成推荐' in body


def test_contact_elder_api(client):
    """家属联系老人（模拟）：返回 success。"""
    oid = client.post('/api/orders', json={
        'meal_id': 'meal_001', 'elder_id': 'elder_001', 'family_id': 'family_001',
    }).json()['order_id']
    r = client.post('/api/family/contact', json={
        'order_id': oid, 'family_id': 'family_001', 'contact_type': 'call',
    })
    assert r.status_code == 200
    assert r.json()['status'] == 'success'
