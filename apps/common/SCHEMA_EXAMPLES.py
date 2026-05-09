"""
Example: Implementing Schema Documentation in Your Serializers and ViewSets

This file shows practical examples of how to use drf-spectacular schema
decorators in your actual application code.
"""

# ============================================================================
# EXAMPLE 1: Fully Documented Transaction ViewSet
# ============================================================================

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from apps.payments.models import Transaction
from apps.payments.serializers import TransactionSerializer
from apps.common.rls import RLSPermissionMixin


@extend_schema_view(
    list=extend_schema(
        operation_id='transactions_list',
        summary='List transactions',
        description='Retrieve all transactions for the authenticated user with pagination and filtering.',
        parameters=[
            OpenApiParameter(
                name='transaction_type',
                description='Filter by transaction type',
                enum=['credit', 'debit', 'escrow_hold', 'escrow_release'],
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='status',
                description='Filter by transaction status',
                enum=['pending', 'success', 'failed', 'reversed'],
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page',
                description='Page number',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page_size',
                description='Number of results per page',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            ),
        ],
        tags=['Transactions'],
    ),
    create=extend_schema(
        operation_id='transactions_create',
        summary='Create transaction',
        description='Create a new transaction (admin only)',
        tags=['Transactions'],
    ),
    retrieve=extend_schema(
        operation_id='transactions_retrieve',
        summary='Get transaction',
        description='Retrieve a specific transaction by ID',
        tags=['Transactions'],
    ),
)
class TransactionViewSet(RLSPermissionMixin, viewsets.ModelViewSet):
    """
    Transaction management.
    
    Users can view their own transactions. Admins can create and manage
    all transactions in the system.
    """
    serializer_class = TransactionSerializer
    queryset = Transaction.objects.all()
    
    @extend_schema(
        operation_id='transactions_summary',
        summary='Get transaction summary',
        description='Get aggregated transaction statistics for the user',
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'total_credits': {'type': 'number', 'format': 'decimal'},
                    'total_debits': {'type': 'number', 'format': 'decimal'},
                    'transaction_count': {'type': 'integer'},
                    'pending_count': {'type': 'integer'},
                }
            }
        },
        tags=['Transactions'],
    )
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get transaction summary stats."""
        pass


# ============================================================================
# EXAMPLE 2: Fully Documented Job ViewSet with Complex Actions
# ============================================================================

@extend_schema_view(
    list=extend_schema(
        operation_id='jobs_list',
        summary='List available jobs',
        description='Retrieve jobs available in your area with filtering by skill and location',
        parameters=[
            OpenApiParameter(
                name='skill_required',
                description='Filter by required skill',
                enum=['delivery', 'cooking', 'construction', 'market', 'cleaning', 'security', 'teaching'],
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='location_city',
                description='Filter by city',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='status',
                description='Filter by job status',
                enum=['open', 'filled', 'in_progress', 'completed'],
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='min_pay',
                description='Minimum pay per worker',
                type=OpenApiTypes.DECIMAL,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='max_pay',
                description='Maximum pay per worker',
                type=OpenApiTypes.DECIMAL,
                location=OpenApiParameter.QUERY,
            ),
        ],
        tags=['Jobs'],
    ),
    create=extend_schema(
        operation_id='jobs_create',
        summary='Post a new job',
        description='Create a new job posting (employers only)',
        tags=['Jobs'],
    ),
    retrieve=extend_schema(
        operation_id='jobs_retrieve',
        summary='Get job details',
        description='Retrieve full details of a specific job',
        tags=['Jobs'],
    ),
)
class JobViewSet(RLSPermissionMixin, viewsets.ModelViewSet):
    """
    Job management endpoints.
    
    Users can browse available jobs and apply. Employers can post and
    manage their job listings.
    """
    serializer_class = None  # Set in actual implementation
    queryset = None  # Set in actual implementation
    
    @extend_schema(
        operation_id='jobs_apply',
        summary='Apply for a job',
        description='Submit an application for a specific job',
        request=None,
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'format': 'uuid'},
                    'status': {'type': 'string'},
                    'applied_at': {'type': 'string', 'format': 'date-time'},
                }
            }
        },
        tags=['Jobs'],
    )
    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        """Apply for this job."""
        pass
    
    @extend_schema(
        operation_id='jobs_nearby',
        summary='Find nearby jobs',
        description='Find jobs near your current location',
        parameters=[
            OpenApiParameter(
                name='lat',
                description='Your latitude',
                type=OpenApiTypes.DECIMAL,
                required=True,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='lng',
                description='Your longitude',
                type=OpenApiTypes.DECIMAL,
                required=True,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='radius_km',
                description='Search radius in kilometers',
                type=OpenApiTypes.DECIMAL,
                location=OpenApiParameter.QUERY,
            ),
        ],
        tags=['Jobs'],
    )
    @action(detail=False, methods=['get'])
    def nearby(self, request):
        """Get nearby jobs."""
        pass
    
    @extend_schema(
        operation_id='jobs_accept_application',
        summary='Accept job application',
        description='Employer accepts a worker application',
        request={
            'type': 'object',
            'properties': {
                'application_id': {'type': 'string', 'format': 'uuid'}
            }
        },
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string'},
                    'accepted_at': {'type': 'string', 'format': 'date-time'},
                }
            }
        },
        tags=['Jobs'],
    )
    @action(detail=True, methods=['post'])
    def accept_application(self, request, pk=None):
        """Accept a job application."""
        pass


# ============================================================================
# EXAMPLE 3: Wallet ViewSet with Balance and Transactions
# ============================================================================

@extend_schema_view(
    retrieve=extend_schema(
        operation_id='wallet_retrieve',
        summary='Get wallet details',
        description='Retrieve wallet information including balances',
        tags=['Wallets'],
    ),
)
class WalletViewSet(RLSPermissionMixin, viewsets.ReadOnlyModelViewSet):
    """
    Wallet management.
    
    View wallet balance, transaction history, and perform wallet operations.
    """
    serializer_class = None  # Set in actual implementation
    queryset = None  # Set in actual implementation
    
    @extend_schema(
        operation_id='wallet_balance',
        summary='Get wallet balances',
        description='Retrieve current balance breakdown',
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'balance': {'type': 'number', 'format': 'decimal'},
                    'escrow_balance': {'type': 'number', 'format': 'decimal'},
                    'savings_balance': {'type': 'number', 'format': 'decimal'},
                    'total': {'type': 'number', 'format': 'decimal'},
                }
            }
        },
        tags=['Wallets'],
    )
    @action(detail=False, methods=['get'])
    def balance(self, request):
        """Get wallet balance."""
        pass
    
    @extend_schema(
        operation_id='wallet_transactions',
        summary='Get wallet transaction history',
        description='Retrieve transaction history with pagination',
        parameters=[
            OpenApiParameter(
                name='limit',
                description='Number of transactions to return',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='offset',
                description='Offset for pagination',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            ),
        ],
        tags=['Wallets'],
    )
    @action(detail=False, methods=['get'])
    def transactions(self, request):
        """Get transaction history."""
        pass


# ============================================================================
# EXAMPLE 4: Loan ViewSet with Application Logic
# ============================================================================

@extend_schema_view(
    list=extend_schema(
        operation_id='loans_list',
        summary='List user loans',
        description='Retrieve all loans for the authenticated user',
        tags=['Financial Services'],
    ),
    create=extend_schema(
        operation_id='loans_apply',
        summary='Apply for a loan',
        description='Submit a loan application',
        tags=['Financial Services'],
    ),
)
class LoanViewSet(RLSPermissionMixin, viewsets.ModelViewSet):
    """
    Loan management.
    
    Users can view their loans and apply for new loans based on their
    economic identity score.
    """
    serializer_class = None  # Set in actual implementation
    queryset = None  # Set in actual implementation
    
    @extend_schema(
        operation_id='loans_repay',
        summary='Make loan repayment',
        description='Submit a loan repayment',
        request={
            'type': 'object',
            'properties': {
                'amount': {'type': 'number', 'format': 'decimal'},
            },
            'required': ['amount']
        },
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'transaction_id': {'type': 'string', 'format': 'uuid'},
                    'amount_paid': {'type': 'number', 'format': 'decimal'},
                    'outstanding_balance': {'type': 'number', 'format': 'decimal'},
                }
            }
        },
        tags=['Financial Services'],
    )
    @action(detail=True, methods=['post'])
    def repay(self, request, pk=None):
        """Make a loan repayment."""
        pass
    
    @extend_schema(
        operation_id='loans_schedule',
        summary='Get repayment schedule',
        description='Retrieve the loan repayment schedule',
        tags=['Financial Services'],
    )
    @action(detail=True, methods=['get'])
    def schedule(self, request, pk=None):
        """Get repayment schedule."""
        pass


# ============================================================================
# IMPLEMENTATION CHECKLIST
# ============================================================================

"""
When implementing a new ViewSet, use this checklist:

✅ Add @extend_schema_view decorator with descriptions for:
   - list: What records are returned, filtering options
   - create: What fields required, validation rules
   - retrieve: Single record details
   - update: Which fields can be updated
   - destroy: Deletion rules, cascading effects

✅ For custom @action methods, add @extend_schema with:
   - operation_id: Unique identifier (e.g., 'jobs_apply')
   - summary: One-line description
   - description: Detailed explanation
   - parameters: Query params, path params
   - request: Request body schema
   - responses: Response schema with status code

✅ Document all possible status codes:
   - 200: Success
   - 201: Created
   - 204: No content
   - 400: Validation error
   - 401: Unauthorized
   - 403: Forbidden
   - 404: Not found

✅ Use OpenApiParameter for query parameters:
   - Set type, required, enum choices
   - Add clear descriptions
   - Include examples

✅ Group related endpoints with tags:
   - All transaction endpoints: tags=['Transactions']
   - All job endpoints: tags=['Jobs']

✅ Add field descriptions in serializers:
   - Use help_text parameter
   - This automatically appears in schema
"""
