---
name: eve-esi-api
description: Use when building EVE Online integrations, working with ESI endpoints, handling OAuth2 SSO authentication, rate limiting ESI requests, or debugging EVE API errors. Covers all 195 endpoints, 64 OAuth scopes, cache TTLs, pagination, and versioning.
---

# EVE Online ESI API Reference

Source: https://developers.eveonline.com/docs/ + OpenAPI spec at esi.evetech.net

## Quick Start

```
Base URL:    https://esi.evetech.net/latest/
Auth:        OAuth2 Bearer token via SSO at login.eveonline.com
Spec:        https://esi.evetech.net/latest/swagger.json (860KB, 195 endpoints)
SSO Metadata: https://login.eveonline.com/.well-known/oauth-authorization-server
```

## Versioning

### URL Path Versioning
| Path | Stability |
|------|-----------|
| `/dev/` | Unstable, changes without notice |
| `/latest/` | Stable, changes announced in advance |
| `/legacy/` | Previous `/latest/` after version bump |
| `/v1/`, `/v2/` | Pinned versions for production |

### Compatibility Date Header
Every request can include `X-Compatibility-Date: YYYY-MM-DD` to get API behavior as of that date.
If omitted, the oldest available date is used. API changes date at 11:00 UTC.

Changes under **new** compatibility date: adding routes, changing required params, changing types, removing fields.
Changes under **existing** date: adding optional params, adding response fields/enums.

## SSO OAuth2 Flow

### Authorization Code Flow

**1. Authorization URL**
```
https://login.eveonline.com/v2/oauth/authorize/?
  response_type=code
  &client_id=<client-id>
  &redirect_uri=<callback>         # Must exactly match registered URL
  &scope=<space-delimited-scopes>
  &state=<random-csrf-token>
```

**2. Exchange Code for Tokens**
```python
POST https://login.eveonline.com/v2/oauth/token
Authorization: Basic base64(client_id:secret_key)
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&code=<one-time-code>
# Code expires in 5 minutes, single use only
```

Response: `{"access_token": "<JWT ~20min>", "expires_in": 1199, "token_type": "Bearer", "refresh_token": "<long-lived>"}`

**3. Refresh Token** (new refresh_token may differ — always store the new one)
```python
POST https://login.eveonline.com/v2/oauth/token
Authorization: Basic base64(client_id:secret_key)

grant_type=refresh_token&refresh_token=<token>
# Optional: &scope=<subset-of-original-scopes>
```

### PKCE Flow (mobile/desktop apps)
For apps that can't securely store client secret:
1. Generate `code_verifier` (32 random bytes, base64url-encoded)
2. Generate `code_challenge` = SHA256(code_verifier), base64url-encoded (no padding)
3. Add `code_challenge=<hash>&code_challenge_method=S256` to authorize URL
4. Add `code_verifier=<verifier>&client_id=<id>` to token request (no Basic auth)

### JWT Validation
- **Signature**: Fetch public key from JWKS endpoint (get URL from `.well-known/oauth-authorization-server`)
- **Issuer** (`iss`): Must be `https://login.eveonline.com/` or `login.eveonline.com`
- **Audience** (`aud`): Must contain your `client_id` AND `"EVE Online"`
- **Expiration** (`exp`): Unix timestamp, reject if expired
- **Claims**: `sub` = `CHARACTER:EVE:<character-id>`, `name` = character name, `scp` = granted scopes array

## Rate Limiting (New Bucket System)

ESI uses **floating window rate limiting** (not fixed window).

### Token Costs per Status Code
| Status | Cost | Reason |
|--------|------|--------|
| 2XX | 2 tokens | Normal |
| 3XX | 1 token | Promotes conditional requests |
| 4XX | 5 tokens | Discourages errors (not 429) |
| 5XX | 0 tokens | Server errors don't penalize |

### Bucket Assignment
Each `rate_limit_group + userID` pair gets its own bucket:
- Authenticated: `applicationID:characterID`
- Public: `sourceIP` (or `sourceIP:applicationID` if token provided)

### Rate Limit Headers
- `X-Ratelimit-Group`: Route group identifier
- `X-Ratelimit-Limit`: Total tokens per window (e.g., `150/15m`)
- `X-Ratelimit-Remaining`: Available tokens remaining
- `X-Ratelimit-Used`: Tokens consumed by this request
- `Retry-After`: Seconds to wait (only on 429)

### OpenAPI Extension
Routes with rate limiting have `x-rate-limit`: `{group, window-size, max-tokens}`

### Error Rate Limit (Legacy)
For routes without bucket limiting: max 100 non-2xx/3xx per minute.
- `X-ESI-Error-Limit-Remain`: Errors remaining
- `X-ESI-Error-Limit-Reset`: Seconds until reset

## Caching

| Header | Purpose |
|--------|---------|
| `Expires` | When fresh data becomes available |
| `Last-Modified` | Timestamp of last cache update |
| `ETag` / `If-None-Match` | Conditional requests (304 if unchanged) |

**Critical:** Requesting before `expires` = cache circumvention = potential ban.

### Cache TTL by Endpoint

| TTL | Endpoints |
|-----|-----------|
| **5s** | Calendar, fleet, location, ship, sovereignty campaigns |
| **30s** | Mail, status |
| **60s** | Fleet info, online status |
| **120s** | Attributes, clones, skills, wallet, sovereignty structures |
| **300s** | Contacts, contracts, industry, killmails, market orders, incursions |
| **600s** | Mining, notifications, planets, market types |
| **1200s** | Character open orders |
| **1800s** | FW systems, public contracts, moon extractions |
| **3600s** | Alliances, corps, assets, blueprints, market prices, structures, insurance, wars |
| **86400s** | Corporation history, routes |
| **604800s** | Character public info (7 days) |
| **30758400s** | Killmails (~1 year, immutable) |
| **no-cache** | Write ops, dogma, universe static data, search, loyalty |

## Pagination (3 Types)

### 1. X-Pages (traditional)
- Request: `?page=N`
- Response header: `X-Pages` = total pages
- Risk: cache expiry between pages causes duplicates

### 2. Cursor-based (new)
- Response: `{"data": [...], "cursor": {"before": "<token>", "after": "<token>"}}`
- `before` = older records, `after` = newer records
- Tokens are opaque position markers — don't parse them
- Initial: no params → get recent. Then use `before` to paginate backward
- Monitor: use `after` token to detect new/modified records
- Duplicates are normal — replace stored record if using `after`

### 3. From-ID (historical)
- Request: `?from_id=<transaction_id>`
- Returns that record + older records, ordered most-recent-first
- Stop when response contains only the `from_id` record

## User-Agent Requirements

Must include contact info for CCP support. Options by capability:

| Capability | Method |
|-----------|--------|
| Can set headers, not browser | `User-Agent: AppName/1.2.3 (email@example.com)` |
| Browser app | `X-User-Agent` header (Chrome drops `User-Agent`) |
| No header control | `?user_agent=<url-encoded>` query param |

Include: email (preferred), app name+version, source URL, Discord, or EVE character.

## All 195 Endpoints

### markets (7)
```
GET /markets/prices/                          3600s   pub
GET /markets/groups/                          no-cache pub
GET /markets/groups/{market_group_id}/        no-cache pub
GET /markets/{region_id}/orders/              300s    pub
GET /markets/{region_id}/types/               600s    pub
GET /markets/{region_id}/history/             no-cache pub
GET /markets/structures/{structure_id}/       300s    AUTH
```

### characters (63)
```
# Real-time (5-60s)
GET /characters/{id}/calendar/                5s      AUTH
GET /characters/{id}/location/                5s      AUTH
GET /characters/{id}/ship/                    5s      AUTH
GET /characters/{id}/mail/                    30s     AUTH
GET /characters/{id}/fleet/                   60s     AUTH
GET /characters/{id}/online/                  60s     AUTH

# Medium (120-600s)
GET /characters/{id}/attributes/              120s    AUTH
GET /characters/{id}/skillqueue/              120s    AUTH
GET /characters/{id}/skills/                  120s    AUTH
GET /characters/{id}/wallet/                  120s    AUTH
GET /characters/{id}/contacts/                300s    AUTH
GET /characters/{id}/contracts/               300s    AUTH
GET /characters/{id}/industry/jobs/           300s    AUTH
GET /characters/{id}/killmails/recent/        300s    AUTH
GET /characters/{id}/notifications/           600s    AUTH
GET /characters/{id}/mining/                  600s    AUTH
GET /characters/{id}/planets/                 600s    AUTH

# Slow (3600s+)
GET /characters/{id}/assets/                  3600s   AUTH
GET /characters/{id}/blueprints/              3600s   AUTH
GET /characters/{id}/loyalty/points/          3600s   AUTH
GET /characters/{id}/orders/history/          3600s   AUTH
GET /characters/{id}/wallet/journal/          3600s   AUTH
GET /characters/{id}/wallet/transactions/     3600s   AUTH
GET /characters/{id}/corporationhistory/      86400s  pub
GET /characters/{id}/                         604800s pub

# Write (no cache)
POST /characters/affiliation/                 3600s   pub   Bulk lookup
POST /characters/{id}/assets/locations/       no-cache AUTH
POST /characters/{id}/contacts/               no-cache AUTH
POST /characters/{id}/mail/                   no-cache AUTH
```

### corporations (39)
```
GET /corporations/{id}/                       3600s   pub
GET /corporations/{id}/members/               3600s   AUTH
GET /corporations/{id}/assets/                3600s   AUTH roles=[Director]
GET /corporations/{id}/structures/            3600s   AUTH roles=[Station_Manager]
GET /corporations/{id}/wallets/               300s    AUTH roles=[Accountant]
GET /corporations/{id}/orders/                1200s   AUTH roles=[Accountant,Trader]
GET /corporations/{id}/contracts/             300s    AUTH
GET /corporations/{id}/industry/jobs/         300s    AUTH roles=[Factory_Manager]
```

### universe (31)
```
# Static (no cache)
GET /universe/types/                          pub
GET /universe/types/{type_id}/                pub
GET /universe/regions/                        pub
GET /universe/systems/                        pub
GET /universe/categories/                     pub
GET /universe/groups/                         pub
POST /universe/ids/                           pub   Bulk names→IDs
POST /universe/names/                         pub   Bulk IDs→names

# Dynamic
GET /universe/structures/                     3600s   pub
GET /universe/structures/{structure_id}/      3600s   AUTH
GET /universe/system_jumps/                   3600s   pub
GET /universe/system_kills/                   3600s   pub
```

### Other groups
- **alliances** (6): list, info, corporations, icons, contacts
- **contracts** (3): public bids, items, region contracts
- **dogma** (5): attributes, effects, dynamic items
- **fleets** (13): CRUD fleet, members, wings, squads
- **fw** (6): leaderboards, stats, systems, wars
- **incursions** (1): list active incursions
- **industry** (2): facilities, system cost indices
- **insurance** (1): price levels
- **killmails** (1): get single killmail (30758400s cache)
- **loyalty** (1): store offers
- **route** (1): system-to-system routing (86400s cache)
- **sovereignty** (3): campaigns, map, structures
- **status** (1): uptime and player count (30s cache)
- **ui** (5): open windows, set waypoints
- **wars** (3): list, info, killmails
- **corporation/mining** (3): extractions, observers

## All 64 OAuth Scopes

### Market & Trading
```
esi-markets.read_character_orders.v1    esi-markets.read_corporation_orders.v1
esi-markets.structure_markets.v1        esi-wallet.read_character_wallet.v1
esi-wallet.read_corporation_wallets.v1
```

### Assets
```
esi-assets.read_assets.v1               esi-assets.read_corporation_assets.v1
```

### Character
```
esi-characters.read_blueprints.v1       esi-characters.read_contacts.v1
esi-characters.write_contacts.v1        esi-characters.read_corporation_roles.v1
esi-characters.read_fatigue.v1          esi-characters.read_standings.v1
esi-characters.read_medals.v1           esi-characters.read_titles.v1
esi-characters.read_loyalty.v1          esi-characters.read_agents_research.v1
esi-characters.read_notifications.v1    esi-characters.read_fw_stats.v1
```

### Skills & Clones
```
esi-skills.read_skills.v1               esi-skills.read_skillqueue.v1
esi-clones.read_clones.v1               esi-clones.read_implants.v1
```

### Industry & Combat
```
esi-industry.read_character_jobs.v1     esi-industry.read_corporation_jobs.v1
esi-industry.read_character_mining.v1   esi-industry.read_corporation_mining.v1
esi-killmails.read_killmails.v1         esi-killmails.read_corporation_killmails.v1
esi-location.read_location.v1           esi-location.read_online.v1
esi-location.read_ship_type.v1
```

### Corporation
```
esi-corporations.read_corporation_membership.v1  esi-corporations.track_members.v1
esi-corporations.read_structures.v1       esi-corporations.read_starbases.v1
esi-corporations.read_divisions.v1        esi-corporations.read_facilities.v1
esi-corporations.read_blueprints.v1       esi-corporations.read_contacts.v1
esi-corporations.read_container_logs.v1   esi-corporations.read_medals.v1
esi-corporations.read_standings.v1        esi-corporations.read_titles.v1
esi-corporations.read_fw_stats.v1
```

### Mail, Calendar, Other
```
esi-mail.read_mail.v1       esi-mail.send_mail.v1       esi-mail.organize_mail.v1
esi-calendar.read_calendar_events.v1    esi-calendar.respond_calendar_events.v1
esi-fittings.read_fittings.v1           esi-fittings.write_fittings.v1
esi-fleets.read_fleet.v1                esi-fleets.write_fleet.v1
esi-planets.manage_planets.v1           esi-planets.read_customs_offices.v1
esi-contracts.read_character_contracts.v1  esi-contracts.read_corporation_contracts.v1
esi-search.search_structures.v1         esi-universe.read_structures.v1
esi-alliances.read_contacts.v1          esi-ui.open_window.v1
esi-ui.write_waypoint.v1
```

## Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | — |
| 304 | Not modified (ETag match) | Use cached data |
| 400 | Bad request | Check parameters |
| 401 | Unauthorized | Refresh token |
| 403 | Forbidden | Check scopes |
| 404 | Not found | Verify IDs |
| 420 | Error limited (legacy) | Stop until X-ESI-Error-Limit-Reset |
| 422 | Unprocessable | Check request body |
| 429 | Rate limited | Wait Retry-After seconds |
| 500 | Server error | Retry with backoff |
| 503 | Unavailable | Retry later |
| 504 | Gateway timeout | Retry later |
| 520 | EVE internal (mail/contracts) | Counts against error limit |

## Third-Party Data

| Source | URL | Content |
|--------|-----|---------|
| Fuzzwork | market.fuzzwork.co.uk/api/ | Market order scrapes |
| EVE Ref | everef.net/data | Market history (>1yr), orders, contracts |
| SDE | See SDE section below | Type IDs, regions, systems, blueprints |
| Image Server | imageserver.eveonline.com | Character/type/alliance portraits |

## SDE (Static Data Export)

Reference: https://developers.eveonline.com/docs/services/static-data/

### Update Frequency
SDE **only changes with game updates** on Tranquility server. No fixed calendar schedule — releases are tied to game patches.

### Download URLs

**Always-latest (redirect to current build):**
| Format | URL |
|--------|-----|
| YAML | `https://developers.eveonline.com/static-data/eve-online-static-data-latest-yaml.zip` |
| JSON Lines | `https://developers.eveonline.com/static-data/eve-online-static-data-latest-jsonl.zip` |

**Versioned (for automation):**
```
https://developers.eveonline.com/static-data/tranquility/eve-online-static-data-<build>-<variant>.zip
```

### Automation Endpoints

| Purpose | URL | Notes |
|---------|-----|-------|
| Latest build number | `developers.eveonline.com/static-data/tranquility/latest.jsonl` | `{"_key":"sde","buildNumber":3366957,"releaseDate":"2026-05-29T12:13:06Z"}` |
| Per-build changes | `developers.eveonline.com/static-data/tranquility/changes/<build>.jsonl` | `_meta.lastBuildNumber` = previous build |
| Schema changelog | `developers.eveonline.com/static-data/tranquility/schema-changelog.yaml` | Breaking schema changes |

### Version Detection Flow
```
1. GET latest.jsonl → parse buildNumber
2. Compare with locally stored build number
3. If different → download new ZIP
4. Save build number + ZIP to disk
```

### HTTP Caching
All resources support `ETag` and `Last-Modified` headers. Non-static files cached for 5 minutes. Resources only update when content actually changes.

### File Formats
- **YAML**: Integer keys native. Memory-intensive for large files (e.g., `mapMoons`).
- **JSON Lines**: Keys must be strings; integer keys become `{"_key":N,"_value":...}` entries. Recommended for large datasets.

### Key YAML Files (in ZIP)
| Path | Content |
|------|---------|
| `fsd/categories.yaml` | Item categories (e.g., Ship, Module, Material) |
| `fsd/groups.yaml` | Item groups (e.g., Frigate, Cruiser) |
| `fsd/types.yaml` | All item types with name, volume, basePrice, published flag |
| `bsd/staStations.yaml` | NPC stations (list format) |
| `universe/eve/<region>/region.yaml` | Regions with regionID, name |
| `universe/eve/<region>/<const>/<system>/solarsystem.yaml` | Systems with systemID, regionID, security |

### Legacy S3 URL (deprecated)
```
https://eve-static-data-export.s3-eu-west-1.amazonaws.com/tranquility/sde.zip
```
Use the official developers.eveonline.com endpoints above instead.

## Map Data & Coordinates

Two coordinate systems, same scale (1.0 = 1 meter), different axes.

### Universe Coordinate System (Left-Handed)
Used by: regions, constellations, solarsystems. Origin near Zarzakh ("Point of No Return").
- `+X` = East, `-X` = West
- `+Y` = Up, `-Y` = Down
- `+Z` = North, `-Z` = South

Data: SDE `mapRegions`/`mapConstellations`/`mapSolarSystems`, ESI `/universe/regions/` etc.
Includes all space types (known, wormhole, abyssal). Only New Eden systems (30,000,000–30,999,999) appear on in-game map.

### 2D Schematic Map
Same X direction as 3D. `position2D.Y` corresponds to 3D `Z` direction. Used for in-game 2D map.

### Solarsystem Coordinate System (Right-Handed)
Used by: planets, moons, stars, killmail positions. Origin = star at `[0, 0, 0]`.
- `+X` = **West** (opposite of universe!), `-X` = East
- `+Y` = Up, `-Y` = Down
- `+Z` = North, `-Z` = South

**Not every system has a star** (abyssal deadspace). Star position is always `[0, 0, 0]`.

### Combining Coordinates (system → universe)
```
x_universe = x_system - x_planet   # negate X!
y_universe = y_system + y_planet
z_universe = z_system + z_planet
```
**Warning:** Use 64-bit doubles. 32-bit floats lack precision for interstellar + interplanetary scales.

### Rendering 3D → 2D Image (top-left origin)
```
X_img = X_eve
Y_img = -Z_eve       # discard Y_eve for vertical flatten
```
For solarsystem maps (X is negated):
```
X_img = -X_eve
Y_img = -Z_eve
```
Use logarithmic scaling for solarsystem maps (distances span orders of magnitude).

### Jump Drive Range
Jump drives can reach any low/nullsec system within range (excluding Pochven, Jove regions). Can jump FROM highsec TO low/nullsec.

Distance formula:
```
sqrt((x1-x2)^2 + (y1-y2)^2 + (z1-z2)^2) <= jump_range_ly * 9_460_000_000_000_000.0
```
**1 lightyear = 9,460,000,000,000,000.0 meters** (exact game value, slightly less than real-world).

### ID Ranges
| Entity | Known Space | Wormhole | Abyssal |
|--------|------------|----------|---------|
| Region | 10000001–10000070 | 11000001–11000033 | 12000001+ |
| Constellation | 20000001–20000500+ | 21000001+ | 22000001+ |
| Solar System | 30000001–30009999 | 31000001+ | 32000001+ |

## Best Practices

1. **User-Agent** — Include email: `AppName/1.2.3 (email@example.com)`. Browser apps use `X-User-Agent`.
2. **Respect caching** — Don't request before `Expires`. Use `If-None-Match` + ETag for 304.
3. **Spread load** — Consistent slow traffic > spiky bursts. Don't run `*/5` cronjobs; use 5min-after-last-finish.
4. **Monitor limits** — Back off when `X-Ratelimit-Remaining` approaches zero. 4XX costs 5x tokens.
5. **Pin versions** — Use `/v1/` in production, not `/latest/`.
6. **Store multiple tokens per character** — Different scopes, stored separately.
7. **CharacterOwnerHash > character_id** — Characters can be sold.
8. **No bulk discovery** — Using search to enumerate entities = ban.
9. **Don't parse cursor tokens** — Use them as opaque black boxes.
10. **IP bans are permanent** — Don't circumvent; contact CCP support.
