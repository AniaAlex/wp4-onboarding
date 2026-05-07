# Onboarding (Django version)

Trust-list editorial app for WP4Trust — Django flavor. Same data model and same public `/lists/*` contract as the [Pocketbase version](../onboarding/), implemented on the production-grade Django stack from `ms-registry`.

## Fast launch

```sh
cp .env.example .env             # set DJANGO_SECRET_KEY + admin creds
make run                         # docker compose build + up
make migrate                     # apply migrations
make seed                        # demo operator + 7 schemes
```

Two UIs:

| URL | Audience | Login |
|---|---|---|
| http://localhost:8000/ | Operators (end-users) | `operator@wp4trust.local` / `demo-pass-12345` |
| http://localhost:8000/admin/ | Super-admin | Run `make createsuperuser` first |

## Public trust-list endpoints (no auth)

| URL | What it returns |
|---|---|
| `GET /lists/` | HTML directory of all published lists |
| `GET /lists/index.json` | Machine-readable manifest |
| `GET /lists/<basename>-<territory>.json` | Canonical ETSI 119 602 unsigned LoTE/LoTL |

Where `<basename>` is one of: `pid`, `wallet`, `pubeaa`, `wrpac`, `wrprc`, `registrars`, `list_of_trusted_lists`.

## Make targets

| Target | Effect |
|---|---|
| `make run` | Build + start container in background |
| `make stop` | Stop containers (data preserved) |
| `make logs` | Tail Django logs |
| `make shell` | Django shell (`python manage.py shell`) |
| `make sh` | Container shell |
| `make migrate` | Apply DB migrations |
| `make migrations` | Make new migrations from model changes |
| `make seed` | Seed demo operator + 7 schemes |
| `make createsuperuser` | Interactive Django super-admin creation |
| `make clean` | Stop AND wipe SQLite volume (full reset) |

## Stack

- **Django 5.2 LTS** — the same major version as `ms-registry`
- **SQLite** by default (single file, zero ops). Switch to Postgres by changing `DATABASES['default']` in `lote_registry/settings.py`.
- **WhiteNoise** for static files
- **No Celery / Redis yet** — added later if/when async signing is needed

## What's NOT here yet

- Multi-language form repeaters (HTMX) — admin UI handles CRUD for now
- Audit log (`django-simple-history`) — drop-in addition
- Approval workflow (`django-fsm`) — drop-in addition
- Signer integration — kept as a separate story

## Architecture (matches Pocketbase version)

```
   ┌──────────────────────────┐
   │ Django (this app)        │
   │  • SQLite source-of-truth│
   │  • Operator UI           │
   │  • django.contrib.admin  │
   │  • Public /lists/* API   │
   └──────────┬───────────────┘
              │ HTTP (later: shared volume)
              ▼
   ┌──────────────────────────┐
   │ Go signer (g119612)      │
   │  • polls /lists/*        │
   │  • signs JAdES + XAdES   │
   └──────────┬───────────────┘
              │
              ▼
   ┌──────────────────────────┐
   │ Nginx (public, TLS)      │
   └──────────────────────────┘
```
