"""
Final Ranking Engine

Combines:
    0.6 → Personality Compatibility
    0.4 → Text Compatibility

Returns sorted applicants
"""

from typing import List, Dict

from app.utils.numerical import compute_quiz_score
from app.utils.text_matcher import compute_text_match_score


# =====================================================
# SINGLE APPLICANT SCORING
# =====================================================

def _compute_final_score(
    applicant: dict,
    group: dict,
) -> Dict:
    """
    Computes full compatibility score for one applicant.
    """

    quiz_score = compute_quiz_score(applicant, group)
    text_score = compute_text_match_score(applicant, group)

    final_score = round(quiz_score + text_score, 4)

    return {
        "student": applicant,
        "quizScore": quiz_score,
        "textScore": text_score,
        "finalScore": final_score,
    }


# =====================================================
# MAIN RANKING FUNCTION
# =====================================================

def rank_applicants(
    group: dict,
    applicants: List[dict],
) -> List[Dict]:
    """
    Ranks applicants for a group.

    Input:
        group       → Mongo group document (must include students)
        applicants  → List of student documents

    Output:
        Sorted list (highest score first)
    """

    ranked = []

    for applicant in applicants:
        try:
            scored = _compute_final_score(applicant, group)
            ranked.append(scored)
        except Exception:
            # Prevent single bad profile from breaking ranking
            continue

    # Sort by finalScore descending
    ranked.sort(
        key=lambda x: x["finalScore"],
        reverse=True
    )

    return ranked