<div align="center">

<br>

<img src="https://img.shields.io/badge/%F0%9F%9B%A1%EF%B8%8F-PingGuard-0d1117?style=for-the-badge&labelColor=0d1117" height="40" />

### Real-time server uptime & performance monitoring API

Monitor IP addresses and HTTP endpoints in real-time.<br>
Get instant email & webhook alerts when things go down — and again when they recover.

<br>

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-6.0-092E20?style=flat-square&logo=django&logoColor=white)](https://djangoproject.com)
[![DRF](https://img.shields.io/badge/DRF-3.16-A30000?style=flat-square&logo=django&logoColor=white)](https://www.django-rest-framework.org)
[![Celery](https://img.shields.io/badge/Celery-5.6-37814A?style=flat-square&logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-EAB308?style=flat-square)](LICENSE)

<br>

[Getting Started](#getting-started) · [API Reference](#api-reference) · [Architecture](#architecture) · [Deployment](#docker-deployment)

<br>

</div>

---

## Overview

**PingGuard** is a multi-tenant uptime monitoring API that lets users register IP addresses and HTTP endpoints, then continuously monitors them in the background using Celery workers. When a target goes down, the system opens an **incident**, sends **email & webhook alerts**, and continues sending periodic reminders until the target recovers. All monitoring data is aggregated into hourly and daily statistics for historical analysis.

<br>

## Features

<table>
<tr><td>

**Monitoring**
- ICMP ping / TCP socket checks for IPs (SSL on 443/8443/9443)
- HTTP/HTTPS endpoint monitoring with configurable method, headers, body, status code, and keyword validation
- Organize targets into groups with bulk start/stop

</td><td>

**Incident & Alerting**
- Automatic incident creation on failure, resolution on recovery
- Email alerts via Gmail SMTP
- Webhook alerts (Discord, Slack compatible)
- Configurable reminder intervals for ongoing outages

</td></tr>
<tr><td>

**Data & Analytics**
- Three-tier aggregation: raw checks → hourly → daily stats
- Dashboard with real-time UP/DOWN counts
- Multi-granularity statistics (5-min, hourly, daily, all-time)
- Full-text search across all monitored targets

</td><td>

**Platform**
- JWT auth with email verification (OTP) and password reset
- Per-user monitoring interval (10–3600s) and notification settings
- Auto-generated Swagger UI & ReDoc API docs
- Full Docker Compose deployment with Nginx

</td></tr>
</table>

<br>

## Architecture

```
                          ┌──────────────────┐       ┌───────────────────┐
   ┌──────────┐           │      Nginx       │       │  Django / Gunicorn │
   │  Client  │ ────────▶ │   reverse proxy  │ ────▶ │    application    │
   └──────────┘           │     :80          │       │      :8000        │
                          └──────────────────┘       └────────┬──────────┘
                                                              │
                          ┌───────────────────────────────────┼───────────────┐
                          │                                   │               │
                          ▼                                   ▼               ▼
                   ┌─────────────┐                   ┌──────────────┐  ┌────────────┐
                   │ PostgreSQL  │                   │    Redis     │  │ Gmail SMTP │
                   │  database   │                   │   broker     │  │   alerts   │
                   └─────────────┘                   └──────┬───────┘  └────────────┘
                                                            │
                                              ┌─────────────┴──────────────┐
                                              ▼                            ▼
                                      ┌──────────────┐            ┌──────────────┐
                                      │ Celery Worker │            │ Celery Beat  │
                                      │              │            │              │
                                      │  ping_ip     │            │  hourly agg  │
                                      │  check_ep    │            │  daily agg   │
                                      │  alerts      │            │              │
                                      └──────────────┘            └──────────────┘
```

**Request flow:** Client → Nginx → Django (persists to Postgres, dispatches to Redis) → Celery Worker executes checks, records results, self-reschedules → on failure, the notification system fires alerts and opens an Incident → Celery Beat triggers periodic aggregation of raw checks into hourly/daily stats.

<br>

## Tech Stack

| Layer | Technology |
| :--- | :--- |
| Language | Python 3.13 |
| Framework | Django 6.0 + Django REST Framework 3.16 |
| Auth | `djangorestframework-simplejwt` — JWT with token blacklisting |
| Task Queue | Celery 5.6 + Redis 7 |
| Scheduler | Celery Beat + `django-celery-beat` |
| Database | PostgreSQL via `psycopg2-binary` |
| WSGI | Gunicorn 26 |
| Proxy | Nginx |
| Static Files | WhiteNoise |
| API Docs | `drf-yasg` (Swagger / ReDoc) |
| Email | Django SMTP backend (Gmail) |
| Config | `python-decouple` |
| Containers | Docker + Docker Compose |

<br>

## Getting Started

### Prerequisites

- Python 3.13+
- PostgreSQL (local or hosted)
- Redis 7+
- Docker & Docker Compose (for containerized deployment)

### Local Development

```bash
# 1. Clone and enter the project
git clone https://github.com/timmyades3/PingGuard.git
cd PingGuard

# 2. Create a virtual environment
python -m venv env
source env/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your credentials (see Environment Variables below)

# 5. Run migrations
python manage.py makemigrations
python manage.py migrate

# 6. (Optional) Create a superuser
python manage.py createsuperuser
```

Then, in separate terminals:

```bash
# Terminal 1 — Redis
docker run -d -p 6379:6379 redis:7

# Terminal 2 — Celery worker
celery -A core worker --loglevel=info --pool=solo

# Terminal 3 — Celery Beat
celery -A core beat --loglevel=info

# Terminal 4 — Django dev server
python manage.py runserver
```

API docs will be available at **http://localhost:8000/swagger/**

### Docker Deployment

```bash
docker compose up --build -d
# API available at http://localhost (port 80 via Nginx)
```

| Service | Role |
| :--- | :--- |
| `web` | Django + Gunicorn |
| `redis` | Message broker |
| `worker` | Celery task executor |
| `beat` | Celery Beat scheduler |
| `nginx` | Reverse proxy on port 80 |

<br>

## Environment Variables

Create a `.env` file in the project root (see [`.env.example`](.env.example) for the template).

| Variable | Description | Required |
| :--- | :--- | :---: |
| `DJANGO_SECRET_KEY` | Django secret key for cryptographic signing | Yes |
| `DJANGO_DEBUG` | Debug mode (`True` / `False`) | Yes |
| `APP_SCHEME` | Custom URL scheme for redirect handling | Yes |
| `FRONTEND_URL` | Frontend URL for password reset redirects | Yes |
| `DATABASE_URL` | PostgreSQL connection URL | Yes |
| `GOOGLE_EMAIL_HOST_USER` | Gmail address for sending emails | Yes |
| `GOOGLE_EMAIL_HOST_PASSWORD` | Gmail app-specific password | Yes |
| `CELERY_BROKER_URL` | Redis URL (e.g., `redis://localhost:6379/0`) | Yes |
| `POSTGRES_NAME` | PostgreSQL database name | No |
| `POSTGRES_USER` | PostgreSQL user | No |
| `POSTGRES_PASSWORD` | PostgreSQL password | No |
| `POSTGRES_HOST` | PostgreSQL host | No |
| `POSTGRES_PORT` | PostgreSQL port | No |

<br>

## API Reference

> Interactive docs are available at `/swagger/` (Swagger UI) and `/redoc/` (ReDoc) when the server is running.

### Authentication

All endpoints prefixed with `/api/auth/`.

| Method | Endpoint | Description | Auth |
| :--- | :--- | :--- | :---: |
| POST | `/register/` | Register a new user (sends OTP) | — |
| POST | `/verify-email/` | Verify email with OTP | — |
| POST | `/request-otp/` | Request a new OTP | — |
| POST | `/login/` | Login, receive JWT tokens | — |
| GET | `/profile/` | Current user's profile | Yes |
| POST | `/api/token/refresh/` | Refresh access token | — |
| POST | `/logout/` | Blacklist refresh token | Yes |
| POST | `/request-reset-email` | Request password reset | — |
| GET | `/password-reset/<uidb64>/<token>/` | Validate reset token | — |
| PATCH | `/password-reset-complete/` | Set new password | — |

<details>
<summary><strong>Example: Register</strong></summary>

```json
POST /api/auth/register/
{
  "email": "user@example.com",
  "username": "johndoe",
  "password": "securepassword123"
}
```

</details>

<details>
<summary><strong>Example: Login Response</strong></summary>

```json
{
  "data": {
    "email": "user@example.com",
    "username": "johndoe",
    "tokens": {
      "access": "eyJ0eXAiOi...",
      "refresh": "eyJ0eXAiOi..."
    }
  }
}
```

</details>

### Monitoring

All endpoints prefixed with `/api/monitor/`. All require authentication.

#### CRUD Resources

| Resource | Endpoint | Methods |
| :--- | :--- | :--- |
| Groups | `/groups/` | GET, POST, PUT, PATCH, DELETE |
| IP Addresses | `/ip-addresses/` | GET, POST, PUT, PATCH, DELETE |
| Endpoints | `/endpoints/` | GET, POST, PUT, PATCH, DELETE |
| Settings | `/settings/` | GET, PUT, PATCH |

<details>
<summary><strong>Example: Create an IP Address</strong></summary>

```json
POST /api/monitor/ip-addresses/
Authorization: Bearer <access_token>
{
  "ip_address": "8.8.8.8",
  "label": "Google DNS",
  "group": 1,
  "port": null,
  "timeout_seconds": 10
}
```

</details>

<details>
<summary><strong>Example: Create an Endpoint</strong></summary>

```json
POST /api/monitor/endpoints/
Authorization: Bearer <access_token>
{
  "label": "My API Health",
  "url": "https://api.example.com/health",
  "http_method": "GET",
  "group": 1,
  "expected_status_code": 200,
  "request_headers": {},
  "request_body": {},
  "timeout_seconds": 10,
  "expected_response_keyword": "ok"
}
```

</details>

#### Monitoring Control

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| PATCH | `/start-monitoring/<ip_id>/` | Start monitoring an IP |
| PATCH | `/stop-monitoring/<ip_id>/` | Stop monitoring an IP |
| PATCH | `/start-endpoint-monitoring/<endpoint_id>/` | Start monitoring an endpoint |
| PATCH | `/stop-endpoint-monitoring/<endpoint_id>/` | Stop monitoring an endpoint |
| PATCH | `/group-start-monitoring-all/<group_id>/` | Start all targets in a group |
| PATCH | `/group-stop-monitoring-all/<group_id>/` | Stop all targets in a group |

#### Other

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| GET | `/group-all/?group_id=<id>` | List all IPs and endpoints in a group |
| GET | `/search/?q=<query>` | Search across IPs and endpoints |

### Statistics & Dashboard

| Method | Endpoint | Params | Description |
| :--- | :--- | :--- | :--- |
| GET | `/dashboard/` | — | Overview counts (total, active, up, down) |
| GET | `/stats/<id>/` | `stat_type`, `target_type` | Stats for a specific target |

**`stat_type`** — `five_minute` · `hourly` · `daily` · `all_time`
**`target_type`** — `ENDPOINT` · `IP`

<details>
<summary><strong>Example: Dashboard Response</strong></summary>

```json
{
  "total_endpoints": 5,
  "total_ip_addresses": 3,
  "active_endpoints": 4,
  "active_ip_addresses": 2,
  "total_up_count": 5,
  "total_down_count": 1
}
```

</details>

<br>

## Data Aggregation Pipeline

PingGuard uses a three-tier storage strategy to balance granularity with efficiency:

```
 MonitorCheck              HourlyStat               DailyStat
 (raw checks)     ──▶     (per hour)       ──▶     (per day)
                aggregate             aggregate
                & delete              & delete
```

| Task | Schedule | Action |
| :--- | :--- | :--- |
| `hourly_aggregate_and_cleanup` | Every hour | Roll up raw checks into `HourlyStat`, delete originals |
| `daily_aggregate_and_cleanup` | Every 24 hours | Roll up hourly stats into `DailyStat`, delete originals |

Each aggregation computes: **total checks**, **up/down counts**, **weighted average response time**, and **uptime percentage**.

<br>

## Notification System

PingGuard uses an incident-driven notification model with two flows:

**When a target goes DOWN:**

1. If no open incident exists → create one, send **DOWN** alert (email + webhook)
2. If an open incident exists and the notification interval has elapsed → send **STILL DOWN** reminder
3. Otherwise → do nothing

**When a target comes back UP:**

1. If an open incident exists → resolve it, send **UP (resolved)** alert
2. Otherwise → do nothing

### Channels

| Channel | Config | Details |
| :--- | :--- | :--- |
| Email | Gmail SMTP | Override recipient via `Settings.notification_email` |
| Webhook | User-configured URL | JSON with `content` field (Discord/Slack compatible) |

Reminder frequency is controlled by `Settings.notification_interval_minutes` (default: 30, range: 5–1440).

<br>

## Project Structure

```
PingGuard/
├── core/                        # Django project configuration
│   ├── settings.py              #   DB, JWT, email, Celery config
│   ├── celery.py                #   Celery app & beat schedule
│   ├── urls.py                  #   Root URL configuration
│   └── wsgi.py                  #   WSGI entry point
│
├── users/                       # Authentication & user management
│   ├── models.py                #   Custom User, EmailVerificationOTP
│   ├── serializers.py           #   Register, Login, OTP, Password Reset
│   ├── views.py                 #   Auth API views
│   ├── urls.py                  #   Auth routes
│   └── utils.py                 #   OTP generation, threaded email
│
├── monitoring/                  # Core monitoring engine
│   ├── models.py                #   Group, IpAddress, Endpoint, MonitorCheck,
│   │                            #   HourlyStat, DailyStat, Incident, Settings
│   ├── serializers.py           #   All monitoring serializers
│   ├── views.py                 #   ViewSets and API views
│   ├── tasks.py                 #   Celery tasks (ping, check, aggregate)
│   ├── notifications.py         #   Email & webhook notification system
│   └── permissions.py           #   IsOwner permission
│
├── utils/                       # Shared utilities
│   └── pagination.py            #   StandardResultsSetPagination
│
├── nginx/default.conf           # Nginx reverse proxy config
├── docker-compose.yml           # Multi-service orchestration
├── Dockerfile                   # Python 3.13-slim container
├── requirements.txt             # Python dependencies
└── .env.example                 # Environment variable template
```

<br>

## Contributing

1. Fork the repository
2. Create a feature branch — `git checkout -b feature/my-feature`
3. Commit your changes — `git commit -m 'Add my feature'`
4. Push to the branch — `git push origin feature/my-feature`
5. Open a Pull Request

## License

This project is open source under the [MIT License](LICENSE).

---

<div align="center">
<sub>Built by <a href="https://github.com/timmyades3">Timmy</a></sub>
</div>