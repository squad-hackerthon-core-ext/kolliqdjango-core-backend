from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from kolliq.utils import success_response, error_response
from .models import Wallet


class WalletDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='wallet_detail_retrieve',
        summary='Get wallet details',
        description='Get current user\'s wallet information',
        tags=['Wallets'],
    )
    def get(self, request):
        try:
            wallet = request.user.wallet
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