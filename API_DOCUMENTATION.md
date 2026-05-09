# Swagger/OpenAPI Documentation Setup

## Quick Start

Your API is now fully documented with interactive Swagger UI and ReDoc. Access the documentation at:

- **Swagger UI (Interactive)**: http://localhost:8000/api/docs/
- **ReDoc (Beautiful)**: http://localhost:8000/api/redoc/
- **OpenAPI Schema (JSON)**: http://localhost:8000/api/schema/
- **OpenAPI Schema (YAML)**: http://localhost:8000/api/schema/?format=yaml

## What Was Configured

### 1. **Settings Configuration** (`kolliq/settings.py`)

Added drf-spectacular to `INSTALLED_APPS`:
```python
THIRD_PARTY_APPS = [
    ...
    'drf_spectacular',
    ...
]
```

Configured schema generation in `REST_FRAMEWORK` and `SPECTACULAR_SETTINGS`:
- Default schema class set to `drf_spectacular.openapi.AutoSchema`
- JWT authentication configured for Swagger
- API metadata (title, version, contact)
- Sorting and enum handling

### 2. **URL Configuration** (`kolliq/urls.py`)

Added three documentation endpoints:
```python
path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
```

### 3. **Schema Utilities** (`apps/common/schema.py`)

Reusable decorators and factories for:
- Paginated list endpoints
- Create/retrieve/update operations
- Common parameter definitions
- Standardized error responses
- Example payloads

### 4. **Documentation Files**

- **SCHEMA_GUIDE.md**: Comprehensive guide on using drf-spectacular
- **SCHEMA_EXAMPLES.py**: Code examples for decorating ViewSets
- **schema.py**: Reusable utilities and decorators

## Features

### ✅ Automatic Documentation

All endpoints are automatically documented with:
- Request/response schemas
- Parameter descriptions
- Type information
- Authentication requirements
- Error responses

### ✅ Interactive Testing

In Swagger UI, you can:
- Test endpoints directly
- See live responses
- Validate parameters
- Try different scenarios

### ✅ Authentication

JWT authentication is integrated:
1. Open http://localhost:8000/api/docs/
2. Click "Authorize" button
3. Get token from `/api/users/token/`
4. Paste token in Bearer field
5. All requests now include auth header

### ✅ Schema Download

Download OpenAPI schema for external tools:
```bash
# JSON format
curl http://localhost:8000/api/schema/ > openapi.json

# YAML format
curl http://localhost:8000/api/schema/?format=yaml > openapi.yaml
```

Use with:
- OpenAPI Code Generators
- Client SDK generation
- Integration tests
- API monitoring

## Using in Your ViewSets

### Basic Example

```python
from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import viewsets

@extend_schema_view(
    list=extend_schema(
        operation_id='transactions_list',
        summary='List transactions',
        description='Get all transactions for the user',
        tags=['Transactions'],
    ),
)
class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    queryset = Transaction.objects.all()
```

### Custom Actions

```python
@extend_schema(
    operation_id='jobs_apply',
    summary='Apply for job',
    description='Submit application for a specific job',
    tags=['Jobs'],
)
@action(detail=True, methods=['post'])
def apply(self, request, pk=None):
    pass
```

### Parameters

```python
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes

@extend_schema(
    parameters=[
        OpenApiParameter(
            name='skill',
            description='Filter by skill',
            enum=['delivery', 'cooking', 'cleaning'],
            type=OpenApiTypes.STR,
        ),
    ]
)
```

## Documentation Structure

```
apps/common/
├── rls.py                    # Row-level security
├── schema.py                 # Schema utilities
├── SCHEMA_GUIDE.md          # Usage guide
├── SCHEMA_EXAMPLES.py       # Code examples
└── RLS_GUIDE.md             # RLS documentation
```

## Best Practices

### ✅ DO:

- Add meaningful `operation_id` (used for code generation)
- Include `summary` and `description` for clarity
- Group endpoints with `tags`
- Add examples for complex payloads
- Document all error responses (400, 401, 403, 404)
- Mark deprecated endpoints with `deprecated=True`

### ❌ DON'T:

- Leave operations without descriptions
- Use vague tag names
- Hardcode examples (use `OpenApiExample`)
- Forget required field documentation
- Mix naming conventions (use list/create/retrieve/destroy)

## API Metadata

Current API configuration in `settings.py`:

```python
SPECTACULAR_SETTINGS = {
    'TITLE': 'Kolliq API',
    'DESCRIPTION': 'Micro-work & Gig Economy Platform API',
    'VERSION': '1.0.0',
    'CONTACT': {
        'name': 'Kolliq Support',
        'email': 'support@kolliq.com',
    },
    'LICENSE': {
        'name': 'Proprietary',
        'url': 'https://kolliq.com/license',
    },
}
```

Update these values in `settings.py` as needed.

## Common Patterns

### List with Filtering

```python
@extend_schema(
    parameters=[
        OpenApiParameter(
            name='status',
            enum=['open', 'closed', 'pending'],
            type=OpenApiTypes.STR,
        ),
    ]
)
def list(self, request):
    pass
```

### Create with Response

```python
@extend_schema(
    request=TransactionSerializer,
    responses={
        201: TransactionSerializer,
        400: ErrorSerializer,
    }
)
def create(self, request):
    pass
```

### Custom Action with Parameters

```python
@extend_schema(
    parameters=[
        OpenApiParameter(name='lat', type=OpenApiTypes.DECIMAL),
        OpenApiParameter(name='lng', type=OpenApiTypes.DECIMAL),
    ],
    responses={200: LocationListSerializer(many=True)},
)
@action(detail=False, methods=['get'])
def nearby(self, request):
    pass
```

## Troubleshooting

### Schema not showing fields

**Cause**: Serializer fields lack descriptions
**Solution**: Add `help_text` to model fields
```python
amount = models.DecimalField(
    help_text='Transaction amount in naira'
)
```

### Authentication not working in Swagger

**Cause**: Token not in correct format
**Solution**: Make sure to use "Bearer {token}" in auth header
- Get token: POST `/api/users/token/`
- Paste in Authorize dialog without "Bearer" prefix
- Swagger adds "Bearer" automatically

### Schema generation slow

**Cause**: Large number of endpoints
**Solution**: Optimize with caching or split into sub-schemas
```python
SPECTACULAR_SETTINGS = {
    'SPECTACULAR_CACHE_TIMEOUT': 60 * 60,  # Cache for 1 hour
}
```

### Enums not showing in dropdown

**Cause**: Enum not properly defined
**Solution**: Use `enum` parameter in `OpenApiParameter`
```python
OpenApiParameter(
    name='status',
    enum=['pending', 'approved', 'rejected'],
    type=OpenApiTypes.STR,
)
```

## External Integration

### Generate Python Client

```bash
openapi-generator-cli generate \
    -i http://localhost:8000/api/schema/ \
    -g python \
    -o ./python-client
```

### Generate JavaScript Client

```bash
openapi-generator-cli generate \
    -i http://localhost:8000/api/schema/ \
    -g javascript \
    -o ./js-client
```

### Postman Import

1. Download schema: `curl http://localhost:8000/api/schema/ > openapi.json`
2. In Postman: File → Import → Choose openapi.json
3. All endpoints auto-imported with documentation

## Next Steps

1. **Document your ViewSets**: Use examples in `SCHEMA_EXAMPLES.py`
2. **Test the UI**: Visit http://localhost:8000/api/docs/
3. **Add descriptions**: Update `SPECTACULAR_SETTINGS` in `settings.py`
4. **Export schema**: For integrations and code generation

## Files Modified

- `kolliq/settings.py` - Added drf-spectacular config
- `kolliq/urls.py` - Added documentation endpoints
- `requirements.txt` - Added drf-spectacular dependency
- `apps/common/` - New schema utilities and guides

## Support

For more information:
- [drf-spectacular Docs](https://drf-spectacular.readthedocs.io/)
- [OpenAPI Specification](https://spec.openapis.org/)
- See `SCHEMA_GUIDE.md` for detailed usage
- See `SCHEMA_EXAMPLES.py` for code examples
