"""
Partner-ready export endpoints.
These are your pitch deck to microfinance banks and insurance companies.
"""
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from django.conf import settings
from django.db.models import Avg, Count, Sum
from decimal import Decimal
from kolliq.utils import success_response, error_response
import logging

logger = logging.getLogger(__name__)


class PartnerAuthMixin:
    """Require partner API secret in header."""
    def check_partner_auth(self, request):
        secret = request.headers.get('x-partner-secret', '')
        return secret == settings.PARTNER_API_SECRET


class EligibleBorrowersView(APIView, PartnerAuthMixin):
    """
    GET /api/partner/eligible-borrowers/
    Returns anonymized list of users pre-qualified for loans.
    This is the endpoint you show to microfinance banks.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='partner_eligible_borrowers',
        summary='Get eligible borrowers',
        description='Get anonymized list of pre-qualified loan borrowers',
        tags=['Partner'],
    )
    def get(self, request):
        if not self.check_partner_auth(request):
            return error_response('Invalid partner credentials.', status=401)

        from apps.scoring.models import EconomicIdentityScore
        from apps.jobs.models import JobApplication
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Users with score ≥ 50, no active loan, not flagged
        eligible_scores = EconomicIdentityScore.objects.filter(
            score__gte=settings.LOAN_SCORE_THRESHOLD,
            loan_unlocked=True,
        ).select_related('user')

        from apps.financial_services.models import Loan

        results = []
        total_recommended = Decimal('0')

        for score_obj in eligible_scores:
            user = score_obj.user
            if user.is_flagged:
                continue
            has_active_loan = user.loans.filter(
                status__in=['active', 'partially_repaid']
            ).exists()
            if has_active_loan:
                continue

            # Loan limit based on score
            if score_obj.score < 60:
                max_loan = Decimal('10000')
            elif score_obj.score < 75:
                max_loan = Decimal('25000')
            elif score_obj.score < 90:
                max_loan = Decimal('50000')
            else:
                max_loan = Decimal('100000')

            total_recommended += max_loan
            gigs_completed = user.applications.filter(status='completed').count()
            avg_rating = user.ratings_received.aggregate(avg=Avg('stars'))['avg']

            results.append({
                'anonymous_id': str(user.id)[:8],   # Never expose full ID to partners
                'score': score_obj.score,
                'location_city': user.location_city,
                'role': user.role,
                'gigs_completed': gigs_completed,
                'avg_rating': round(avg_rating, 1) if avg_rating else None,
                'recommended_loan_amount': str(max_loan),
                'interest_rate_suggested': settings.LOAN_INTEREST_RATE_MONTHLY,
                'repayment_period_days': 28,
            })

        # Estimate default rate from historical data
        total_loans = Loan.objects.count()
        defaulted_loans = Loan.objects.filter(status='defaulted').count()
        default_rate = (defaulted_loans / total_loans * 100) if total_loans > 0 else 0

        return success_response({
            'summary': {
                'total_eligible': len(results),
                'total_recommended_lending': str(total_recommended),
                'estimated_default_rate_percent': round(default_rate, 2),
                'funding_mode': settings.FINANCIAL_PARTNER_MODE,
                'note': (
                    'All scores derived from verified economic activity: '
                    'gigs completed, payments received, loans repaid. '
                    'No self-reported data.'
                ),
            },
            'eligible_borrowers': results,
        })


class UserScoreReportView(APIView, PartnerAuthMixin):
    """
    GET /api/partner/score-report/<user_id>/
    Full economic history for a specific user.
    Used when a partner wants to underwrite a specific borrower.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='partner_score_report',
        summary='Get user score report',
        description='Get detailed score breakdown for a user',
        tags=['Partner'],
    )
    def get(self, request, user_id):
        if not self.check_partner_auth(request):
            return error_response('Invalid partner credentials.', status=401)

        from django.contrib.auth import get_user_model
        from apps.payments.models import Transaction
        from apps.jobs.models import JobApplication, Rating
        from django.db.models import Avg, Sum

        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return error_response('User not found.', status=404)

        score_obj = getattr(user, 'economic_score', None)
        gigs = user.applications.filter(status='completed')
        ratings = user.ratings_received.all()
        transactions = user.transactions.filter(status='success')

        total_earned = transactions.filter(
            transaction_type='credit'
        ).aggregate(total=Sum('amount'))['total'] or 0

        loans = user.loans.all()
        repaid_loans = loans.filter(status='repaid').count()
        defaulted_loans = loans.filter(status='defaulted').count()

        return success_response({
            'user_id': str(user.id),
            'score': score_obj.score if score_obj else 0,
            'score_breakdown': score_obj.breakdown if score_obj else {},
            'profile': {
                'role': user.role,
                'location_city': user.location_city,
                'skills': user.skills,
                'days_on_platform': (
                    (__import__('django.utils.timezone', fromlist=['now']).now() - user.created_at).days
                ),
            },
            'activity': {
                'gigs_completed': gigs.count(),
                'total_earned_naira': str(total_earned),
                'average_rating': round(
                    ratings.aggregate(avg=Avg('stars'))['avg'] or 0, 2
                ),
                'total_transactions': transactions.count(),
            },
            'credit_history': {
                'loans_taken': loans.count(),
                'loans_repaid': repaid_loans,
                'loans_defaulted': defaulted_loans,
                'repayment_rate_percent': (
                    round(repaid_loans / loans.count() * 100, 1)
                    if loans.count() > 0 else None
                ),
            },
            'financial_services_active': {
                'savings': hasattr(user, 'savings_pot'),
                'insurance': user.insurance_policies.filter(status='active').exists(),
                'active_loan': user.loans.filter(
                    status__in=['active', 'partially_repaid']
                ).exists(),
            },
        })


class PlatformSummaryView(APIView, PartnerAuthMixin):
    """
    GET /api/partner/summary/
    High-level platform health for investor/partner pitch.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='partner_platform_summary',
        summary='Get platform summary',
        description='Get platform-wide statistics and metrics',
        tags=['Partner'],
    )
    def get(self, request):
        if not self.check_partner_auth(request):
            return error_response('Invalid partner credentials.', status=401)

        from django.contrib.auth import get_user_model
        from apps.jobs.models import Job, JobApplication
        from apps.payments.models import Transaction
        from apps.financial_services.models import Loan, InsurancePolicy, SavingsPot
        from apps.scoring.models import EconomicIdentityScore
        from django.db.models import Sum, Count

        User = get_user_model()

        total_users = User.objects.filter(is_active=True).count()
        score_dist = {
            'starter_0_20': EconomicIdentityScore.objects.filter(score__lt=20).count(),
            'active_20_40': EconomicIdentityScore.objects.filter(score__gte=20, score__lt=40).count(),
            'trusted_40_60': EconomicIdentityScore.objects.filter(score__gte=40, score__lt=60).count(),
            'established_60_80': EconomicIdentityScore.objects.filter(score__gte=60, score__lt=80).count(),
            'champion_80_100': EconomicIdentityScore.objects.filter(score__gte=80).count(),
        }

        wallet_volume = Transaction.objects.filter(
            status='success', transaction_type='credit'
        ).aggregate(total=Sum('amount'))['total'] or 0

        return success_response({
            'platform': {
                'total_users': total_users,
                'financial_partner_mode': settings.FINANCIAL_PARTNER_MODE,
            },
            'score_distribution': score_dist,
            'jobs': {
                'total_posted': Job.objects.count(),
                'completed': Job.objects.filter(status='completed').count(),
                'active': Job.objects.filter(status__in=['open', 'in_progress']).count(),
            },
            'payments': {
                'total_wallet_volume_naira': str(wallet_volume),
                'total_transactions': Transaction.objects.filter(status='success').count(),
            },
            'financial_services': {
                'active_loans': Loan.objects.filter(status__in=['active', 'partially_repaid']).count(),
                'total_loan_book_naira': str(
                    Loan.objects.filter(
                        status__in=['active', 'partially_repaid']
                    ).aggregate(total=Sum('amount'))['total'] or 0
                ),
                'loans_repaid': Loan.objects.filter(status='repaid').count(),
                'loans_defaulted': Loan.objects.filter(status='defaulted').count(),
                'active_insurance_policies': InsurancePolicy.objects.filter(status='active').count(),
                'total_in_savings_naira': str(
                    SavingsPot.objects.aggregate(total=Sum('balance'))['total'] or 0
                ),
                'loan_eligible_users': EconomicIdentityScore.objects.filter(
                    loan_unlocked=True
                ).count(),
                'insurance_eligible_users': EconomicIdentityScore.objects.filter(
                    insurance_unlocked=True
                ).count(),
            },
        })