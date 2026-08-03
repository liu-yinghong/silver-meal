import json
import os
import re
from typing import Any


_ALLOWED_DIETARY = {
    'low_oil', 'low_salt', 'low_sugar', 'soft_food',
    'vegetarian', 'high_protein', 'low_carb', 'gluten_free',
    'halal', 'no_pork', 'no_seafood', 'low_purine',
}


class LLMService:
    '''大模型服务：优先调用阿里云百炼（DashScope OpenAI 兼容端点）qwen3.7-max
    解析老人用餐需求，任何失败自动降级为本地关键词解析，绝不阻断主链路。'''

    def __init__(self, api_key: str | None = None, model: str = 'qwen3.7-max',
                 base_url: str = 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                 timeout: float = 20.0, use_remote: bool = True):
        self._api_key = api_key if api_key else os.environ.get('OPENAI_API_KEY')
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
        self._use_remote = use_remote
        self.last_source = 'local'

    # ---- 对外入口 ----
    def extract_meal_query(self, user_input: str) -> dict[str, Any]:
        if self._use_remote and self._api_key:
            try:
                result = self._remote_extract(user_input)
            except Exception:
                result = None
            if result is not None:
                self.last_source = 'remote'
                return result
        self.last_source = 'local'
        return self._local_extract(user_input)

    # ---- 远程：DashScope qwen ----
    def _remote_chat(self, system: str, user: str, temperature: float = 0,
                     max_tokens: int = 120, timeout: float | None = None,
                     retry: bool = True) -> str | None:
        """调用远程大模型，返回纯文本内容；失败可选重试一次，最终返回 None。"""
        import time
        t = timeout if timeout is not None else self._timeout
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self._api_key, base_url=self._base_url,
                            timeout=t, max_retries=0)
            resp = client.chat.completions.create(
                model=self._model,
                messages=[
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return (resp.choices[0].message.content or '').strip() or None
        except Exception:
            if not retry:
                return None
        # 失败重试一次（短暂等待，规避瞬时错误/限流）
        time.sleep(0.8)
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self._api_key, base_url=self._base_url,
                            timeout=t, max_retries=0)
            resp = client.chat.completions.create(
                model=self._model,
                messages=[
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return (resp.choices[0].message.content or '').strip() or None
        except Exception:
            return None

    def _remote_extract(self, user_input: str) -> dict[str, Any] | None:
        system = (
            '你是饭心点餐助手的意图解析器。把老人的一句用餐需求解析成 JSON，'
            '只输出 JSON，不要任何其他文字。JSON 结构固定为：'
            '{"summary": "老人的原话", "dietary_preferences": [], '
            '"price_max": null, "price_min": null, "keywords": []}。'
            'dietary_preferences 只能取以下枚举值的子集：'
            'low_oil（低油）、low_salt（低盐）、low_sugar（低糖）、soft_food（软烂易消化）、'
            'vegetarian（素食）、high_protein（高蛋白）、low_carb（低碳水）、gluten_free（无麸质）、'
            'halal（清真）、no_pork（无猪肉）、no_seafood（无海鲜）、low_purine（低嘌呤）。'
            '例如老人说清淡、少油少盐，则填 ["low_oil","low_salt"]；说软和好消化则填 ["soft_food"]。'
            'price_max/price_min 是数字或 null，从“30元以内/不超过30元/15到20元”等表达解析，'
            '没有则填 null。keywords 是老人提到的具体食物词，如 鱼、粥、面、饺子、包子、豆腐，'
            '没有则填空数组。'
        )
        content = self._remote_chat(system, user_input, temperature=0, max_tokens=120)
        if content is None:
            return None
        return self._parse_remote_json(content)

    def pick_meal_for_weather(self, weather: dict[str, Any], meal_lines: str) -> dict[str, Any] | None:
        """根据天气从候选餐食中挑选最合适的一份（大模型）。失败返回 None。"""
        if not (self._use_remote and self._api_key):
            return None
        condition = weather.get('condition', '')
        temp = weather.get('temp')
        system = (
            '你是饭心点餐助手的餐食推荐官。根据今日天气，从候选餐食中挑选最合适的一份。'
            '只输出 JSON，不要任何其他文字。JSON 格式：{"meal_id":"...","reason":"..."}。'
            'reason 要简短、口语化、贴近老年人的表述，说明为什么这份适合今天这种天气。'
        )
        user = (
            f'今日天气：{condition}{("，"+str(temp)+"℃") if temp is not None else ""}。\n'
            f'候选餐食（格式：ID|名称|描述|价格元）：\n{meal_lines}\n'
            '请选出最合适今日天气的一份餐食。'
        )
        content = self._remote_chat(system, user, temperature=0.3, max_tokens=150)
        if content is None:
            return None
        start = content.find('{')
        end = content.rfind('}')
        if start == -1 or end <= start:
            return None
        try:
            data = json.loads(content[start:end + 1])
        except Exception:
            return None
        if not isinstance(data, dict):
            return None
        meal_id = data.get('meal_id')
        reason = data.get('reason')
        if not isinstance(meal_id, str) or not isinstance(reason, str):
            return None
        self.last_source = 'remote'
        return {'meal_id': meal_id.strip(), 'reason': reason.strip()}

    def generate_analysis(self, rules_text: str, meal_text: str) -> dict[str, Any] | None:
        """根据家属饮食规则与推荐餐食，生成 AI 推荐分析（大模型）。失败返回 None。"""
        if not (self._use_remote and self._api_key):
            return None
        system = (
            '你是饭心点餐助手的营养分析专家。根据家属设定的饮食规则与本次推荐的餐食，'
            '生成推荐分析。只输出 JSON，不要任何其他文字，格式：'
            '{"summary":"对推荐的整体分析，说明如何结合老人口味与家属规则进行推荐",'
            '"matches":[{"label":"规则/维度名称","desc":"分析过程与结果说明","status":"match或info或warn"}]}。'
            'status 取值：match=匹配通过，info=参考信息，warn=需注意。'
            'matches 应覆盖：预算、饮食偏好、禁忌食材等维度。'
        )
        user = f'家属设定的饮食规则：{rules_text}\n本次推荐的餐食：{meal_text}\n请生成本次推荐分析。'
        content = self._remote_chat(system, user, temperature=0.3, max_tokens=300,
                                    timeout=28, retry=False)
        if content is None:
            return None
        data = self._parse_analysis_json(content)
        if data is None:
            return None
        summary = data.get('summary')
        matches = data.get('matches')
        if not isinstance(summary, str) or not isinstance(matches, list) or not matches:
            return None
        clean = []
        for m in matches:
            if isinstance(m, dict) and isinstance(m.get('label'), str):
                clean.append({
                    'label': m.get('label'),
                    'desc': str(m.get('desc', '')),
                    'status': m.get('status') if m.get('status') in ('match', 'info', 'warn') else 'info',
                })
        if not clean:
            return None
        self.last_source = 'remote'
        return {'summary': summary, 'matches': clean}

    @staticmethod
    def _parse_analysis_json(content: str) -> dict[str, Any] | None:
        text = content.strip()
        if text.startswith('```'):
            text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
        start = text.find('{')
        end = text.rfind('}')
        if start == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start:end + 1])
        except Exception:
            return None
        return data if isinstance(data, dict) else None



    def _parse_remote_json(self, content: str) -> dict[str, Any] | None:
        text = content.strip()
        if text.startswith('```'):
            text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
        start = text.find('{')
        end = text.rfind('}')
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start:end + 1])
        except Exception:
            return None
        if not isinstance(data, dict):
            return None

        prefs = data.get('dietary_preferences', []) or []
        if not isinstance(prefs, list):
            prefs = []
        prefs = [p for p in prefs if isinstance(p, str) and p in _ALLOWED_DIETARY]
        prefs = list(dict.fromkeys(prefs))

        def _to_price(v: Any) -> float | None:
            if v is None:
                return None
            if isinstance(v, (int, float)):
                return float(v)
            m = re.search(r'\d+(?:\.\d+)?', str(v))
            if not m:
                return None
            return float(m.group())

        keywords = data.get('keywords', []) or []
        if not isinstance(keywords, list):
            keywords = []
        keywords = [str(k) for k in keywords if isinstance(k, str)]

        summary = data.get('summary') or ''
        if not isinstance(summary, str):
            summary = ''

        return {
            'summary': summary,
            'dietary_preferences': prefs,
            'price_max': _to_price(data.get('price_max')),
            'price_min': _to_price(data.get('price_min')),
            'keywords': keywords,
        }

    # ---- 本地：关键词解析降级 ----
    def _local_extract(self, user_input: str) -> dict[str, Any]:
        result = {
            'summary': user_input,
            'dietary_preferences': [],
            'price_max': None,
            'price_min': None,
            'keywords': [],
        }

        input_lower = user_input.lower()

        if '清淡' in input_lower:
            result['dietary_preferences'].extend(['low_oil', 'low_salt', 'soft_food'])
        if '低糖' in input_lower or '无糖' in input_lower:
            result['dietary_preferences'].append('low_sugar')
        if '低盐' in input_lower or '少盐' in input_lower:
            result['dietary_preferences'].append('low_salt')
        if '低油' in input_lower or '少油' in input_lower or '清淡' in input_lower:
            if 'low_oil' not in result['dietary_preferences']:
                result['dietary_preferences'].append('low_oil')
        if '软' in input_lower or '好消化' in input_lower or '容易嚼' in input_lower:
            result['dietary_preferences'].append('soft_food')
        if '素食' in input_lower or '素餐' in input_lower or '不吃肉' in input_lower:
            result['dietary_preferences'].append('vegetarian')
        if '高蛋白' in input_lower or '补充蛋白' in input_lower:
            result['dietary_preferences'].append('high_protein')
        if '低碳水' in input_lower or '少主食' in input_lower:
            result['dietary_preferences'].append('low_carb')
        if '无麸质' in input_lower:
            result['dietary_preferences'].append('gluten_free')
        if '清真' in input_lower:
            result['dietary_preferences'].extend(['halal', 'no_pork'])
        if ('不吃猪肉' in input_lower or '忌猪肉' in input_lower) and 'no_pork' not in result['dietary_preferences']:
            result['dietary_preferences'].append('no_pork')
        if '不吃海鲜' in input_lower or '海鲜过敏' in input_lower:
            result['dietary_preferences'].append('no_seafood')
        if '低嘌呤' in input_lower or '痛风' in input_lower:
            result['dietary_preferences'].append('low_purine')

        price_patterns = [
            (r'(\d+)\s*元\s*(以[内下]|左右)', lambda m: ('max', float(m.group(1)))),
            (r'(以[内下]|不超过)\s*(\d+)\s*元', lambda m: ('max', float(m.group(2)))),
            (r'(\d+)\s*到\s*(\d+)\s*元', lambda m: ('range', float(m.group(1)), float(m.group(2)))),
        ]
        for pattern, extractor in price_patterns:
            match = re.search(pattern, input_lower)
            if match:
                extracted = extractor(match)
                if extracted[0] == 'max':
                    result['price_max'] = extracted[1]
                elif extracted[0] == 'range':
                    result['price_min'] = extracted[1]
                    result['price_max'] = extracted[2]
                break

        food_keywords = ['鱼', '面', '粥', '饭', '汤', '饺子', '包子', '豆腐', '蔬菜', '肉']
        for kw in food_keywords:
            if kw in input_lower:
                result['keywords'].append(kw)

        return result
