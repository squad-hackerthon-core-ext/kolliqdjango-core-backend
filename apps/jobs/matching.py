"""
Kolliq Job Matching Engine
Weighted SQL scoring — no ML in pilot, fully replaceable post-pilot.

Score breakdown per job (max 100):
  Skill match      40 pts  — exact match required, partial match for 'other'
  Distance         30 pts  — 0km = 30, decays linearly to 0 at 20km+
  Pay amount       15 pts  — relative to max pay available in feed
  Employer rating  15 pts  — 5-star normalised to 15
"""
from django.db.models import Avg, F, FloatField, ExpressionWrapper, Value
from django.db.models.functions import Coalesce
from django.db import models
import math
import logging

from .models import Job, Rating

logger = logging.getLogger(__name__)

MAX_DISTANCE_KM = 20.0   # Jobs beyond this get 0 distance points
TOP_N_JOBS = 3           # Jobs shown in worker feed


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine formula — distance in km between two lat/lng points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def distance_score(km: float) -> float:
    """30 pts at 0km, decays to 0 at MAX_DISTANCE_KM."""
    if km >= MAX_DISTANCE_KM:
        return 0.0
    return 30.0 * (1 - km / MAX_DISTANCE_KM)


def skill_score(job_skill: str, worker_skills: list) -> float:
    """40 pts for exact match, 10 pts if worker has 'other' or job is 'other'."""
    if not worker_skills:
        return 0.0
    if job_skill in worker_skills:
        return 40.0
    if 'other' in worker_skills or job_skill == 'other':
        return 10.0
    return 0.0


def pay_score(job_pay: float, max_pay_in_feed: float) -> float:
    """15 pts proportional to pay vs highest paying job in current feed."""
    if max_pay_in_feed == 0:
        return 0.0
    return 15.0 * (job_pay / max_pay_in_feed)


def employer_rating_score(employer_avg_rating: float | None) -> float:
    """15 pts for 5-star employer, proportional."""
    if employer_avg_rating is None:
        return 7.5   # New employer: neutral midpoint
    return 15.0 * (employer_avg_rating / 5.0)


def get_employer_avg_ratings() -> dict:
    """
    Returns { employer_id: avg_rating } for all employers who have ratings.
    Called once per matching run — not per job.
    """
    ratings = (
        Rating.objects
        .values('to_user_id')
        .annotate(avg=Avg('stars'))
    )
    return {str(r['to_user_id']): r['avg'] for r in ratings}


def match_jobs_for_worker(worker) -> list:
    """
    Returns top N scored jobs for a given worker.
    Each result is a dict with the job + computed match_score + distance_km.
    """
    from apps.users.models import User

    # Pull worker's location and skills
    worker_lat = float(worker.location_lat) if worker.location_lat else None
    worker_lng = float(worker.location_lng) if worker.location_lng else None
    worker_skills = worker.skills or []
    worker_city = worker.location_city or 'Lagos'

    # Get open jobs — filter by city first (cheap DB filter before Python scoring)
    open_jobs = Job.objects.filter(
        status=Job.Status.OPEN,
        escrow_funded=True,
    ).select_related('employer').order_by('-created_at')[:100]
    # Pull 100 candidates max — Python scores them

    if not open_jobs:
        return []

    # Get employer ratings once
    employer_ratings = get_employer_avg_ratings()

    # Max pay for normalisation
    pays = [float(j.pay_per_worker) for j in open_jobs]
    max_pay = max(pays) if pays else 1.0

    scored = []
    for job in open_jobs:
        # Skill
        s_skill = skill_score(job.skill_required, worker_skills)

        # If skill score is 0 and worker has no 'other' skills, skip entirely
        if s_skill == 0:
            continue

        # Distance
        if worker_lat and worker_lng and job.location_lat and job.location_lng:
            km = haversine_km(
                worker_lat, worker_lng,
                float(job.location_lat), float(job.location_lng)
            )
            s_dist = distance_score(km)
        else:
            # No coordinates — fall back to city match heuristic
            km = 0.0 if job.location_city == worker_city else 15.0
            s_dist = distance_score(km)

        # Pay
        s_pay = pay_score(float(job.pay_per_worker), max_pay)

        # Employer rating
        emp_rating = employer_ratings.get(str(job.employer_id))
        s_rating = employer_rating_score(emp_rating)

        total = s_skill + s_dist + s_pay + s_rating

        scored.append({
            'job': job,
            'match_score': round(total, 1),
            'distance_km': round(km, 1),
            'employer_rating': round(emp_rating, 1) if emp_rating else None,
            'score_breakdown': {
                'skill': round(s_skill, 1),
                'distance': round(s_dist, 1),
                'pay': round(s_pay, 1),
                'employer_rating': round(s_rating, 1),
            }
        })

    # Sort by total score descending, return top N
    scored.sort(key=lambda x: x['match_score'], reverse=True)
    return scored[:TOP_N_JOBS]