from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from kolliq.permissions import IsAuthenticatedOrInternalSecret, resolve_user
from drf_spectacular.utils import extend_schema
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction as db_transaction
from kolliq.utils import success_response, error_response
from .models import Job, JobApplication, Rating
from .serializers import (
    JobCreateSerializer, JobListSerializer, JobDetailSerializer,
    JobApplicationSerializer, RatingCreateSerializer, RatingListSerializer
)
from .matching import match_jobs_for_worker
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class JobFeedView(APIView):
    """
    GET /api/jobs/feed/
    Returns top 3 matched open jobs for the authenticated worker.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='jobs_feed',
        summary='Get job feed',
        description='Get top matched jobs for worker',
        tags=['Jobs'],
    )
    def get(self, request):
        user = request.user
        if user.role != 'worker':
            return error_response('Job feed is for workers only.', status=403)

        matches = match_jobs_for_worker(user)

        if not matches:
            return success_response({
                'jobs': [],
                'message': 'No matching jobs right now. Check back soon!'
            })

        # Attach computed scores to job objects for serializer
        jobs_data = []
        for match in matches:
            job = match['job']
            serializer = JobListSerializer(job)
            data = serializer.data
            data['match_score'] = match['match_score']
            data['distance_km'] = match['distance_km']
            data['employer_rating'] = match['employer_rating']
            data['score_breakdown'] = match['score_breakdown']
            jobs_data.append(data)

        return success_response({'jobs': jobs_data, 'count': len(jobs_data)})


class JobCreateView(APIView):
    """
    POST /api/jobs/create/
    Employer posts a new job. Called by WhatsApp bot (Node) or app.
    Returns a Squad payment link for escrow deposit.
    """
    permission_classes = [IsAuthenticatedOrInternalSecret]

    @extend_schema(
        operation_id='jobs_create',
        summary='Create job',
        description='Employer posts a new job',
        request=JobCreateSerializer,
        tags=['Jobs'],
    )
    def post(self, request):
        user, err = resolve_user(request)
        if err:
            return err

        if user.role != 'employer':
            return error_response('Only employers can post jobs.', status=403)

        serializer = JobCreateSerializer(data=request.data, context={'request': request, 'user': user})
        if not serializer.is_valid():
            return error_response(serializer.errors)

        job = serializer.save()

        # Generate Squad escrow payment link
    
        from apps.payments.escrow import get_escrow_payment_instructions
        escrow_info = get_escrow_payment_instructions(job)

        return success_response({
            'job_id': str(job.id),
            'title': job.title,
            'pay_per_worker': str(job.pay_per_worker),
            'workers_needed': job.workers_needed,
            'total_escrow_amount': float(job.pay_per_worker) * job.workers_needed,
            'escrow_instructions': escrow_info,
            'message': (
                f"Job posted! Transfer ₦{float(job.pay_per_worker) * job.workers_needed:,.0f} "
                f"to activate matching. Reference: {job.escrow_reference}"
            ),
        }, status=201)

class JobAcceptView(APIView):
    """
    POST /api/jobs/accept/
    Worker accepts a job from their feed.
    Body: { "job_id": "uuid" }
    """
    permission_classes = [IsAuthenticatedOrInternalSecret]

    @extend_schema(
        operation_id='jobs_accept',
        summary='Accept job',
        description='Worker accepts a job',
        tags=['Jobs'],
    )
    def post(self, request):
        user, err = resolve_user(request)
        if err:
            return err
        if user.role != 'worker':
            return error_response('Only workers can accept jobs.', status=403)

        job_id = request.data.get('job_id')
        if not job_id:
            return error_response('job_id is required.')

        job = get_object_or_404(Job, id=job_id)

        if job.status != Job.Status.OPEN:
            return error_response('This job is no longer available.', status=409)

        if not job.escrow_funded:
            return error_response('This job has not been funded yet.', status=409)

        # Prevent double-accept
        if JobApplication.objects.filter(job=job, worker=user).exists():
            return error_response('You have already applied to this job.', status=409)

        with db_transaction.atomic():
            application = JobApplication.objects.create(
                job=job,
                worker=user,
                status=JobApplication.Status.ACCEPTED,
            )

            # Fill job if enough workers accepted
            accepted_count = job.applications.filter(
                status=JobApplication.Status.ACCEPTED
            ).count()
            if accepted_count >= job.workers_needed:
                job.status = Job.Status.IN_PROGRESS
                job.save(update_fields=['status', 'updated_at'])

        # Notify employer async
        from apps.jobs.tasks import notify_employer_worker_accepted
        notify_employer_worker_accepted.delay(str(application.id))

        return success_response({
            'application_id': str(application.id),
            'job_title': job.title,
            'pay': str(job.pay_per_worker),
            'employer_phone': job.employer.phone,
            'location': job.location_area,
            'message': f'Job accepted! Contact employer to confirm start.',
        }, status=201)


class JobCompleteView(APIView):
    """
    POST /api/jobs/complete/
    Employer confirms job is done. Triggers escrow release.
    Body: { "job_id": "uuid", "worker_id": "uuid" }  (worker_id optional if 1 worker)
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='jobs_complete',
        summary='Complete job',
        description='Employer confirms job completion',
        tags=['Jobs'],
    )
    def post(self, request):
        user = request.user
        if user.role != 'employer':
            return error_response('Only employers can confirm job completion.', status=403)

        job_id = request.data.get('job_id')
        if not job_id:
            return error_response('job_id is required.')

        job = get_object_or_404(Job, id=job_id, employer=user)

        if job.status not in [Job.Status.OPEN, Job.Status.IN_PROGRESS, Job.Status.FILLED]:
            return error_response(f'Job cannot be completed from status: {job.status}', status=409)

        worker_id = request.data.get('worker_id')

        with db_transaction.atomic():
            if worker_id:
                applications = job.applications.filter(
                    worker_id=worker_id,
                    status=JobApplication.Status.ACCEPTED,
                )
            else:
                applications = job.applications.filter(
                    status=JobApplication.Status.ACCEPTED,
                )

            if not applications.exists():
                return error_response('No accepted workers found for this job.')

            # Capture IDs BEFORE update so we can count and iterate after
            worker_ids = list(
                applications.values_list('worker_id', flat=True)
            )

            applications.update(
                status=JobApplication.Status.COMPLETED,
                completed_at=timezone.now(),
            )

            job.status = Job.Status.COMPLETED
            job.save(update_fields=['status', 'updated_at'])

            # Release escrow per worker
            from apps.payments.tasks import release_escrow_for_job
            for wid in worker_ids:
                release_escrow_for_job.delay(str(job.id), str(wid))

        return success_response({
            'job_id': str(job.id),
            'status': 'completed',
            'workers_paid': len(worker_ids),
            'message': 'Job confirmed. Payments released.',
        })


class JobDetailView(APIView):
    permission_classes = [IsAuthenticatedOrInternalSecret]

    @extend_schema(
        operation_id='jobs_retrieve',
        summary='Get job details',
        description='Get details for a specific job',
        tags=['Jobs'],
    )
    def get(self, request, job_id):
        job = get_object_or_404(Job, id=job_id)
        return success_response(JobDetailSerializer(job).data)


class MyJobsView(APIView):
    """
    GET /api/jobs/mine/
    Returns jobs for current user — posted jobs for employer, applied jobs for worker.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='my_jobs_list',
        summary='Get my jobs',
        description='Get jobs posted or applied by current user',
        tags=['Jobs'],
    )
    def get(self, request):
        user = request.user
        if user.role == 'employer':
            jobs = Job.objects.filter(employer=user).order_by('-created_at')
            return success_response({
                'jobs': JobListSerializer(jobs, many=True).data,
                'count': jobs.count(),
            })
        else:
            applications = JobApplication.objects.filter(
                worker=user
            ).select_related('job', 'job__employer').order_by('-accepted_at')
            return success_response({
                'applications': JobApplicationSerializer(applications, many=True).data,
                'count': applications.count(),
            })


class RatingCreateView(APIView):
    """
    POST /api/jobs/rate/
    Either side rates the other after a completed job.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='ratings_create',
        summary='Create rating',
        description='Submit rating after job completion',
        request=RatingCreateSerializer,
        tags=['Jobs'],
    )
    def post(self, request):
        serializer = RatingCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        if not serializer.is_valid():
            return error_response(serializer.errors)

        rating = serializer.save()

        # Recalculate score of the rated user
        from apps.scoring.tasks import recalculate_score
        recalculate_score.delay(str(rating.to_user_id))

        return success_response({
            'rating_id': str(rating.id),
            'stars': rating.stars,
            'message': 'Rating submitted. Thank you!',
        }, status=201)


class UserRatingsView(APIView):
    """GET /api/jobs/ratings/<user_id>/ — public rating history for any user."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='user_ratings_list',
        summary='Get user ratings',
        description='Get rating history for a specific user',
        tags=['Jobs'],
    )
    def get(self, request, user_id):
        ratings = Rating.objects.filter(
            to_user_id=user_id
        ).order_by('-created_at')
        from django.db.models import Avg
        avg = ratings.aggregate(avg=Avg('stars'))['avg']
        return success_response({
            'average_rating': round(avg, 2) if avg else None,
            'total_ratings': ratings.count(),
            'ratings': RatingListSerializer(ratings, many=True).data,
        })

class JobEscrowInstructionsView(APIView):
    """
    GET /api/jobs/<job_id>/escrow/
    Returns payment instructions for a job's escrow deposit.
    Employer can view this anytime before the job goes live.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        job = get_object_or_404(Job, id=job_id, employer=request.user)

        if job.escrow_funded:
            return success_response({
                'escrow_funded': True,
                'message': 'Escrow already funded. Job is live.',
                'job_status': job.status,
            })

        from apps.payments.escrow import get_escrow_payment_instructions
        instructions = get_escrow_payment_instructions(job)

        return success_response({
            'escrow_funded': False,
            'job_id': str(job.id),
            'job_title': job.title,
            **instructions,
        })

class JobApplicantsView(APIView):
    """
    GET /api/jobs/<job_id>/applicants/
    Employer sees all workers who accepted their job.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        user = request.user
        if user.role != 'employer':
            return error_response('Only employers can view applicants.', status=403)

        job = get_object_or_404(Job, id=job_id, employer=user)

        applications = job.applications.select_related('worker').filter(
            status__in=[
                JobApplication.Status.ACCEPTED,
                JobApplication.Status.COMPLETED,
            ]
        ).order_by('-accepted_at')

        data = []
        for app in applications:
            worker = app.worker
            data.append({
                'application_id': str(app.id),
                'status': app.status,
                'accepted_at': app.accepted_at,
                'completed_at': app.completed_at,
                'worker': {
                    'id': str(worker.id),
                    'name': worker.full_name or worker.phone,
                    'phone': worker.phone,
                    'skills': worker.skills,
                    'location': worker.location_area,
                    'has_vehicle': worker.has_vehicle,
                    'vehicle_type': worker.vehicle_type,
                }
            })

        return success_response({
            'job_id': str(job.id),
            'job_title': job.title,
            'workers_needed': job.workers_needed,
            'accepted_count': len(data),
            'applicants': data,
        })

class JobFundEscrowView(APIView):
    """
    POST /api/jobs/<job_id>/fund-escrow/
    Employer funds escrow directly from their Kolliq wallet balance.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        user = request.user
        if user.role != 'employer':
            return error_response('Only employers can fund escrow.', status=403)

        job = get_object_or_404(Job, id=job_id, employer=user)

        if job.escrow_funded:
            return error_response('Escrow already funded. Job is live.', status=409)

        wallet = getattr(user, 'wallet', None)
        if not wallet:
            return error_response('Wallet not found.', status=404)

        total_amount = (job.pay_per_worker * job.workers_needed).quantize(Decimal('0.01'))

        if wallet.balance < total_amount:
            return error_response(
                f'Insufficient wallet balance. '
                f'Need ₦{total_amount:,.2f}, have ₦{wallet.balance:,.2f}. '
                f'Please top up your wallet first.',
                status=400,
            )

        try:
            with db_transaction.atomic():
                # Debit employer wallet
                wallet.debit(total_amount)

                # Credit escrow balance
                wallet.escrow_balance += total_amount
                wallet.save(update_fields=['escrow_balance', 'updated_at'])

                # Mark job as funded
                job.escrow_funded = True
                if not job.escrow_reference:
                    job.escrow_reference = str(job.id).replace('-', '')[:12].upper()
                job.save(update_fields=['escrow_funded', 'escrow_reference', 'updated_at'])

                # Record transaction
                from apps.payments.models import Transaction
                Transaction.objects.create(
                    user=user,
                    transaction_type=Transaction.Type.ESCROW_HOLD,
                    amount=total_amount,
                    status=Transaction.Status.SUCCESS,
                    job=job,
                    description=f'Escrow funded from wallet for: {job.title}',
                    metadata={
                        'job_id': str(job.id),
                        'pay_per_worker': str(job.pay_per_worker),
                        'workers_needed': job.workers_needed,
                        'funded_from': 'wallet',
                    }
                )

        except ValueError as e:
            return error_response(str(e), status=400)
        except Exception as e:
            logger.error(f"Fund escrow failed: job={job_id} user={user.id} error={e}")
            return error_response('Failed to fund escrow. Please try again.', status=500)

        # Trigger worker matching notifications now job is live
        from apps.jobs.tasks import trigger_job_matching_notifications
        trigger_job_matching_notifications.delay(str(job.id))

        return success_response({
            'job_id': str(job.id),
            'job_title': job.title,
            'escrow_funded': True,
            'amount_held': str(total_amount),
            'wallet_balance': str(wallet.balance),
            'message': f'₦{total_amount:,.2f} held in escrow. Job is now live and workers are being notified.',
        })