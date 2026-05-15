from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Wallet , WithdrawalRequest
from services.squad import SquadService, SquadAPIError
from django.utils import timezone


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'squad_account_number', 'balance',
        'escrow_balance', 'squad_creation_status', 'created_at'
    ]
    list_filter = ['squad_creation_status']
    search_fields = ['user__phone', 'squad_account_number', 'user__full_name']
    readonly_fields = ['id', 'created_at', 'updated_at']

    def get_user_phone(self, obj):
        return obj.user.phone
    get_user_phone.short_description = 'User Phone'

    

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'get_user_phone', 'amount', 'bank_name',
        'bank_account_number', 'status', 'created_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['wallet__user__phone', 'bank_account_number', 'bank_account_name']
    readonly_fields = [
        'id', 'wallet', 'amount', 'bank_account_number', 'bank_code',
        'bank_name', 'bank_account_name', 'squad_reference',
        'reviewed_by', 'reviewed_at', 'created_at', 'updated_at',
    ]
    actions = ['approve_withdrawals', 'reject_withdrawals']

    def get_user_phone(self, obj):
        return obj.wallet.user.phone
    get_user_phone.short_description = 'User Phone'

    @admin.action(description='✅ Approve & pay out selected withdrawals')
    def approve_withdrawals(self, request, queryset):
        pending = queryset.filter(status=WithdrawalRequest.Status.PENDING)
        if not pending.exists():
            self.message_user(request, 'No pending withdrawals selected.', level='warning')
            return

        squad = SquadService()
        success_count = 0
        fail_count = 0

        for withdrawal in pending:
            try:
                withdrawal.status = WithdrawalRequest.Status.PROCESSING
                withdrawal.reviewed_by = request.user
                withdrawal.reviewed_at = timezone.now()
                withdrawal.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])

                result = squad.initiate_transfer(
                    amount_naira=withdrawal.amount,
                    bank_code=withdrawal.bank_code,
                    account_number=withdrawal.bank_account_number,
                    account_name=withdrawal.bank_account_name,
                    reference_suffix=str(withdrawal.id).replace('-', '')[:20],
                    narration=f'Kolliq withdrawal {str(withdrawal.id)[:8]}',
                )

                withdrawal.status = WithdrawalRequest.Status.COMPLETED
                withdrawal.squad_reference = result.get('full_reference', '')
                withdrawal.save(update_fields=['status', 'squad_reference', 'updated_at'])
                success_count += 1

            except SquadAPIError as e:
                # Refund wallet — transfer failed
                withdrawal.wallet.credit(withdrawal.amount)
                withdrawal.status = WithdrawalRequest.Status.FAILED
                withdrawal.rejection_reason = str(e)
                withdrawal.save(update_fields=['status', 'rejection_reason', 'updated_at'])
                fail_count += 1

        self.message_user(
            request,
            f'{success_count} withdrawal(s) paid out successfully. {fail_count} failed (wallet refunded).',
            level='success' if fail_count == 0 else 'warning',
        )

    @admin.action(description='❌ Reject selected withdrawals (refund wallet)')
    def reject_withdrawals(self, request, queryset):
        pending = queryset.filter(status=WithdrawalRequest.Status.PENDING)
        if not pending.exists():
            self.message_user(request, 'No pending withdrawals selected.', level='warning')
            return

        for withdrawal in pending:
            # Refund the wallet
            withdrawal.wallet.credit(withdrawal.amount)
            withdrawal.status = WithdrawalRequest.Status.REJECTED
            withdrawal.rejection_reason = f'Rejected by {request.user.phone}'
            withdrawal.reviewed_by = request.user
            withdrawal.reviewed_at = timezone.now()
            withdrawal.save(update_fields=[
                'status', 'rejection_reason',
                'reviewed_by', 'reviewed_at', 'updated_at',
            ])

        self.message_user(
            request,
            f'{pending.count()} withdrawal(s) rejected and wallets refunded.',
        )
