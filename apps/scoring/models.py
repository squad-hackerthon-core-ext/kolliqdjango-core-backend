from django.db import models
from django.conf import settings
import uuid
from apps.common.rls import UserOwnedModel


class EconomicIdentityScore(UserOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='economic_score'
    )
    score = models.PositiveSmallIntegerField(default=10)

    # Score breakdown stored so users can see WHY their score is what it is
    breakdown = models.JSONField(default=dict, blank=True)
    # e.g. {
    #   "base": 10,
    #   "gigs_completed": 25,
    #   "transactions_recorded": 6,
    #   "loans_repaid": 0,
    #   "ratings_received": 9,
    #   "insurance_days": 0,
    # }

    # Unlocked service flags — denormalised for fast reads
    savings_unlocked = models.BooleanField(default=False)
    insurance_unlocked = models.BooleanField(default=False)
    loan_unlocked = models.BooleanField(default=False)

    last_calculated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'economic_identity_scores'

    def __str__(self):
        return f"Score({self.user.phone}): {self.score}/100"