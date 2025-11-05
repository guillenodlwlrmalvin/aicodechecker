"""
Plagiarism Detection Module
Detects code similarity between student submissions
"""

import re
from typing import Dict, List, Tuple, Any
from difflib import SequenceMatcher
import hashlib


def normalize_code(code: str) -> str:
    """
    Normalize code for comparison by removing:
    - Comments
    - Whitespace variations
    """
    if not code:
        return ""
    
    # Remove single-line comments
    lines = code.split('\n')
    normalized_lines = []
    for line in lines:
        # Remove comments (both // and # style)
        line = re.sub(r'//.*$', '', line)  # C/Java style
        line = re.sub(r'#.*$', '', line)    # Python style
        # Remove /* */ style comments (simple approach)
        line = re.sub(r'/\*.*?\*/', '', line, flags=re.DOTALL)
        normalized_lines.append(line.strip())
    
    # Join and normalize whitespace
    normalized = ' '.join(normalized_lines)
    # Remove all extra whitespace
    normalized = re.sub(r'\s+', ' ', normalized)
    # Normalize to lowercase
    normalized = normalized.lower()
    
    return normalized.strip()


def calculate_similarity(code1: str, code2: str) -> float:
    """
    Calculate similarity between two code strings (0.0 to 1.0)
    Returns a score from 0 (completely different) to 1 (identical)
    """
    if not code1 or not code2:
        return 0.0
    
    # Normalize both codes
    norm1 = normalize_code(code1)
    norm2 = normalize_code(code2)
    
    if not norm1 or not norm2:
        return 0.0
    
    # Use SequenceMatcher for similarity calculation
    similarity = SequenceMatcher(None, norm1, norm2).ratio()
    
    # Also check for exact match after normalization
    if norm1 == norm2:
        return 1.0
    
    return similarity


def get_code_hash(code: str) -> str:
    """Get hash of normalized code for quick identical detection"""
    normalized = normalize_code(code)
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def detect_plagiarism(submissions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detect plagiarism among a list of submissions.
    
    Args:
        submissions: List of submission dictionaries with 'id', 'code_content', 'username', etc.
    
    Returns:
        List of plagiarism matches with similarity scores
    """
    plagiarism_matches = []
    
    # First, get all submission contents (text or file content)
    submission_contents = []
    for sub in submissions:
        # Use code_content which combines text content and file content
        content = sub.get('code_content') or sub.get('content') or ''
        
        # Only compare submissions that have code content
        if content and content.strip():
            submission_contents.append({
                'id': sub.get('id'),
                'username': sub.get('username'),
                'content': content,
                'submission': sub
            })
    
    # Compare each pair of submissions
    for i in range(len(submission_contents)):
        for j in range(i + 1, len(submission_contents)):
            sub1 = submission_contents[i]
            sub2 = submission_contents[j]
            
            similarity = calculate_similarity(sub1['content'], sub2['content'])
            
            # Consider it plagiarism if similarity is above 80%
            if similarity >= 0.8:
                plagiarism_matches.append({
                    'submission1_id': sub1['id'],
                    'submission1_username': sub1['username'],
                    'submission2_id': sub2['id'],
                    'submission2_username': sub2['username'],
                    'similarity': similarity,
                    'similarity_percent': round(similarity * 100, 2),
                    'is_identical': similarity >= 0.99
                })
    
    # Sort by similarity (highest first)
    plagiarism_matches.sort(key=lambda x: x['similarity'], reverse=True)
    
    return plagiarism_matches


def compare_two_submissions(code1: str, code2: str, username1: str, username2: str) -> Dict[str, Any]:
    """
    Compare two specific code submissions.
    
    Returns:
        Dictionary with comparison results
    """
    similarity = calculate_similarity(code1, code2)
    hash1 = get_code_hash(code1)
    hash2 = get_code_hash(code2)
    
    return {
        'similarity': similarity,
        'similarity_percent': round(similarity * 100, 2),
        'is_identical': hash1 == hash2,
        'user1': username1,
        'user2': username2,
        'status': 'identical' if hash1 == hash2 else 'highly_similar' if similarity >= 0.9 else 'similar' if similarity >= 0.8 else 'different'
    }
