"""Compatibility module for the original recommendation-engine scaffold.

The V1 advisor routes live in app.api.advisor. Keep this module so imports from the
original architecture do not break while callers migrate to /advisor/session.
"""

from app.advisor.models import BeautyProfile
from app.advisor.recommender import recommend


def get_recommendations(profile: BeautyProfile):
    return recommend(profile)
