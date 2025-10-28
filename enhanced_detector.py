#!/usr/bin/env python3
"""
Enhanced Code Detector
Enhanced code detection system that integrates with the comprehensive code dataset.
"""

import os
import sys
import re
import pandas as pd
from typing import Dict, Any, List, Optional
from pathlib import Path

# Import existing detectors
from detector import analyze_code
from deep_learning_detector import analyze_code_deep_learning

# Import new dataset loader
from code_dataset_loader import CodeDatasetLoader


class EnhancedCodeDetector:
    """Enhanced code detector that uses the comprehensive dataset for better analysis."""
    
    def __init__(self, dataset_path: str = "AIGCodeSet"):
        self.dataset_loader = CodeDatasetLoader(dataset_path)
        self.dataset_loaded = False
        self.has_python2 = False
        self.code_patterns = self._initialize_code_patterns()
    
    def _initialize_code_patterns(self) -> Dict[str, List[str]]:
        return {
            'ai_indicators': [
                r'\b(import\s+\w+\s*$)',
                r'\bdef\s+\w+\s*\([^)]*\):\s*$',
                r'\bclass\s+\w+\s*\([^)]*\):\s*$',
                r'\b#\s*(TODO|FIXME|NOTE)\b',
                r'\bprint\s*\([^)]*\)',
                r'\breturn\s+\w+\s*$',
                r'^\s{4}\w+.*$',
                r'\n\s*\n\s*\n',
                r'\b(temp|tmp|var|val|data|result|output|input)\d*\b',
                r'\bif\s+__name__\s*==\s*["\']__main__["\']:',
                r'\btry:\s*\n\s*.*\s*\nexcept\s+Exception:',
                # Common AI generator signatures
                r'\bfrom\s+typing\s+import\s+.*',
                r'->\s*[A-Za-z_][A-Za-z0-9_\[\], ]*',  # return type hints
                r'^\s*"""[\s\S]{0,200}?Args?:',      # docstring with Args section
                r'^\s*"""[\s\S]{0,200}?Returns?:',   # docstring with Returns section
                r'\braise\s+ValueError\(',              # defensive checks typical of LLM templates
            ],
            'human_indicators': [
                r'\b#\s*(This|Here|Now|Let|I|We|My|Our)\b',
                r'\b#\s*(hack|quick|dirty|ugly|stupid|weird)\b',
                r'\b#\s*(test|debug|check|verify)\b',
                r'\b(debug|test|check|verify|validate)\w*\s*\(',
                r'\bprint\s*\([^)]*debug[^)]*\)',
                r'\b#\s*TODO:\s*.*',
                r'\b#\s*FIXME:\s*.*',
                r'\s{2,3}\w+',
                r'\t\s+\w+',
                r'\b(my_|our_|test_|debug_|temp_)\w+\b',
                r'\b\w+_\d{4,}\b',
                r'\bif\s+True:\s*#\s*debug',
                r'\bpass\s*#\s*(placeholder|temp)',
            ],
            'llm_specific': {
                'CODESTRAL': [r'\bfrom\s+typing\s+import\s+.*', r'\bdef\s+\w+\s*\([^)]*\)\s*->\s*\w+:', r'\bclass\s+\w+\s*\([^)]*\):\s*\n\s*""".*"""'],
                'GEMINI': [r'\bimport\s+collections\b', r'\bfrom\s+collections\s+import\s+defaultdict', r'\bdef\s+\w+\s*\([^)]*\):\s*\n\s*"""\s*Args:'],
                'LLAMA': [r'\bdef\s+\w+\s*\([^)]*\):\s*\n\s*"""\s*[A-Z]', r'\bclass\s+\w+\s*\([^)]*\):\s*\n\s*"""\s*[A-Z]', r'\breturn\s+\w+\s*#\s*[A-Z]'],
            },
        }
    
    def load_dataset(self) -> bool:
        if not self.dataset_loaded:
            # Load multiple datasets: Java datasets (primary), program dataset (secondary), and others
            java_loaded = self.dataset_loader.load_java_datasets()
            program_loaded = self.dataset_loader.load_program_dataset()
            llm_loaded = self.dataset_loader.load_llm_dataset()
            human_loaded = self.dataset_loader.load_human_dataset()
            self.dataset_loaded = java_loaded or program_loaded or llm_loaded or human_loaded
            self.has_python2 = False
        return self.dataset_loaded
    
    def analyze_code_enhanced(self, code: str, language: str = 'auto') -> Dict[str, Any]:
        self.load_dataset()
        basic_result = analyze_code(code, language)
        deep_learning_result = analyze_code_deep_learning(code, language)
        enhanced_analysis = self._analyze_with_dataset_patterns(code)
        return {
            'basic_analysis': basic_result,
            'deep_learning_analysis': deep_learning_result,
            'enhanced_analysis': enhanced_analysis,
            'dataset_sources': {
                'java_datasets': bool(getattr(self.dataset_loader, 'java_datasets', None) is not None),
                'program_dataset': bool(getattr(self.dataset_loader, 'program_dataset', None) is not None),
                'llm_dataset': bool(getattr(self.dataset_loader, 'llm_dataset', None) is not None),
                'human_dataset': bool(getattr(self.dataset_loader, 'human_dataset', None) is not None),
            },
            'final_prediction': self._combine_predictions(basic_result, deep_learning_result, enhanced_analysis)
        }
    
    def _analyze_with_dataset_patterns(self, code: str) -> Dict[str, Any]:
        analysis = {
            'ai_score': 0,
            'human_score': 0,
            'llm_model_prediction': None,
            'pattern_matches': {'ai_indicators': [], 'human_indicators': [], 'llm_specific': {}},
            'code_metrics': self._calculate_code_metrics(code),
            'match_spans': {
                'ai_indicators': [],
                'human_indicators': [],
            },
        }
        for pattern in self.code_patterns['ai_indicators']:
            for m in re.finditer(pattern, code, re.MULTILINE | re.IGNORECASE):
                analysis['pattern_matches']['ai_indicators'].append(m.group(0))
                analysis['match_spans']['ai_indicators'].append((m.start(), m.end()))
                analysis['ai_score'] += 3
        for pattern in self.code_patterns['human_indicators']:
            for m in re.finditer(pattern, code, re.MULTILINE | re.IGNORECASE):
                analysis['pattern_matches']['human_indicators'].append(m.group(0))
                analysis['match_spans']['human_indicators'].append((m.start(), m.end()))
                analysis['human_score'] += 2
        for llm_model, patterns in self.code_patterns['llm_specific'].items():
            model_matches = []
            for pattern in patterns:
                matches = re.findall(pattern, code, re.MULTILINE | re.IGNORECASE)
                if matches:
                    model_matches.extend(matches)
                    analysis['ai_score'] += len(matches) * 5
            if model_matches:
                analysis['pattern_matches']['llm_specific'][llm_model] = model_matches
                analysis['llm_model_prediction'] = llm_model
        total_patterns = len(analysis['pattern_matches']['ai_indicators']) + len(analysis['pattern_matches']['human_indicators'])
        if total_patterns > 0:
            analysis['ai_score'] = min(100, (analysis['ai_score'] / total_patterns) * 70)
            analysis['human_score'] = min(100, (analysis['human_score'] / total_patterns) * 50)
        analysis['highlighted_html'] = self._build_highlighted_html(code, analysis['match_spans'])
        return analysis

    def _build_highlighted_html(self, code: str, spans: Dict[str, List[tuple]]) -> str:
        # Merge spans and mark kinds; resolve overlaps preferring AI over Human
        markers: List[tuple] = []
        for s, e in spans.get('ai_indicators', []):
            markers.append((s, e, 'ai'))
        for s, e in spans.get('human_indicators', []):
            markers.append((s, e, 'human'))
        if not markers:
            return f"<pre class=\"code-block\">{self._escape_html(code)}</pre>"
        markers.sort(key=lambda x: (x[0], -(x[1]-x[0])))
        merged: List[tuple] = []
        for s, e, kind in markers:
            if not merged:
                merged.append((s, e, kind)); continue
            ps, pe, pk = merged[-1]
            if s <= pe:
                # overlap: prefer AI, extend end
                if kind == 'ai' and pk != 'ai':
                    pk = 'ai'
                merged[-1] = (ps, max(pe, e), pk)
            else:
                merged.append((s, e, kind))
        out: List[str] = []
        cur = 0
        for s, e, kind in merged:
            if cur < s:
                out.append(self._escape_html(code[cur:s]))
            css = 'hl-ai' if kind == 'ai' else 'hl-human'
            out.append(f"<mark class=\"{css}\">{self._escape_html(code[s:e])}</mark>")
            cur = e
        if cur < len(code):
            out.append(self._escape_html(code[cur:]))
        return f"<pre class=\"code-block\">{''.join(out)}</pre>"

    def _escape_html(self, text: str) -> str:
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;'))
    
    def _calculate_code_metrics(self, code: str) -> Dict[str, Any]:
        lines = code.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        comment_lines = [line for line in lines if line.strip().startswith('#')]
        return {
            'total_lines': len(lines),
            'non_empty_lines': len(non_empty_lines),
            'comment_lines': len(comment_lines),
            'comment_ratio': len(comment_lines) / len(non_empty_lines) if non_empty_lines else 0,
            'avg_line_length': sum(len(line) for line in non_empty_lines) / len(non_empty_lines) if non_empty_lines else 0,
            'function_count': len(re.findall(r'\bdef\s+\w+\s*\(', code)),
            'class_count': len(re.findall(r'\bclass\s+\w+\s*\(', code)),
            'import_count': len(re.findall(r'\bimport\s+\w+', code)),
            'complexity_score': self._calculate_complexity_score(code),
        }
    
    def _calculate_complexity_score(self, code: str) -> float:
        complexity_indicators = [r'\bif\s+', r'\bfor\s+', r'\bwhile\s+', r'\btry\s*:', r'\bexcept\s+', r'\bdef\s+', r'\bclass\s+', r'\blambda\s+', r'\bwith\s+']
        total_complexity = 0
        for pattern in complexity_indicators:
            total_complexity += len(re.findall(pattern, code))
        return total_complexity
    
    def _combine_predictions(self, basic_result: Dict, deep_result: Dict, enhanced_result: Dict) -> Dict[str, Any]:
        predictions: List[float] = []
        weights: List[float] = []
        if basic_result and 'score' in basic_result:
            predictions.append(basic_result['score']); weights.append(0.3)
        if deep_result and 'score' in deep_result:
            predictions.append(deep_result['score']); weights.append(0.4)
        if enhanced_result and 'ai_score' in enhanced_result:
            predictions.append(enhanced_result['ai_score']); weights.append(0.3)
        final_score = sum(p * w for p, w in zip(predictions, weights)) / sum(weights) if predictions else 50.0
        if final_score > 60: final_label = 'AI-generated'
        elif final_score < 40: final_label = 'Human-written'
        else: final_label = 'Uncertain'
        return {
            'label': final_label,
            'score': final_score,
            'confidence': abs(final_score - 50) / 50,
            'method_breakdown': {
                'basic': basic_result.get('score', 0) if basic_result else 0,
                'deep_learning': deep_result.get('score', 0) if deep_result else 0,
                'enhanced': enhanced_result.get('ai_score', 0) if enhanced_result else 0,
            },
        }
    
    def validate_with_dataset(self, num_samples: int = 100) -> Dict[str, Any]:
        self.load_dataset()
        samples = []
        if self.has_python2:
            samples = self.dataset_loader.get_sample_codes(num_samples, 'python2')
        if not samples:
            samples = self.dataset_loader.get_sample_codes(num_samples, 'mixed')
        correct_predictions = 0
        results: List[Dict[str, Any]] = []
        for sample in samples:
            result = self.analyze_code_enhanced(sample['code'])
            predicted_label = result['final_prediction']['label']
            true_label = sample['label']
            is_correct = (predicted_label == true_label)
            if is_correct: correct_predictions += 1
            results.append({'id': sample['id'], 'true_label': true_label, 'predicted_label': predicted_label, 'score': result['final_prediction']['score'], 'is_correct': is_correct})
        total = len(samples)
        accuracy = (correct_predictions / total) if total else 0
        return {'total_samples': total, 'correct_predictions': correct_predictions, 'accuracy': accuracy, 'results': results}


def analyze_code_with_enhanced_dataset(code: str, language: str = 'auto') -> Dict[str, Any]:
    detector = EnhancedCodeDetector()
    return detector.analyze_code_enhanced(code, language)


if __name__ == "__main__":
    detector = EnhancedCodeDetector()
    sample_code = "def add(a, b):\n    return a + b\n"
    print(detector.analyze_code_enhanced(sample_code)['final_prediction'])
