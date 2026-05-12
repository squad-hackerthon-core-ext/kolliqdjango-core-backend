# Kolliq API - Global Schema & Response Format Standard

## Universal JSON Response Structure

**All endpoints in the Kolliq codebase** use this standardized response format.

### Standard Success Response (2xx)
```json
{
  "code": <HTTP_STATUS_CODE>,
  "success": true,
  "message": "<human-readable success message>",
  "data": {
    // Endpoint-specific payload
  }
}
```

### Standard Error Response (4xx, 5xx)
```json
{
  "code": <HTTP_STATUS_CODE>,
  "success": false,
  "message": "<human-readable error message>",
  "errors": {
    // Optional: field validation errors (for 400 Bad Request)
    "field_name": ["error message 1", "error message 2"]
  }
}
```

## Response Structure Breakdown

### `code` (Integer, Required)
HTTP status code mirrored in response body for client convenience.
- `200` - Success
- `201` - Resource Created
- `400` - Validation Error
- `401` - Authentication Required
- `403` - Permission Denied
- `404` - Not Found
- `500` - Server Error

### `success` (Boolean, Required)
- `true` if operation succeeded
- `false` if operation failed

### `message` (String, Required)
Human-readable message describing the result. Examples:
- "User created successfully"
- "Validation error"
- "Insufficient balance"
- "Invalid PIN"

### `data` (Object, Optional)
The actual response payload. Structure varies by endpoint.
- Present on success (even if empty `{}`)
- Absent on errors

### `errors` (Object, Optional)
Validation error details. Only present on 400 Bad Request.
- Keys are field names
- Values are arrays of error messages

## Standard HTTP Status Codes

| Code | When to Use | Example Scenario |
|------|-----------|------------------|
| **200 OK** | Successful GET, PATCH, DELETE | User profile retrieved, profile updated |
| **201 Created** | Successful POST that creates resource | User account created, job posted |
| **400 Bad Request** | Invalid input, validation failed | Missing required field, invalid format |
| **401 Unauthorized** | Missing or invalid auth token | Token expired, no token provided |
| **403 Forbidden** | Auth valid but lacks permission | Worker trying to post job, employer accessing worker-only endpoint |
| **404 Not Found** | Resource doesn't exist | User not found, job not found |
| **409 Conflict** | Request conflicts with current state | Duplicate action, already accepted job |
| **500 Server Error** | Unexpected server error | Database connection error, unhandled exception |

## Field Type Standards

### String Formats
| Format | Example | Usage |
|--------|---------|-------|
| Phone (E.164) | `+2348012345678` | User phone numbers |
| Email | `john@example.com` | User email |
| UUID | `550e8400-e29b-41d4-a716-446655440000` | IDs (user, job, wallet) |
| ISO 8601 Date | `2026-05-11` | Date of birth, dates |
| ISO 8601 DateTime | `2026-05-11T10:30:00Z` | Timestamps (always UTC) |
| Decimal/Money | `3500.00` | Amounts (always 2 decimal places) |
| Latitude | `6.5009` | Geographic coordinates |
| Longitude | `3.3564` | Geographic coordinates |

### Boolean Values
- `true` or `false` (lowercase JSON)
- Never use `"yes"`, `"no"`, `1`, `0`

### Null Values
- Use `null` (not empty string `""` or missing key)
- For optional fields not set

### Arrays
- Always use `[]` even for empty arrays
- Never use `null` for empty lists

### Decimal Numbers
- Always include decimal point: `5000.00` (not `5000`)
- For money: 2 decimal places
- For coordinates: 4 decimal places
- No currency symbols in JSON (currency implied by context)

## Common Response Patterns

### Successful Resource Creation (201)
```json
{
  "code": 201,
  "success": true,
  "message": "Job posted successfully",
  "data": {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "title": "Delivery Rider Needed",
    "created_at": "2026-05-11T10:30:00Z"
  }
}
```

### Successful Data Retrieval (200)
```json
{
  "code": 200,
  "success": true,
  "message": "User profile retrieved successfully",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "phone": "+2348012345678",
    "full_name": "John Doe"
  }
}
```

### Validation Error (400)
```json
{
  "code": 400,
  "success": false,
  "message": "Validation error",
  "errors": {
    "phone": ["Invalid phone format"],
    "pin": ["PIN must be 4 digits"],
    "amount": ["Amount must be greater than 0"]
  }
}
```

### Authentication Error (401)
```json
{
  "code": 401,
  "success": false,
  "message": "Invalid PIN",
  "errors": {}
}
```

### Permission Error (403)
```json
{
  "code": 403,
  "success": false,
  "message": "Only workers can accept jobs"
}
```

### Not Found (404)
```json
{
  "code": 404,
  "success": false,
  "message": "User not found"
}
```

### Conflict Error (409)
```json
{
  "code": 409,
  "success": false,
  "message": "Job is no longer available"
}
```

### Server Error (500)
```json
{
  "code": 500,
  "success": false,
  "message": "Internal server error"
}
```

## Authentication Header Format

For all endpoints requiring authentication:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
```

## Nested Objects

Keep nesting shallow (1-2 levels). Avoid deep hierarchies:

### ✅ Good
```json
{
  "data": {
    "user": { "id": "...", "name": "..." },
    "wallet": { "balance": "5000.00" }
  }
}
```

### ❌ Avoid
```json
{
  "data": {
    "user": {
      "personal": {
        "info": {
          "name": "John"
        }
      }
    }
  }
}
```

## List Responses

### Without Pagination
```json
{
  "code": 200,
  "success": true,
  "message": "Jobs retrieved successfully",
  "data": {
    "jobs": [
      { "id": "...", "title": "..." },
      { "id": "...", "title": "..." }
    ]
  }
}
```

### With Pagination (Future Standard)
```json
{
  "code": 200,
  "success": true,
  "message": "Users retrieved successfully",
  "data": {
    "count": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5,
    "next": "/api/users/?page=2",
    "previous": null,
    "results": [
      { "id": "...", "name": "..." }
    ]
  }
}
```

## Filtering & Query Parameters

Standard filter formats (all endpoints):

```
GET /api/jobs/?
  status=open
  &location_city=Lagos
  &skill_required=delivery
  &sort=-created_at
  &page=1
  &limit=20
```

## Response Header Standards

All API responses include:

```
Content-Type: application/json
X-Request-ID: <unique-request-id>
X-Response-Time: <milliseconds>
```

Protected endpoints include:
```
X-User-ID: <authenticated-user-id>
```

## Error Message Guidelines

### Validation Errors
- Be specific: `"Phone number must start with +234"`
- Not: `"Invalid phone"`

### Business Logic Errors
- Explain the issue: `"Job already filled, 3 workers have accepted"`
- Include next steps: `"Please post a new job or wait for completion"`

### Technical Errors (500)
- Keep generic for security
- Log detailed error server-side
- Suggest action: `"An error occurred. Support ticket: #12345"`

## Timestamp Standards

All timestamps in **ISO 8601** format with **UTC timezone**:
- `2026-05-11T10:30:00Z`
- Always include `Z` suffix for UTC
- Use `T` separator between date and time

Date-only inputs (no time): `2026-05-11`

## Code Examples

### Python - Creating Response
```python
from rest_framework.response import Response
from rest_framework import status

return Response({
    'code': 201,
    'success': True,
    'message': 'User created successfully',
    'data': user_serializer.data
}, status=status.HTTP_201_CREATED)
```

### JavaScript - Handling Response
```javascript
const response = await fetch('/api/users/create/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(userData)
});

const result = await response.json();
if (result.success) {
  console.log('Success:', result.data);
} else {
  console.error('Error:', result.message, result.errors);
}
```

## Implementation Checklist

Every endpoint should:
- ✅ Return `code`, `success`, `message` fields
- ✅ Use appropriate HTTP status codes
- ✅ Include `data` on success (even if empty)
- ✅ Include `errors` on 400 Bad Request
- ✅ Use ISO 8601 timestamps with Z suffix
- ✅ Use E.164 phone format
- ✅ Use UUIDs for resource IDs
- ✅ Use decimal strings for amounts
- ✅ Validate input before processing
- ✅ Handle and log errors properly
- ✅ Return consistent message strings

## API Endpoints by App

See individual app schema files:
- `apps/users/API_SCHEMA.md` - User creation, login, profile
- `apps/jobs/API_SCHEMA.md` - Job posting, acceptance, completion (TBD)
- `apps/wallets/API_SCHEMA.md` - Wallet operations (TBD)
- `apps/payments/API_SCHEMA.md` - Payment processing (TBD)
- `apps/marketplace/API_SCHEMA.md` - Marketplace listings (TBD)
- `apps/scoring/API_SCHEMA.md` - Score queries (TBD)

---

**Last Updated:** May 11, 2026  
**Version:** 1.0  
**All endpoints must comply with this standard.**
