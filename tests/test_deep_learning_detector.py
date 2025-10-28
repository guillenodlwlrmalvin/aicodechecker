from deep_learning_detector import analyze_code_deep_learning


def test_deep_learning_detector_returns_shape():
    code = """
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
""".strip()
    out = analyze_code_deep_learning(code, 'python')
    assert set(['label', 'score', 'features', 'category_scores', 'explanation', 'confidence']) <= set(out.keys())
    assert 0 <= out['score'] <= 100


