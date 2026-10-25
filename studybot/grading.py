import re


def grade_multiple_choice(answer: str, correct: str) -> tuple[float, str]:
    normalized = re.sub(r"[^a-z0-9가-힣]", "", answer.lower())
    target = re.sub(r"[^a-z0-9가-힣]", "", correct.lower())
    ok = normalized == target or (len(normalized) == 1 and normalized in {"a", "b", "c", "d", "1", "2", "3", "4"} and normalized == target)
    return (1.0, "정답입니다. 핵심 개념을 실제 데이터에서 다시 확인해 보세요.") if ok else (0.0, f"정답은 {correct}입니다.")


def grade_short_answer(answer: str, expected: str, keywords=None) -> tuple[float, str]:
    """Deterministic fallback grader; AI grading can be added without making this path optional."""
    words = keywords or [w for w in re.findall(r"[가-힣A-Za-z]{2,}", expected) if len(w) > 2][:8]
    answer_words = [w.lower() for w in re.findall(r"[가-힣A-Za-z]{2,}", answer)]
    matched = [word for word in words if any(word.lower() in got or got in word.lower() for got in answer_words)]
    score = min(1.0, len(matched) / max(2, min(3, len(words))))
    note = "핵심어를 잘 포함했습니다." if score >= 0.6 else "핵심 개념을 더 구체적으로 설명해 보세요."
    return score, note + f" 핵심어 반영 {len(matched)}/{len(words)}."
