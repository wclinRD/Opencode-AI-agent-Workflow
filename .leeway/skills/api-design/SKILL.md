# api-design

API design review guidelines and best practices.

## RESTful API Principles

### URL Design
- Use nouns, not verbs: `/users` not `/getUsers`
- Use plural for collections: `/users`, `/orders`
- Use hyphens for readability: `/user-profiles`
- Keep URLs lowercase
- No trailing slashes

### HTTP Methods

| Method | Usage | Idempotent |
|--------|-------|------------|
| GET | Retrieve resources | Yes |
| POST | Create new resources | No |
| PUT | Replace entire resource | Yes |
| PATCH | Partial update | No |
| DELETE | Remove resource | Yes |

### Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Success |
| 201 | Created - Resource created |
| 204 | No Content - Success, no response body |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Permission denied |
| 404 | Not Found - Resource doesn't exist |
| 500 | Internal Error - Server error |

## Request/Response Format

### JSON Conventions
- Use camelCase for field names
- Include `_metadata` for pagination
- Use ISO 8601 for dates
- Use UUIDs for IDs

### Example Request
```json
{
  "name": "John Doe",
  "email": "john@example.com"
}
```

### Example Response
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "John Doe",
  "email": "john@example.com",
  "created_at": "2024-01-15T10:30:00Z"
}
```

## Error Handling

### Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "details": [
      { "field": "email", "message": "Invalid format" }
    ]
  }
}
```

### Best Practices
- Consistent error format
- Include error codes
- Provide actionable messages
- Log errors for debugging
- Never expose stack traces

## Versioning

### URL Versioning
- `/api/v1/users`
- `/api/v2/users`

### Header Versioning
- `Accept: application/vnd.myapp.v1+json`

## Pagination

### Query Parameters
- `page` - Page number (default: 1)
- `limit` - Items per page (default: 20, max: 100)
- `sort` - Sort field
- `order` - Sort order (asc/desc)

### Response Format
```json
{
  "data": [...],
  "_metadata": {
    "total": 150,
    "page": 1,
    "limit": 20,
    "total_pages": 8
  }
}
```

## Usage Example

```typescript
workflow({
  name: "api-design",
  user_context: "Review the API design in src/api.ts"
})
```