from unittest.mock import Mock
from decimal import Decimal
from django.test import TestCase
from rest_framework.serializers import ModelSerializer
from apps.wallets.serializers import WalletSerializer, WalletPublicSerializer


class TestWalletSerializer(TestCase):
    """Test WalletSerializer without hitting the database."""

    def setUp(self):
        """Create mock wallet object."""
        self.mock_wallet = Mock()
        self.mock_wallet.id = '660e8400-e29b-41d4-a716-446655440001'
        self.mock_wallet.squad_account_number = '0700123456789'
        self.mock_wallet.squad_account_name = 'Tunde Adeyemi'
        self.mock_wallet.squad_bank_name = 'GTBank'
        self.mock_wallet.balance = Decimal('5000.00')
        self.mock_wallet.escrow_balance = Decimal('2000.00')
        self.mock_wallet.savings_balance = Decimal('1000.00')
        self.mock_wallet.squad_creation_status = 'created'
        self.mock_wallet.created_at = '2026-05-11T10:30:00Z'

    def test_serializer_fields_are_defined(self):
        """Test that WalletSerializer has all expected fields."""
        serializer = WalletSerializer()
        expected_fields = [
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
        for field in expected_fields:
            self.assertIn(field, serializer.fields)

    def test_serializer_all_fields_are_read_only(self):
        """Test that all WalletSerializer fields are read-only."""
        serializer = WalletSerializer()
        for field_name, field in serializer.fields.items():
            self.assertTrue(
                field.read_only,
                f"Field '{field_name}' should be read-only"
            )

    def test_serializer_meta_model_is_wallet(self):
        """Test that WalletSerializer uses Wallet model."""
        from apps.wallets.models import Wallet
        self.assertEqual(WalletSerializer.Meta.model, Wallet)

    def test_serializer_rejects_write_attempts(self):
        """Test that serializer rejects write operations on read-only fields."""
        data = {
            'balance': '999999.99',
            'squad_account_number': '0700999999999',
        }
        serializer = WalletSerializer(data=data)
        # All fields are read-only, so no valid data can be written
        self.assertFalse(serializer.is_valid())

    def test_serializer_has_correct_model_serializer_base(self):
        """Test that WalletSerializer extends ModelSerializer."""
        self.assertTrue(issubclass(WalletSerializer, ModelSerializer))

    def test_serializer_includes_balance_fields(self):
        """Test that balance-related fields are present."""
        serializer = WalletSerializer()
        balance_fields = ['balance', 'escrow_balance', 'savings_balance']
        for field in balance_fields:
            self.assertIn(field, serializer.fields)

    def test_serializer_includes_account_info_fields(self):
        """Test that account information fields are present."""
        serializer = WalletSerializer()
        account_fields = [
            'squad_account_number',
            'squad_account_name',
            'squad_bank_name'
        ]
        for field in account_fields:
            self.assertIn(field, serializer.fields)

    def test_serializer_includes_status_field(self):
        """Test that status field is present."""
        serializer = WalletSerializer()
        self.assertIn('squad_creation_status', serializer.fields)

    def test_serializer_includes_id_and_timestamp(self):
        """Test that id and created_at fields are present."""
        serializer = WalletSerializer()
        self.assertIn('id', serializer.fields)
        self.assertIn('created_at', serializer.fields)


class TestWalletPublicSerializer(TestCase):
    """Test WalletPublicSerializer without hitting the database."""

    def setUp(self):
        """Create mock wallet object."""
        self.mock_wallet = Mock()
        self.mock_wallet.squad_account_number = '0700123456789'
        self.mock_wallet.squad_account_name = 'Tunde Adeyemi'
        self.mock_wallet.squad_bank_name = 'GTBank'
        self.mock_wallet.squad_creation_status = 'created'

    def test_serializer_includes_only_public_fields(self):
        """Test that WalletPublicSerializer has only safe fields."""
        serializer = WalletPublicSerializer()
        expected_fields = [
            'squad_account_number',
            'squad_account_name',
            'squad_bank_name',
            'squad_creation_status',
        ]
        self.assertEqual(set(serializer.fields.keys()), set(expected_fields))

    def test_serializer_excludes_sensitive_fields(self):
        """Test that balance fields are NOT in public serializer."""
        serializer = WalletPublicSerializer()
        sensitive_fields = [
            'balance',
            'escrow_balance',
            'savings_balance',
            'id',
            'created_at'
        ]
        for field in sensitive_fields:
            self.assertNotIn(field, serializer.fields)

    def test_serializer_all_fields_are_read_only(self):
        """Test that all WalletPublicSerializer fields are read-only."""
        serializer = WalletPublicSerializer()
        for field_name, field in serializer.fields.items():
            self.assertTrue(
                field.read_only,
                f"Field '{field_name}' should be read-only"
            )

    def test_serializer_meta_model_is_wallet(self):
        """Test that WalletPublicSerializer uses Wallet model."""
        from apps.wallets.models import Wallet
        self.assertEqual(WalletPublicSerializer.Meta.model, Wallet)

    def test_serializer_rejects_write_attempts(self):
        """Test that serializer rejects write operations."""
        data = {
            'squad_account_number': '0700999999999',
            'squad_account_name': 'Fake Name',
        }
        serializer = WalletPublicSerializer(data=data)
        # All fields are read-only, so no valid data can be written
        self.assertFalse(serializer.is_valid())

    def test_serializer_has_correct_model_serializer_base(self):
        """Test that WalletPublicSerializer extends ModelSerializer."""
        self.assertTrue(issubclass(WalletPublicSerializer, ModelSerializer))

    def test_public_serializer_is_safe_for_employers(self):
        """Test that public serializer only exposes account info, no balances."""
        serializer = WalletPublicSerializer()
        # Should have account info
        self.assertIn('squad_account_number', serializer.fields)
        self.assertIn('squad_account_name', serializer.fields)
        # Should NOT have sensitive info
        self.assertNotIn('balance', serializer.fields)
        self.assertNotIn('escrow_balance', serializer.fields)
