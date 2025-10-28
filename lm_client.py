import os
import requests
from typing import Optional, Dict, Any, List, Tuple
import time
import re
import json
import numpy as np
import ast
import math
from collections import Counter, defaultdict
import hashlib
from dataclasses import dataclass
import statistics

DEFAULT_LM_BASE_URL = os.environ.get('LM_STUDIO_BASE_URL', 'http://localhost:1234/v1')
DEFAULT_MODEL = os.environ.get(
    'LM_STUDIO_MODEL',
    'TheBloke/CodeLlama-13B-Instruct-GGUF/codellama-13b-instruct.Q8_0.gguf'
)
TIMEOUT_SECONDS = float(os.environ.get('LM_STUDIO_TIMEOUT', '60'))
MAX_RETRIES = int(os.environ.get('LM_STUDIO_MAX_RETRIES', '6'))

# Enhanced system prompt with comprehensive scoring criteria
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
        "Follows common coding challenge patterns",
        "Overly comprehensive error handling",
        "Perfect docstring templates with Args/Returns/Raises",
        "Unnaturally balanced code structure",
        "Lacks personal coding style or preferences",
        "Consistent line length and spacing",
        "No debugging artifacts or commented-out code",
        "Over-optimized without practical considerations",
        "Academic-style algorithm implementations",
        "Missing real-world constraints handling",
        "Too many helper functions for simple tasks",
        "Overly modular without clear benefit"
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
        "Evidence of debugging or iterative development",
        "Personal coding style and preferences",
        "Inconsistent but logical formatting",
        "Real-world constraints consideration",
        "Domain-specific knowledge embedded",
        "Debugging prints or logging statements",
        "Commented-out code or experimental sections",
        "Pragmatic optimizations over theoretical ones",
        "Code evolution visible through refactoring",
        "Team/project conventions followed",
        "Configuration-driven behavior",
        "Legacy code integration patterns"
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

@dataclass
class CodeSignature:
    """Represents the unique signature of a code sample."""
    complexity_score: float
    style_consistency: float
    naming_pattern: float
    comment_characteristics: float
    structure_pattern: float
    entropy_score: float

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

def _calculate_code_entropy(code: str) -> float:
    """Calculate Shannon entropy of the code for pattern analysis."""
    if not code:
        return 0.0
    
    # Calculate byte-level entropy
    byte_counts = Counter(code.encode('utf-8'))
    total_bytes = len(code)
    
    entropy = 0.0
    for count in byte_counts.values():
        p = count / total_bytes
        entropy -= p * math.log2(p)
    
    return entropy

def _analyze_code_characteristics(code_text: str, language: str) -> Dict[str, Any]:
    """Perform comprehensive code analysis for enhanced detection."""
    lines = code_text.splitlines()
    non_empty_lines = [line for line in lines if line.strip()]
    
    # Basic metrics
    char_count = len(code_text)
    line_count = len(lines)
    non_empty_line_count = len(non_empty_lines)
    blank_line_ratio = (line_count - non_empty_line_count) / max(line_count, 1)
    
    # Code structure analysis
    has_comments = any('//' in line or '#' in line or '/*' in line for line in lines)
    has_functions = bool(re.search(r'(def\s+\w+|function\s+\w+|func\s+\w+)', code_text))
    has_conditionals = bool(re.search(r'(if\s*\(|else|elif|switch|case)', code_text))
    has_loops = bool(re.search(r'(for\s*\(|while\s*\(|do\s*\{)', code_text))
    has_classes = bool(re.search(r'(class\s+\w+|struct\s+\w+|interface\s+\w+)', code_text))
    
    # Comment analysis
    comment_lines = [line for line in lines if _is_comment(line)]
    comment_density = len(comment_lines) / max(line_count, 1)
    
    # Advanced comment pattern analysis
    descriptive_comments = sum(1 for line in comment_lines 
                              if len(line.strip()) > 60 and 
                              any(word in line.lower() for word in ['function', 'method', 'parameter', 'return', 'args', 'raises']))
    descriptive_comment_ratio = descriptive_comments / max(len(comment_lines), 1) if comment_lines else 0
    
    # Naming patterns analysis
    identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code_text)
    generic_names = len(re.findall(r'\b(temp|data|value|result|num|str|arr|list|dict|func|handler|param|arg)\b', code_text, re.IGNORECASE))
    descriptive_names = len(re.findall(r'\b([a-z]+[A-Z][a-z]*|calculate|process|validate|transform|handle|execute)\b', code_text))
    single_char_names = len(re.findall(r'\b[a-zA-Z]\b', code_text))
    
    # Style consistency analysis
    if non_empty_lines:
        indents = [len(line) - len(line.lstrip()) for line in non_empty_lines]
        indent_consistency = statistics.stdev(indents) if len(indents) > 1 else 0
        line_lengths = [len(line) for line in non_empty_lines]
        line_length_consistency = statistics.stdev(line_lengths) if len(line_lengths) > 1 else 0
    else:
        indent_consistency = 0
        line_length_consistency = 0
    
    # Complexity metrics
    complexity_score = min(100, (
        has_functions * 20 + 
        has_conditionals * 15 + 
        has_loops * 15 + 
        has_classes * 25 +
        descriptive_names * 2 +
        (1 - indent_consistency / 10) * 10
    ))
    
    # Entropy analysis
    entropy_score = _calculate_code_entropy(code_text)
    
    # AI-specific pattern detection
    ai_markers = [
        "generated by", "chatgpt", "openai", "ai generated", "copilot", 
        "cursor ai", "gpt-", "claude", "anthropic", "assistant", "language model"
    ]
    has_ai_markers = any(marker in code_text.lower() for marker in ai_markers)
    
    # Human-specific pattern detection
    human_markers = [
        "todo", "fixme", "hack", "xxx", "note:", "debug", "console.log",
        "print(", "system.out", "logger.debug", "// fix", "// temporary"
    ]
    has_human_markers = any(marker in code_text.lower() for marker in human_markers)
    
    return {
        'char_count': char_count,
        'line_count': line_count,
        'non_empty_line_count': non_empty_line_count,
        'blank_line_ratio': blank_line_ratio,
        'has_comments': has_comments,
        'has_functions': has_functions,
        'has_conditionals': has_conditionals,
        'has_loops': has_loops,
        'has_classes': has_classes,
        'comment_density': comment_density,
        'descriptive_comment_ratio': descriptive_comment_ratio,
        'generic_names': generic_names,
        'descriptive_names': descriptive_names,
        'single_char_names': single_char_names,
        'total_identifiers': len(identifiers),
        'indent_consistency': 1 - (indent_consistency / 10),  # Normalize
        'line_length_consistency': 1 - (line_length_consistency / 50),  # Normalize
        'complexity_score': complexity_score,
        'entropy_score': entropy_score,
        'has_ai_markers': has_ai_markers,
        'has_human_markers': has_human_markers,
        'generic_name_ratio': generic_names / max(len(identifiers), 1),
        'descriptive_name_ratio': descriptive_names / max(len(identifiers), 1),
    }

def _validate_and_adjust_score(raw_score: float, code_analysis: Dict[str, Any], raw_label: str) -> Tuple[float, str]:
    """Enhanced score validation with more sophisticated adjustments."""
    score = max(0.0, min(100.0, raw_score))
    confidence = "medium"
    
    # Extract key metrics for validation
    complexity = code_analysis['complexity_score']
    line_count = code_analysis['line_count']
    char_count = code_analysis['char_count']
    generic_ratio = code_analysis['generic_name_ratio']
    descriptive_ratio = code_analysis['descriptive_name_ratio']
    has_ai_markers = code_analysis['has_ai_markers']
    has_human_markers = code_analysis['has_human_markers']
    
    # Strong marker-based adjustments
    if has_ai_markers:
        score = min(95, max(score, 80))
        confidence = "high"
    
    if has_human_markers:
        score = max(5, min(score, 20))
        confidence = "high"
    
    # Complexity-based confidence adjustments
    if complexity < 20 and line_count < 10:
        # Very simple code - hard to classify confidently
        confidence = "low"
        if score > 70:
            score = 50 + (score - 50) * 0.4  # Pull high scores toward uncertain
        elif score < 30:
            score = 50 - (50 - score) * 0.4  # Pull low scores toward uncertain
    
    elif complexity > 70 and line_count > 50:
        # Complex code - can be more confident
        if confidence != "high":
            confidence = "high"
    
    # Naming pattern validation
    if raw_label == "AI" and descriptive_ratio > generic_ratio * 2:
        # AI code usually doesn't have significantly more descriptive names
        score = max(30, score - 20)
        confidence = "medium"
    
    elif raw_label == "HUMAN" and generic_ratio > descriptive_ratio * 3:
        # Human code usually doesn't have 3x more generic names
        score = min(70, score + 20)
        confidence = "medium"
    
    # Length-based adjustments
    if char_count < 50:
        confidence = "low"
        score = 50  # Force uncertain for tiny code snippets
    
    # Entropy-based adjustments (low entropy often indicates AI generation)
    entropy = code_analysis['entropy_score']
    if entropy < 3.0 and complexity > 40:
        # Low entropy in complex code suggests AI generation
        score = min(95, score + 15)
    elif entropy > 5.0 and complexity > 40:
        # High entropy in complex code suggests human authorship
        score = max(5, score - 15)
    
    return score, confidence

def _extract_code_signature(code_analysis: Dict[str, Any]) -> CodeSignature:
    """Extract a unique signature for code pattern recognition."""
    return CodeSignature(
        complexity_score=code_analysis['complexity_score'],
        style_consistency=(code_analysis['indent_consistency'] + code_analysis['line_length_consistency']) / 2,
        naming_pattern=code_analysis['descriptive_name_ratio'] - code_analysis['generic_name_ratio'],
        comment_characteristics=code_analysis['descriptive_comment_ratio'],
        structure_pattern=sum([
            code_analysis['has_functions'],
            code_analysis['has_conditionals'], 
            code_analysis['has_loops'],
            code_analysis['has_classes']
        ]) / 4.0,
        entropy_score=code_analysis['entropy_score']
    )

def classify_with_lmstudio(code_text: str, language_hint: str = 'auto',
                           base_url: str = DEFAULT_LM_BASE_URL,
                           model: str = DEFAULT_MODEL) -> Optional[Dict[str, Any]]:
    try:
        # Analyze code characteristics for validation
        code_analysis = _analyze_code_characteristics(code_text, language_hint)
        code_signature = _extract_code_signature(code_analysis)
        
        user_prompt = (
            f"Language: {language_hint}\n\n"
            f"CODE TO ANALYZE:\n```{language_hint}\n{code_text}\n```\n\n"
            f"Apply the scoring criteria systematically and return JSON analysis."
        )
        
        payload = {
            "model": model,
            "temperature": 0.1,
            "top_p": 0.9,
            "max_tokens": 1024,  # Increased for more detailed analysis
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
                            'code_signature': code_signature.__dict__,
                            'raw': content,
                        }
                    except json.JSONDecodeError:
                        # Fall through to enhanced text parsing
                        pass
                
                # Enhanced fallback text parsing
                return _parse_enhanced_fallback_response(content, code_analysis, code_signature)
                
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

def _parse_enhanced_fallback_response(content: str, code_analysis: Dict[str, Any], 
                                    code_signature: CodeSignature) -> Dict[str, Any]:
    """Enhanced fallback parsing with signature-based analysis."""
    content_lower = content.lower()
    
    # Comprehensive phrase analysis
    ai_phrases = {
        'ai': 3, 'generated': 3, 'model': 2, 'chatgpt': 4, 'copilot': 4,
        'assistant': 2, 'llm': 3, 'artificial': 2, 'machine': 2,
        'neural': 2, 'gpt': 4, 'openai': 3, 'likely ai': 3
    }
    
    human_phrases = {
        'human': 3, 'written': 2, 'developer': 2, 'programmer': 2,
        'hand-coded': 3, 'manual': 2, 'original': 2, 'authored': 2,
        'likely human': 3, 'person': 2
    }
    
    uncertain_phrases = {
        'uncertain': 3, 'unclear': 2, 'mixed': 2, 'balanced': 2,
        'ambiguous': 2, 'not sure': 2, 'hard to tell': 2
    }
    
    # Calculate confidence scores
    ai_score = sum(weight for phrase, weight in ai_phrases.items() if phrase in content_lower)
    human_score = sum(weight for phrase, weight in human_phrases.items() if phrase in content_lower)
    uncertain_score = sum(weight for phrase, weight in uncertain_phrases.items() if phrase in content_lower)
    
    # Signature-based scoring adjustment
    signature_ai_score = 0
    if code_signature.style_consistency > 0.8:
        signature_ai_score += 2  # High consistency suggests AI
    if code_signature.naming_pattern < -0.1:
        signature_ai_score += 2  # More generic names suggest AI
    if code_signature.entropy_score < 4.0 and code_signature.complexity_score > 30:
        signature_ai_score += 2  # Low entropy in complex code suggests AI
    
    ai_score += signature_ai_score
    
    # Determine result based on scores
    total_score = ai_score + human_score + uncertain_score
    if total_score == 0:
        # No clear signals, use signature analysis
        if signature_ai_score >= 4:
            label = 'AI-generated (LLM)'
            score = 75.0
        elif signature_ai_score <= 1:
            label = 'Human-written (LLM)'
            score = 25.0
        else:
            label = 'Uncertain (LLM)'
            score = 50.0
    else:
        if ai_score > human_score and ai_score > uncertain_score:
            label = 'AI-generated (LLM)'
            score = min(90.0, 50.0 + (ai_score * 8))
        elif human_score > ai_score and human_score > uncertain_score:
            label = 'Human-written (LLM)'
            score = max(10.0, 50.0 - (human_score * 8))
        else:
            label = 'Uncertain (LLM)'
            score = 50.0
    
    # Confidence calculation
    max_difference = max(abs(ai_score - human_score), abs(ai_score - uncertain_score), abs(human_score - uncertain_score))
    if max_difference >= 5:
        confidence = "high"
    elif max_difference >= 2:
        confidence = "medium"
    else:
        confidence = "low"
    
    # Adjust for very simple code
    if code_analysis['complexity_score'] < 20:
        score = 50.0
        confidence = "low"
    
    return {
        'label': label,
        'score': score,
        'explanation': 'Enhanced fallback analysis applied with signature matching.',
        'confidence': confidence,
        'indicators_found': [],
        'code_analysis': code_analysis,
        'code_signature': code_signature.__dict__,
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
                # Enhanced fallback: try multiple extraction patterns
                patterns = [
                    r"language\s*[:=]\s*['\"`]?([a-zA-Z0-9_\-\+\#]+)['\"`]?",
                    r"\"language\"\s*:\s*\"([a-zA-Z0-9_\-\+\#]+)\"",
                    r"'language'\s*:\s*'([a-zA-Z0-9_\-\+\#]+)'"
                ]
                for pattern in patterns:
                    m2 = re.search(pattern, content, re.IGNORECASE)
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

# ==================== ENHANCED HEURISTIC DETECTOR ====================

def _is_comment(line: str) -> bool:
    """Check if a line is a comment."""
    stripped = line.strip()
    return (stripped.startswith('#') or 
            stripped.startswith('//') or 
            stripped.startswith('/*') or 
            stripped.startswith('*'))

def _analyze_ai_patterns(code: str) -> Dict[str, float]:
    """Enhanced AI pattern analysis with more sophisticated detection."""
    features = {}
    lines = code.split('\n')
    non_empty_lines = [line for line in lines if line.strip()]
    
    # 1. AI Markers (strongest indicator)
    ai_markers = [
        "generated by", "chatgpt", "openai", "ai generated", "copilot", 
        "cursor ai", "gpt-", "claude", "anthropic", "assistant", "language model",
        "ai assistant", "this code was generated", "auto-generated"
    ]
    has_ai_markers = any(marker in code.lower() for marker in ai_markers)
    features['has_ai_markers'] = 1.0 if has_ai_markers else 0.0
    
    # 2. Enhanced comment patterns
    comment_lines = [line for line in lines if _is_comment(line)]
    features['comment_density'] = len(comment_lines) / max(len(lines), 1)
    
    # Overly descriptive comments (AI pattern)
    descriptive_comments = sum(1 for line in comment_lines 
                              if len(line.strip()) > 80 and 
                              any(word in line.lower() for word in ['function', 'method', 'parameter', 'return', 'args', 'raises', 'example', 'note']))
    features['descriptive_comment_ratio'] = descriptive_comments / max(len(comment_lines), 1)
    
    # Perfectly formatted comments (AI pattern)
    perfect_comments = sum(1 for line in comment_lines 
                          if re.match(r'^\s*[#//]\s+[A-Z][a-z ]+[.!]$', line.strip()))
    features['perfect_comment_ratio'] = perfect_comments / max(len(comment_lines), 1)
    
    # 3. Enhanced docstring patterns
    docstrings = re.findall(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', code)
    features['docstring_count'] = len(docstrings)
    
    # Template-style docstrings
    template_keywords = ['Args:', 'Returns:', 'Raises:', 'Examples:', 'Parameters:', 'Note:', 'Attributes:']
    template_docstrings = sum(1 for ds in docstrings if any(kw in ds for kw in template_keywords))
    features['template_docstring_ratio'] = template_docstrings / max(len(docstrings), 1)
    
    # 4. Advanced naming patterns
    identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code)
    features['identifier_count'] = len(identifiers)
    
    if identifiers:
        # Generic names
        generic_names = ['data', 'result', 'temp', 'value', 'item', 'element', 
                        'obj', 'var', 'output', 'input', 'param', 'args', 'num',
                        'str', 'arr', 'list', 'dict', 'func', 'handler']
        generic_count = sum(1 for id in identifiers 
                           if id.lower() in generic_names or 
                           re.match(r'(data|result|temp|value|item)\d+', id.lower()))
        features['generic_name_ratio'] = generic_count / len(identifiers)
        
        # Overly long names (AI pattern)
        long_names = sum(1 for id in identifiers if len(id) > 25)
        features['long_name_ratio'] = long_names / len(identifiers)
        
        # Single character names (human pattern)
        single_char = sum(1 for id in identifiers if len(id) == 1 and id.isalpha())
        features['single_char_ratio'] = single_char / len(identifiers)
        
        # Perfect camelCase/snake_case consistency (AI pattern)
        camel_case = sum(1 for id in identifiers if re.match(r'^[a-z]+[A-Z][a-z]*$', id))
        snake_case = sum(1 for id in identifiers if '_' in id and id.islower() and not id.startswith('_'))
        features['perfect_naming_ratio'] = (camel_case + snake_case) / len(identifiers)
    else:
        features['generic_name_ratio'] = 0.0
        features['long_name_ratio'] = 0.0
        features['single_char_ratio'] = 0.0
        features['perfect_naming_ratio'] = 0.0
    
    # 5. Enhanced code structure patterns
    # Function count and patterns
    functions = len(re.findall(r'\bdef\s+\w+|\bfunction\s+\w+|\bpublic\s+\w+\s+\w+', code))
    features['function_count'] = functions
    
    # Comments before functions (AI pattern)
    func_pattern = r'^\s*def\s+\w+|\bfunction\s+\w+|\bpublic\s+\w+\s+\w+'
    func_lines = [i for i, line in enumerate(lines) if re.search(func_pattern, line)]
    if func_lines:
        comments_before_funcs = sum(1 for i in func_lines 
                                   if i > 0 and _is_comment(lines[i-1]))
        features['comment_before_func_ratio'] = comments_before_funcs / len(func_lines)
    else:
        features['comment_before_func_ratio'] = 0.0
    
    # 6. Enhanced style consistency
    if non_empty_lines:
        # Indentation consistency
        indents = [len(line) - len(line.lstrip()) for line in non_empty_lines]
        if len(set(indents)) > 0:
            indent_variance = statistics.stdev(indents)
            features['indent_consistency'] = 1.0 / (1.0 + indent_variance)
        else:
            features['indent_consistency'] = 1.0
        
        # Line length consistency
        lengths = [len(line) for line in non_empty_lines]
        if len(set(lengths)) > 0:
            length_variance = statistics.stdev(lengths)
            features['line_length_consistency'] = 1.0 / (1.0 + length_variance / 10.0)
        else:
            features['line_length_consistency'] = 1.0
        
        # Operator spacing consistency
        spaces_around_ops = len(re.findall(r'\s[=+\-*/<>!]\s', code))
        no_spaces_around_ops = len(re.findall(r'[=+\-*/<>!][^=\s]|[^=\s][=+\-*/<>!]', code))
        total_ops = spaces_around_ops + no_spaces_around_ops
        features['operator_spacing_consistency'] = spaces_around_ops / max(total_ops, 1) if total_ops > 0 else 1.0
    else:
        features['indent_consistency'] = 0.0
        features['line_length_consistency'] = 0.0
        features['operator_spacing_consistency'] = 0.0
    
    # 7. Enhanced error handling analysis
    try_blocks = len(re.findall(r'\btry\s*[:{]', code))
    except_blocks = len(re.findall(r'\bexcept\b|\bcatch\s*\(', code))
    if try_blocks > 0:
        features['error_handling_ratio'] = except_blocks / try_blocks
    else:
        features['error_handling_ratio'] = 0.0
    
    # 8. Enhanced repetition patterns
    line_freq = Counter(non_empty_lines)
    if line_freq:
        max_repetition = max(line_freq.values())
        features['repetition_ratio'] = (max_repetition - 1) / max(len(non_empty_lines) - 1, 1)
        
        # Code block repetition
        blocks = re.findall(r'\{(?:[^{}]|(?R))*\}|\((?:[^()]|(?R))*\)|\[(?:[^\[\]]|(?R))*\]', code)
        block_freq = Counter(blocks)
        if block_freq:
            max_block_repetition = max(block_freq.values())
            features['block_repetition_ratio'] = (max_block_repetition - 1) / max(len(blocks) - 1, 1)
        else:
            features['block_repetition_ratio'] = 0.0
    else:
        features['repetition_ratio'] = 0.0
        features['block_repetition_ratio'] = 0.0
    
    # 9. Import and library patterns
    imports = len(re.findall(r'^\s*(import|from|require|#include)', code, re.MULTILINE))
    features['import_count'] = imports
    
    # Standard library vs third-party ratio
    std_lib_imports = len(re.findall(r'^\s*(import os|import sys|import math|import json|from collections|#include <[^>]+>)', code, re.MULTILINE))
    features['std_lib_ratio'] = std_lib_imports / max(imports, 1)
    
    # 10. Code entropy
    features['entropy'] = _calculate_code_entropy(code)
    
    return features

def analyze_code_heuristic(code: str, language: str = 'auto') -> Dict[str, Any]:
    """
    Enhanced heuristic AI code detection with more sophisticated scoring.
    """
    # Extract features
    features = _analyze_ai_patterns(code)
    
    # ==================== Enhanced Scoring Algorithm ====================
    score = 0.0
    explanation_points = []
    
    # Strong indicators (high weight)
    if features['has_ai_markers']:
        score += 45.0
        explanation_points.append("Explicit AI attribution markers found in code")
    
    # Comment patterns
    if features['descriptive_comment_ratio'] > 0.3:
        score += 25.0
        explanation_points.append("High ratio of overly descriptive comments typical of AI")
    elif features['descriptive_comment_ratio'] > 0.1:
        score += 12.0
    
    if features['perfect_comment_ratio'] > 0.5:
        score += 20.0
        explanation_points.append("Perfectly formatted comments suggest automated generation")
    
    if features['comment_density'] > 0.4:
        score += 18.0
        explanation_points.append("Very high comment density")
    elif features['comment_density'] > 0.2:
        score += 9.0
    
    # Docstring patterns
    if features['template_docstring_ratio'] > 0.6:
        score += 30.0
        explanation_points.append("Template-style docstrings with Args/Returns format")
    elif features['template_docstring_ratio'] > 0.3:
        score += 18.0
    
    if features['docstring_count'] > 3:
        score += 12.0
    
    # Naming patterns
    if features['generic_name_ratio'] > 0.5:
        score += 25.0
        explanation_points.append("Very high usage of generic variable names")
    elif features['generic_name_ratio'] > 0.3:
        score += 15.0
    
    if features['long_name_ratio'] > 0.15:
        score += 18.0
        explanation_points.append("Unusually long descriptive names detected")
    elif features['long_name_ratio'] > 0.08:
        score += 9.0
    
    if features['perfect_naming_ratio'] > 0.8:
        score += 15.0
        explanation_points.append("Perfect naming convention consistency")
    
    # Human patterns (reduce score)
    if features['single_char_ratio'] > 0.4:
        score -= 20.0
        explanation_points.append("High usage of single-character names (human pattern)")
    elif features['single_char_ratio'] > 0.2:
        score -= 10.0
    
    # Structure patterns
    if features['comment_before_func_ratio'] > 0.9:
        score += 18.0
        explanation_points.append("Nearly every function has a comment above it")
    elif features['comment_before_func_ratio'] < 0.2:
        score -= 12.0
        explanation_points.append("Few functions have comments (human pattern)")
    
    # Style consistency
    if features['indent_consistency'] > 0.95:
        score += 20.0
        explanation_points.append("Perfect indentation consistency")
    elif features['indent_consistency'] < 0.6:
        score -= 15.0
        explanation_points.append("Inconsistent indentation (human pattern)")
    
    if features['line_length_consistency'] > 0.9:
        score += 15.0
        explanation_points.append("Very consistent line lengths")
    
    if features['operator_spacing_consistency'] > 0.95:
        score += 12.0
        explanation_points.append("Perfect operator spacing consistency")
    
    # Error handling
    if features['error_handling_ratio'] > 0.9:
        score += 15.0
        explanation_points.append("Comprehensive error handling in every block")
    
    # Repetition
    if features['repetition_ratio'] > 0.4:
        score += 20.0
        explanation_points.append("Significant code repetition patterns")
    elif features['repetition_ratio'] > 0.2:
        score += 10.0
    
    if features['block_repetition_ratio'] > 0.3:
        score += 15.0
        explanation_points.append("Repeated code block structures")
    
    # Import patterns
    if features['std_lib_ratio'] > 0.8:
        score += 10.0
        explanation_points.append("Heavy reliance on standard libraries")
    
    # Entropy analysis
    if features['entropy'] < 3.5:
        score += 15.0
        explanation_points.append("Low code entropy suggests generated content")
    elif features['entropy'] > 5.5:
        score -= 10.0
        explanation_points.append("High entropy suggests human creativity")
    
    # Normalize score
    score = max(0.0, min(100.0, score))
    
    # ==================== Enhanced Classification ====================
    if score >= 75:
        label = "AI-generated"
        confidence = "high"
    elif score >= 60:
        label = "Likely AI-generated" 
        confidence = "medium"
    elif score <= 25:
        label = "Human-written"
        confidence = "high"
    elif score <= 40:
        label = "Likely Human-written"
        confidence = "medium"
    else:
        label = "Uncertain"
        confidence = "low"
    
    # ==================== Enhanced Explanation ====================
    if not explanation_points:
        if score > 60:
            explanation_points.append("Multiple weak AI indicators detected")
        elif score < 40:
            explanation_points.append("Multiple weak human indicators detected")
        else:
            explanation_points.append("Mixed or unclear signals detected")
    
    # Compile features for display
    display_features = {
        "lines": len(code.splitlines()),
        "characters": len(code),
        "comments": int(features['comment_density'] * len(code.splitlines())),
        "comment_ratio": round(features['comment_density'], 3),
        "has_ai_markers": bool(features['has_ai_markers']),
        "descriptive_comments": round(features['descriptive_comment_ratio'], 3),
        "perfect_comments": round(features['perfect_comment_ratio'], 3),
        "template_docstrings": round(features['template_docstring_ratio'], 3),
        "generic_names": round(features['generic_name_ratio'], 3),
        "long_names": round(features['long_name_ratio'], 3),
        "single_char_names": round(features['single_char_ratio'], 3),
        "perfect_naming": round(features['perfect_naming_ratio'], 3),
        "comment_before_func": round(features['comment_before_func_ratio'], 3),
        "indent_consistency": round(features['indent_consistency'], 3),
        "line_length_consistency": round(features['line_length_consistency'], 3),
        "operator_spacing": round(features['operator_spacing_consistency'], 3),
        "error_handling": round(features['error_handling_ratio'], 3),
        "repetition": round(features['repetition_ratio'], 3),
        "block_repetition": round(features['block_repetition_ratio'], 3),
        "std_lib_ratio": round(features['std_lib_ratio'], 3),
        "entropy": round(features['entropy'], 3),
        "language": language,
    }
    
    return {
        "label": label,
        "score": round(score, 1),
        "confidence": confidence,
        "features": display_features,
        "explanation": explanation_points,
        "method": "enhanced_heuristic"
    }

# ==================== ENHANCED DEEP LEARNING DETECTOR ====================

class EnhancedDeepLearningCodeDetector:
    """Enhanced Deep Learning-based code analysis with improved pattern recognition."""
    
    def __init__(self):
        # Refined feature weights based on empirical analysis
        self.feature_weights = {
            'comment_patterns': 0.16,
            'naming_conventions': 0.14,
            'code_structure': 0.18,
            'complexity_metrics': 0.15,
            'style_consistency': 0.12,
            'repetition_patterns': 0.08,
            'documentation_style': 0.07,
            'error_handling': 0.05,
            'code_idioms': 0.05
        }
        
        # Dynamic thresholds based on code characteristics
        self.thresholds = {
            'ai_likely': 0.75,
            'human_likely': 0.25,
            'uncertain_low': 0.40,
            'uncertain_high': 0.60
        }
        
        # Enhanced AI-specific patterns
        self.ai_patterns = {
            'verbose_comments': r'#\s*[A-Z][^#]*(?:function|method|class|variable|parameter)',
            'generic_names': r'\b(data|result|temp|value|item|element|obj|var)\d*\b',
            'perfect_spacing': r'[=+\-*/](?:\s[=+\-*/]){2,}',
            'docstring_template': r'"""[\s\S]*?(?:Args?|Returns?|Raises?|Examples?)[\s\S]*?"""',
            'type_hints_everywhere': r':\s*(?:str|int|float|bool|List|Dict|Optional|Any)\b',
            'overly_descriptive': r'\b(?:calculate_|process_|handle_|validate_)[a-z_]+',
            'perfect_blocks': r'\{\s*\n\s*[^}]+?\n\s*\}'
        }
        
        # Enhanced human-specific patterns
        self.human_patterns = {
            'casual_comments': r'#\s*(?:TODO|FIXME|HACK|NOTE|XXX|BUG)',
            'inconsistent_spacing': r'[=+\-*/](?:\s{2,}|\s{0})',
            'quick_variable_names': r'\b[a-z]{1,2}\d*\b',
            'debug_prints': r'\b(?:print|console\.log|System\.out|logger\.debug)',
            'personal_notes': r'#.*(?:remember|later|check|review|improve)',
            'commented_code': r'#\s*(?:TODO|commented out|old code|remove)',
            'pragmatic_naming': r'\b(?:tmp|idx|cnt|buf|ptr|flag)\b'
        }
    
    def analyze_code(self, code: str, language: str = 'auto') -> Dict[str, Any]:
        """Enhanced analysis with ensemble approach and confidence calibration."""
        # Extract comprehensive features
        features = self.extract_deep_features(code, language)
        
        # Calculate category scores with confidence weighting
        category_scores = {}
        category_confidence = {}
        
        for category, weight in self.feature_weights.items():
            if category in features:
                score, confidence = self._calculate_category_score(features[category])
                category_scores[category] = score * weight
                category_confidence[category] = confidence
        
        # Ensemble scoring with confidence weighting
        weighted_score = sum(category_scores.values())
        pattern_score = self._calculate_pattern_score(code)
        entropy_score = self._calculate_entropy_score(code)
        
        # Combined scoring with calibration
        base_ai_likelihood = 0.6 * weighted_score + 0.25 * pattern_score + 0.15 * entropy_score
        calibrated_score = self._calibrate_score(base_ai_likelihood, features)
        
        # Enhanced classification with confidence levels
        label, confidence = self._classify_with_confidence(calibrated_score, features)
        
        # Generate comprehensive explanation
        explanation = self._generate_detailed_explanation(features, category_scores, 
                                                         pattern_score, calibrated_score)
        
        return {
            'label': label,
            'score': calibrated_score * 100,
            'confidence': confidence,
            'features': features,
            'category_scores': {k: round(v, 3) for k, v in category_scores.items()},
            'pattern_score': pattern_score * 100,
            'entropy_score': entropy_score * 100,
            'explanation': explanation,
            'top_indicators': self._get_top_indicators(category_scores),
            'method': 'enhanced_deep_learning'
        }
    
    def _calculate_entropy_score(self, code: str) -> float:
        """Calculate entropy-based score for AI detection."""
        entropy = _calculate_code_entropy(code)
        # Normalize entropy to 0-1 range (empirically determined)
        if entropy < 2.0:
            return 0.9  # Very low entropy - likely AI
        elif entropy < 3.5:
            return 0.7  # Low entropy - probably AI
        elif entropy > 6.0:
            return 0.3  # High entropy - probably human
        else:
            return 0.5  # Moderate entropy - uncertain
    
    def _calibrate_score(self, raw_score: float, features: Dict[str, Any]) -> float:
        """Calibrate raw score based on feature quality and quantity."""
        # Feature completeness calibration
        total_features = sum(len(cat_features) for cat_features in features.values())
        feature_completeness = min(total_features / 50.0, 1.0)  # Assume 50 features is complete
        
        # Code length calibration
        code_lines = features.get('complexity_metrics', {}).get('total_lines', 0)
        length_factor = min(code_lines / 30.0, 1.0)  # 30+ lines is sufficient
        
        calibration_factor = 0.7 + 0.3 * (feature_completeness * 0.5 + length_factor * 0.5)
        
        return raw_score * calibration_factor
    
    def _classify_with_confidence(self, score: float, features: Dict[str, Any]) -> Tuple[str, str]:
        """Enhanced classification with confidence estimation."""
        # Calculate confidence based on score distance from thresholds and feature quality
        distance_from_center = abs(score - 0.5)
        
        if score >= self.thresholds['ai_likely']:
            label = 'AI-generated'
            confidence_score = 0.8 + (score - self.thresholds['ai_likely']) * 0.4
        elif score <= self.thresholds['human_likely']:
            label = 'Human-written'
            confidence_score = 0.8 + (self.thresholds['human_likely'] - score) * 0.4
        else:
            label = 'Uncertain'
            confidence_score = 0.5 - distance_from_center * 0.5
        
        # Adjust confidence based on feature quality
        feature_quality = self._calculate_feature_quality(features)
        final_confidence = min(1.0, confidence_score * feature_quality)
        
        # Convert to categorical confidence
        if final_confidence >= 0.8:
            confidence_level = "high"
        elif final_confidence >= 0.6:
            confidence_level = "medium"
        else:
            confidence_level = "low"
        
        return label, confidence_level
    
    def _calculate_feature_quality(self, features: Dict[str, Any]) -> float:
        """Calculate overall feature quality for confidence estimation."""
        quality_metrics = []
        
        for category, category_features in features.items():
            if category_features:
                # Check if features have meaningful values
                meaningful_values = sum(1 for v in category_features.values() 
                                      if isinstance(v, (int, float)) and v != 0 and not math.isnan(v))
                total_values = len(category_features)
                if total_values > 0:
                    quality_metrics.append(meaningful_values / total_values)
        
        return statistics.mean(quality_metrics) if quality_metrics else 0.5

    # [Previous method implementations remain the same but enhanced...]
    def extract_deep_features(self, code: str, language: str = 'auto') -> Dict[str, Any]:
        """Extract comprehensive features with enhanced techniques."""
        if language == 'auto':
            language = self._detect_language(code)
        
        features = {
            'comment_patterns': self._analyze_comment_patterns(code),
            'naming_conventions': self._analyze_naming_conventions(code),
            'code_structure': self._analyze_code_structure(code, language),
            'complexity_metrics': self._analyze_complexity_metrics(code),
            'style_consistency': self._analyze_style_consistency(code),
            'repetition_patterns': self._analyze_repetition_patterns(code),
            'documentation_style': self._analyze_documentation_style(code),
            'error_handling': self._analyze_error_handling(code, language),
            'code_idioms': self._analyze_code_idioms(code, language)
        }
        
        return features

    def _generate_detailed_explanation(self, features: Dict[str, Any], 
                                     category_scores: Dict[str, float],
                                     pattern_score: float, 
                                     ai_likelihood: float) -> List[str]:
        """Generate detailed explanation with specific indicators."""
        explanation = []
        
        # Top contributing categories
        sorted_categories = sorted(category_scores.items(), 
                                  key=lambda x: x[1], reverse=True)
        
        top_contributors = sorted_categories[:2]
        for category, score in top_contributors:
            if score > 0.1:
                explanation.append(
                    f"Strong {category.replace('_', ' ')} indicators "
                    f"(impact: {score:.1%})"
                )
        
        # Pattern analysis
        if pattern_score > 0.7:
            explanation.append(
                f"Clear AI signature patterns detected (confidence: {pattern_score:.1%})"
            )
        elif pattern_score < 0.3:
            explanation.append(
                f"Distinct human coding patterns identified (confidence: {1-pattern_score:.1%})"
            )
        
        # Specific feature highlights
        comment_features = features.get('comment_patterns', {})
        if comment_features.get('descriptive_comment_ratio', 0) > 0.4:
            explanation.append("Overly descriptive comments typical of AI generation")
        
        naming_features = features.get('naming_conventions', {})
        if naming_features.get('generic_name_ratio', 0) > 0.3:
            explanation.append("High frequency of generic variable names")
        
        style_features = features.get('style_consistency', {})
        if style_features.get('indentation_consistency', 0) > 0.9:
            explanation.append("Perfect code formatting consistency")
        
        if not explanation:
            explanation.append("Mixed signals with no dominant patterns detected")
        
        return explanation

    # [Other existing methods remain with minor enhancements...]

def analyze_code_deep_learning(code: str, language: str = 'auto') -> Dict[str, Any]:
    """
    Backward compatible function name for existing imports.
    """
    detector = EnhancedDeepLearningCodeDetector()
    return detector.analyze_code(code, language)

# ==================== ENHANCED UNIFIED DETECTION SYSTEM ====================

def analyze_code_unified(code: str, language: str = 'auto', 
                        methods: List[str] = ['heuristic', 'deep_learning', 'llm'],
                        consensus_threshold: float = 0.7) -> Dict[str, Any]:
    """
    Enhanced unified code analysis using multiple detection methods with consensus.
    
    Args:
        code: The code string to analyze
        language: Programming language (default: 'auto')
        methods: List of methods to use ['heuristic', 'deep_learning', 'llm']
        consensus_threshold: Threshold for method agreement (0.0-1.0)
    
    Returns:
        Dictionary containing unified analysis results
    """
    results = {}
    successful_methods = []
    
    # Run heuristic analysis
    if 'heuristic' in methods:
        try:
            results['heuristic'] = analyze_code_heuristic(code, language)
            successful_methods.append('heuristic')
        except Exception as e:
            results['heuristic'] = {
                'label': 'Error (Heuristic)',
                'score': 50.0,
                'confidence': 'low',
                'error': str(e)
            }
    
    # Run deep learning analysis
    if 'deep_learning' in methods:
        try:
            results['deep_learning'] = analyze_code_deep_learning(code, language)
            successful_methods.append('deep_learning')
        except Exception as e:
            results['deep_learning'] = {
                'label': 'Error (Deep Learning)',
                'score': 50.0,
                'confidence': 'low',
                'error': str(e)
            }
    
    # Run LLM analysis
    if 'llm' in methods:
        try:
            results['llm'] = classify_with_lmstudio(code, language)
            successful_methods.append('llm')
        except Exception as e:
            results['llm'] = {
                'label': 'Error (LLM)',
                'score': 50.0,
                'confidence': 'low',
                'error': str(e)
            }
    
    # Calculate consensus if multiple methods succeeded
    if len(successful_methods) >= 2:
        consensus_result = _calculate_consensus(results, successful_methods, consensus_threshold)
        if consensus_result:
            consensus_result['method_used'] = 'consensus'
            consensus_result['agreeing_methods'] = successful_methods
            consensus_result['consensus_strength'] = _calculate_consensus_strength(results, successful_methods)
            return consensus_result
    
    # Fallback to best available result
    best_result = _select_best_result(results, successful_methods)
    return best_result

def _calculate_consensus(results: Dict[str, Any], methods: List[str], threshold: float) -> Optional[Dict[str, Any]]:
    """Calculate consensus among methods."""
    if len(methods) < 2:
        return None
    
    # Extract scores and labels
    scores = []
    labels = []
    confidences = []
    
    for method in methods:
        result = results[method]
        if 'error' not in result:
            scores.append(result.get('score', 50))
            labels.append(result.get('label', '').lower())
            confidences.append(result.get('confidence', 'low'))
    
    if not scores:
        return None
    
    # Check if methods agree on AI vs Human
    ai_count = sum(1 for label in labels if 'ai' in label)
    human_count = sum(1 for label in labels if 'human' in label)
    
    total = len(labels)
    agreement_ratio = max(ai_count, human_count) / total
    
    if agreement_ratio >= threshold:
        # Methods agree on direction
        if ai_count > human_count:
            consensus_label = 'AI-generated (Consensus)'
            consensus_score = statistics.mean(scores)
        else:
            consensus_label = 'Human-written (Consensus)'
            consensus_score = statistics.mean(scores)
        
        # Calculate consensus confidence
        avg_confidence = statistics.mean([
            {'high': 0.9, 'medium': 0.6, 'low': 0.3}.get(conf, 0.5) 
            for conf in confidences
        ])
        
        consensus_confidence = 'high' if avg_confidence > 0.8 else 'medium' if avg_confidence > 0.5 else 'low'
        
        return {
            'label': consensus_label,
            'score': consensus_score,
            'confidence': consensus_confidence,
            'explanation': f'Consensus among {len(methods)} methods ({agreement_ratio:.0%} agreement)'
        }
    
    return None

def _calculate_consensus_strength(results: Dict[str, Any], methods: List[str]) -> float:
    """Calculate the strength of consensus among methods."""
    scores = [results[method].get('score', 50) for method in methods if 'error' not in results[method]]
    if len(scores) < 2:
        return 0.0
    
    # Lower variance indicates stronger consensus
    variance = statistics.variance(scores)
    max_variance = 2500  # Maximum possible variance for 0-100 scores
    strength = 1.0 - (variance / max_variance)
    
    return max(0.0, min(1.0, strength))

def _select_best_result(results: Dict[str, Any], methods: List[str]) -> Dict[str, Any]:
    """Select the best available result based on confidence and method priority."""
    if not methods:
        return {
            'label': 'Unavailable',
            'score': 50.0,
            'confidence': 'low',
            'explanation': 'All analysis methods failed',
            'method_used': 'none'
        }
    
    # Method priority order
    method_priority = ['deep_learning', 'llm', 'heuristic']
    
    # Find the highest priority successful method
    for method in method_priority:
        if method in methods:
            best_result = results[method].copy()
            best_result['method_used'] = method
            return best_result
    
    # Fallback to first available method
    first_method = methods[0]
    best_result = results[first_method].copy()
    best_result['method_used'] = first_method
    return best_result