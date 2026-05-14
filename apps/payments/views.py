import json
import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from kolliq.utils import success_response, error_response
from .models import Transaction
from .serializers import TransactionSerializer

logger = logging.getLogger(__name__)


class TransactionListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='transactions_list',
        summary='Get transaction history',
        description='Returns the last 50 transactions for the authenticated user, ordered by most recent.',
        request=None,
        responses={
            200: OpenApiResponse(response=TransactionSerializer, description='Transaction history.'),
            401: OpenApiResponse(description='Not authenticated.'),
        },
        examples=[
            OpenApiExample(
                'Transaction list response',
                value={
                    'transactions': [
                        {'id': 'txn123', 'amount': '5000.00', 'transaction_type': 'credit', 'status': 'success'}
                    ],
                    'count': 1,
                },
                response_only=True,
            ),
        ],
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


@method_decorator(csrf_exempt, name='dispatch')
class SquadWebhookView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id='payments_squad_webhook',
        summary='Squad payment webhook',
        description=(
            'Webhook endpoint called by Squad on every virtual account payment. '
            'Signature verification uses HMAC-SHA512 of pipe-joined fields. '
            'Duplicate events are safely ignored. Processing is async.'
        ),
        request=None,
        responses={
            200: OpenApiResponse(description='Event received and queued for processing.'),
            400: OpenApiResponse(description='Invalid JSON payload.'),
            401: OpenApiResponse(description='Invalid webhook signature.'),
        },
        examples=[
            OpenApiExample(
                'Squad webhook response',
                value={'response_code': 200, 'transaction_reference': 'TXN-123', 'response_description': 'Success'},
                response_only=True,
            ),
        ],
        tags=['Payments'],
    )
    def post(self, request):
        from services.squad import SquadService

        signature = request.headers.get('x-squad-encrypted-body', '')

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            logger.warning("Squad webhook: invalid JSON body")
            return Response({'status': 'bad payload'}, status=400)

        if signature:
            squad = SquadService()
            if not squad.verify_webhook_signature(payload, signature):
                logger.warning(
                    f"Squad webhook: invalid signature. "
                    f"ref={payload.get('transaction_reference', 'unknown')}"
                )
                return Response({'status': 'invalid signature'}, status=401)

        from apps.payments.models import Transaction
        tx_ref = payload.get('transaction_reference', '')
        if tx_ref and Transaction.objects.filter(squad_reference=tx_ref).exists():
            logger.info(f"Squad webhook duplicate ignored: {tx_ref}")
            return Response({
                'response_code': 200,
                'transaction_reference': tx_ref,
                'response_description': 'Already processed',
            }, status=200)

        from apps.payments.tasks import process_squad_webhook
        process_squad_webhook.delay(payload)

        return Response({
            'response_code': 200,
            'transaction_reference': tx_ref,
            'response_description': 'Success',
        }, status=200)


@method_decorator(csrf_exempt, name='dispatch')
class InternalWebhookView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id='payments_internal_webhook',
        summary='Internal webhook',
        description=(
            'Internal webhook called by the Node partner service to forward Squad events. '
            'Secured by a shared secret in the x-internal-secret header.'
        ),
        request=None,
        responses={
            200: OpenApiResponse(description='Event received.'),
            400: OpenApiResponse(description='Invalid JSON payload.'),
            401: OpenApiResponse(description='Invalid or missing internal secret.'),
        },
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