from app.utils.numerical_scorer import calculate_numerical_score
from app.utils.nlp_scorer import calculate_nlp_score

# Define how much weight each subsystem gets
NUMERICAL_WEIGHT = 0.60  # Habits/Sliders (60%)
NLP_WEIGHT = 0.40        # Interests/Text (40%)

def get_total_compatibility_initial(user1_data: dict, target_data: dict) -> dict:
    """
    Calculates BOTH numerical and NLP scores from scratch.
    Use this for the first time two users are compared.
    """
    
    num_score = calculate_numerical_score(user1_data, target_data)
    
    text1 = user1_data.get("interests", "")
    text2 = target_data.get("interests", target_data.get("description", ""))
    nlp_score = calculate_nlp_score(text1, text2)
    
    final_raw_score = (num_score * NUMERICAL_WEIGHT) + (nlp_score * NLP_WEIGHT)
    
    return {
        "matchPercentage": round(final_raw_score * 100, 1),
        "breakdown": {
            "lifestyleScore": round(num_score * 100, 1),
            "interestsScore": round(nlp_score * 100, 1)
        }
    }

def update_total_compatibility(user1_data: dict, target_data: dict, stored_interests_score: float) -> dict:
    """
    Calculates ONLY the numerical score and reuses a previously saved NLP score.
    Use this when a user updates their slider habits but hasn't changed their interests.
    """
    num_score = calculate_numerical_score(user1_data, target_data)
    
    nlp_score = stored_interests_score / 100.0
    
    final_raw_score = (num_score * NUMERICAL_WEIGHT) + (nlp_score * NLP_WEIGHT)
    
    return {
        "matchPercentage": round(final_raw_score * 100, 1),
        "breakdown": {
            "lifestyleScore": round(num_score * 100, 1),
            "interestsScore": stored_interests_score 
        }
    }