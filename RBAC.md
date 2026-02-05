# Role-Based Access Control (RBAC)

NoobBook supports two user roles for multi-user deployments.

## Roles

| Role | Description |
|------|-------------|
| **admin** | Full access: API keys, user management, databases, processing settings, Google Drive config |
| **user** | Standard access: chat, studio, sources, projects |

## Environment Variables

Add these to `docker/.env`:

```bash
# Enable authentication (required for RBAC)
NOOBBOOK_AUTH_REQUIRED=true

# Comma-separated emails that get admin role on signup
NOOBBOOK_ADMIN_EMAILS=admin@example.com,another@example.com

# Bootstrap admin on startup (optional)
NOOBBOOK_BOOTSTRAP_ADMIN_EMAIL=admin@example.com
NOOBBOOK_BOOTSTRAP_ADMIN_PASSWORD=YourSecurePassword
NOOBBOOK_BOOTSTRAP_ADMIN_FORCE_RESET=false
```

## Admin-Only Features

### Backend Endpoints (Protected)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/settings/api-keys` | GET/POST | View/update API keys |
| `/settings/api-keys/<id>` | DELETE | Delete API key |
| `/settings/api-keys/validate` | POST | Test API key |
| `/settings/users` | GET | List all users |
| `/settings/users/<id>/role` | PUT | Change user role |
| `/settings/processing` | GET/POST | Processing tier config |
| `/settings/databases` | POST | Add database connection |
| `/settings/databases/<id>` | DELETE | Remove database |
| `/settings/databases/validate` | POST | Test database connection |

### Frontend UI

- **Admin Settings** button (gear icon) - only visible to admins
- User role management table in Admin Settings
- API key configuration
- Database connection management
- Processing settings (tier, workers)

## How It Works

1. **Authentication Flow**:
   - User signs up/in via `/auth/signup` or `/auth/signin`
   - Backend returns JWT token from Supabase Auth
   - Frontend stores token in localStorage
   - All API requests include `Authorization: Bearer <token>`

2. **Role Assignment**:
   - If email is in `NOOBBOOK_ADMIN_EMAILS` → admin
   - If no admins exist yet → admin (bootstrap)
   - Otherwise → user

3. **Authorization Check**:
   - `@require_admin` decorator on protected endpoints
   - Returns 403 if user is not admin
   - Returns 401 if not authenticated (when `NOOBBOOK_AUTH_REQUIRED=true`)

## Database Schema

```sql
-- users table has role column
ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user';
CONSTRAINT valid_user_role CHECK (role IN ('admin', 'user'))
```

## Testing

### 1. Check Auth Status
```bash
curl http://localhost:5001/api/v1/auth/me
# Returns: auth_required, user info, role
```

### 2. Sign In as Admin
```bash
curl -X POST http://localhost:5001/api/v1/auth/signin \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"Admin12345"}'
# Returns: access_token, refresh_token
```

### 3. Test Admin Endpoint
```bash
# With admin token - succeeds
curl http://localhost:5001/api/v1/settings/api-keys \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
# Returns: {"success": true, "api_keys": [...]}

# Without token - blocked
curl http://localhost:5001/api/v1/settings/api-keys
# Returns: {"success": false, "error": "Authentication required"}

# With user token - blocked
curl http://localhost:5001/api/v1/settings/api-keys \
  -H "Authorization: Bearer <USER_TOKEN>"
# Returns: {"success": false, "error": "Admin access required"}
```

### 4. Test Authenticated Request
```bash
curl http://localhost:5001/api/v1/auth/me \
  -H "Authorization: Bearer <TOKEN>"
# Returns: user_id, email, role, is_admin, is_authenticated
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/services/auth/rbac.py` | Core RBAC logic, decorators |
| `backend/app/api/auth/routes.py` | Auth endpoints (signup, signin, me) |
| `backend/app/services/data_services/user_service.py` | User management service |
| `backend/app/api/settings/users.py` | User management endpoints |
| `frontend/src/lib/auth/session.ts` | Token storage |
| `frontend/src/lib/api/auth.ts` | Auth API client |
| `frontend/src/components/auth/AuthPage.tsx` | Login/signup UI |

## Single-User Mode

When `NOOBBOOK_AUTH_REQUIRED=false` (default):
- No login required
- Default user gets admin role
- All features accessible

This maintains backward compatibility for local/single-user deployments.
