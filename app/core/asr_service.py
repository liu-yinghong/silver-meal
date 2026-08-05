"""语音识别工具（智能体可调用的 ASR 能力）。

调用阿里云百炼 DashScope Paraformer（paraformer-realtime-v2）将语音转文字。
API Key 复用 OPENAI_API_KEY 环境变量（与 LLM 一致）。
未配置 Key / 调用失败时返回 None，由上层降级处理，绝不阻断主链路。
"""

import os
import tempfile
from pathlib import Path
from typing import Any


class ASRService:
    """语音识别工具。"""

    MODEL = 'paraformer-realtime-v2'
    SAMPLE_RATE = 16000

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get('OPENAI_API_KEY')

    def transcribe(self, wav_bytes: bytes, sample_rate: int = SAMPLE_RATE) -> str | None:
        """将 16kHz 单声道 PCM WAV 音频转文字。失败返回 None。"""
        if not wav_bytes:
            return None
        if not self._api_key:
            return None
        try:
            import dashscope
            dashscope.api_key = self._api_key
            from dashscope.audio.asr import Recognition

            tmp_path = self._write_temp_wav(wav_bytes)
            recognition = Recognition(
                model=self.MODEL,
                format='wav',
                sample_rate=sample_rate,
                callback=None,
            )
            result = recognition.call(str(tmp_path))
            if result is None or getattr(result, 'status_code', None) != 200:
                return None
            return self._extract_text(result)
        except Exception:
            return None

    def _write_temp_wav(self, wav_bytes: bytes) -> Path:
        tmp_dir = Path(tempfile.gettempdir()) / 'silver-meal'
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / 'asr_input.wav'
        tmp_path.write_bytes(wav_bytes)
        return tmp_path

    def _extract_text(self, result: Any) -> str | None:
        try:
            sentence = result.get_sentence()
        except Exception:
            return None
        text = ''
        if isinstance(sentence, dict):
            text = sentence.get('text') or ''
        elif isinstance(sentence, list):
            for s in sentence:
                if isinstance(s, dict):
                    text += s.get('text') or ''
        text = text.strip()
        return text or None
