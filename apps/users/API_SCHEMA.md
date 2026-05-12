# Users API Schema

## Overview
All API responses follow a standard JSON format with consistent structure across all endpoints in the codebase.

## Standard Response Format

### Success Response (2xx)
```json
{
  "code": 200,
  "success": true,
  "message": "Description of successful operation",
  "data": {
    // Response payload varies by endpoint
  }
}
```

### Error Response (4xx, 5xx)
```json
{
  "code": 400,
  "success": false,
  "message": "Description of error",
  "errors": {
    // Optional: validation errors
    "field_name": ["error message"]
  }
}
```

## Endpoints

### 1. User Creation
**POST** `/api/users/create/`

Creates a new user with SQUAD virtual account.

#### Request Body
```json
{
  "phone": "+2348012345678",
  "full_name": "John Doe",
  "role": "worker",
  "email": "john@example.com",
  "date_of_birth": "1990-01-15",
  "bvn": "22345678901",
  "gender": "M",
  "address": "123 Main Street",
  "location_area": "Surulere",
  "location_city": "Lagos",
  "skills": ["delivery", "cleaning"],
  "languages": ["en", "yo"],
  "has_vehicle": true,
  "vehicle_type": "bike",
  "availability": "full_day",
  "trade_category": "",
  "market_name": "",
  "weekly_income_range": "₦10,000-₦50,000",
  "business_name": "",
  "channel": "app",
  "pin": "1234"
}
```

#### Response (201 Created)
```json
{
  "code": 201,
  "success": true,
  "message": "User created successfully",
  "data": {
    "tokens": {
      "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    },
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "phone": "+2348012345678",
      "full_name": "John Doe",
      "email": "john@example.com",
      "role": "worker",
      "bvn": "22345678901",
      "gender": "M",
      "address": "123 Main Street",
      "location_area": "Surulere",
      "location_city": "Lagos",
      "location_lat": "6.5009",
      "location_lng": "3.3564",
      "skills": ["delivery", "cleaning"],
      "languages": ["en", "yo"],
      "has_vehicle": true,
      "vehicle_type": "bike",
      "availability": "full_day",
      "squad_account_number": "0700123456789",
      "squad_bank_name": "GTBank",
      "squad_account_status": "active",
      "squad_account_created_at": "2026-05-11T10:30:00Z",
      "is_active": true,
      "onboarding_complete": false,
      "created_at": "2026-05-11T10:30:00Z",
      "updated_at": "2026-05-11T10:30:00Z"
    }
  }
}
```

#### Response (200 OK - User Exists)
```json
{
  "code": 200,
  "success": true,
  "message": "User already exists",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "phone": "+2348012345678",
    "full_name": "John Doe",
    "role": "worker",
    "is_active": true
  }
}
```

#### Error Response (400 Bad Request)
```json
{
  "code": 400,
  "success": false,
  "message": "Validation error",
  "errors": {
    "phone": ["This field is required."],
    "role": ["Invalid choice: xyz"]
  }
}
```

---

### 2. User Login
**POST** `/api/users/login/`

Authenticate user by phone and PIN, returns JWT tokens.

#### Request Body
```json
{
  "phone": "+2348012345678",
  "pin": "1234"
}
```

#### Response (200 OK)
```json
{
  "code": 200,
  "success": true,
  "message": "Login successful",
  "data": {
    "tokens": {
      "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    },
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "phone": "+2348012345678",
      "full_name": "John Doe",
      "role": "worker"
    }
  }
}
```

#### Error Response (401 Unauthorized)
```json
{
  "code": 401,
  "success": false,
  "message": "Invalid PIN"
}
```

---

### 3. Get User Profile
**GET** `/api/users/profile/`

Retrieve authenticated user's profile information.

**Authentication Required:** Bearer token

#### Response (200 OK)
```json
{
  "code": 200,
  "success": true,
  "message": "Profile retrieved successfully",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "phone": "+2348012345678",
    "full_name": "John Doe",
    "email": "john@example.com",
    "role": "worker",
    "bvn": "22345678901",
    "location_area": "Surulere",
    "location_city": "Lagos",
    "skills": ["delivery", "cleaning"],
    "squad_account_number": "0700123456789",
    "squad_bank_name": "GTBank",
    "is_active": true,
    "onboarding_complete": false,
    "created_at": "2026-05-11T10:30:00Z"
  }
}
```

---

### 4. Update User Profile
**PATCH** `/api/users/profile/`

Update authenticated user's profile fields.

**Authentication Required:** Bearer token

#### Request Body (partial update)
```json
{
  "full_name": "Jane Doe",
  "location_area": "Lekki",
  "skills": ["delivery", "security"],
  "availability": "part_time"
}
```

#### Response (200 OK)
```json
{
  "code": 200,
  "success": true,
  "message": "Profile updated successfully",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "phone": "+2348012345678",
    "full_name": "Jane Doe",
    "location_area": "Lekki",
    "skills": ["delivery", "security"],
    "availability": "part_time",
    "updated_at": "2026-05-11T11:00:00Z"
  }
}
```

---

## Standard HTTP Status Codes

| Code | Meaning | Use Case |
|------|---------|----------|
| 200 | OK | Successful GET, PATCH |
| 201 | Created | Successful POST with resource creation |
| 400 | Bad Request | Validation error, invalid input |
| 401 | Unauthorized | Missing/invalid authentication token |
| 403 | Forbidden | Authenticated but lacks permission |
| 404 | Not Found | Resource not found |
| 500 | Server Error | Unexpected server error |

## Field Definitions

### User Object
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| id | UUID | Unique user identifier | `550e8400-e29b-41d4-a716-446655440000` |
| phone | String | Phone number (E.164 format) | `+2348012345678` |
| full_name | String | User's full name | `John Doe` |
| email | String | User's email address | `john@example.com` |
| role | Enum | User role: worker, trader, employer | `worker` |
| bvn | String | Bank Verification Number | `22345678901` |
| gender | String | Gender: M, F, O | `M` |
| address | String | Residential address | `123 Main Street` |
| location_area | String | Specific area/neighborhood | `Surulere` |
| location_city | String | City name | `Lagos` |
| location_lat | String | Latitude coordinate | `6.5009` |
| location_lng | String | Longitude coordinate | `3.3564` |
| skills | Array | List of skills | `["delivery", "cleaning"]` |
| languages | Array | Languages spoken | `["en", "yo"]` |
| has_vehicle | Boolean | Vehicle availability | `true` |
| vehicle_type | String | Type of vehicle | `bike`, `car`, `none` |
| availability | Enum | Work availability | `full_day`, `part_time`, `weekends` |
| squad_account_number | String | Virtual account number | `0700123456789` |
| squad_bank_name | String | Bank name | `GTBank` |
| squad_account_status | String | VA status | `active`, `failed` |
| squad_account_created_at | ISO DateTime | VA creation timestamp | `2026-05-11T10:30:00Z` |
| is_active | Boolean | Account active status | `true` |
| onboarding_complete | Boolean | Onboarding completion | `false` |
| created_at | ISO DateTime | Account creation timestamp | `2026-05-11T10:30:00Z` |
| updated_at | ISO DateTime | Last update timestamp | `2026-05-11T11:00:00Z` |

## Authentication

### Bearer Token
All protected endpoints require the `Authorization` header with JWT token:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Token Structure
- **Access Token**: Short-lived JWT for API requests (15 minutes)
- **Refresh Token**: Long-lived JWT for obtaining new access tokens (7 days)

## Enum Values

### Role
- `worker`: Service provider/gig worker
- `trader`: Small business owner/trader
- `employer`: Business hiring services

### Gender
- `M`: Male
- `F`: Female
- `O`: Other

### Availability
- `full_day`: Full-time availability
- `part_time`: Part-time availability
- `weekends`: Weekends only

### Vehicle Type
- `bike`: Motorcycle/Bike
- `car`: Car/Vehicle
- `van`: Van
- `none`: No vehicle

## Error Codes and Messages

| Code | Message | Resolution |
|------|---------|-----------|
| 400 | Validation error | Check request body for missing/invalid fields |
| 401 | Invalid PIN | Verify PIN is correct |
| 404 | User not found | Verify phone number exists |
| 403 | Account deactivated | Contact support for account reactivation |
| 500 | Internal server error | Retry request, contact support if persists |

## Date/Time Format

All timestamps are in **ISO 8601** format with UTC timezone:
- `2026-05-11T10:30:00Z`

All date inputs should also be ISO 8601:
- `2026-05-11` or `2026-05-11T00:00:00Z`

## Pagination (Future Implementation)

When endpoints support pagination, the response structure will be:

```json
{
  "code": 200,
  "success": true,
  "message": "List retrieved successfully",
  "data": {
    "count": 100,
    "next": "/api/users/?page=2",
    "previous": null,
    "results": [
      { /* user object */ }
    ]
  }
}
```

## Rate Limiting (Future Implementation)

Response headers will include:
- `X-RateLimit-Limit`: Max requests per hour
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp of limit reset
