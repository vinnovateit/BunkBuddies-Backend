"""
Text Compatibility Engine (0.4 Weight)

Breakdown:
    0.3 → Room Description vs Applicant Interests
    0.1 → Room Description vs Applicant Description

Final Output Range:
    0.0 → 0.4
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# =====================================================
# INTERNAL NLP SIMILARITY
# =====================================================

def _similarity(text1: str | None, text2: str | None) -> float:
    """
    Computes cosine similarity between two texts using TF-IDF.

    Returns:
        float between 0 and 1
    """

    if not text1 or not text2:
        return 0.0

    text1 = text1.strip()
    text2 = text2.strip()

    if not text1 or not text2:
        return 0.0

    try:
        vectorizer = TfidfVectorizer(stop_words="english")

        tfidf_matrix = vectorizer.fit_transform([
            text1,
            text2
        ])

        score = cosine_similarity(
            tfidf_matrix[0:1],
            tfidf_matrix[1:2]
        )[0][0]

        return float(score)

    except Exception:
        # Fail-safe → never crash ranking pipeline
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
        group.preferences        → room description
        student.interests        → personality interests
        student.description      → free-form bio

    Weighting:
        0.3 → interests match
        0.1 → description match

    Returns:
        float in range [0.0 , 0.4]
    """

    # ---------- ROOM DESCRIPTION ----------
    room_description = (group.get("preferences") or "").strip()

    # If admin gave no room description → no NLP signal
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