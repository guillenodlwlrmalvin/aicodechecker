import numpy as np
import re
import ast
from typing import Dict, List, Tuple, Any, Optional
from collections import Counter, defaultdict
import math

class EnhancedDeepLearningCodeDetector:
    """
    Enhanced Deep Learning-based code analysis for detecting AI-generated vs human-written code.
    Features improved pattern recognition, ensemble methods, and contextual analysis.
    """
    
    def __init__(self):
        # Refined feature weights with better balance
        self.feature_weights = {
            'comment_patterns': 0.14,
            'naming_conventions': 0.11,
            'code_structure': 0.16,
            'complexity_metrics': 0.18,
            'style_consistency': 0.13,
            'repetition_patterns': 0.09,
            'documentation_style': 0.08,
            'error_handling': 0.06,
            'code_idioms': 0.05
        }
        
        # Adjusted thresholds based on uncertainty zones
        self.thresholds = {
            'ai_likely': 0.70,
            'human_likely': 0.30,
            'uncertain': 0.50
        }
        
        # AI-specific patterns (common in generated code)
        self.ai_patterns = {
            'verbose_comments': r'#\s*[A-Z][^#]*(?:function|method|class|variable|parameter)',
            'generic_names': r'\b(data|result|temp|value|item|element|obj|var)\d*\b',
            'perfect_spacing': r'[=+\-*/](?:\s[=+\-*/]){2,}',
            'docstring_template': r'"""[\s\S]*?(?:Args?|Returns?|Raises?|Examples?)[\s\S]*?"""',
            'type_hints_everywhere': r':\s*(?:str|int|float|bool|List|Dict|Optional|Any)\b'
        }
        
        # Human-specific patterns (common quirks)
        self.human_patterns = {
            'casual_comments': r'#\s*(?:TODO|FIXME|HACK|NOTE|XXX)',
            'inconsistent_spacing': r'[=+\-*/](?:\s{2,}|\s{0})',
            'quick_variable_names': r'\b[a-z]{1,2}\d*\b',
            'debug_prints': r'\b(?:print|console\.log|System\.out)',
            'personal_notes': r'#.*(?:remember|later|check|review)'
        }
    
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
    
    def _detect_language(self, code: str) -> str:
        """Detect programming language from code patterns."""
        scores = {
            'python': 0,
            'javascript': 0,
            'java': 0,
            'cpp': 0,
            'generic': 0
        }
        
        if 'def ' in code or 'import ' in code or 'self.' in code:
            scores['python'] += 3
        if 'function ' in code or 'const ' in code or '=>' in code:
            scores['javascript'] += 3
        if 'public class' in code or 'void main' in code:
            scores['java'] += 3
        if '#include' in code or 'std::' in code:
            scores['cpp'] += 3
        
        detected = max(scores.items(), key=lambda x: x[1])
        return detected[0] if detected[1] > 0 else 'generic'
    
    def _analyze_comment_patterns(self, code: str) -> Dict[str, float]:
        """Enhanced comment analysis with AI signature detection."""
        lines = code.split('\n')
        comment_lines = [line for line in lines if self._is_comment(line)]
        
        features = {}
        
        # Basic metrics
        features['comment_density'] = len(comment_lines) / max(len(lines), 1)
        
        if comment_lines:
            lengths = [len(line.strip()) for line in comment_lines]
            features['avg_comment_length'] = np.mean(lengths)
            features['comment_length_variance'] = np.var(lengths)
            features['comment_length_std'] = np.std(lengths)
            
            # AI signature: overly descriptive comments
            descriptive_count = sum(1 for line in comment_lines 
                                   if len(line.strip()) > 60 and 
                                   any(word in line.lower() for word in ['function', 'method', 'parameter', 'return']))
            features['descriptive_comment_ratio'] = descriptive_count / len(comment_lines)
            
            # Check for perfect comment formatting (AI tendency)
            perfect_format = sum(1 for line in comment_lines 
                               if re.match(r'^\s*#\s+[A-Z].*[.!]$', line))
            features['perfect_format_ratio'] = perfect_format / len(comment_lines)
            
            # Comment above every function (AI pattern)
            func_pattern = r'^\s*def\s+\w+|^\s*function\s+\w+|^\s*public\s+\w+\s+\w+'
            functions = [i for i, line in enumerate(lines) if re.search(func_pattern, line)]
            comments_above_funcs = sum(1 for i in functions 
                                      if i > 0 and self._is_comment(lines[i-1]))
            features['comment_before_func_ratio'] = (comments_above_funcs / len(functions) 
                                                     if functions else 0)
        else:
            features.update({
                'avg_comment_length': 0,
                'comment_length_variance': 0,
                'comment_length_std': 0,
                'descriptive_comment_ratio': 0,
                'perfect_format_ratio': 0,
                'comment_before_func_ratio': 0
            })
        
        # Style consistency entropy
        comment_styles = []
        for line in comment_lines:
            if line.strip().startswith('#'):
                comment_styles.append('hash')
            elif '//' in line:
                comment_styles.append('double_slash')
            elif '/*' in line or '*/' in line:
                comment_styles.append('block')
        
        features['comment_style_entropy'] = self._calculate_entropy(Counter(comment_styles))
        
        return features
    
    def _is_comment(self, line: str) -> bool:
        """Check if a line is a comment."""
        stripped = line.strip()
        return (stripped.startswith('#') or 
                stripped.startswith('//') or 
                stripped.startswith('/*') or 
                stripped.startswith('*'))
    
    def _analyze_naming_conventions(self, code: str) -> Dict[str, float]:
        """Enhanced naming analysis with pattern detection."""
        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code)
        
        features = {}
        
        if not identifiers:
            return self._empty_naming_features()
        
        # Style ratios
        camel_case = sum(1 for id in identifiers if re.match(r'^[a-z][a-zA-Z0-9]*[A-Z]', id))
        snake_case = sum(1 for id in identifiers if '_' in id and id.islower())
        screaming_case = sum(1 for id in identifiers if id.isupper() and len(id) > 1)
        single_char = sum(1 for id in identifiers if len(id) == 1)
        
        total = len(identifiers)
        features['camel_case_ratio'] = camel_case / total
        features['snake_case_ratio'] = snake_case / total
        features['screaming_case_ratio'] = screaming_case / total
        features['single_char_ratio'] = single_char / total
        
        # Generic names (AI tendency)
        generic_names = ['data', 'result', 'temp', 'value', 'item', 'element', 
                        'obj', 'var', 'output', 'input']
        generic_count = sum(1 for id in identifiers 
                           if id.lower() in generic_names or 
                           re.match(r'(data|result|temp|value)\d+', id.lower()))
        features['generic_name_ratio'] = generic_count / total
        
        # Name length distribution
        lengths = [len(id) for id in identifiers]
        features['avg_name_length'] = np.mean(lengths)
        features['name_length_std'] = np.std(lengths)
        
        # Very descriptive names (AI pattern)
        long_descriptive = sum(1 for id in identifiers if len(id) > 20)
        features['long_descriptive_ratio'] = long_descriptive / total
        
        # Naming entropy
        features['naming_entropy'] = self._calculate_entropy(Counter(identifiers))
        
        # Consistency score
        style_scores = [
            features['camel_case_ratio'],
            features['snake_case_ratio'],
            features['screaming_case_ratio']
        ]
        features['naming_consistency'] = max(style_scores)
        
        return features
    
    def _empty_naming_features(self) -> Dict[str, float]:
        """Return empty feature dict for naming."""
        return {
            'camel_case_ratio': 0, 'snake_case_ratio': 0,
            'screaming_case_ratio': 0, 'single_char_ratio': 0,
            'generic_name_ratio': 0, 'avg_name_length': 0,
            'name_length_std': 0, 'long_descriptive_ratio': 0,
            'naming_entropy': 0, 'naming_consistency': 0
        }
    
    def _analyze_code_structure(self, code: str, language: str) -> Dict[str, float]:
        """Enhanced structure analysis with organizational patterns."""
        features = {}
        
        try:
            if language == 'python':
                tree = ast.parse(code)
                features['function_count'] = len([n for n in ast.walk(tree) 
                                                  if isinstance(n, ast.FunctionDef)])
                features['class_count'] = len([n for n in ast.walk(tree) 
                                              if isinstance(n, ast.ClassDef)])
                features['import_count'] = len([n for n in ast.walk(tree) 
                                               if isinstance(n, (ast.Import, ast.ImportFrom))])
                features['max_nesting_depth'] = self._calculate_nesting_depth(tree)
                
                # Function length variance (humans vary more)
                func_lengths = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        func_lengths.append(len(ast.unparse(node).split('\n')))
                features['func_length_variance'] = np.var(func_lengths) if func_lengths else 0
                
            else:
                features['function_count'] = len(re.findall(
                    r'\b(def|function|func|method)\s+\w+', code, re.IGNORECASE))
                features['class_count'] = len(re.findall(
                    r'\b(class|struct|interface)\s+\w+', code, re.IGNORECASE))
                features['import_count'] = len(re.findall(
                    r'\b(import|using|include|require)\b', code, re.IGNORECASE))
                features['max_nesting_depth'] = self._estimate_nesting_depth(code)
                features['func_length_variance'] = 0
        
        except:
            features = {
                'function_count': 0, 'class_count': 0, 'import_count': 0,
                'max_nesting_depth': 0, 'func_length_variance': 0
            }
        
        # Organizational patterns
        lines = code.split('\n')
        features['blank_line_clustering'] = self._analyze_blank_line_patterns(lines)
        features['code_section_count'] = self._count_code_sections(lines)
        
        # Structure complexity
        features['structure_complexity'] = (
            features['function_count'] * 0.25 +
            features['class_count'] * 0.35 +
            features['import_count'] * 0.15 +
            features['max_nesting_depth'] * 0.15 +
            features['func_length_variance'] * 0.10
        )
        
        return features
    
    def _analyze_blank_line_patterns(self, lines: List[str]) -> float:
        """Analyze how blank lines are distributed (AI tends to be more regular)."""
        blank_positions = [i for i, line in enumerate(lines) if not line.strip()]
        if len(blank_positions) < 2:
            return 0
        
        gaps = [blank_positions[i+1] - blank_positions[i] 
                for i in range(len(blank_positions)-1)]
        return np.std(gaps) if gaps else 0
    
    def _count_code_sections(self, lines: List[str]) -> int:
        """Count distinct code sections separated by blank lines."""
        sections = 0
        in_section = False
        
        for line in lines:
            if line.strip():
                if not in_section:
                    sections += 1
                    in_section = True
            else:
                in_section = False
        
        return sections
    
    def _analyze_complexity_metrics(self, code: str) -> Dict[str, float]:
        """Enhanced complexity analysis."""
        features = {}
        
        lines = code.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        # Cyclomatic complexity
        complexity_keywords = ['if', 'elif', 'else', 'for', 'while', 
                              'and', 'or', 'except', 'case', 'switch']
        features['cyclomatic_complexity'] = sum(
            code.lower().count(kw) for kw in complexity_keywords)
        
        # Lines of code
        features['total_lines'] = len(lines)
        features['code_lines'] = len(non_empty_lines)
        features['blank_line_ratio'] = (len(lines) - len(non_empty_lines)) / max(len(lines), 1)
        
        # Line length metrics
        if non_empty_lines:
            lengths = [len(line) for line in non_empty_lines]
            features['avg_line_length'] = np.mean(lengths)
            features['max_line_length'] = max(lengths)
            features['line_length_std'] = np.std(lengths)
            
            # AI tends to have more consistent line lengths
            features['line_length_consistency'] = 1 / (1 + features['line_length_std'] / 10)
        else:
            features['avg_line_length'] = 0
            features['max_line_length'] = 0
            features['line_length_std'] = 0
            features['line_length_consistency'] = 0
        
        # Token analysis
        tokens = re.findall(r'\b\w+\b', code)
        features['token_count'] = len(tokens)
        features['unique_token_ratio'] = len(set(tokens)) / max(len(tokens), 1)
        
        # Operator density
        operators = len(re.findall(r'[+\-*/%=<>!&|^~]', code))
        features['operator_density'] = operators / max(len(code), 1)
        
        return features
    
    def _analyze_style_consistency(self, code: str) -> Dict[str, float]:
        """Enhanced style analysis with AI pattern detection."""
        features = {}
        
        lines = [line for line in code.split('\n') if line.strip()]
        if not lines:
            return {'indentation_consistency': 0, 'spacing_consistency': 0, 
                   'style_entropy': 0, 'perfect_style_ratio': 0}
        
        # Indentation analysis
        indents = [len(line) - len(line.lstrip()) for line in lines]
        indent_counter = Counter(indents)
        features['indentation_consistency'] = max(indent_counter.values()) / len(indents)
        
        # Check for perfect 4-space or 2-space indentation (AI pattern)
        indent_steps = [indents[i+1] - indents[i] 
                       for i in range(len(indents)-1) if indents[i+1] != indents[i]]
        if indent_steps:
            perfect_steps = sum(1 for step in indent_steps if abs(step) in [2, 4])
            features['perfect_indent_ratio'] = perfect_steps / len(indent_steps)
        else:
            features['perfect_indent_ratio'] = 0
        
        # Spacing around operators
        spaces_before = len(re.findall(r'\s[+\-*/=<>!]', code))
        spaces_after = len(re.findall(r'[+\-*/=<>!]\s', code))
        spaces_both = len(re.findall(r'\s[+\-*/=<>!]\s', code))
        total_ops = len(re.findall(r'[+\-*/=<>!]', code))
        
        features['spacing_consistency'] = spaces_both / max(total_ops, 1)
        
        # Perfect style (AI tendency)
        features['perfect_style_ratio'] = (features['perfect_indent_ratio'] + 
                                          features['spacing_consistency']) / 2
        
        # Style entropy
        style_patterns = []
        for line in lines:
            indent = len(line) - len(line.lstrip())
            spaces = len(re.findall(r'\s+', line))
            style_patterns.append(f"i{indent}_s{spaces}")
        
        features['style_entropy'] = self._calculate_entropy(Counter(style_patterns))
        
        return features
    
    def _analyze_repetition_patterns(self, code: str) -> Dict[str, float]:
        """Enhanced repetition analysis."""
        features = {}
        
        # Function call patterns
        func_calls = re.findall(r'\b\w+\s*\(', code)
        features['function_call_entropy'] = self._calculate_entropy(Counter(func_calls))
        features['function_call_diversity'] = len(set(func_calls)) / max(len(func_calls), 1)
        
        # Variable usage
        variables = re.findall(r'\b\w+\s*=', code)
        features['variable_usage_entropy'] = self._calculate_entropy(Counter(variables))
        
        # Line similarity (AI tends to have more similar lines)
        lines = [line.strip() for line in code.split('\n') if line.strip()]
        if len(lines) > 1:
            similar_pairs = sum(1 for i in range(len(lines)-1) 
                               if self._similarity(lines[i], lines[i+1]) > 0.7)
            features['line_similarity_ratio'] = similar_pairs / (len(lines) - 1)
        else:
            features['line_similarity_ratio'] = 0
        
        # Pattern repetition
        patterns = re.findall(r'\b\w+\s*\(\s*\w+\s*\)', code)
        features['pattern_repetition'] = len(patterns) - len(set(patterns))
        
        features['repetition_score'] = (
            features['function_call_entropy'] * 0.3 +
            features['variable_usage_entropy'] * 0.3 +
            features['line_similarity_ratio'] * 0.4
        )
        
        return features
    
    def _similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity between two strings."""
        if not s1 or not s2:
            return 0
        
        set1, set2 = set(s1.split()), set(s2.split())
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / max(union, 1)
    
    def _analyze_documentation_style(self, code: str) -> Dict[str, float]:
        """Enhanced documentation analysis."""
        features = {}
        
        # Docstring analysis
        docstrings = re.findall(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', code)
        features['docstring_count'] = len(docstrings)
        
        if docstrings:
            lengths = [len(ds) for ds in docstrings]
            features['avg_docstring_length'] = np.mean(lengths)
            features['docstring_length_variance'] = np.var(lengths)
            
            # Check for template-style docstrings (AI pattern)
            template_keywords = ['Args:', 'Returns:', 'Raises:', 'Examples:', 
                               'Parameters:', 'Note:']
            template_count = sum(1 for ds in docstrings 
                                if any(kw in ds for kw in template_keywords))
            features['template_docstring_ratio'] = template_count / len(docstrings)
        else:
            features['avg_docstring_length'] = 0
            features['docstring_length_variance'] = 0
            features['template_docstring_ratio'] = 0
        
        # Inline documentation
        inline_docs = len(re.findall(r'#.*$', code, re.MULTILINE))
        features['inline_doc_ratio'] = inline_docs / max(len(code.split('\n')), 1)
        
        # Documentation consistency
        features['doc_consistency'] = (
            min(features['docstring_count'] * 0.1, 1) * 0.6 +
            min(features['inline_doc_ratio'] * 10, 1) * 0.4
        )
        
        return features
    
    def _analyze_error_handling(self, code: str, language: str) -> Dict[str, float]:
        """Analyze error handling patterns (new feature)."""
        features = {}
        
        # Exception handling
        if language == 'python':
            try_blocks = len(re.findall(r'\btry\s*:', code))
            except_blocks = len(re.findall(r'\bexcept\b', code))
            finally_blocks = len(re.findall(r'\bfinally\s*:', code))
        else:
            try_blocks = len(re.findall(r'\btry\s*\{', code))
            except_blocks = len(re.findall(r'\bcatch\s*\(', code))
            finally_blocks = len(re.findall(r'\bfinally\s*\{', code))
        
        features['try_count'] = try_blocks
        features['except_count'] = except_blocks
        features['finally_count'] = finally_blocks
        
        # Proper error handling ratio (AI tends to be more thorough)
        if try_blocks > 0:
            features['proper_handling_ratio'] = (except_blocks + finally_blocks) / (try_blocks * 2)
        else:
            features['proper_handling_ratio'] = 0
        
        # Generic exception catching (AI pattern)
        generic_catches = len(re.findall(r'except\s*:|catch\s*\(\s*\w*Exception', code))
        features['generic_exception_ratio'] = (generic_catches / max(except_blocks, 1) 
                                              if except_blocks > 0 else 0)
        
        return features
    
    def _analyze_code_idioms(self, code: str, language: str) -> Dict[str, float]:
        """Analyze language-specific idioms and patterns (new feature)."""
        features = {}
        
        if language == 'python':
            # Pythonic patterns (humans often use these)
            features['list_comprehension'] = len(re.findall(r'\[.+for\s+\w+\s+in\s+', code))
            features['enumerate_usage'] = code.count('enumerate(')
            features['zip_usage'] = code.count('zip(')
            features['with_statement'] = len(re.findall(r'\bwith\s+', code))
            
            # AI patterns
            features['explicit_range'] = len(re.findall(r'range\(len\(', code))
            features['index_iteration'] = len(re.findall(r'for\s+\w+\s+in\s+range\(len\(', code))
        else:
            features['list_comprehension'] = 0
            features['enumerate_usage'] = 0
            features['zip_usage'] = 0
            features['with_statement'] = 0
            features['explicit_range'] = 0
            features['index_iteration'] = 0
        
        # Calculate idiom score
        pythonic_score = (features['list_comprehension'] + features['enumerate_usage'] + 
                         features['zip_usage'] + features['with_statement'])
        non_pythonic_score = features['explicit_range'] + features['index_iteration']
        
        total_patterns = pythonic_score + non_pythonic_score
        features['idiom_score'] = (pythonic_score - non_pythonic_score) / max(total_patterns, 1)
        
        return features
    
    def _calculate_entropy(self, counter: Counter) -> float:
        """Calculate Shannon entropy."""
        if not counter:
            return 0
        
        total = sum(counter.values())
        if total == 0:
            return 0
        
        entropy = 0
        for count in counter.values():
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)
        
        return entropy
    
    def _calculate_nesting_depth(self, tree: ast.AST) -> int:
        """Calculate maximum nesting depth."""
        def get_depth(node, current=0):
            max_depth = current
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
                    max_depth = max(max_depth, get_depth(child, current + 1))
                else:
                    max_depth = max(max_depth, get_depth(child, current))
            return max_depth
        
        return get_depth(tree)
    
    def _estimate_nesting_depth(self, code: str) -> int:
        """Estimate nesting depth for non-Python code."""
        max_depth = 0
        current = 0
        
        for char in code:
            if char in '{(':
                current += 1
                max_depth = max(max_depth, current)
            elif char in '})':
                current = max(0, current - 1)
        
        return max_depth
    
    def analyze_code(self, code: str, language: str = 'auto') -> Dict[str, Any]:
        """Main analysis with ensemble approach."""
        # Extract features
        features = self.extract_deep_features(code, language)
        
        # Calculate category scores
        category_scores = {}
        for category, weight in self.feature_weights.items():
            if category in features:
                score = self._calculate_category_score(features[category])
                category_scores[category] = score * weight
        
        # Ensemble scoring
        weighted_score = sum(category_scores.values())
        pattern_score = self._calculate_pattern_score(code)
        
        # Combine scores with ensemble weighting
        ai_likelihood = 0.7 * weighted_score + 0.3 * pattern_score
        ai_likelihood = max(0, min(ai_likelihood, 1))
        
        # Classification
        if ai_likelihood > self.thresholds['ai_likely']:
            label = 'AI-generated'
        elif ai_likelihood < self.thresholds['human_likely']:
            label = 'Human-written'
        else:
            label = 'Uncertain'
        
        # Generate explanation
        explanation = self._generate_explanation(features, category_scores, 
                                                pattern_score, ai_likelihood)
        
        return {
            'label': label,
            'score': ai_likelihood * 100,
            'confidence': self._calculate_confidence(features, ai_likelihood),
            'features': features,
            'category_scores': category_scores,
            'pattern_score': pattern_score * 100,
            'explanation': explanation,
            'top_indicators': self._get_top_indicators(category_scores)
        }
    
    def _calculate_pattern_score(self, code: str) -> float:
        """Calculate score based on AI vs human patterns."""
        ai_score = 0
        human_score = 0
        
        # Check AI patterns
        for pattern_name, pattern in self.ai_patterns.items():
            matches = len(re.findall(pattern, code))
            ai_score += matches * 0.1
        
        # Check human patterns
        for pattern_name, pattern in self.human_patterns.items():
            matches = len(re.findall(pattern, code))
            human_score += matches * 0.1
        
        # Normalize
        total = ai_score + human_score
        if total == 0:
            return 0.5
        
        return ai_score / total
    
    def _calculate_category_score(self, category_features: Dict[str, float]) -> float:
        """Calculate normalized category score."""
        if not category_features:
            return 0.5
        
        scores = []
        for name, value in category_features.items():
            normalized = self._normalize_feature(name, value)
            scores.append(normalized)
        
        return np.mean(scores) if scores else 0.5
    
    def _normalize_feature(self, name: str, value: float) -> float:
        """Normalize feature to 0-1 range."""
        if math.isnan(value) or math.isinf(value):
            return 0.5
        
        if 'entropy' in name:
            return min(value / 5.0, 1.0)
        elif 'ratio' in name or 'consistency' in name:
            return max(0, min(value, 1))
        elif 'count' in name:
            return min(math.log2(value + 1) / 8.0, 1.0)
        elif 'length' in name:
            return min(value / 80.0, 1.0)
        elif 'complexity' in name or 'depth' in name:
            return min(value / 15.0, 1.0)
        elif 'variance' in name or 'std' in name:
            return min(value / 50.0, 1.0)
        else:
            return max(0, min(value, 1.0))
    
    def _generate_explanation(self, features: Dict[str, Any], 
                            category_scores: Dict[str, float],
                            pattern_score: float, 
                            ai_likelihood: float) -> List[str]:
        """Generate detailed explanation."""
        explanation = []
        
        # Top contributing categories
        sorted_categories = sorted(category_scores.items(), 
                                  key=lambda x: x[1], reverse=True)
        
        if sorted_categories:
            top_cat, top_score = sorted_categories[0]
            explanation.append(
                f"Primary indicator: {top_cat.replace('_', ' ').title()} "
                f"(weighted score: {top_score:.3f})"
            )
        
        # Specific feature insights
        if 'comment_patterns' in features:
            cp = features['comment_patterns']
            if cp.get('descriptive_comment_ratio', 0) > 0.5:
                explanation.append(
                    "High ratio of descriptive comments typical of AI-generated code"
                )
            if cp.get('comment_before_func_ratio', 0) > 0.8:
                explanation.append(
                    "Nearly every function has a comment above it (AI pattern)"
                )
        
        if 'naming_conventions' in features:
            nc = features['naming_conventions']
            if nc.get('generic_name_ratio', 0) > 0.3:
                explanation.append(
                    "High usage of generic variable names (data, result, temp)"
                )
            if nc.get('long_descriptive_ratio', 0) > 0.2:
                explanation.append(
                    "Unusually long descriptive names detected"
                )
        
        if 'style_consistency' in features:
            sc = features['style_consistency']
            if sc.get('perfect_style_ratio', 0) > 0.85:
                explanation.append(
                    "Perfect style consistency suggests automated generation"
                )
            elif sc.get('perfect_style_ratio', 0) < 0.4:
                explanation.append(
                    "Inconsistent styling suggests human authorship"
                )
        
        if 'error_handling' in features:
            eh = features['error_handling']
            if eh.get('proper_handling_ratio', 0) > 0.9:
                explanation.append(
                    "Comprehensive error handling (common in AI code)"
                )
            if eh.get('generic_exception_ratio', 0) > 0.7:
                explanation.append(
                    "Excessive use of generic exception catching"
                )
        
        if 'code_idioms' in features:
            ci = features['code_idioms']
            if ci.get('idiom_score', 0) > 0.5:
                explanation.append(
                    "Good use of language idioms suggests human expertise"
                )
            elif ci.get('index_iteration', 0) > 3:
                explanation.append(
                    "Non-idiomatic iteration patterns (AI tendency)"
                )
        
        # Pattern analysis
        if pattern_score > 0.7:
            explanation.append(
                f"Strong AI signature patterns detected (score: {pattern_score:.2f})"
            )
        elif pattern_score < 0.3:
            explanation.append(
                f"Human coding quirks identified (score: {pattern_score:.2f})"
            )
        
        # Overall assessment
        if ai_likelihood > 0.85:
            explanation.append(
                "Multiple strong indicators converge on AI generation"
            )
        elif ai_likelihood < 0.15:
            explanation.append(
                "Clear human patterns with characteristic inconsistencies"
            )
        elif 0.4 <= ai_likelihood <= 0.6:
            explanation.append(
                "Mixed signals - could be human with AI assistance or well-edited AI code"
            )
        
        return explanation
    
    def _calculate_confidence(self, features: Dict[str, Any], 
                            ai_likelihood: float) -> float:
        """Calculate prediction confidence."""
        # Feature completeness
        total_features = 0
        valid_features = 0
        
        for category_features in features.values():
            if isinstance(category_features, dict):
                for value in category_features.values():
                    total_features += 1
                    if isinstance(value, (int, float)) and not math.isnan(value):
                        valid_features += 1
        
        feature_confidence = valid_features / max(total_features, 1)
        
        # Prediction strength (distance from uncertain threshold)
        prediction_strength = abs(ai_likelihood - 0.5) * 2
        
        # Agreement across categories
        category_agreement = self._calculate_category_agreement(features)
        
        # Combined confidence
        confidence = (
            feature_confidence * 0.3 +
            prediction_strength * 0.4 +
            category_agreement * 0.3
        )
        
        return max(0, min(confidence, 1))
    
    def _calculate_category_agreement(self, features: Dict[str, Any]) -> float:
        """Calculate how much categories agree on the prediction."""
        scores = []
        
        for category_features in features.values():
            if isinstance(category_features, dict):
                category_score = self._calculate_category_score(category_features)
                scores.append(category_score)
        
        if len(scores) < 2:
            return 0.5
        
        # Calculate variance - lower variance = higher agreement
        variance = np.var(scores)
        agreement = 1 / (1 + variance)
        
        return agreement
    
    def _get_top_indicators(self, category_scores: Dict[str, float], 
                          top_n: int = 3) -> List[Tuple[str, float]]:
        """Get top N contributing indicators."""
        sorted_scores = sorted(category_scores.items(), 
                             key=lambda x: x[1], reverse=True)
        return [(name.replace('_', ' ').title(), score) 
                for name, score in sorted_scores[:top_n]]
    
    def batch_analyze(self, code_samples: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
        """
        Analyze multiple code samples.
        
        Args:
            code_samples: List of (code, language) tuples
        
        Returns:
            List of analysis results
        """
        results = []
        for code, language in code_samples:
            result = self.analyze_code(code, language)
            results.append(result)
        return results
    
    def compare_codes(self, code1: str, code2: str, 
                     language: str = 'auto') -> Dict[str, Any]:
        """
        Compare two code samples and determine which is more likely AI-generated.
        
        Args:
            code1: First code sample
            code2: Second code sample
            language: Programming language
        
        Returns:
            Comparison results
        """
        result1 = self.analyze_code(code1, language)
        result2 = self.analyze_code(code2, language)
        
        return {
            'code1': {
                'label': result1['label'],
                'score': result1['score'],
                'confidence': result1['confidence']
            },
            'code2': {
                'label': result2['label'],
                'score': result2['score'],
                'confidence': result2['confidence']
            },
            'comparison': {
                'more_likely_ai': 'code1' if result1['score'] > result2['score'] else 'code2',
                'score_difference': abs(result1['score'] - result2['score']),
                'confidence_difference': abs(result1['confidence'] - result2['confidence'])
            }
        }


# Backward compatibility wrapper
def analyze_code_deep_learning(code: str, language: str = 'auto') -> Dict[str, Any]:
    """
    Backward compatible function name for existing imports.
    
    Args:
        code: The code string to analyze
        language: Programming language (default: 'auto')
    
    Returns:
        Dictionary containing analysis results
    """
    detector = EnhancedDeepLearningCodeDetector()
    return detector.analyze_code(code, language)


# Convenience functions
def analyze_code_enhanced(code: str, language: str = 'auto') -> Dict[str, Any]:
    """
    Convenience function for enhanced code analysis.
    
    Args:
        code: The code string to analyze
        language: Programming language (default: 'auto')
    
    Returns:
        Dictionary containing detailed analysis results
    """
    detector = EnhancedDeepLearningCodeDetector()
    return detector.analyze_code(code, language)


def quick_check(code: str) -> str:
    """
    Quick check that returns simple label.
    
    Args:
        code: The code string to analyze
    
    Returns:
        Simple label: 'AI-generated', 'Human-written', or 'Uncertain'
    """
    detector = EnhancedDeepLearningCodeDetector()
    result = detector.analyze_code(code)
    return result['label']


def detailed_report(code: str, language: str = 'auto') -> str:
    """
    Generate a detailed human-readable report.
    
    Args:
        code: The code string to analyze
        language: Programming language
    
    Returns:
        Formatted report string
    """
    detector = EnhancedDeepLearningCodeDetector()
    result = detector.analyze_code(code, language)
    
    report = []
    report.append("=" * 60)
    report.append("CODE ANALYSIS REPORT")
    report.append("=" * 60)
    report.append(f"\nClassification: {result['label']}")
    report.append(f"AI Likelihood Score: {result['score']:.2f}%")
    report.append(f"Confidence Level: {result['confidence']*100:.2f}%")
    
    report.append("\n" + "-" * 60)
    report.append("TOP INDICATORS:")
    report.append("-" * 60)
    for indicator, score in result['top_indicators']:
        report.append(f"  • {indicator}: {score:.3f}")
    
    report.append("\n" + "-" * 60)
    report.append("DETAILED EXPLANATION:")
    report.append("-" * 60)
    for i, explanation in enumerate(result['explanation'], 1):
        report.append(f"  {i}. {explanation}")
    
    report.append("\n" + "-" * 60)
    report.append("FEATURE BREAKDOWN:")
    report.append("-" * 60)
    for category, score in result['category_scores'].items():
        report.append(f"  • {category.replace('_', ' ').title()}: {score:.3f}")
    
    report.append("\n" + "=" * 60)
    
    return "\n".join(report)


# Example usage
if __name__ == "__main__":
    sample_code = '''
def calculate_fibonacci(n: int) -> int:
    """
    Calculate the nth Fibonacci number.
    
    Args:
        n: The position in the Fibonacci sequence
    
    Returns:
        The nth Fibonacci number
    """
    if n <= 1:
        return n
    return calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2)
'''
    
    print(detailed_report(sample_code, 'python'))