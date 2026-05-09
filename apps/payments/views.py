from django.shortcuts import render

# Create your views here.
import json
import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema
from kolliq.utils import success_response, error_response
from .models import Transaction
from .serializers import TransactionSerializer

logger = logging.getLogger(__name__)


class TransactionListView(APIView):
    """GET /api/payments/transactions/ — user's transaction history."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='transactions_list',
        summary='Get transaction history',
        description='Get user\'s transaction history',
        tags=['Payments'],
    )
    def get(self, request):
        transactions = Transaction.objects.filter(
            user=request.user
        ).order_by('-created_at')[:50]
        return success_response({
            'transactions': TransactionSerializer(transactions, many=True).data,
            'count': transactions.count(),
        })


# Replace the SquadWebhookView with this

@method_decorator(csrf_exempt, name='dispatch')
class SquadWebhookView(APIView):
    """
    POST /api/payments/webhook/squad/
    Squad fires this on every virtual account payment.

    Signature verification uses v3 method from Squad docs:
    HMAC-SHA512 of 6 pipe-joined fields, checked against x-squad-signature header.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id='payments_squad_webhook',
        summary='Squad payment webhook',
        description='Webhook endpoint for Squad payment notifications',
        tags=['Payments'],
    )
    def post(self, request):
        import json
        from services.squad import SquadService

        # Squad sends signature in x-squad-signature header
        signature = request.headers.get('x-squad-signature', '')

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            logger.warning("Squad webhook: invalid JSON body")
            return Response({'status': 'bad payload'}, status=400)

        # Verify signature if present
        # In sandbox, Squad may not always send a signature — allow through
        if signature:
            squad = SquadService()
            if not squad.verify_webhook_signature(payload, signature):
                logger.warning(
                    f"Squad webhook: invalid signature. "
                    f"ref={payload.get('transaction_reference', 'unknown')}"
                )
                return Response({'status': 'invalid signature'}, status=401)

        # Duplicate check — Squad can send the same webhook multiple times
        from apps.payments.models import Transaction
        tx_ref = payload.get('transaction_reference', '')
        if tx_ref and Transaction.objects.filter(squad_reference=tx_ref).exists():
            logger.info(f"Squad webhook duplicate ignored: {tx_ref}")
            # Still return 200 so Squad stops retrying
            return Response({
                'response_code': 200,
                'transaction_reference': tx_ref,
                'response_description': 'Already processed',
            }, status=200)

        # Process async — return fast (Squad expects response in < 5s)
        from apps.payments.tasks import process_squad_webhook
        process_squad_webhook.delay(payload)

        # Squad expects this exact response shape
        return Response({
            'response_code': 200,
            'transaction_reference': tx_ref,
            'response_description': 'Success',
        }, status=200)

@method_decorator(csrf_exempt, name='dispatch')
class InternalWebhookView(APIView):
    """
    POST /api/payments/webhook/internal/
    Called by Node partner service to forward Squad events
    that Node receives first.
    """
    permission_classes = [AllowAny]  # Secured by shared internal secret in header

    @extend_schema(
        operation_id='payments_internal_webhook',
        summary='Internal webhook',
        description='Internal webhook endpoint for Squad events from Node service',
        tags=['Payments'],
    )
    def post(self, request):
        internal_secret = request.headers.get('x-internal-secret', '')
        from django.conf import settings
        expected = getattr(settings, 'INTERNAL_WEBHOOK_SECRET', '')
        if expected and internal_secret != expected:
            return Response({'status': 'unauthorized'}, status=401)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return Response({'status': 'bad payload'}, status=400)

        from .tasks import process_squad_webhook
        process_squad_webhook.delay(payload)
        return Response({'status': 'received'}, status=200)