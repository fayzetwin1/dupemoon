from src.config import settings

def calculate_new_mood(current_mood: float, impact: float) -> float:
    """
    Math for emotional inertia:
    Mood_t = Mood_{t-1} + Impact - alpha*(Mood_{t-1} - BaseLine)
    """
    alpha = settings.emotional_inertia_alpha
    baseline = settings.base_mood
    
    new_mood = current_mood + impact - alpha * (current_mood - baseline)
    
    # Clamp value within [0.0, 1.0]
    return max(0.0, min(1.0, new_mood))
