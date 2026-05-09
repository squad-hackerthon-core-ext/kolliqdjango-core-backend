"""
IMPLEMENTATION CHECKLIST: Adding Schema Documentation to Your Endpoints

Use this checklist to systematically add documentation to all your ViewSets
and Serializers for complete API documentation.
"""

# ============================================================================
# PHASE 1: SERIALIZER DOCUMENTATION
# ============================================================================

SERIALIZER_CHECKLIST = """
For each serializer file (e.g., apps/payments/serializers.py):

1. Add field help_text:
   ✓ user = serializers.PrimaryKeyRelatedField(help_text='User ID')
   ✓ amount = serializers.DecimalField(help_text='Transaction amount in naira')
   ✓ status = serializers.ChoiceField(help_text='Transaction status')

2. Add class docstring:
   ✓ \"\"\"Transaction serializer for API responses\"\"\"

3. Add field validation examples:
   ✓ validators list with descriptions
   ✓ to_representation() documentation

SERIALIZERS TO UPDATE:
[ ] apps/users/serializers.py
[ ] apps/payments/serializers.py
[ ] apps/wallets/serializers.py
[ ] apps/jobs/serializers.py
[ ] apps/financial_services/serializers.py
[ ] apps/scoring/serializers.py
"""

# ============================================================================
# PHASE 2: VIEWSET DOCUMENTATION
# ============================================================================

VIEWSET_CHECKLIST = """
For each viewset (e.g., apps/payments/views.py):

1. Import schema utilities:
   ✓ from drf_spectacular.utils import extend_schema_view, extend_schema
   ✓ from drf_spectacular.types import OpenApiTypes
   ✓ from drf_spectacular.utils import OpenApiParameter

2. Add @extend_schema_view with:
   ✓ operation_id (unique identifier)
   ✓ summary (one-liner)
   ✓ description (detailed explanation)
   ✓ tags (grouping)
   
   Example:
   @extend_schema_view(
       list=extend_schema(
           operation_id='transactions_list',
           summary='List transactions',
           description='Get all user transactions',
           tags=['Transactions'],
       ),
   )

3. For each custom @action:
   ✓ Add @extend_schema decorator
   ✓ Specify operation_id
   ✓ Include summary and description
   ✓ Define parameters if needed
   ✓ Specify response type and status codes

4. Document error cases:
   ✓ 400 - Validation error
   ✓ 401 - Unauthorized
   ✓ 403 - Forbidden
   ✓ 404 - Not found

VIEWSETS TO UPDATE:
[ ] apps/users/views.py (UserViewSet, ...)
[ ] apps/payments/views.py (TransactionViewSet, ...)
[ ] apps/wallets/views.py (WalletViewSet, ...)
[ ] apps/jobs/views.py (JobViewSet, JobApplicationViewSet, RatingViewSet)
[ ] apps/financial_services/views.py (LoanViewSet, InsurancePolicyViewSet, ...)
[ ] apps/scoring/views.py (ScoreViewSet, ...)
[ ] apps/partner/views.py (PartnerViewSet, ...)
"""

# ============================================================================
# PHASE 3: URL ROUTING DOCUMENTATION
# ============================================================================

URL_CHECKLIST = """
For each urls.py file (e.g., apps/payments/urls.py):

Check that:
✓ Router is properly configured
✓ All viewsets registered with router
✓ Custom endpoints have unique operation_ids
✓ URL patterns follow RESTful conventions

Example:
    from rest_framework.routers import DefaultRouter
    from .views import TransactionViewSet
    
    router = DefaultRouter()
    router.register('', TransactionViewSet, basename='transaction')
    
    urlpatterns = router.urls
"""

# ============================================================================
# PHASE 4: SPECIFIC ENDPOINT TEMPLATES
# ============================================================================

TRANSACTION_ENDPOINT_TEMPLATE = """
# Transaction ViewSet - Complete Example

@extend_schema_view(
    list=extend_schema(
        operation_id='transactions_list',
        summary='List transactions',
        description='Retrieve all transactions for the authenticated user',
        parameters=[
            OpenApiParameter(
                name='type',
                description='Filter by transaction type',
                enum=['credit', 'debit', 'escrow_hold', 'escrow_release', 'platform_fee'],
                type=OpenApiTypes.STR,
            ),
            OpenApiParameter(
                name='status',
                description='Filter by status',
                enum=['pending', 'success', 'failed', 'reversed'],
                type=OpenApiTypes.STR,
            ),
        ],
        tags=['Transactions'],
    ),
    create=extend_schema(
        operation_id='transaction_create',
        summary='Create transaction',
        description='Create a new transaction (admin only)',
        tags=['Transactions'],
    ),
    retrieve=extend_schema(
        operation_id='transaction_retrieve',
        summary='Get transaction',
        description='Retrieve a specific transaction by ID',
        tags=['Transactions'],
    ),
    update=extend_schema(
        operation_id='transaction_update',
        summary='Update transaction',
        description='Update a transaction (admin only)',
        tags=['Transactions'],
    ),
    destroy=extend_schema(
        operation_id='transaction_destroy',
        summary='Delete transaction',
        description='Delete a transaction (admin only)',
        tags=['Transactions'],
    ),
)
class TransactionViewSet(viewsets.ModelViewSet):
    '''Transaction management endpoints.'''
    serializer_class = TransactionSerializer
    queryset = Transaction.objects.all()
"""

JOB_ENDPOINT_TEMPLATE = """
# Job ViewSet - Complete Example with Custom Actions

@extend_schema_view(
    list=extend_schema(
        operation_id='job_list',
        summary='List jobs',
        description='List available jobs with filtering',
        parameters=[
            OpenApiParameter(
                name='skill_required',
                type=OpenApiTypes.STR,
                enum=['delivery', 'cooking', 'construction', 'market', 'cleaning'],
            ),
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                enum=['open', 'filled', 'in_progress', 'completed'],
            ),
        ],
        tags=['Jobs'],
    ),
)
class JobViewSet(viewsets.ModelViewSet):
    serializer_class = JobSerializer
    queryset = Job.objects.all()
    
    @extend_schema(
        operation_id='job_apply',
        summary='Apply for job',
        description='Submit a worker application for this job',
        tags=['Jobs'],
    )
    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        pass
    
    @extend_schema(
        operation_id='job_nearby',
        summary='Find nearby jobs',
        description='Find jobs near your location',
        parameters=[
            OpenApiParameter(name='lat', type=OpenApiTypes.DECIMAL, required=True),
            OpenApiParameter(name='lng', type=OpenApiTypes.DECIMAL, required=True),
        ],
        tags=['Jobs'],
    )
    @action(detail=False, methods=['get'])
    def nearby(self, request):
        pass
"""

LOAN_ENDPOINT_TEMPLATE = """
# Loan ViewSet - Complete Example

@extend_schema_view(
    list=extend_schema(
        operation_id='loan_list',
        summary='List loans',
        description='List all loans for the user',
        tags=['Financial Services'],
    ),
    create=extend_schema(
        operation_id='loan_apply',
        summary='Apply for loan',
        description='Submit a loan application',
        tags=['Financial Services'],
    ),
)
class LoanViewSet(viewsets.ModelViewSet):
    serializer_class = LoanSerializer
    queryset = Loan.objects.all()
    
    @extend_schema(
        operation_id='loan_repay',
        summary='Make repayment',
        description='Submit a loan repayment',
        request={'amount': serializers.DecimalField()},
        tags=['Financial Services'],
    )
    @action(detail=True, methods=['post'])
    def repay(self, request, pk=None):
        pass
    
    @extend_schema(
        operation_id='loan_schedule',
        summary='Get repayment schedule',
        description='View the loan repayment schedule',
        tags=['Financial Services'],
    )
    @action(detail=True, methods=['get'])
    def schedule(self, request, pk=None):
        pass
"""

# ============================================================================
# PHASE 5: TAGGING STRATEGY
# ============================================================================

TAGS_STRATEGY = """
Use consistent tags to organize endpoints:

[ ] Users          - User management, auth, profiles
[ ] Wallets        - Wallet operations, balances
[ ] Jobs           - Job listings, applications, matching
[ ] Transactions   - Payment history, transfers
[ ] Financial      - Loans, insurance, savings
[ ] Scoring        - Economic identity, credit score
[ ] Partner        - Partner integrations

Example:
    @extend_schema(..., tags=['Wallets'])
    def list(self, request):
        pass
"""

# ============================================================================
# PRIORITY ORDER
# ============================================================================

PRIORITY_ORDER = """
1. HIGH PRIORITY (Most used endpoints):
   [ ] Authentication endpoints (users/token/)
   [ ] Transaction list/detail
   [ ] Wallet balance
   [ ] Job list/apply
   [ ] Loan apply/status

2. MEDIUM PRIORITY (Important flows):
   [ ] Job applications
   [ ] Repayment operations
   [ ] Insurance enrollment
   [ ] Ratings/reviews

3. LOWER PRIORITY (Admin/support):
   [ ] Platform fees
   [ ] Demo float management
   [ ] System operations
"""

# ============================================================================
# QUICK REFERENCE
# ============================================================================

QUICK_REFERENCE = """
Common decorators:

List endpoint:
    @extend_schema(
        operation_id='resource_list',
        summary='List resources',
        tags=['Resource'],
    )

Create endpoint:
    @extend_schema(
        operation_id='resource_create',
        summary='Create resource',
        request=ResourceSerializer,
        tags=['Resource'],
    )

Custom action with params:
    @extend_schema(
        operation_id='resource_action',
        summary='Action description',
        parameters=[OpenApiParameter(name='param', type=OpenApiTypes.STR)],
        tags=['Resource'],
    )
    @action(detail=True/False, methods=['get'/'post'])
    def action_name(self, request, pk=None):
        pass

Error responses:
    responses={
        200: ResourceSerializer,
        400: ErrorSerializer,
        401: ErrorSerializer,
    }
"""

# ============================================================================
# TESTING CHECKLIST
# ============================================================================

TESTING_CHECKLIST = """
After adding documentation:

[ ] Visit http://localhost:8000/api/docs/
[ ] Check all endpoints appear in sidebar
[ ] Click on each endpoint to see details
[ ] Verify operation_id is unique
[ ] Test parameters with Try-it-out
[ ] Verify response examples
[ ] Check authentication works
[ ] Download schema and verify JSON/YAML
[ ] Test in Postman by importing schema

Issues to look for:
[ ] Missing descriptions
[ ] Unclear parameter types
[ ] Wrong status codes
[ ] Missing error responses
[ ] Vague endpoint names
[ ] Non-unique operation_ids
"""

# ============================================================================
# AUTOMATION TIPS
# ============================================================================

AUTOMATION_TIPS = """
Speed up documentation with:

1. Copy templates from SCHEMA_EXAMPLES.py
2. Find/Replace patterns:
   - Replace "class.*ViewSet" with decorated version
   - Batch add operation_ids with consistent naming

3. Use IDE shortcuts:
   - Duplicate lines with Ctrl+Shift+D
   - Multi-cursor for bulk edits
   - Search/replace in directory

4. Generate from docstrings:
   - Add detailed docstrings
   - drf-spectacular can extract some info

5. Version control:
   - Track schema changes with git
   - Review schema diffs alongside code
"""

# ============================================================================
# REFERENCE
# ============================================================================

print(f"""
SCHEMA DOCUMENTATION IMPLEMENTATION GUIDE
{'='*60}

PHASE 1: Serializer Documentation
{SERIALIZER_CHECKLIST}

PHASE 2: ViewSet Documentation  
{VIEWSET_CHECKLIST}

PHASE 3: URL Routing
{URL_CHECKLIST}

PHASE 4: Templates
See SCHEMA_EXAMPLES.py for complete examples

PHASE 5: Tagging
{TAGS_STRATEGY}

PRIORITY
{PRIORITY_ORDER}

TESTING
{TESTING_CHECKLIST}

For more info, see:
- API_DOCUMENTATION.md
- SCHEMA_GUIDE.md
- SCHEMA_EXAMPLES.py
""")
