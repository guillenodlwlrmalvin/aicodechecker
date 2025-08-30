import os
import requests
from typing import Optional, Dict, Any
import time

DEFAULT_LM_BASE_URL = os.environ.get('LM_STUDIO_BASE_URL', 'http://localhost:1234/v1')
DEFAULT_MODEL = os.environ.get(
    'LM_STUDIO_MODEL',
    'TheBloke/CodeLlama-7B-Instruct-GGUF/codellama-7b-instruct.Q4_K_S.gguf'
)
TIMEOUT_SECONDS = float(os.environ.get('LM_STUDIO_TIMEOUT', '60'))
MAX_RETRIES = int(os.environ.get('LM_STUDIO_MAX_RETRIES', '6'))

SYSTEM_PROMPT = (
    "You are a precise classifier for code origin (AI vs HUMAN).\n"
    "Return only a single JSON object with keys: label, score, explanation.\n"
    "- label: one of AI, HUMAN, UNCERTAIN\n"
    "- score: float 0..100 = probability code is AI-generated\n"
    "- explanation: one short sentence\n"
    "Be conservative; if unsure use UNCERTAIN with score near 50."
)

LANG_SYSTEM_PROMPT = (
    "You are a programming language identifier. Given CODE, respond with only JSON: {\"language\": <lowercase language name or 'unknown'>}.\n"
    "If ambiguous, return 'unknown'. Return ONLY the JSON."
)

def _filename_of_model(model: str) -> str:
    return (model or '').rstrip('/').split('/')[-1] or model

def _post_chat(base_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()

def _should_retry(exc: Exception) -> bool:
    if isinstance(exc, requests.Timeout):
        return True
    if isinstance(exc, requests.ConnectionError):
        return True
    if isinstance(exc, requests.HTTPError):
        try:
            status = exc.response.status_code
        except Exception:
            status = None
        if status in (429, 500, 502, 503, 504):
            return True
        try:
            text = exc.response.text.lower()
            if 'not loaded' in text or 'loading' in text or 'model is not loaded' in text:
                return True
        except Exception:
            pass
    return False


def classify_with_lmstudio(code_text: str, language_hint: str = 'auto',
                           base_url: str = DEFAULT_LM_BASE_URL,
                           model: str = DEFAULT_MODEL) -> Optional[Dict[str, Any]]:
    try:
        user_prompt = (
            f"Language: {language_hint}\n\n"
            f"CODE:\n````\n{code_text}\n````\n\nReply with only the JSON object."
        )
        payload = {
            "model": model,
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 256,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }

        attempts = 0
        tried_fallback = False
        last_error: Optional[Exception] = None
        while attempts < MAX_RETRIES:
            try:
                data = _post_chat(base_url, payload)
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if not content:
                    raise requests.HTTPError("Empty response from LM Studio", response=None)
                import json, re
                match = re.search(r"\{[\s\S]*\}", content)
                if match:
                    try:
                        parsed = json.loads(match.group(0))
                        raw_label = str(parsed.get('label', 'UNCERTAIN')).upper()
                        score = float(parsed.get('score', 50.0))
                        explanation = parsed.get('explanation', 'No explanation provided.')
                        label_map = {
                            'AI': 'AI-generated (LLM)',
                            'HUMAN': 'Human-written (LLM)',
                            'UNCERTAIN': 'Uncertain (LLM)'
                        }
                        return {
                            'label': label_map.get(raw_label, 'Uncertain (LLM)'),
                            'score': max(0.0, min(100.0, score)),
                            'explanation': explanation,
                            'raw': content,
                        }
                    except Exception:
                        pass
                low = content.lower()
                if 'ai' in low and 'human' not in low:
                    label, score = 'AI-generated (LLM)', 90.0
                elif 'human' in low and 'ai' not in low:
                    label, score = 'Human-written (LLM)', 20.0
                else:
                    label, score = 'Uncertain (LLM)', 50.0
                return {
                    'label': label,
                    'score': score,
                    'explanation': 'Parsed non-JSON output; applied fallback mapping.',
                    'raw': content,
                }
            except Exception as e:  # noqa: BLE001
                last_error = e
                if not tried_fallback:
                    tried_fallback = True
                    fallback_model = _filename_of_model(payload.get("model", ""))
                    if fallback_model and fallback_model != payload.get("model"):
                        payload["model"] = fallback_model
                        time.sleep(0.5)
                        attempts += 1
                        continue
                if _should_retry(e):
                    delay = min(1.0 * (2 ** attempts), 8.0)
                    time.sleep(delay)
                    attempts += 1
                    continue
                break
        raise last_error or RuntimeError("LM Studio request failed")

    except Exception as e:
        return {
            'label': 'Unavailable (LLM)',
            'score': 0.0,
            'explanation': f'LM Studio error: {e}',
        }


def detect_language_with_lmstudio(code_text: str,
                                  base_url: str = DEFAULT_LM_BASE_URL,
                                  model: str = DEFAULT_MODEL) -> Optional[str]:
    try:
        payload = {
            "model": model,
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 64,
            "messages": [
                {"role": "system", "content": LANG_SYSTEM_PROMPT},
                {"role": "user", "content": f"CODE:\n````\n{code_text}\n````\n"},
            ],
            "stream": False,
        }
        attempts = 0
        tried_fallback = False
        last_error: Optional[Exception] = None
        while attempts < MAX_RETRIES:
            try:
                data = _post_chat(base_url, payload)
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if not content:
                    raise requests.HTTPError("Empty response from LM Studio", response=None)
                import json, re
                match = re.search(r"\{[\s\S]*\}", content)
                if match:
                    try:
                        parsed = json.loads(match.group(0))
                        language = str(parsed.get('language', 'unknown')).strip().lower()
                        return language or 'unknown'
                    except Exception:
                        pass
                # Fallback: try to extract a single word
                m2 = re.search(r"language\s*[:=]\s*([a-zA-Z0-9_\-\+\#]+)", content, re.IGNORECASE)
                if m2:
                    return m2.group(1).strip().lower()
                return 'unknown'
            except Exception as e:  # noqa: BLE001
                last_error = e
                if not tried_fallback:
                    tried_fallback = True
                    fallback_model = _filename_of_model(payload.get("model", ""))
                    if fallback_model and fallback_model != payload.get("model"):
                        payload["model"] = fallback_model
                        time.sleep(0.5)
                        attempts += 1
                        continue
                if _should_retry(e):
                    delay = min(1.0 * (2 ** attempts), 8.0)
                    time.sleep(delay)
                    attempts += 1
                    continue
                break
        raise last_error or RuntimeError("LM Studio language detect failed")
    except Exception:
        return None 