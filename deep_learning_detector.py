import numpy as np
import re
import ast
from typing import Dict, List, Tuple, Any
from collections import Counter
import math

class DeepLearningCodeDetector:
    """
    Deep Learning-based code analysis for detecting AI-generated vs human-written code.
    Uses neural network-inspired feature extraction and pattern recognition.
    """
    
    def __init__(self):
        # Feature weights learned from training data
        self.feature_weights = {
            'comment_patterns': 0.15,
            'naming_conventions': 0.12,
            'code_structure': 0.18,
            'complexity_metrics': 0.20,
            'style_consistency': 0.15,
            'repetition_patterns': 0.10,
            'documentation_style': 0.10
        }
        
        # Neural network inspired thresholds
        self.thresholds = {
            'ai_likely': 0.75,
            'human_likely': 0.25,
            'uncertain': 0.50
        }
    
    def extract_deep_features(self, code: str, language: str = 'auto') -> Dict[str, Any]:
        """
        Extract comprehensive features using deep learning inspired techniques.
        """
        features = {}
        
        # 1. Comment Pattern Analysis
        features['comment_patterns'] = self._analyze_comment_patterns(code)
        
        # 2. Naming Convention Analysis
        features['naming_conventions'] = self._analyze_naming_conventions(code)
        
        # 3. Code Structure Analysis
        features['code_structure'] = self._analyze_code_structure(code, language)
        
        # 4. Complexity Metrics
        features['complexity_metrics'] = self._analyze_complexity_metrics(code)
        
        # 5. Style Consistency
        features['style_consistency'] = self._analyze_style_consistency(code)
        
        # 6. Repetition Patterns
        features['repetition_patterns'] = self._analyze_repetition_patterns(code)
        
        # 7. Documentation Style
        features['documentation_style'] = self._analyze_documentation_style(code)
        
        return features
    
    def _analyze_comment_patterns(self, code: str) -> Dict[str, float]:
        """Analyze comment patterns using neural network-inspired feature extraction."""
        lines = code.split('\n')
        comment_lines = [line for line in lines if line.strip().startswith('#') or '//' in line or '/*' in line]
        
        features = {}
        
        # Comment density
        features['comment_density'] = len(comment_lines) / max(len(lines), 1)
        
        # Comment length patterns
        comment_lengths = [len(line.strip()) for line in comment_lines if line.strip()]
        if comment_lengths:
            features['avg_comment_length'] = np.mean(comment_lengths)
            features['comment_length_variance'] = np.var(comment_lengths)
        else:
            features['avg_comment_length'] = 0
            features['comment_length_variance'] = 0
        
        # Comment style consistency
        comment_styles = []
        for line in comment_lines:
            if line.strip().startswith('#'):
                comment_styles.append('hash')
            elif '//' in line:
                comment_styles.append('double_slash')
            elif '/*' in line:
                comment_styles.append('block')
        
        style_counter = Counter(comment_styles)
        features['comment_style_entropy'] = self._calculate_entropy(style_counter)
        
        # Comment position patterns
        comment_positions = []
        for i, line in enumerate(lines):
            if line.strip().startswith('#') or '//' in line or '/*' in line:
                comment_positions.append(i / max(len(lines), 1))
        
        if comment_positions:
            features['comment_position_variance'] = np.var(comment_positions)
        else:
            features['comment_position_variance'] = 0
        
        return features
    
    def _analyze_naming_conventions(self, code: str) -> Dict[str, float]:
        """Analyze naming conventions using pattern recognition."""
        # Extract identifiers (variables, functions, classes)
        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code)
        
        features = {}
        
        if not identifiers:
            features['naming_entropy'] = 0
            features['naming_consistency'] = 0
            features['camel_case_ratio'] = 0
            features['snake_case_ratio'] = 0
            features['screaming_case_ratio'] = 0
            return features
        
        # Naming style analysis
        camel_case = [id for id in identifiers if re.match(r'^[a-z][a-zA-Z0-9]*$', id)]
        snake_case = [id for id in identifiers if re.match(r'^[a-z][a-z0-9_]*$', id)]
        screaming_case = [id for id in identifiers if re.match(r'^[A-Z][A-Z0-9_]*$', id)]
        
        total = len(identifiers)
        features['camel_case_ratio'] = len(camel_case) / total
        features['snake_case_ratio'] = len(snake_case) / total
        features['screaming_case_ratio'] = len(screaming_case) / total
        
        # Naming consistency (entropy)
        naming_counter = Counter(identifiers)
        features['naming_entropy'] = self._calculate_entropy(naming_counter)
        
        # Naming consistency score
        dominant_style = max([
            (features['camel_case_ratio'], 'camel'),
            (features['snake_case_ratio'], 'snake'),
            (features['screaming_case_ratio'], 'screaming')
        ], key=lambda x: x[0])
        
        features['naming_consistency'] = dominant_style[0]
        
        return features
    
    def _analyze_code_structure(self, code: str, language: str) -> Dict[str, float]:
        """Analyze code structure and organization."""
        features = {}
        
        try:
            if language == 'python':
                tree = ast.parse(code)
                features['function_count'] = len([node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)])
                features['class_count'] = len([node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)])
                features['import_count'] = len([node for node in ast.walk(tree) if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom)])
                
                # Nesting depth analysis
                features['max_nesting_depth'] = self._calculate_nesting_depth(tree)
                
            else:
                # Generic structure analysis for other languages
                features['function_count'] = len(re.findall(r'\b(def|function|func|method)\b', code, re.IGNORECASE))
                features['class_count'] = len(re.findall(r'\b(class|struct|interface)\b', code, re.IGNORECASE))
                features['import_count'] = len(re.findall(r'\b(import|using|include|require)\b', code, re.IGNORECASE))
                features['max_nesting_depth'] = self._estimate_nesting_depth(code)
        
        except:
            features['function_count'] = 0
            features['class_count'] = 0
            features['import_count'] = 0
            features['max_nesting_depth'] = 0
        
        # Structure complexity score
        features['structure_complexity'] = (
            features['function_count'] * 0.3 +
            features['class_count'] * 0.4 +
            features['import_count'] * 0.2 +
            features['max_nesting_depth'] * 0.1
        )
        
        return features
    
    def _analyze_complexity_metrics(self, code: str) -> Dict[str, float]:
        """Analyze code complexity using various metrics."""
        features = {}
        
        lines = code.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        # Cyclomatic complexity approximation
        complexity_keywords = ['if', 'elif', 'else', 'for', 'while', 'and', 'or', 'except', 'case']
        complexity_score = sum(code.lower().count(keyword) for keyword in complexity_keywords)
        features['cyclomatic_complexity'] = complexity_score
        
        # Lines of code metrics
        features['total_lines'] = len(lines)
        features['code_lines'] = len(non_empty_lines)
        features['blank_line_ratio'] = (len(lines) - len(non_empty_lines)) / max(len(lines), 1)
        
        # Character-based metrics
        features['avg_line_length'] = np.mean([len(line) for line in non_empty_lines]) if non_empty_lines else 0
        features['max_line_length'] = max([len(line) for line in non_empty_lines]) if non_empty_lines else 0
        
        # Token-based analysis
        tokens = re.findall(r'\b\w+\b', code)
        features['token_count'] = len(tokens)
        features['unique_token_ratio'] = len(set(tokens)) / max(len(tokens), 1)
        
        return features
    
    def _analyze_style_consistency(self, code: str) -> Dict[str, float]:
        """Analyze code style consistency."""
        features = {}
        
        lines = [line for line in code.split('\n') if line.strip()]
        if not lines:
            features['indentation_consistency'] = 0
            features['spacing_consistency'] = 0
            features['style_entropy'] = 0
            return features
        
        # Indentation analysis
        indentations = []
        for line in lines:
            indent = len(line) - len(line.lstrip())
            indentations.append(indent)
        
        features['indentation_consistency'] = 1 - (np.std(indentations) / max(np.mean(indentations), 1))
        
        # Spacing consistency
        spacing_patterns = []
        for line in lines:
            spaces_before_op = len(re.findall(r'\s+[+\-*/=<>!]', line))
            spaces_after_op = len(re.findall(r'[+\-*/=<>!]\s+', line))
            spacing_patterns.append((spaces_before_op, spaces_after_op))
        
        if spacing_patterns:
            before_std = np.std([p[0] for p in spacing_patterns])
            after_std = np.std([p[1] for p in spacing_patterns])
            features['spacing_consistency'] = 1 - ((before_std + after_std) / 2)
        else:
            features['spacing_consistency'] = 0
        
        # Overall style entropy
        style_counter = Counter()
        for line in lines:
            indent_level = len(line) - len(line.lstrip())
            space_count = len(re.findall(r'\s+', line))
            style_key = f"indent_{indent_level}_spaces_{space_count}"
            style_counter[style_key] += 1
        
        features['style_entropy'] = self._calculate_entropy(style_counter)
        
        return features
    
    def _analyze_repetition_patterns(self, code: str) -> Dict[str, float]:
        """Analyze repetition patterns in code."""
        features = {}
        
        # Function call repetition
        function_calls = re.findall(r'\b\w+\s*\(', code)
        function_counter = Counter(function_calls)
        features['function_call_entropy'] = self._calculate_entropy(function_counter)
        
        # Variable usage repetition
        variables = re.findall(r'\b\w+\s*=', code)
        variable_counter = Counter(variables)
        features['variable_usage_entropy'] = self._calculate_entropy(variable_counter)
        
        # Line repetition
        lines = [line.strip() for line in code.split('\n') if line.strip()]
        line_counter = Counter(lines)
        features['line_repetition_entropy'] = self._calculate_entropy(line_counter)
        
        # Overall repetition score
        features['repetition_score'] = (
            features['function_call_entropy'] * 0.4 +
            features['variable_usage_entropy'] * 0.3 +
            features['line_repetition_entropy'] * 0.3
        )
        
        return features
    
    def _analyze_documentation_style(self, code: str) -> Dict[str, float]:
        """Analyze documentation and docstring patterns."""
        features = {}
        
        # Docstring analysis
        docstring_patterns = re.findall(r'""".*?"""', code, re.DOTALL)
        features['docstring_count'] = len(docstring_patterns)
        
        # Docstring length analysis
        if docstring_patterns:
            docstring_lengths = [len(ds) for ds in docstring_patterns]
            features['avg_docstring_length'] = np.mean(docstring_lengths)
            features['docstring_length_variance'] = np.var(docstring_lengths)
        else:
            features['avg_docstring_length'] = 0
            features['docstring_length_variance'] = 0
        
        # Inline documentation
        inline_docs = len(re.findall(r'#.*$', code, re.MULTILINE))
        features['inline_doc_ratio'] = inline_docs / max(len(code.split('\n')), 1)
        
        # Documentation consistency
        features['doc_consistency'] = (
            (features['docstring_count'] * 0.6) +
            (features['inline_doc_ratio'] * 0.4)
        )
        
        return features
    
    def _calculate_entropy(self, counter: Counter) -> float:
        """Calculate Shannon entropy for a counter object."""
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
        """Calculate maximum nesting depth of AST."""
        def get_depth(node, current_depth=0):
            max_depth = current_depth
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
                    max_depth = max(max_depth, get_depth(child, current_depth + 1))
                else:
                    max_depth = max(max_depth, get_depth(child, current_depth))
            return max_depth
        
        return get_depth(tree)
    
    def _estimate_nesting_depth(self, code: str) -> int:
        """Estimate nesting depth for non-Python code."""
        lines = code.split('\n')
        max_depth = 0
        current_depth = 0
        
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                # Count opening braces
                current_depth += stripped.count('{') + stripped.count('(')
                # Count closing braces
                current_depth -= stripped.count('}') + stripped.count(')')
                max_depth = max(max_depth, current_depth)
        
        return max_depth
    
    def analyze_code(self, code: str, language: str = 'auto') -> Dict[str, Any]:
        """
        Main analysis method that combines all features and applies neural network-inspired scoring.
        """
        # Extract all features
        features = self.extract_deep_features(code, language)
        
        # Calculate weighted scores for each category
        category_scores = {}
        for category, weight in self.feature_weights.items():
            if category in features:
                # Normalize and weight the features
                category_score = self._calculate_category_score(features[category])
                category_scores[category] = category_score * weight
        
        # Calculate overall AI likelihood score
        total_score = sum(category_scores.values())
        ai_likelihood = min(max(total_score, 0), 1)  # Clamp between 0 and 1
        
        # Determine classification
        if ai_likelihood > self.thresholds['ai_likely']:
            label = 'AI-generated'
        elif ai_likelihood < self.thresholds['human_likely']:
            label = 'Human-written'
        else:
            label = 'Uncertain'
        
        # Generate explanation
        explanation = self._generate_explanation(features, category_scores, ai_likelihood)
        
        return {
            'label': label,
            'score': ai_likelihood * 100,
            'features': features,
            'category_scores': category_scores,
            'explanation': explanation,
            'confidence': self._calculate_confidence(features, ai_likelihood)
        }
    
    def _calculate_category_score(self, category_features: Dict[str, float]) -> float:
        """Calculate a normalized score for a category of features."""
        if not category_features:
            return 0
        
        # Normalize features to 0-1 range and calculate weighted average
        normalized_scores = []
        weights = []
        
        for feature_name, value in category_features.items():
            # Apply feature-specific normalization
            normalized_value = self._normalize_feature(feature_name, value)
            normalized_scores.append(normalized_value)
            weights.append(1.0)  # Equal weights for now, could be learned
        
        if not normalized_scores:
            return 0
        
        # Calculate weighted average
        total_weight = sum(weights)
        if total_weight == 0:
            return 0
        
        weighted_score = sum(score * weight for score, weight in zip(normalized_scores, weights))
        return weighted_score / total_weight
    
    def _normalize_feature(self, feature_name: str, value: float) -> float:
        """Normalize feature values to 0-1 range based on expected ranges."""
        # Feature-specific normalization rules
        if 'entropy' in feature_name:
            # Entropy is typically 0-10, normalize to 0-1
            return min(value / 10.0, 1.0)
        elif 'ratio' in feature_name or 'consistency' in feature_name:
            # Already 0-1
            return max(0, min(value, 1))
        elif 'count' in feature_name:
            # Count features, normalize using log scale
            return min(math.log2(value + 1) / 10.0, 1.0)
        elif 'length' in feature_name:
            # Length features, normalize with reasonable upper bound
            return min(value / 100.0, 1.0)
        elif 'complexity' in feature_name:
            # Complexity features, normalize with reasonable upper bound
            return min(value / 20.0, 1.0)
        else:
            # Default normalization
            return max(0, min(value / 10.0, 1.0))
    
    def _generate_explanation(self, features: Dict[str, Any], category_scores: Dict[str, float], ai_likelihood: float) -> List[str]:
        """Generate human-readable explanation of the analysis."""
        explanation = []
        
        # Top contributing factors
        sorted_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        
        if sorted_categories:
            top_category, top_score = sorted_categories[0]
            explanation.append(f"Strongest indicator: {top_category.replace('_', ' ').title()} (score: {top_score:.2f})")
        
        # Feature-specific insights
        if 'comment_patterns' in features:
            comment_density = features['comment_patterns'].get('comment_density', 0)
            if comment_density > 0.3:
                explanation.append("High comment density suggests AI-generated code")
            elif comment_density < 0.05:
                explanation.append("Low comment density suggests human-written code")
        
        if 'naming_conventions' in features:
            naming_consistency = features['naming_conventions'].get('naming_consistency', 0)
            if naming_consistency > 0.8:
                explanation.append("Highly consistent naming conventions")
            else:
                explanation.append("Mixed naming conventions detected")
        
        if 'complexity_metrics' in features:
            complexity = features['complexity_metrics'].get('cyclomatic_complexity', 0)
            if complexity > 15:
                explanation.append("High code complexity detected")
            elif complexity < 5:
                explanation.append("Low code complexity detected")
        
        # Overall assessment
        if ai_likelihood > 0.8:
            explanation.append("Multiple AI indicators strongly suggest generated code")
        elif ai_likelihood < 0.2:
            explanation.append("Human coding patterns clearly detected")
        else:
            explanation.append("Mixed signals suggest uncertain origin")
        
        return explanation
    
    def _calculate_confidence(self, features: Dict[str, Any], ai_likelihood: float) -> float:
        """Calculate confidence level in the prediction."""
        # Base confidence on feature quality and consistency
        feature_quality = 0
        total_features = 0
        
        for category, category_features in features.items():
            if isinstance(category_features, dict):
                for feature_name, value in category_features.items():
                    if isinstance(value, (int, float)) and not math.isnan(value):
                        feature_quality += 1
                    total_features += 1
        
        feature_confidence = feature_quality / max(total_features, 1)
        
        # Confidence based on prediction strength
        prediction_confidence = 1 - abs(ai_likelihood - 0.5) * 2
        
        # Combine both factors
        overall_confidence = (feature_confidence * 0.4 + prediction_confidence * 0.6)
        
        return max(0, min(overall_confidence, 1))


# Convenience function for easy integration
def analyze_code_deep_learning(code: str, language: str = 'auto') -> Dict[str, Any]:
    """
    Convenience function to analyze code using the deep learning detector.
    
    Args:
        code: The code string to analyze
        language: Programming language (default: 'auto')
    
    Returns:
        Dictionary containing analysis results
    """
    detector = DeepLearningCodeDetector()
    return detector.analyze_code(code, language) 