"""
FULL AI MATCH ENGINE TEST

Simulates:
Group (room)
+
20 incoming applicants
+
Rank Engine sorting

Run using:
python -m app.utils.ai.test_rank_engine
"""

import json
from pathlib import Path

from app.utils.rank_engine import rank_applicants


# --------------------------------------------------
# LOAD MOCK STUDENTS (20 applicants)
# --------------------------------------------------

DATA_PATH = Path("app/utils/mock_students.json")


def load_students():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------
# MOCK GROUP (REAL STRUCTURE)
# --------------------------------------------------

def mock_group():
    return {
        "preferences": """
        Looking for ambitious, clean, academically focused roommates.
        Prefer quiet or balanced personalities.
        Coding, productivity, and discipline vibe.
        No loud late-night parties or chaotic environments.
        """,

        # Existing room members
        "students": [
            {
                "regNo": "22BCE0001",
                "sleepTime": 23.5,
                "wakeTime": 6.5,
                "cleanliness": 5,
                "socialScene": 2,
                "languages": ["English", "Hindi"],
                "interests": "Coding, gym, productivity, hackathons",
                "description": "Quiet and focused person"
            },
            {
                "regNo": "22BCE0002",
                "sleepTime": 24.0,
                "wakeTime": 7.0,
                "cleanliness": 4,
                "socialScene": 2,
                "languages": ["English"],
                "interests": "Academics and research",
                "description": "Clean and disciplined lifestyle"
            }
        ]
    }


# --------------------------------------------------
# MAIN TEST
# --------------------------------------------------

def main():

    group = mock_group()
    applicants = load_students()

    ranked = rank_applicants(group, applicants)

    print("\n====== SORTED APPLICANTS ======\n")

    for i, result in enumerate(ranked, start=1):
        student = result["student"]

        print(
            f"{i:02d}. "
            f"{student.get('regNo', 'N/A')} | "
            f"Final={result['finalScore']:.4f} | "
            f"Quiz={result['quizScore']:.4f} | "
            f"Text={result['textScore']:.4f}"
        )


if __name__ == "__main__":
    main()