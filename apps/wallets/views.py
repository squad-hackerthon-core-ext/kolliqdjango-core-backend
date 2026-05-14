import logging
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from kolliq.permissions import IsAuthenticatedOrInternalSecret, resolve_user
from drf_spectacular.utils import extend_schema
from kolliq.utils import success_response, error_response
from .models import Wallet
from apps.wallets.serializers import (
    NigerianBankSerializer,
    BankAccountVerifySerializer,
    BankAccountSaveSerializer,
    BankAccountDetailSerializer,
)


logger = logging.getLogger(__name__)
 




class WalletDetailView(APIView):
    permission_classes = [IsAuthenticatedOrInternalSecret]

    @extend_schema(
        operation_id='wallet_detail_retrieve',
        summary='Get wallet details',
        description='Get current user\'s wallet information',
        tags=['Wallets'],
    )
    def get(self, request):
        user, err = resolve_user(request)
        if err:
            return err

        try:
            wallet = user.wallet
        except Wallet.DoesNotExist:
            return error_response('Wallet not yet created. Please try again shortly.', status=404)

        return success_response({
            'account_number': wallet.squad_account_number,
            'account_name': wallet.squad_account_name,
            'bank_name': wallet.squad_bank_name,
            'balance': str(wallet.balance),
            'escrow_balance': str(wallet.escrow_balance),
            'savings_balance': str(wallet.savings_balance),
            'wallet_ready': wallet.squad_creation_status == 'created',
        })

class NigerianBankListView(APIView):
    """
    GET /wallets/banks/
    Returns the full list of Nigerian banks for frontend dropdowns.
    No auth required — public endpoint.
    """
    permission_classes = []
 
    def get(self, request):
        serializer = NigerianBankSerializer(NIGERIAN_BANKS, many=True)
        return Response({
            'count': len(NIGERIAN_BANKS),
            'banks': serializer.data,
        })
 
 
class BankAccountDetailView(APIView):
    """
    GET /wallets/bank-account/
    Returns the authenticated user's currently saved bank account details.
    """
    permission_classes = [IsAuthenticated]
 
    def get(self, request):
        wallet = getattr(request.user, 'wallet', None)
        if not wallet:
            return Response(
                {'detail': 'Wallet not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
 
        if not wallet.bank_account_number:
            return Response({
                'has_bank_account': False,
                'detail': 'No bank account saved yet.',
            })
 
        serializer = BankAccountDetailSerializer({
            'bank_account_number':    wallet.bank_account_number,
            'bank_code':              wallet.bank_code,
            'bank_name':              wallet.bank_name,
            'bank_account_name':      wallet.bank_account_name,
            'bank_account_verified':  wallet.bank_account_verified,
            'bank_account_updated_at': wallet.bank_account_updated_at,
        })
 
        return Response({
            'has_bank_account': True,
            **serializer.data,
        })
 
 
class BankAccountVerifyView(APIView):
    """
    POST /wallets/bank-account/verify/
    Body: { "bank_code": "058", "account_number": "0123456789" }
 
    Hits Squad's account lookup API and returns the account name.
    Does NOT save anything — frontend must confirm then call /save/.
    """
    permission_classes = [IsAuthenticated]
 
    def post(self, request):
        serializer = BankAccountVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
 
        bank_code      = serializer.validated_data['bank_code']
        account_number = serializer.validated_data['account_number']
        bank_name      = get_bank_name(bank_code)
 
        try:
            result = verify_bank_account(bank_code, account_number)
        except ValueError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except Exception as e:
            logger.error(f"Bank verify error for user {request.user.id}: {e}")
            return Response(
                {'detail': 'Bank verification service unavailable. Please try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
 
        return Response({
            'verified':       True,
            'account_name':   result['account_name'],
            'account_number': account_number,
            'bank_code':      bank_code,
            'bank_name':      bank_name,
            'message': (
                f"Account found: {result['account_name']}. "
                f"Please confirm this is correct before saving."
            ),
        })
 
 
class BankAccountSaveView(APIView):
    """
    POST /wallets/bank-account/save/
    Body:
    {
        "bank_code":         "058",
        "account_number":    "0123456789",
        "bank_account_name": "JOHN DOE",   ← as returned by /verify/
        "confirm":           true           ← user must explicitly confirm
    }
 
    Saves bank details to the user's wallet. Ready for payouts.
    """
    permission_classes = [IsAuthenticated]
 
    def post(self, request):
        serializer = BankAccountSaveSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
 
        data = serializer.validated_data
 
        wallet = getattr(request.user, 'wallet', None)
        if not wallet:
            return Response(
                {'detail': 'Wallet not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
 
        bank_name = get_bank_name(data['bank_code'])
 
        wallet.bank_account_number   = data['account_number']
        wallet.bank_code             = data['bank_code']
        wallet.bank_name             = bank_name
        wallet.bank_account_name     = data['bank_account_name']
        wallet.bank_account_verified = True
        wallet.bank_account_updated_at = timezone.now()
 
        wallet.save(update_fields=[
            'bank_account_number',
            'bank_code',
            'bank_name',
            'bank_account_name',
            'bank_account_verified',
            'bank_account_updated_at',
            'updated_at',
        ])
 
        logger.info(
            f"Bank account saved: user={request.user.id} "
            f"bank={bank_name} acct=***{data['account_number'][-4:]}"
        )
 
        return Response({
            'success':        True,
            'bank_name':      bank_name,
            'account_number': data['account_number'],
            'account_name':   data['bank_account_name'],
            'message':        'Bank account saved successfully. You can now receive payouts.',
        }, status=status.HTTP_200_OK)
