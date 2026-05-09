"""
Schema utilities for drf-spectacular documentation.

This module provides decorators and helpers for enriching API documentation
with better descriptions, examples, and type information.
"""

from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiExample,
    OpenApiResponse,
)
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers


# ============================================================================
# Common Parameter Definitions
# ============================================================================

PAGINATION_PARAMS = [
    OpenApiParameter(
        name='page',
        description='Page number for pagination',
        required=False,
        type=OpenApiTypes.INT,
        location=OpenApiParameter.QUERY,
    ),
    OpenApiParameter(
        name='page_size',
        description='Number of results per page',
        required=False,
        type=OpenApiTypes.INT,
        location=OpenApiParameter.QUERY,
    ),
]

FILTER_PARAMS = [
    OpenApiParameter(
        name='search',
        description='Search by title, description, or other fields',
        required=False,
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
    ),
    OpenApiParameter(
        name='ordering',
        description='Ordering field (-field for descending)',
        required=False,
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
    ),
]


# ============================================================================
# Decorator Factories
# ============================================================================

def paginated_list_schema(
    operation_id,
    description,
    response_serializer,
    parameters=None,
):
    """
    Factory for paginated list endpoints.
    
    Usage:
        @paginated_list_schema(
            'transactions_list',
            'List user transactions',
            TransactionSerializer(many=True),
            parameters=[...]
        )
    """
    params = PAGINATION_PARAMS + (parameters or [])
    return extend_schema(
        operation_id=operation_id,
        description=description,
        parameters=params,
        responses=response_serializer,
        tags=['Transactions'],
    )


def create_schema(
    operation_id,
    description,
    request_serializer,
    response_serializer=None,
    examples=None,
):
    """
    Factory for create endpoints.
    
    Usage:
        @create_schema(
            'transaction_create',
            'Create a new transaction',
            TransactionSerializer,
            TransactionSerializer,
        )
    """
    return extend_schema(
        operation_id=operation_id,
        description=description,
        request=request_serializer,
        responses={201: response_serializer or request_serializer},
        examples=examples,
        tags=['Transactions'],
    )


def retrieve_schema(
    operation_id,
    description,
    response_serializer,
):
    """Factory for retrieve endpoints."""
    return extend_schema(
        operation_id=operation_id,
        description=description,
        responses=response_serializer,
        tags=['Transactions'],
    )


def update_schema(
    operation_id,
    description,
    request_serializer,
    response_serializer=None,
    partial=False,
):
    """Factory for update endpoints."""
    return extend_schema(
        operation_id=operation_id,
        description=description,
        request=request_serializer,
        responses={200: response_serializer or request_serializer},
        tags=['Transactions'],
    )


# ============================================================================
# Common Error Responses
# ============================================================================

ERROR_400_RESPONSE = OpenApiResponse(
    response=serializers.Serializer(
        error=serializers.CharField(help_text='Error message'),
        code=serializers.CharField(help_text='Error code'),
    ),
    description='Bad request - validation error',
)

ERROR_401_RESPONSE = OpenApiResponse(
    response=serializers.Serializer(
        detail=serializers.CharField(help_text='Authentication failed'),
    ),
    description='Unauthorized - authentication required',
)

ERROR_403_RESPONSE = OpenApiResponse(
    response=serializers.Serializer(
        detail=serializers.CharField(help_text='Permission denied'),
    ),
    description='Forbidden - insufficient permissions',
)

ERROR_404_RESPONSE = OpenApiResponse(
    response=serializers.Serializer(
        detail=serializers.CharField(help_text='Resource not found'),
    ),
    description='Not found',
)


# ============================================================================
# Common Examples
# ============================================================================

TRANSACTION_EXAMPLE = OpenApiExample(
    'Transaction Example',
    value={
        'id': '550e8400-e29b-41d4-a716-446655440000',
        'user': '550e8400-e29b-41d4-a716-446655440001',
        'transaction_type': 'credit',
        'amount': '1000.00',
        'status': 'success',
        'description': 'Gig payment',
        'squad_reference': 'SQ-20240501-000001',
        'created_at': '2024-05-01T10:30:00Z',
        'updated_at': '2024-05-01T10:30:00Z',
    },
    request_only=False,
)

WALLET_EXAMPLE = OpenApiExample(
    'Wallet Example',
    value={
        'id': '550e8400-e29b-41d4-a716-446655440000',
        'user': '550e8400-e29b-41d4-a716-446655440001',
        'balance': '5000.00',
        'escrow_balance': '2000.00',
        'savings_balance': '3000.00',
        'squad_account_number': '9876543210',
        'squad_bank_name': 'Squad MFB',
        'is_active': True,
        'created_at': '2024-05-01T10:00:00Z',
        'updated_at': '2024-05-01T10:00:00Z',
    },
    request_only=False,
)

JOB_EXAMPLE = OpenApiExample(
    'Job Example',
    value={
        'id': '550e8400-e29b-41d4-a716-446655440000',
        'employer': '550e8400-e29b-41d4-a716-446655440001',
        'title': 'Need delivery driver for office relocation',
        'description': 'Move office items from Lekki to VI, must be fast and reliable',
        'skill_required': 'delivery',
        'workers_needed': 3,
        'location_area': 'Ikoyi',
        'location_city': 'Lagos',
        'pay_per_worker': '5000.00',
        'duration_hours': 4.5,
        'status': 'open',
        'escrow_funded': True,
        'created_at': '2024-05-01T10:00:00Z',
        'updated_at': '2024-05-01T10:00:00Z',
    },
    request_only=False,
)

LOAN_EXAMPLE = OpenApiExample(
    'Loan Example',
    value={
        'id': '550e8400-e29b-41d4-a716-446655440000',
        'user': '550e8400-e29b-41d4-a716-446655440001',
        'amount': '25000.00',
        'interest_rate_monthly': 5.0,
        'total_repayable': '26250.00',
        'amount_repaid': '0.00',
        'status': 'pending',
        'funding_source': 'demo_float',
        'created_at': '2024-05-01T10:00:00Z',
        'updated_at': '2024-05-01T10:00:00Z',
    },
    request_only=False,
)
