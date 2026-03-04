from sentence_transformers import SentenceTransformer, util
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

_model = SentenceTransformer('all-MiniLM-L6-v2')
nltk.download('vader_lexicon', quiet=True)
_sia = SentimentIntensityAnalyzer()

def calculate_nlp_score(text1: str, text2: str) -> float:
    if not text1 or not text2:
        return 0.5

    text1 = text1.strip().lower()
    text2 = text2.strip().lower()

    
    emb1 = _model.encode(text1, convert_to_tensor=True)
    emb2 = _model.encode(text2, convert_to_tensor=True)
    raw_similarity = util.cos_sim(emb1, emb2)[0][0].item()
    
    
    base_sim = max(0.0, float(raw_similarity))

    
    if base_sim > 0.50:
        sent1 = _sia.polarity_scores(text1)['compound']
        sent2 = _sia.polarity_scores(text2)['compound']
        
        penalty = 1.0
        
        if (sent1 > 0.1 and sent2 < -0.1) or (sent1 < -0.1 and sent2 > 0.1):
            penalty = 0.3
        elif abs(sent1) < 0.1 or abs(sent2) < 0.1:
            penalty = 0.8 
        final_score = base_sim * penalty
    
    else:
        final_score = base_sim

    boosted_score = min(1.0, final_score * 1.3)

    return round(float(boosted_score), 4)