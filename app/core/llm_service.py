import json
from typing import Any


class LLMService:
    \"\"\"大模型服务 - Demo 阶段使用模拟实现，后期可替换为真实 API\"\"\"

    def __init__(self, api_key: str | None = None, model: str = 'gpt-3.5-turbo'):
        self._api_key = api_key
        self._model = model

    def extract_meal_query(self, user_input: str) -> dict[str, Any]:
        \"\"\"将老人输入转换为结构化查询参数。
        Demo 阶段使用关键词匹配模拟，后期替换为真实大模型调用。\"\"\"
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

        import re
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