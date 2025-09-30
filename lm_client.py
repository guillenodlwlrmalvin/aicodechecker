import os
import requests
from typing import Optional, Dict, Any, List, Tuple
import time
import re
import json

DEFAULT_LM_BASE_URL = os.environ.get('LM_STUDIO_BASE_URL', 'http://localhost:1234/v1')
DEFAULT_MODEL = os.environ.get(
    'LM_STUDIO_MODEL',
    'TheBloke/CodeLlama-13B-Instruct-GGUF/codellama-13b-instruct.Q8_0.gguf'
)
TIMEOUT_SECONDS = float(os.environ.get('LM_STUDIO_TIMEOUT', '60'))
MAX_RETRIES = int(os.environ.get('LM_STUDIO_MAX_RETRIES', '6'))

# Enhanced system prompt with detailed scoring criteria
SCORING_CRITERIA = {
    "AI_INDICATORS": [
        "Overly consistent formatting and indentation",
        "Generic variable/function names (temp, data, value, func)",
        "Perfect syntax but lacks edge case handling",
        "Repetitive patterns across similar operations",
        "Excessive comments explaining obvious code",
        "Standard library overuse without custom logic",
        "Template-like structure with placeholder names",
        "Lacks project-specific context or business logic",
        "Follows common coding challenge patterns"
    ],
    "HUMAN_INDICATORS": [
        "Idiomatic language features and patterns",
        "Creative variable/function naming",
        "Mixed code style and formatting",
        "Practical error handling and edge cases",
        "Project-specific optimizations",
        "Comments explaining complex business logic",
        "Custom utility functions or helpers",
        "Integration with specific libraries/frameworks",
        "Evidence of debugging or iterative development"
    ]
}

SYSTEM_PROMPT = f"""
You are an expert code origin classifier (AI vs HUMAN). Analyze code for these specific indicators:

AI-GENERATED INDICATORS:
{chr(10).join(f"- {indicator}" for indicator in SCORING_CRITERIA["AI_INDICATORS"])}

HUMAN-WRITTEN INDICATORS:
{chr(10).join(f"- {indicator}" for indicator in SCORING_CRITERIA["HUMAN_INDICATORS"])}

SCORING GUIDELINES:
- 0-20: Clearly human-written (strong human indicators, weak/no AI signals)
- 21-40: Likely human-written (more human than AI indicators)
- 41-59: Uncertain/balanced (mixed or unclear signals)
- 60-79: Likely AI-generated (more AI than human indicators)
- 80-100: Clearly AI-generated (strong AI indicators, weak/no human signals)

Return ONLY JSON with: label, score, explanation, confidence, indicators_found
- label: "AI", "HUMAN", or "UNCERTAIN"
- score: 0-100 (probability of AI origin)
- explanation: brief reasoning based on specific indicators found
- confidence: "high", "medium", "low" based on signal strength
- indicators_found: list of specific AI/human indicators detected
"""

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

def _analyze_code_characteristics(code_text: str, language: str) -> Dict[str, Any]:
    """Perform basic code analysis to help with scoring validation"""
    lines = code_text.splitlines()
    non_empty_lines = [line for line in lines if line.strip()]
    
    # Basic metrics
    char_count = len(code_text)
    line_count = len(lines)
    non_empty_line_count = len(non_empty_lines)
    
    # Code structure analysis
    has_comments = any('//' in line or '#' in line or '/*' in line for line in lines)
    has_functions = bool(re.search(r'(def\s+\w+|function\s+\w+|func\s+\w+)', code_text))
    has_conditionals = bool(re.search(r'(if\s*\(|else|elif|switch|case)', code_text))
    has_loops = bool(re.search(r'(for\s*\(|while\s*\(|do\s*\{)', code_text))
    
    # Naming patterns
    generic_names = len(re.findall(r'\b(temp|data|value|result|num|str|arr|list|dict|func|handler)\b', code_text))
    descriptive_names = len(re.findall(r'\b([a-z]+[A-Z][a-z]*|calculate|process|validate|transform)\b', code_text))
    
    return {
        'char_count': char_count,
        'line_count': line_count,
        'non_empty_line_count': non_empty_line_count,
        'has_comments': has_comments,
        'has_functions': has_functions,
        'has_conditionals': has_conditionals,
        'has_loops': has_loops,
        'generic_names': generic_names,
        'descriptive_names': descriptive_names,
        'complexity_score': min(100, (has_functions + has_conditionals + has_loops) * 20 + descriptive_names * 5)
    }

def _validate_and_adjust_score(raw_score: float, code_analysis: Dict[str, Any], raw_label: str) -> Tuple[float, str]:
    """Validate the LLM score against code characteristics and adjust if needed"""
    score = max(0.0, min(100.0, raw_score))
    confidence = "medium"
    
    # Low complexity code should have scores pulled toward uncertain
    complexity = code_analysis['complexity_score']
    if complexity < 30 and code_analysis['line_count'] < 10:
        # Very simple code is hard to classify confidently
        if score > 70:
            score = 50 + (score - 50) * 0.3  # Pull high scores down
            confidence = "low"
        elif score < 30:
            score = 50 - (50 - score) * 0.3  # Pull low scores up
            confidence = "low"
    
    # Validate against code length
    if code_analysis['char_count'] < 100:
        confidence = "low"
        if abs(score - 50) > 40:  # Extreme confidence on tiny code
            score = 50 + (score - 50) * 0.5
    
    # Check for contradictory signals
    if raw_label == "AI" and code_analysis['descriptive_names'] > code_analysis['generic_names']:
        # AI code usually has more generic names
        score = max(30, score - 15)
        confidence = "medium"
    
    elif raw_label == "HUMAN" and code_analysis['generic_names'] > code_analysis['descriptive_names'] * 2:
        # Human code usually has more descriptive names
        score = min(70, score + 15)
        confidence = "medium"
    
    # High confidence for medium-length, structured code
    if 50 <= complexity <= 80 and code_analysis['line_count'] >= 15:
        confidence = "high"
    
    return score, confidence

def classify_with_lmstudio(code_text: str, language_hint: str = 'auto',
                           base_url: str = DEFAULT_LM_BASE_URL,
                           model: str = DEFAULT_MODEL) -> Optional[Dict[str, Any]]:
    try:
        # Analyze code characteristics for validation
        code_analysis = _analyze_code_characteristics(code_text, language_hint)
        
        user_prompt = (
            f"Language: {language_hint}\n\n"
            f"CODE TO ANALYZE:\n```{language_hint}\n{code_text}\n```\n\n"
            f"Apply the scoring criteria systematically and return JSON analysis."
        )
        
        payload = {
            "model": model,
            "temperature": 0.1,  # Slight temperature for better reasoning
            "top_p": 0.9,
            "max_tokens": 512,  # Increased for detailed analysis
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
                
                # Parse JSON response
                match = re.search(r"\{[\s\S]*\}", content)
                if match:
                    try:
                        parsed = json.loads(match.group(0))
                        raw_label = str(parsed.get('label', 'UNCERTAIN')).upper()
                        raw_score = float(parsed.get('score', 50.0))
                        explanation = parsed.get('explanation', 'No explanation provided.')
                        confidence = parsed.get('confidence', 'medium')
                        indicators_found = parsed.get('indicators_found', [])
                        
                        # Validate and potentially adjust score
                        final_score, final_confidence = _validate_and_adjust_score(
                            raw_score, code_analysis, raw_label
                        )
                        
                        # Use validated confidence if not provided
                        if confidence == 'medium':
                            confidence = final_confidence
                        
                        label_map = {
                            'AI': 'AI-generated (LLM)',
                            'HUMAN': 'Human-written (LLM)', 
                            'UNCERTAIN': 'Uncertain (LLM)'
                        }
                        
                        return {
                            'label': label_map.get(raw_label, 'Uncertain (LLM)'),
                            'score': final_score,
                            'explanation': explanation,
                            'confidence': confidence,
                            'indicators_found': indicators_found,
                            'code_analysis': code_analysis,
                            'raw': content,
                        }
                    except json.JSONDecodeError:
                        # Fall through to text parsing
                        pass
                
                # Fallback text parsing for non-JSON responses
                return _parse_fallback_response(content, code_analysis)
                
            except Exception as e:
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
            'confidence': 'low',
            'indicators_found': [],
        }

def _parse_fallback_response(content: str, code_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Parse non-JSON responses with improved fallback logic"""
    content_lower = content.lower()
    
    # More nuanced fallback parsing
    ai_confidence = 0
    human_confidence = 0
    
    # Check for AI indicators in response
    ai_phrases = ['ai', 'generated', 'model', 'chatgpt', 'copilot', 'assistant', 'llm']
    human_phrases = ['human', 'written', 'developer', 'programmer', 'hand-coded', 'manual']
    
    for phrase in ai_phrases:
        if phrase in content_lower:
            ai_confidence += 1
    
    for phrase in human_phrases:
        if phrase in content_lower:
            human_confidence += 1
    
    # Determine label and score based on confidence signals
    if ai_confidence > human_confidence:
        label = 'AI-generated (LLM)'
        score = min(90.0, 50.0 + (ai_confidence * 10))
    elif human_confidence > ai_confidence:
        label = 'Human-written (LLM)'
        score = max(10.0, 50.0 - (human_confidence * 10))
    else:
        label = 'Uncertain (LLM)'
        score = 50.0
    
    # Adjust based on code analysis
    if code_analysis['complexity_score'] < 20:
        score = 50.0  # Force uncertain for very simple code
        confidence = "low"
    else:
        confidence = "medium"
    
    return {
        'label': label,
        'score': score,
        'explanation': 'Parsed non-JSON output; applied fallback analysis.',
        'confidence': confidence,
        'indicators_found': [],
        'code_analysis': code_analysis,
        'raw': content,
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
            except Exception as e:
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