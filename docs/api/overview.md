# API Overview

Precogly exposes a REST API built with Django REST Framework. All endpoints are documented with an OpenAPI schema and can be explored interactively via Swagger UI.

## Base URL

All endpoints are prefixed with `/api/`:

```
http://localhost:8000/api/
```

## Content format

**Request and response bodies use JSON with camelCase keys.** The backend uses snake_case internally, but `djangorestframework-camel-case` converts keys automatically at the API boundary.

```json
{
  "threatModel": {
    "id": 1,
    "name": "Payment Gateway",
    "riskScoringMethod": "tm_library",
    "createdAt": "2026-01-15T10:30:00Z"
  }
}
```

A small set of keys are passed through without conversion for `dj-rest-auth` compatibility: `password1`, `password2`, `new_password1`, `new_password2`, `email`.

## Authentication

The API uses JWT bearer tokens via `djangorestframework-simplejwt`.

### Obtaining tokens

```
POST /api/auth/login/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

Response:

```json
{
  "accessToken": "eyJ...",
  "refreshToken": "eyJ...",
  "user": {
    "pk": 1,
    "email": "user@example.com"
  }
}
```

### Using tokens

Include the access token in the `Authorization` header:

```
Authorization: Bearer eyJ...
```

### Token lifetimes

| Token | Lifetime |
|-------|----------|
| Access token | 60 minutes |
| Refresh token | 7 days |

Refresh tokens rotate on each use. The previous refresh token is blacklisted after rotation.

### Refreshing tokens

```
POST /api/auth/token/refresh/

{
  "refresh": "eyJ..."
}
```

### Auth endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login/` | Obtain access and refresh tokens |
| `POST` | `/api/auth/logout/` | Blacklist refresh token |
| `POST` | `/api/auth/registration/` | Register a new account |
| `GET` | `/api/auth/user/` | Current user profile |
| `PUT/PATCH` | `/api/auth/user/` | Update profile |
| `POST` | `/api/auth/password/change/` | Change password |
| `POST` | `/api/auth/password/reset/` | Request password reset email |
| `POST` | `/api/auth/password/reset/confirm/` | Confirm password reset |
| `POST` | `/api/auth/token/refresh/` | Refresh access token |

## Pagination

Responses that return lists use page-based pagination with a default page size of **20**.

```json
{
  "count": 58,
  "next": "http://localhost:8000/api/threat-models/?page=2",
  "previous": null,
  "results": [...]
}
```

Use the `page` query parameter to navigate: `?page=2`, `?page=3`, etc.

Some endpoints (library browsing, scoring methods) disable pagination and return all results directly.

## Filtering, search, and ordering

Three filter backends are enabled globally:

- **DjangoFilterBackend** for field-level filtering: `?criticality=high&status=exposed`
- **SearchFilter** for text search: `?search=payment`
- **OrderingFilter** for sorting: `?ordering=-created_at`

Available filter fields vary by endpoint. Refer to the OpenAPI schema for each endpoint's supported parameters.

## Permissions

The API uses two levels of role-based access control. See [Roles and Permissions](../concepts/roles-and-permissions.md) for full details.

**Organization roles** determine broad access:

- **Security Team** has full read/write access across the organization, including library pack management and platform control assignments.
- **Member** has read access across accessible teams, write access only within teams they belong to (with a non-viewer team role).

**Team roles** (Lead, Member, Viewer) control write access to a team's threat models and related data. Viewers are read-only.

All endpoints require authentication by default. The only exceptions are magic link access (`/api/share/{token}/`) and invitation preview (`GET /api/invite/{token}/`).

## Interactive documentation

| URL | Format |
|-----|--------|
| `/api/docs/` | Swagger UI |
| `/api/redoc/` | ReDoc |
| `/api/schema/` | Raw OpenAPI 3.0 schema (YAML) |

The generated OpenAPI documentation is the canonical, exhaustive reference for request
fields, response schemas, filters, and status codes. The tables below provide a practical
map of the public resources and custom actions.

## Endpoint reference

### Threat models

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/threat-models/` | List threat models |
| `POST` | `/api/threat-models/` | Create threat model |
| `GET` | `/api/threat-models/{id}/` | Retrieve threat model |
| `PUT/PATCH` | `/api/threat-models/{id}/` | Update threat model |
| `DELETE` | `/api/threat-models/{id}/` | Delete threat model |
| `GET` | `/api/threat-models/{id}/threats/` | Aggregated threat analysis |
| `GET` | `/api/threat-models/{id}/report/` | Full report data |
| `GET` | `/api/threat-models/{id}/delete_preview/` | Preview cascade before deletion |
| `GET` | `/api/threat-models/{id}/zone_protections/` | Analyze zone protection suggestions |
| `POST` | `/api/threat-models/{id}/apply_zone_protections/` | Apply zone protection inheritance |
| `POST` | `/api/threat-models/{id}/add_system/` | Link an existing system |
| `POST` | `/api/threat-models/{id}/remove_system/` | Unlink a system |
| `POST` | `/api/threat-models/{id}/add_referenced_model/` | Add model relationship |
| `POST` | `/api/threat-models/{id}/remove_referenced_model/` | Remove model relationship |
| `POST` | `/api/threat-models/{id}/add_pack/` | Attach a library pack |
| `POST` | `/api/threat-models/{id}/remove_pack/` | Detach a library pack |
| `GET` | `/api/threat-models/{id}/countermeasures-in-use/` | List countermeasures active in the model |
| `GET` | `/api/threat-models/{id}/compliance_drift/` | Compare instance mappings with their library sources |
| `POST` | `/api/threat-models/{id}/refresh_compliance/` | Refresh instance compliance mappings from libraries |
| `POST` | `/api/threat-models/import/tm-library/` | Import from TM-Library JSON |
| `GET` | `/api/threat-models/{id}/export/tm-library/` | Export as TM-Library JSON |
| `POST` | `/api/threat-models/import/cyclonedx/` | Import from CycloneDX 2.0 TM-BOM JSON |
| `GET` | `/api/threat-models/{id}/export/cyclonedx/` | Export as CycloneDX 2.0 TM-BOM JSON |

**Reference images** (nested under threat model):

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/threat-models/{id}/reference-images/` | List images |
| `POST` | `/api/threat-models/{id}/reference-images/upload/` | Upload image (multipart) |
| `DELETE` | `/api/reference-images/{id}/` | Delete image |

**Out-of-scope items** (nested under threat model):

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/threat-models/{id}/out-of-scope-items/` | List or create |
| `GET/PUT/PATCH/DELETE` | `/api/threat-models/{id}/out-of-scope-items/{id}/` | Retrieve, update, or delete |

### Diagrams

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/diagrams/` | List DFDs |
| `POST` | `/api/diagrams/` | Create DFD |
| `GET` | `/api/diagrams/{id}/` | Retrieve DFD with canvas data |
| `PUT/PATCH` | `/api/diagrams/{id}/` | Update DFD (triggers component sync for primary DFDs) |
| `DELETE` | `/api/diagrams/{id}/` | Delete DFD |
| `POST` | `/api/diagrams/create_for_threat_model/` | Create DFD from template for a threat model |
| `GET` | `/api/diagrams/ai-availability/` | Check whether AI diagram generation is configured |
| `POST` | `/api/diagrams/analyze-image/` | Analyze an uploaded architecture image |
| `POST` | `/api/diagrams/generate-dfd/` | Generate DFD canvas data from an analyzed image |
| `GET` | `/api/diagrams/{id}/delete_preview/` | Preview cascade before deletion |

**DFD templates** (read-only):

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/dfd-templates/` | List templates |
| `GET` | `/api/dfd-templates/{id}/` | Template detail |
| `GET` | `/api/dfd-templates/{id}/resolved/` | Template with component library references resolved |

### Systems and components

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/systems/` | List or create systems |
| `GET/PUT/PATCH/DELETE` | `/api/systems/{id}/` | System CRUD |
| `GET/POST` | `/api/components/` | List or create components |
| `GET/PUT/PATCH/DELETE` | `/api/components/{id}/` | Component CRUD |
| `PATCH` | `/api/components/{id}/assign_system/` | Assign component to a system |
| `POST` | `/api/components/{id}/generate_threats/` | Generate threats from component library |
| `GET/POST` | `/api/component-library/` | Browse or create library components |
| `GET/PUT/PATCH/DELETE` | `/api/component-library/{id}/` | Library component CRUD |

### Trust zones and boundaries

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/trust-zones/` | List or create trust zones |
| `GET/PUT/PATCH/DELETE` | `/api/trust-zones/{id}/` | Trust zone CRUD |
| `GET/POST` | `/api/trust-boundaries/` | List or create trust boundaries |
| `GET/PUT/PATCH/DELETE` | `/api/trust-boundaries/{id}/` | Trust boundary CRUD |

### Data assets and flows

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/data-assets/` | List or create data assets |
| `GET/PUT/PATCH/DELETE` | `/api/data-assets/{id}/` | Data asset CRUD |
| `GET/POST` | `/api/data-flows/` | List or create data flows |
| `GET/PUT/PATCH/DELETE` | `/api/data-flows/{id}/` | Data flow CRUD |
| `GET/POST` | `/api/component-data-assets/` | Link data assets to components |
| `GET/POST` | `/api/data-flow-assets/` | Link data assets to data flows |
| `GET/POST` | `/api/integrations/` | List or create integration sources |
| `GET/PUT/PATCH/DELETE` | `/api/integrations/{id}/` | Integration source CRUD |

### Threats

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/threat-library/` | Browse or create library threats |
| `GET/PUT/PATCH/DELETE` | `/api/threat-library/{id}/` | Library threat CRUD |
| `GET/POST` | `/api/component-library-threats/` | Map library threats to library components |
| `GET/POST` | `/api/component-threats/` | List or create component instance threats |
| `GET/PUT/PATCH/DELETE` | `/api/component-threats/{id}/` | Instance threat CRUD |
| `GET` | `/api/component-threats/{id}/suggested_countermeasures/` | Countermeasure suggestions from library |
| `POST` | `/api/component-threats/{id}/apply_countermeasure/` | Apply a library countermeasure |
| `POST` | `/api/component-threats/{id}/recalculate_status/` | Recalculate threat status |
| `POST` | `/api/component-threats/reorder/` | Reorder component threats |
| `GET` | `/api/component-threats/ai_availability/` | Check AI suggestion availability |
| `POST` | `/api/component-threats/suggest/` | Get AI-ranked threat suggestions |
| `GET/POST` | `/api/flow-threats/` | List or create data flow instance threats |
| `GET/PUT/PATCH/DELETE` | `/api/flow-threats/{id}/` | Flow threat CRUD |
| `POST` | `/api/flow-threats/{id}/apply_countermeasure/` | Apply countermeasure to flow threat |
| `POST` | `/api/flow-threats/{id}/recalculate_status/` | Recalculate flow threat status |
| `POST` | `/api/flow-threats/reorder/` | Reorder data flow threats |

### Countermeasures

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/countermeasure-library/` | Browse or create library countermeasures |
| `GET/PUT/PATCH/DELETE` | `/api/countermeasure-library/{id}/` | Library countermeasure CRUD |
| `GET/POST` | `/api/countermeasures/` | List or create unified countermeasure instances |
| `GET/PUT/PATCH/DELETE` | `/api/countermeasures/{id}/` | Countermeasure instance CRUD |
| `POST` | `/api/countermeasures/{id}/link/` | Link a countermeasure to another component or flow threat |
| `POST` | `/api/countermeasures/{id}/unlink/` | Unlink a countermeasure from a threat |
| `POST` | `/api/countermeasures/reorder/` | Reorder countermeasures within a threat |
| `GET/POST` | `/api/countermeasure-comments/` | List or create countermeasure history entries |
| `GET/PUT/PATCH/DELETE` | `/api/countermeasure-comments/{id}/` | Countermeasure comment CRUD |
| `GET/POST` | `/api/verification-tests/` | List or create verification tests |
| `GET/PUT/PATCH/DELETE` | `/api/verification-tests/{id}/` | Verification test CRUD |
| `GET/POST` | `/api/pentest-findings/` | List or create pentest findings |
| `GET/PUT/PATCH/DELETE` | `/api/pentest-findings/{id}/` | Pentest finding CRUD |

### Compliance

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/frameworks/` | List or create compliance frameworks |
| `GET/PUT/PATCH/DELETE` | `/api/frameworks/{id}/` | Framework CRUD |
| `GET/POST` | `/api/requirements/` | List or create standard requirements |
| `GET/PUT/PATCH/DELETE` | `/api/requirements/{id}/` | Requirement CRUD |
| `GET/POST` | `/api/countermeasure-standards/` | Library-level compliance mappings |

### Taxonomies

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/taxonomies/` | List taxonomies (STRIDE, CAPEC, CWE, etc.) |
| `GET` | `/api/taxonomies/{id}/` | Taxonomy detail |
| `GET` | `/api/taxonomy-entries/` | List taxonomy entries |
| `GET` | `/api/taxonomy-entries/{id}/` | Entry detail |

### Risk management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/threat-models/{id}/risks/` | List or create risks for a threat model |
| `GET/PUT/PATCH/DELETE` | `/api/threat-models/{id}/risks/{id}/` | Risk CRUD |
| `POST` | `/api/threat-models/{id}/risks/{id}/recalculate/` | Recalculate risk scores |
| `POST` | `/api/threat-models/{id}/risks/{id}/add-threats/` | Link threats to a risk |
| `POST` | `/api/threat-models/{id}/risks/{id}/remove-threats/` | Unlink threats from a risk |
| `POST` | `/api/threat-models/{id}/risks/bulk-update/` | Bulk update risk response or owner |
| `GET` | `/api/scoring-methods/` | List available risk scoring methods |

### Threat personas and sources

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/threat-models/{id}/threat-personas/` | List or create threat personas for a model |
| `GET/PUT/PATCH/DELETE` | `/api/threat-models/{id}/threat-personas/{id}/` | Threat persona CRUD |
| `GET` | `/api/threat-sources/` | List global threat source reference data |
| `GET` | `/api/threat-sources/{id}/` | Threat source detail |

### Organizations and teams

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/organizations/` | List or create organizations |
| `GET/PUT/PATCH/DELETE` | `/api/organizations/{id}/` | Organization CRUD |
| `GET` | `/api/organizations/{id}/members/` | List organization members |
| `POST` | `/api/organizations/{id}/add-member/` | Add member to organization |
| `POST` | `/api/organizations/{id}/remove-member/` | Remove member from organization |
| `GET/POST` | `/api/teams/` | List or create teams |
| `GET/PUT/PATCH/DELETE` | `/api/teams/{id}/` | Team CRUD |
| `GET` | `/api/teams/{id}/members/` | List team members |
| `POST` | `/api/teams/{id}/add-member/` | Add member to team |
| `POST` | `/api/teams/{id}/invite-member/` | Send team invitation |
| `POST` | `/api/teams/{id}/remove-member/` | Remove member from team |
| `POST` | `/api/teams/{id}/change-member-role/` | Change a member's team role |
| `POST` | `/api/teams/{id}/join/` | Join a team (via invitation) |
| `GET/POST` | `/api/business-units/` | Business unit CRUD |
| `GET/POST` | `/api/memberships/` | Organization membership CRUD |

### Invitations and sharing

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/team-invitations/` | List or create invitations |
| `POST` | `/api/team-invitations/{id}/revoke/` | Revoke a pending invitation |
| `GET/POST` | `/api/magic-links/` | List or create magic links |
| `POST` | `/api/magic-links/{id}/revoke/` | Revoke a magic link |
| `GET` | `/api/shared-with-me/` | List threat models shared with current user |
| `DELETE` | `/api/shared-with-me/{id}/remove/` | Remove from shared list |
| `GET` | `/api/share/{token}/` | Access a shared threat model (no auth required) |
| `GET` | `/api/invite/{token}/` | Preview invitation details (no auth required) |
| `POST` | `/api/invite/{token}/` | Accept invitation (auth required) |

### Library packs

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/packs/` | List imported packs |
| `GET` | `/api/packs/{id}/` | Pack detail |
| `GET` | `/api/packs/{id}/preview/` | Preview pack contents |
| `GET` | `/api/packs/{id}/check_dependencies/` | Check dependency status |
| `DELETE` | `/api/packs/{id}/unimport/` | Unimport a pack (Security Team only) |
| `GET` | `/api/packs/available_from_source/` | Browse packs available for import |
| `GET` | `/api/packs/preview_from_source/` | Preview a pack before importing |
| `POST` | `/api/packs/import_single/` | Import a pack (Security Team only) |
| `POST` | `/api/packs/sync_from_source/` | Sync pack catalog (Security Team only) |
| `POST` | `/api/packs/validate/` | Validate pack YAML (Security Team only) |
| `GET` | `/api/packs/available_overlays/` | List compliance overlays available for a pack |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health/` | Health check |
| `GET` | `/api/dashboard/stats/` | Dashboard statistics |

### AI providers and usage

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/ai-providers/` | List or create organization AI provider configurations |
| `GET/PUT/PATCH/DELETE` | `/api/ai-providers/{id}/` | AI provider configuration CRUD |
| `POST` | `/api/ai-providers/{id}/test-connection/` | Test an AI provider connection |
| `GET` | `/api/ai-usage/summary/` | Organization AI usage summary |

## Error responses

The API returns standard HTTP status codes:

| Code | Meaning |
|------|---------|
| `400` | Bad request. Validation errors are returned as a JSON object with field names as keys. |
| `401` | Authentication required or token expired. |
| `403` | Insufficient permissions for this action. |
| `404` | Resource not found. |
| `405` | Method not allowed. |

Validation error example:

```json
{
  "name": ["This field is required."],
  "criticality": ["\"invalid\" is not a valid choice."]
}
```

## Multi-tenancy

All data is scoped to the authenticated user's organization memberships. Queries automatically filter to organizations the user belongs to. There is no way to access data from organizations you are not a member of.
