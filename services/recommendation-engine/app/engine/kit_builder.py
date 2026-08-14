"""Complete-look builder compatibility layer.

Complete looks are produced by the deterministic advisor recommender from a
BeautyProfile; commerce validation remains the responsibility of the Go API.
"""
from app.advisor.models import BeautyProfile, Goal
from app.advisor.recommender import recommend


def build_complete_look(profile: BeautyProfile):
    profile = profile.model_copy(deep=True)
    profile.goal = Goal.full_look
    return recommend(profile)
