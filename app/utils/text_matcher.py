"""
Text Compatibility Engine (0.4 Weight)

Breakdown:
    0.3 -> Room Description vs Applicant Interests
    0.1 -> Room Description vs Applicant Description

Final Output Range:
    0.0 -> 0.4
"""

from difflib import SequenceMatcher


# =====================================================
# INTERNAL NLP SIMILARITY
# =====================================================

def _similarity(text1: str | None, text2: str | None) -> float:
    """
    Computes lexical similarity between two texts.

    Returns:
        float between 0 and 1
    """

    if not text1 or not text2:
        return 0.0

    text1 = text1.strip().lower()
    text2 = text2.strip().lower()

    if not text1 or not text2:
        return 0.0

    try:
        seq_ratio = SequenceMatcher(None, text1, text2).ratio()

        tokens1 = set(text1.split())
        tokens2 = set(text2.split())
        if not tokens1 or not tokens2:
            return max(0.0, min(1.0, float(seq_ratio)))

        jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2)
        return max(0.0, min(1.0, (seq_ratio + jaccard) / 2.0))

    except Exception:
        # Fail-safe -> never crash ranking pipeline
        return 0.0


# =====================================================
# MAIN 0.4 MATCH FUNCTION
# =====================================================

def compute_text_match_score(
    student: dict,
    group: dict
) -> float:
    """
    Computes full TEXT compatibility score.

    Uses:
        group.preferences        -> room description
        student.interests        -> personality interests
        student.description      -> free-form bio

    Weighting:
        0.3 -> interests match
        0.1 -> description match

    Returns:
        float in range [0.0 , 0.4]
    """

    # ---------- ROOM DESCRIPTION ----------
    room_description = (group.get("preferences") or "").strip()

    # If admin gave no room description -> no NLP signal
    if not room_description:
        return 0.0

    # ---------- APPLICANT DATA ----------
    applicant_interests = student.get("interests") or ""
    applicant_description = student.get("description") or ""

    # ---------- SIMILARITIES ----------
    interest_similarity = _similarity(
        room_description,
        applicant_interests
    )

    description_similarity = _similarity(
        room_description,
        applicant_description
    )

    # ---------- WEIGHTED SCORE ----------
    interest_score = 0.3 * interest_similarity
    description_score = 0.1 * description_similarity

    total_score = interest_score + description_score

    return round(total_score, 4)
