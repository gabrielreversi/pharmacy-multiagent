import math
from collections import defaultdict

import pytest

from .cases import (
    ALL_CASES,
    BOUNDARY_CASES,
    CATEGORIES,
    NORMAL_CASES,
    OCR_CASES,
    RAG_CASES,
    SQL_CASES,
)

pytestmark = pytest.mark.classifier

MIN_ACCURACY = 0.85
MIN_CATEGORY_ACCURACY = 2 / 3


def _describe(question: str, result: dict) -> str:
    return f"{question!r} → {result['classifer']} (confiança {result['confidence']}, probabilidades {result['probabilities']})"


@pytest.mark.parametrize(("question", "expected"), RAG_CASES)
def test_rag_questions_are_classified_as_rag(classify, question, expected):
    result = classify(question)
    assert result["classifer"] == expected, _describe(question, result)


@pytest.mark.parametrize(("question", "expected"), SQL_CASES)
def test_sql_questions_are_classified_as_sql(classify, question, expected):
    result = classify(question)
    assert result["classifer"] == expected, _describe(question, result)


@pytest.mark.parametrize(("question", "expected"), OCR_CASES)
def test_ocr_requests_are_classified_as_ocr(classify, question, expected):
    result = classify(question)
    assert result["classifer"] == expected, _describe(question, result)


@pytest.mark.parametrize(("question", "expected"), NORMAL_CASES)
def test_casual_messages_are_classified_as_normal(classify, question, expected):
    result = classify(question)
    assert result["classifer"] == expected, _describe(question, result)


@pytest.mark.parametrize(("question", "expected"), BOUNDARY_CASES)
def test_boundary_cases_follow_user_intent(classify, question, expected):
    result = classify(question)
    assert result["classifer"] == expected, _describe(question, result)


def test_output_contract(classify):
    question = "Quais os efeitos colaterais da dipirona?"
    result = classify(question)

    assert set(result) == {"classifer", "confidence", "probabilities"}
    assert result["classifer"] in CATEGORIES
    assert isinstance(result["confidence"], float)
    assert 0.0 <= result["confidence"] <= 1.0
    assert classify(question)["classifer"] == result["classifer"]


@pytest.mark.parametrize(
    "question",
    [RAG_CASES[0][0], SQL_CASES[0][0], OCR_CASES[0][0], NORMAL_CASES[0][0]],
)
def test_probabilities_are_consistent(classify, question):
    result = classify(question)
    probabilities = result["probabilities"]

    assert set(probabilities) == CATEGORIES
    assert sum(probabilities.values()) == pytest.approx(1.0, abs=0.01)
    assert result["classifer"] == max(probabilities, key=probabilities.get)

    # No laya, `confidence` de uma escolha é a entropia normalizada (1 - H(p) / log k),
    # não a probabilidade da categoria escolhida.
    entropy = -sum(p * math.log(p) for p in probabilities.values() if p > 0)
    expected_confidence = 1 - entropy / math.log(len(probabilities))
    assert result["confidence"] == pytest.approx(expected_confidence, abs=0.01)


def test_minimum_accuracy_on_reference_set(classify):
    hits_by_category = defaultdict(int)
    total_by_category = defaultdict(int)
    errors = []

    for question, expected in ALL_CASES:
        result = classify(question)
        total_by_category[expected] += 1
        if result["classifer"] == expected:
            hits_by_category[expected] += 1
        else:
            errors.append(f"{question!r} → esperado {expected} / obtido {result['classifer']} ({result['confidence']})")

    accuracy = sum(hits_by_category.values()) / len(ALL_CASES)
    category_accuracy = {
        category: hits_by_category[category] / total for category, total in total_by_category.items()
    }
    report = (
        f"acurácia geral {accuracy:.0%}; por categoria "
        + ", ".join(f"{c} {a:.0%}" for c, a in sorted(category_accuracy.items()))
        + ("\nerros:\n  " + "\n  ".join(errors) if errors else "")
    )

    assert accuracy >= MIN_ACCURACY, report
    assert all(a >= MIN_CATEGORY_ACCURACY for a in category_accuracy.values()), report
