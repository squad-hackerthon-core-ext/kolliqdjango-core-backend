"""
QUICK START: Swagger Schema in 5 Minutes
"""

# ============================================================================
# STEP 1: ACCESS THE DOCUMENTATION (Right Now!)
# ============================================================================

print("""
Open these URLs in your browser:

✨ Interactive API Testing:
   http://localhost:8000/api/docs/

📖 Beautiful Documentation:
   http://localhost:8000/api/redoc/

🔌 Raw OpenAPI Schema:
   http://localhost:8000/api/schema/
""")


# ============================================================================
# STEP 2: TEST WITH AUTHENTICATION (3 minutes)
# ============================================================================

print("""
1. Get JWT Token:
   POST http://localhost:8000/api/users/token/
   Body: {"phone": "+2341234567890", "password": "your-password"}
   
   Response will have: {"access": "eyJ0eXAi...", "refresh": "..."}

2. In Swagger UI (http://localhost:8000/api/docs/):
   - Click "Authorize" button (top-right)
   - Select "Bearer Token"
   - Paste token (just the token, not "Bearer token")
   - Click "Authorize"

3. Now try "Try-it-out" on any endpoint!
""")


# ============================================================================
# STEP 3: DOCUMENT YOUR ENDPOINTS (2 minutes)
# ============================================================================

print("""
Add schema documentation to your ViewSet:

FROM THIS:
-----------
class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    queryset = Transaction.objects.all()

TO THIS:
--------
from drf_spectacular.utils import extend_schema_view, extend_schema

@extend_schema_view(
    list=extend_schema(
        operation_id='transactions_list',
        summary='List user transactions',
        tags=['Transactions'],
    ),
)
class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    queryset = Transaction.objects.all()

That's it! Your endpoint is now documented.
""")


# ============================================================================
# QUICK REFERENCE: COMMON PATTERNS
# ============================================================================

"""
PATTERN 1: Basic List Endpoint
────────────────────────────────
from drf_spectacular.utils import extend_schema

@extend_schema(
    operation_id='transactions_list',
    summary='List transactions',
    tags=['Transactions'],
)
def list(self, request):
    pass


PATTERN 2: With Parameters
───────────────────────────
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes

@extend_schema(
    parameters=[
        OpenApiParameter(
            name='status',
            enum=['pending', 'success', 'failed'],
            type=OpenApiTypes.STR,
        ),
    ],
)
def list(self, request):
    pass


PATTERN 3: Custom Action
────────────────────────
@extend_schema(
    operation_id='jobs_apply',
    summary='Apply for job',
    tags=['Jobs'],
)
@action(detail=True, methods=['post'])
def apply(self, request, pk=None):
    pass


PATTERN 4: With Response Type
───────────────────────────────
@extend_schema(
    responses={200: TransactionSerializer(many=True)},
)
def list(self, request):
    pass


PATTERN 5: Full ViewSet
──────────────────────
@extend_schema_view(
    list=extend_schema(...),
    create=extend_schema(...),
    retrieve=extend_schema(...),
    update=extend_schema(...),
    destroy=extend_schema(...),
)
class TransactionViewSet(viewsets.ModelViewSet):
    pass
"""


# ============================================================================
# FILE LOCATIONS
# ============================================================================

"""
Configuration Files:
  kolliq/settings.py        - Swagger settings (SPECTACULAR_SETTINGS)
  kolliq/urls.py            - Documentation URLs
  requirements.txt          - drf-spectacular dependency

Schema Utilities:
  apps/common/schema.py     - Reusable decorators
  
Documentation:
  SWAGGER_SETUP_COMPLETE.md - Setup summary
  API_DOCUMENTATION.md      - Full guide
  SCHEMA_GUIDE.md           - Detailed usage
  SCHEMA_EXAMPLES.py        - Code examples
  IMPLEMENTATION_CHECKLIST.md - Step-by-step
"""


# ============================================================================
# COPY-PASTE SOLUTIONS
# ============================================================================

print("""
COPY-PASTE: Import statement for all your views
───────────────────────────────────────────────
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiExample,
)
from drf_spectacular.types import OpenApiTypes


COPY-PASTE: Basic Transaction ViewSet
──────────────────────────────────────
from rest_framework import viewsets
from drf_spectacular.utils import extend_schema_view, extend_schema

@extend_schema_view(
    list=extend_schema(
        operation_id='transactions_list',
        summary='List transactions',
        description='Get all user transactions',
        tags=['Transactions'],
    ),
    create=extend_schema(
        operation_id='transactions_create',
        summary='Create transaction',
        tags=['Transactions'],
    ),
    retrieve=extend_schema(
        operation_id='transactions_retrieve',
        summary='Get transaction',
        tags=['Transactions'],
    ),
)
class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    queryset = Transaction.objects.all()


COPY-PASTE: Custom action
─────────────────────────
from rest_framework.decorators import action

@extend_schema(
    operation_id='wallets_balance',
    summary='Get wallet balance',
    description='Retrieve current wallet balance',
    tags=['Wallets'],
)
@action(detail=False, methods=['get'])
def balance(self, request):
    pass
""")


# ============================================================================
# NEXT STEPS
# ============================================================================

print("""
WHAT TO DO NOW:
───────────────
1. Visit http://localhost:8000/api/docs/
2. Try an endpoint with "Try-it-out"
3. Add @extend_schema to one ViewSet
4. Refresh docs page and see your changes
5. See SCHEMA_EXAMPLES.py for more patterns

COMMON MISTAKES TO AVOID:
─────────────────────────
❌ Forgetting to import extend_schema
❌ Using wrong operation_id format
❌ Not setting enum values for choices
❌ Forgetting tags (endpoints won't group)
❌ Not testing with Try-it-out

BEST PRACTICES:
───────────────
✅ Use lowercase operation_id (e.g., 'transactions_list')
✅ Include tags to organize endpoints
✅ Add helpful summaries and descriptions
✅ Use enums for choice fields
✅ Document error responses (400, 401, 404)

PERFORMANCE TIPS:
─────────────────
⚡ Schema generation happens at request time
⚡ For 100+ endpoints, enable caching
⚡ Use RETRIEVE_TRAILING_SLASH = False (already set)
⚡ SPECTACULAR_CACHE_TIMEOUT can speed things up

TESTING:
────────
curl http://localhost:8000/api/schema/
  → Should return JSON without errors

curl http://localhost:8000/api/schema/?format=yaml
  → Should return YAML without errors

http://localhost:8000/api/docs/
  → Should load without JavaScript errors
""")


# ============================================================================
# TROUBLESHOOTING
# ============================================================================

"""
ISSUE: Schema not loading
SOLUTION: 
  - Restart Django server
  - Check terminal for errors
  - Verify drf-spectacular is installed: pip show drf-spectacular

ISSUE: Authentication button not showing
SOLUTION:
  - Check SPECTACULAR_SETTINGS in settings.py
  - Ensure 'SECURITY' and 'SECURITY_SCHEMES' are configured
  - Already done in your setup ✅

ISSUE: Endpoints not appearing
SOLUTION:
  - Check that URLs are registered in router
  - Verify ROOT_URLCONF is correct
  - Make sure viewset has @extend_schema_view decorator

ISSUE: Parameters not showing
SOLUTION:
  - Import OpenApiParameter correctly
  - Use type=OpenApiTypes.STR (not just 'str')
  - Set location=OpenApiParameter.QUERY for query params

ISSUE: Enum choices not showing dropdown
SOLUTION:
  - Use enum=['value1', 'value2'] parameter
  - Make sure values match actual choices
  - Don't forget to set type parameter
"""


# ============================================================================
# RESOURCES
# ============================================================================

"""
📚 DOCUMENTATION FILES IN THIS PROJECT:
─────────────────────────────────────────
apps/common/
  ├── SCHEMA_GUIDE.md              ← Detailed usage guide
  ├── SCHEMA_EXAMPLES.py           ← Real code examples
  ├── IMPLEMENTATION_CHECKLIST.md  ← Step by step
  ├── RLS_GUIDE.md                 ← Row-level security
  └── schema.py                    ← Reusable utilities

Root level:
  ├── SWAGGER_SETUP_COMPLETE.md    ← Setup summary
  ├── API_DOCUMENTATION.md         ← Full documentation
  └── requirements.txt             ← Dependencies

🌐 EXTERNAL RESOURCES:
──────────────────────
[drf-spectacular]   https://drf-spectacular.readthedocs.io/
[OpenAPI Spec]      https://spec.openapis.org/
[Swagger UI]        https://swagger.io/tools/swagger-ui/
[ReDoc]             https://redoc.ly/

💬 QUESTIONS?
─────────────
See SCHEMA_GUIDE.md for Q&A section
See SCHEMA_EXAMPLES.py for code patterns
See API_DOCUMENTATION.md for troubleshooting
"""


# ============================================================================
# FINAL SUMMARY
# ============================================================================

print("""
╔════════════════════════════════════════════════════════════════╗
║          SWAGGER/OPENAPI SETUP - COMPLETE ✅                 ║
╚════════════════════════════════════════════════════════════════╝

YOUR API IS DOCUMENTED! 🎉

Access Documentation:
  👉 Interactive: http://localhost:8000/api/docs/
  👉 Beautiful:   http://localhost:8000/api/redoc/
  👉 Raw JSON:    http://localhost:8000/api/schema/

Next Steps:
  1. Try an endpoint in Swagger UI
  2. Add @extend_schema to your ViewSets
  3. Share the docs URL with your team

You can now:
  ✅ Test endpoints in browser
  ✅ Generate client SDKs
  ✅ Import into Postman
  ✅ Integrate with monitoring tools

Questions? See:
  → SCHEMA_GUIDE.md for detailed guide
  → SCHEMA_EXAMPLES.py for code examples
  → API_DOCUMENTATION.md for full reference

Happy documenting! 🚀
""")
