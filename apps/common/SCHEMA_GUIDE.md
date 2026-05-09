"""
Swagger/OpenAPI Schema Documentation

This guide explains how to access and enhance your API documentation
using drf-spectacular and OpenAPI schema.
"""

# ============================================================================
# ACCESSING API DOCUMENTATION
# ============================================================================

"""
The API documentation is automatically generated and available at:

1. **Swagger UI** (Interactive)
   - URL: http://localhost:8000/api/docs/
   - Best for: Testing endpoints interactively
   - Features: Try-it-out, parameter validation, response visualization

2. **ReDoc** (Beautiful documentation)
   - URL: http://localhost:8000/api/redoc/
   - Best for: Reading API documentation
   - Features: Clear navigation, type definitions, examples

3. **OpenAPI Schema** (JSON/YAML)
   - URL: http://localhost:8000/api/schema/
   - Best for: Code generation, external tools, CI/CD
   - Format: JSON (default), or ?format=yaml for YAML format
"""


# ============================================================================
# DECORATING VIEWSETS
# ============================================================================

from rest_framework import viewsets
from drf_spectacular.utils import extend_schema, extend_schema_view
from apps.payments.serializers import TransactionSerializer


@extend_schema_view(
    list=extend_schema(
        operation_id='transactions_list',
        summary='List transactions',
        description='Get all transactions for the current user with pagination support.',
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
    update=extend_schema(
        operation_id='transactions_update',
        summary='Update transaction',
        description='Update a transaction (admin only)',
        tags=['Transactions'],
    ),
    destroy=extend_schema(
        operation_id='transactions_destroy',
        summary='Delete transaction',
        description='Delete a transaction (admin only)',
        tags=['Transactions'],
    ),
)
class TransactionViewSet(viewsets.ModelViewSet):
    """
    Transaction management endpoints.
    
    Allows users to view their transaction history and for admins
    to manage transactions across the platform.
    """
    serializer_class = TransactionSerializer
    queryset = TransactionSerializer.model.objects.all()


# ============================================================================
# DECORATING INDIVIDUAL ACTIONS
# ============================================================================

from rest_framework.decorators import action


class JobViewSet(viewsets.ModelViewSet):
    
    @extend_schema(
        summary='Get available jobs',
        description='Retrieve jobs that match the worker skills in the specified location',
        tags=['Jobs'],
        operation_id='jobs_nearby',
    )
    @action(detail=False, methods=['get'])
    def nearby(self, request):
        """Get jobs near worker's location."""
        pass
    
    @extend_schema(
        summary='Accept job application',
        description='Employer accepts a worker application for a job',
        tags=['Jobs'],
        operation_id='job_applications_accept',
        request=None,
        responses={200: {'type': 'object'}},
    )
    @action(detail=True, methods=['post'])
    def accept_application(self, request, pk=None):
        """Accept a job application."""
        pass


# ============================================================================
# DECORATING SERIALIZERS
# ============================================================================

from rest_framework import serializers


class TransactionSerializer(serializers.ModelSerializer):
    """
    Transaction serializer.
    
    Used for representing transaction records in API responses.
    Includes full audit trail with timestamps.
    """
    
    class Meta:
        model = None  # Will be set in actual file
        fields = [
            'id', 'user', 'transaction_type', 'amount',
            'status', 'description', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        
        # Add examples for Swagger
        examples = {
            'valid_transaction': {
                'value': {
                    'transaction_type': 'credit',
                    'amount': '1000.00',
                    'description': 'Gig payment received',
                }
            }
        }


# ============================================================================
# REQUEST/RESPONSE EXAMPLES
# ============================================================================

from drf_spectacular.utils import OpenApiExample

TRANSACTION_EXAMPLES = [
    OpenApiExample(
        'Credit Transaction',
        value={
            'id': '123e4567-e89b-12d3-a456-426614174000',
            'transaction_type': 'credit',
            'amount': '5000.00',
            'status': 'success',
            'description': 'Payment for completed gig',
            'created_at': '2024-05-01T10:30:00Z',
        },
    ),
    OpenApiExample(
        'Debit Transaction',
        value={
            'id': '223e4567-e89b-12d3-a456-426614174000',
            'transaction_type': 'debit',
            'amount': '1000.00',
            'status': 'success',
            'description': 'Platform fee deduction',
            'created_at': '2024-05-01T11:00:00Z',
        },
    ),
]


# ============================================================================
# CUSTOM RESPONSE SCHEMAS
# ============================================================================

from drf_spectacular.utils import OpenApiResponse

# Define standardized responses for consistency
STANDARD_ERROR_RESPONSE = OpenApiResponse(
    response=serializers.Serializer(
        error=serializers.CharField(),
        code=serializers.CharField(),
        details=serializers.JSONField(required=False),
    ),
    description='Error response',
)


# ============================================================================
# OPERATION CUSTOMIZATION
# ============================================================================

from drf_spectacular.utils import extend_schema


class WalletViewSet(viewsets.ModelViewSet):
    
    @extend_schema(
        summary='Get wallet balance',
        description='Retrieve current wallet balance and breakdown by account type',
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'balance': {'type': 'number', 'format': 'decimal'},
                    'escrow_balance': {'type': 'number', 'format': 'decimal'},
                    'savings_balance': {'type': 'number', 'format': 'decimal'},
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
        summary='Deposit to wallet',
        description='Add funds to wallet via Squad virtual account',
        tags=['Wallets'],
        request=serializers.Serializer(
            amount=serializers.DecimalField(max_digits=12, decimal_places=2)
        ),
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'transaction_id': {'type': 'string', 'format': 'uuid'},
                    'amount': {'type': 'number', 'format': 'decimal'},
                    'status': {'type': 'string'},
                }
            }
        },
    )
    @action(detail=False, methods=['post'])
    def deposit(self, request):
        """Deposit funds to wallet."""
        pass


# ============================================================================
# AUTHENTICATION IN SWAGGER
# ============================================================================

"""
To test authenticated endpoints in Swagger:

1. Open http://localhost:8000/api/docs/
2. Find the 'Authorize' button in the top-right corner
3. Select 'Bearer Token' authentication
4. Get a token:
   - POST to /api/users/token/
   - Use phone and password
   - Copy the access token
5. Paste token in the Authorize dialog (without 'Bearer ' prefix)
6. All subsequent requests will include the Authorization header

Example token request:
POST /api/users/token/
Content-Type: application/json

{
    "phone": "+2341234567890",
    "password": "yourpassword"
}

Response:
{
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
"""


# ============================================================================
# SCHEMA GENERATION OPTIONS
# ============================================================================

"""
In settings.py, SPECTACULAR_SETTINGS controls schema generation:

    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny']
    - Who can view the API schema (public by default)
    
    'SCHEMA_PATH_PREFIX': r'/api/'
    - Only document endpoints starting with /api/
    
    'ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE': True
    - Add null option to nullable fields
    
    'SORT_OPERATION_PARAMETERS': True
    - Sort parameters alphabetically
    
    'SORT_SECURITY_SCHEMES': True
    - Sort authentication methods
    
    'TAGS_SORTER': None
    - Custom tag ordering (default: alphabetical)
    
    'OPERATION_SORTER': None
    - Custom operation ordering within tags
"""


# ============================================================================
# BEST PRACTICES
# ============================================================================

"""
✅ DO:
- Add meaningful operation_id for each endpoint (used in client generation)
- Include summary and description for all operations
- Group endpoints with tags for better organization
- Add examples for complex request/response bodies
- Document error responses (400, 401, 403, 404, 500)
- Use consistent naming: list, create, retrieve, update, destroy
- Add deprecated=True to endpoints being retired

❌ DON'T:
- Leave operations without descriptions
- Mix different operation naming conventions
- Create overly complex nested schemas
- Hardcode example values (use OpenApiExample)
- Forget to document required fields
- Leave error cases undocumented

⚡ PERFORMANCE:
- Schema generation happens at request time
- Cache schema if you have thousands of endpoints
- Use operation_sorter for custom ordering (improves readability)
"""


# ============================================================================
# SCHEMA GENERATION FOR EXTERNAL TOOLS
# ============================================================================

"""
Download OpenAPI schema for code generation:

1. JSON format (default):
   curl http://localhost:8000/api/schema/ > schema.json

2. YAML format:
   curl http://localhost:8000/api/schema/?format=yaml > schema.yaml

Then use with external tools:

OpenAPI Code Generator:
   openapi-generator-cli generate -i schema.yaml -g python

Swagger Codegen:
   swagger-codegen generate -i schema.yaml -l javascript

API Blueprint:
   aglio -i schema.yaml -o docs.html
"""
