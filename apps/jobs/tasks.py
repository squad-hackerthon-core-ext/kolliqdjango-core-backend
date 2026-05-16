from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task
def notify_employer_worker_accepted(application_id: str):
    from apps.jobs.models import JobApplication
    from services.notifications import notify_employer_acceptance
    try:
        app = JobApplication.objects.select_related(
            'job', 'job__employer', 'worker'
        ).get(id=application_id)
        notify_employer_acceptance(app)
    except JobApplication.DoesNotExist:
        logger.error(f"Application {application_id} not found")
    except Exception as e:
        logger.error(f"Employer notification failed: {e}")


@shared_task
def trigger_job_matching_notifications(job_id: str):
    """
    After escrow is funded, find matching workers and notify them via SMS.
    Called once per job when it goes live.
    """
    from apps.jobs.models import Job
    from apps.users.models import User
    from services.africas_talking import ATService

    try:
        job = Job.objects.select_related('employer').get(id=job_id)
    except Job.DoesNotExist:
        logger.error(f"trigger_job_matching_notifications: Job {job_id} not found")
        return

    try:
        # Filter in DB — no is_flagged field on User model
        candidate_workers = User.objects.filter(
            role='worker',
            is_active=True,
        )

        # Skill filter — done in Python since skills is a JSONField
        if job.skill_required != 'other':
            candidate_workers = [
                w for w in candidate_workers
                if job.skill_required in (w.skills or [])
            ]
        else:
            candidate_workers = list(candidate_workers[:50])

        at = ATService()
        notified = 0

        for worker in candidate_workers[:20]:
            message = (
                f"Kolliq: New job match! {job.title} in {job.location_area}. "
                f"Pay: ₦{job.pay_per_worker}. "
                f"Open app or dial *347*123# to accept."
            )
            try:
                result = at.send_sms(worker.phone, message)
                if result.get('success'):
                    notified += 1
            except Exception as e:
                logger.warning(f"SMS failed for worker {worker.phone}: {e}")
                continue

        logger.info(f"Job {job_id} — notified {notified} workers")

    except Exception as e:
        logger.error(f"trigger_job_matching_notifications failed for job {job_id}: {e}")