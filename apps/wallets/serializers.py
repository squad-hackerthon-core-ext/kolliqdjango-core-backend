from rest_framework import serializers
from .models import Wallet


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = [
            'id',
            'squad_account_number',
            'squad_account_name',
            'squad_bank_name',
            'balance',
            'escrow_balance',
            'savings_balance',
            'squad_creation_status',
            'created_at',
        ]
        read_only_fields = fields


class WalletPublicSerializer(serializers.ModelSerializer):
    """
    Safe to share with employers / partners.
    No balance info — just the account number for payment instructions.
    """
    class Meta:
        model = Wallet
        fields = [
            'squad_account_number',
            'squad_account_name',
            'squad_bank_name',
            'squad_creation_status',
        ]
        read_only_fields = fields