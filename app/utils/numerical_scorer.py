from typing import List

# Question importance
PERSONALITY_WEIGHTS = {
    "sleepTime": 0.35,
    "wakeTime": 0.25,
    "cleanliness": 0.25,
    "socialScene": 0.15,
}

# Personality vs Language split
PERSONALITY_IMPORTANCE = 0.8
LANGUAGE_IMPORTANCE = 0.2

def _normalize(value: float | None, max_value: float) -> float:
    if value is None:
        return 0.0
    return float(value) / max_value

def _language_similarity(
    langs_a: List[str] | None,
    langs_b: List[str] | None,
) -> float:
    """
    Jaccard similarity between language sets
    """

    set_a = set(langs_a or [])
    set_b = set(langs_b or [])

    if not set_a or not set_b:
        return 0.0

    return len(set_a & set_b) / len(set_a | set_b)

def _student_vector(student: dict) -> dict:
    
    return {
        "sleepTime": _normalize(student.get("sleepTime"), 24.0),
        "wakeTime": _normalize(student.get("wakeTime"), 24.0),
        "cleanliness": _normalize(student.get("cleanliness"), 5.0),
        "socialScene": _normalize(student.get("socialScene"), 5.0),
    }


def _group_reference_vector(group_members: List[dict]) -> dict:
    """
    Average personality of room
    """

    if not group_members:
        return {
            k: 0.5 for k in PERSONALITY_WEIGHTS
        }

    vectors = [_student_vector(m) for m in group_members]

    averaged = {}

    for key in PERSONALITY_WEIGHTS:
        averaged[key] = sum(v[key] for v in vectors) / len(vectors)

    return averaged


def _personality_similarity(
    vec_a: dict,
    vec_b: dict,
) -> float:
    
    weighted_distance = 0.0
    total_weight = sum(PERSONALITY_WEIGHTS.values())

    for trait, weight in PERSONALITY_WEIGHTS.items():
        diff = abs(vec_a[trait] - vec_b[trait])
        weighted_distance += diff * weight

    normalized_distance = weighted_distance / total_weight

    return 1 - normalized_distance


def calculate_numerical_score(
    user1_data: dict,
    target_data: dict,
) -> float:
   
    group_members = target_data.get("students")
    if not group_members:
        group_members = [target_data]

    student_vec = _student_vector(user1_data)
    group_vec = _group_reference_vector(group_members)

    personality_match = _personality_similarity(
        student_vec,
        group_vec,
    )

    room_languages = [
        lang
        for member in group_members
        for lang in (member.get("languages") or [])
    ]

    language_match = _language_similarity(
        user1_data.get("languages"),
        room_languages,
    )

    combined_score = (
        PERSONALITY_IMPORTANCE * personality_match
        +
        LANGUAGE_IMPORTANCE * language_match
    )

    return float(combined_score)