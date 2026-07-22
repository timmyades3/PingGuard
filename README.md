<![CDATA[<div align="center">

# 🛡️ PingGuard

**A robust, real-time server uptime and performance monitoring API built with Django REST Framework.**

[![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-6.0-green?logo=django&logoColor=white)](https://djangoproject.com)
[![DRF](https://img.shields.io/badge/DRF-3.16-red?logo=django&logoColor=white)](https://www.django-rest-framework.org)
[![Celery](https://img.shields.io/badge/Celery-5.6-green?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Redis](https://img.shields.io/badge/Redis-7-red?logo=redis&logoColor=white)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

Monitor your IP addresses and HTTP endpoints in real-time.  
Get instant email & webhook alerts when things go down — and again when they recover.

[Getting Started](#-getting-started) •
[API Reference](#-api-reference) •
[Architecture](#-architecture) •
[Deployment](#-deployment)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Development](#local-development)
  - [Docker Deployment](#docker-deployment)
- [Environment Variables](#-environment-variables)
- [API Reference](#-api-reference)
  - [Authentication](#authentication)
  - [Monitoring](#monitoring)
  - [Statistics & Dashboard](#statistics--dashboard)
- [Project Structure](#-project-structure)
- [Data Aggregation Pipeline](#-data-aggregation-pipeline)
- [Notification System](#-notification-system)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🔍 Overview

**PingGuard** is a multi-tenant uptime monitoring API that lets users register IP addresses and HTTP endpoints, then continuously monitors them in the background using Celery workers. When a target goes down, the system opens an **incident**, sends **email & webhook alerts**, and continues sending periodic reminders until the target recovers. All monitoring data is aggregated into hourly and daily statistics for historical analysis.

---

## ✨ Features

| Category | Feature |
|---|---|
| **IP Monitoring** | ICMP ping (no port) or TCP socket check (with port), including SSL for ports 443/8443/9443 |
| **Endpoint Monitoring** | HTTP/HTTPS monitoring with configurable method (GET, POST, PUT, PATCH, HEAD), headers, body, expected status code, and response keyword validation |
| **Groups** | Organize IPs and endpoints into logical groups; start/stop monitoring for entire groups at once |
| **Incident Management** | Automatic incident creation on target failure, resolution tracking when targets recover |
| **Alerting** | Email notifications (via Gmail SMTP) and webhook notifications (e.g., Discord, Slack) for DOWN, STILL DOWN, and UP events |
| **Data Aggregation** | Raw checks → hourly stats → daily stats pipeline with automatic cleanup of stale data |
| **Dashboard** | Summary endpoint with counts of total/active targets and current UP/DOWN statuses |
| **Statistics** | Multi-granularity stats: five-minute (raw checks), hourly, daily, and all-time aggregates |
| **Search** | Full-text search across endpoints (label, URL) and IP addresses (label, IP) |
| **Authentication** | JWT-based auth with email verification via OTP, password reset flow, and token refresh/blacklisting |
| **User Settings** | Per-user configurable monitoring interval (10–3600s) and notification interval (5–1440min) |
| **API Docs** | Auto-generated Swagger UI and ReDoc documentation via `drf-yasg` |
| **Dockerized** | Full Docker Compose setup with web, Celery worker, Celery beat, Redis, and Nginx |

---

## 🏗 Architecture

```
┌─────────────┐       ┌──────────────────┐       ┌───────────────┐
│   Client     │──────▶│   Nginx (80)     │──────▶│  Django /     │
│  (Browser /  │       │   Reverse Proxy  │       │  Gunicorn     │
│   Mobile)    │       │                  │       │  (8000)       │
└─────────────┘       └──────────────────┘       └───────┬───────┘
                                                         │
                         ┌───────────────────────────────┼────────────────────┐
                         │                               │                    │
                         ▼                               ▼                    ▼
                  ┌──────────────┐              ┌────────────────┐   ┌────────────────┐
                  │  PostgreSQL  │              │  Redis (6379)  │   │  Gmail SMTP    │
                  │  Database    │              │  Message Broker│   │  Email Service │
                  └──────────────┘              └───────┬────────┘   └────────────────┘
                                                        │
                                          ┌─────────────┼──────────────┐
                                          ▼                            ▼
                                  ┌───────────────┐           ┌───────────────┐
                                  │ Celery Worker │           │ Celery Beat   │
                                  │ (Task Exec)   │           │ (Scheduler)   │
                                  │               │           │               │
                                  │ • ping_ip     │           │ • Hourly      │
                                  │ • check_ep    │           │   aggregation │
                                  │ • Alerts      │           │ • Daily       │
                                  └───────────────┘           │   aggregation │
                                                              └───────────────┘
```

### Request Flow

1. **Client** sends a request to the API (e.g., create an IP, start monitoring).
2. **Nginx** reverse-proxies the request to the **Django/Gunicorn** application server.
3. The API processes the request, persists data to **PostgreSQL**, and dispatches Celery tasks to **Redis**.
4. **Celery Worker** picks up the task, performs the ping/HTTP check, records the result, and self-reschedules based on the user's configured monitoring interval.
5. If a target goes DOWN, the **notification system** fires email and/or webhook alerts and opens an **Incident**.
6. **Celery Beat** periodically triggers aggregation tasks that roll up raw checks into hourly/daily statistics.

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.13 |
| **Framework** | Django 6.0 + Django REST Framework 3.16 |
| **Authentication** | `djangorestframework-simplejwt` (JWT access/refresh with token blacklisting) |
| **Task Queue** | Celery 5.6 with Redis 7 as the message broker |
| **Scheduled Tasks** | Celery Beat + `django-celery-beat` |
| **Database** | PostgreSQL (via `psycopg2-binary`) |
| **WSGI Server** | Gunicorn 26 |
| **Reverse Proxy** | Nginx |
| **Static Files** | WhiteNoise |
| **API Documentation** | `drf-yasg` (Swagger / ReDoc) |
| **Email** | Django's SMTP backend (Gmail) |
| **Configuration** | `python-decouple` (`.env` files) |
| **Containerization** | Docker + Docker Compose |

---

## 🚀 Getting Started

### Prerequisites

- **Python** 3.13+
- **PostgreSQL** (local or hosted, e.g., Neon, Supabase)
- **Redis** 7+ (local or Docker)
- **Docker & Docker Compose** (for containerized deployment)

### Local Development

1. **Clone the repository**

   ```bash
   git clone https://github.com/timmyades3/PingGuard.git
   cd PingGuard
   ```

2. **Create and activate a virtual environment**

   ```bash
   python -m venv env
   source env/bin/activate  # macOS/Linux
   # env\Scripts\activate   # Windows
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**

   ```bash
   cp .env.example .env
   # Edit .env with your credentials (see Environment Variables section)
   ```

5. **Run database migrations**

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create a superuser** (optional)

   ```bash
   python manage.py createsuperuser
   ```

7. **Start Redis** (in a separate terminal or via Docker)

   ```bash
   docker run -d -p 6379:6379 redis:7
   ```

8. **Start the Celery worker** (in a separate terminal)

   ```bash
   celery -A core worker --loglevel=info --pool=solo
   ```

9. **Start Celery Beat** (in a separate terminal)

   ```bash
   celery -A core beat --loglevel=info
   ```

10. **Start the development server**

    ```bash
    python manage.py runserver
    ```

11. **Access the API docs** at `http://localhost:8000/swagger/`

### Docker Deployment

```bash
# Build and start all services
docker compose up --build -d

# The API will be available at http://localhost (port 80 via Nginx)
```

The Docker Compose setup includes:

| Service | Description |
|---|---|
| `web` | Django + Gunicorn application server |
| `redis` | Redis 7 message broker |
| `worker` | Celery worker for background tasks |
| `beat` | Celery Beat for scheduled aggregation tasks |
| `nginx` | Nginx reverse proxy serving on port 80 |

---

## 🔐 Environment Variables

Create a `.env` file in the project root. See [`.env.example`](.env.example) for the template.

| Variable | Description | Required |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django secret key for cryptographic signing | ✅ |
| `DJANGO_DEBUG` | Debug mode (`True` / `False`) | ✅ |
| `APP_SCHEME` | Custom URL scheme for redirect handling | ✅ |
| `FRONTEND_URL` | Frontend URL for password reset redirects | ✅ |
| `DATABASE_URL` | PostgreSQL connection URL (e.g., `postgresql://user:pass@host:5432/dbname`) | ✅ |
| `GOOGLE_EMAIL_HOST_USER` | Gmail address for sending emails | ✅ |
| `GOOGLE_EMAIL_HOST_PASSWORD` | Gmail app-specific password | ✅ |
| `CELERY_BROKER_URL` | Redis URL for Celery (e.g., `redis://localhost:6379/0`) | ✅ |
| `EMAIL_HOST_USER` | Email host user (legacy, may mirror Google values) | ❌ |
| `EMAIL_HOST_PASSWORD` | Email host password (legacy) | ❌ |
| `POSTGRES_NAME` | PostgreSQL database name (legacy, used alongside `DATABASE_URL`) | ❌ |
| `POSTGRES_USER` | PostgreSQL user (legacy) | ❌ |
| `POSTGRES_PASSWORD` | PostgreSQL password (legacy) | ❌ |
| `POSTGRES_HOST` | PostgreSQL host (legacy) | ❌ |
| `POSTGRES_PORT` | PostgreSQL port (legacy) | ❌ |

---

## 📡 API Reference

> **Interactive docs** are available at `/swagger/` (Swagger UI) and `/redoc/` (ReDoc) when the server is running.

### Authentication

All auth endpoints are prefixed with `/api/auth/`.

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/auth/register/` | Register a new user (sends OTP to email) | ❌ |
| `POST` | `/api/auth/verify-email/` | Verify email with OTP | ❌ |
| `POST` | `/api/auth/request-otp/` | Request a new OTP | ❌ |
| `POST` | `/api/auth/login/` | Login and receive JWT tokens | ❌ |
| `GET` | `/api/auth/profile/` | Get current user's profile | ✅ |
| `POST` | `/api/auth/api/token/refresh/` | Refresh an access token | ❌ |
| `POST` | `/api/auth/logout/` | Blacklist refresh token (logout) | ✅ |
| `POST` | `/api/auth/request-reset-email` | Request password reset email | ❌ |
| `GET` | `/api/auth/password-reset/<uidb64>/<token>/` | Validate password reset token | ❌ |
| `PATCH` | `/api/auth/password-reset-complete/` | Set new password | ❌ |

#### Register Example

```json
POST /api/auth/register/
{
  "email": "user@example.com",
  "username": "johndoe",
  "password": "securepassword123"
}
```

#### Login Response

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

### Monitoring

All monitoring endpoints are prefixed with `/api/monitor/`.

#### CRUD Resources (ViewSets)

| Resource | Endpoint | Methods | Description |
|---|---|---|---|
| **Groups** | `/api/monitor/groups/` | `GET, POST, PUT, PATCH, DELETE` | Organize targets into logical groups |
| **IP Addresses** | `/api/monitor/ip-addresses/` | `GET, POST, PUT, PATCH, DELETE` | Manage monitored IP addresses |
| **Endpoints** | `/api/monitor/endpoints/` | `GET, POST, PUT, PATCH, DELETE` | Manage monitored HTTP endpoints |
| **Settings** | `/api/monitor/settings/` | `GET, PUT, PATCH` | Configure monitoring & notification intervals |

#### Create an IP Address

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

#### Create an Endpoint

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

#### Monitoring Control

| Method | Endpoint | Description |
|---|---|---|
| `PATCH` | `/api/monitor/start-monitoring/<ip_id>/` | Start monitoring an IP address |
| `PATCH` | `/api/monitor/stop-monitoring/<ip_id>/` | Stop monitoring an IP address |
| `PATCH` | `/api/monitor/start-endpoint-monitoring/<endpoint_id>/` | Start monitoring an endpoint |
| `PATCH` | `/api/monitor/stop-endpoint-monitoring/<endpoint_id>/` | Stop monitoring an endpoint |
| `PATCH` | `/api/monitor/group-start-monitoring-all/<group_id>/` | Start monitoring all targets in a group |
| `PATCH` | `/api/monitor/group-stop-monitoring-all/<group_id>/` | Stop monitoring all targets in a group |

#### Other Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/monitor/group-all/?group_id=<id>` | List all IPs and endpoints in a group (paginated) |
| `GET` | `/api/monitor/search/?q=<query>` | Search across IPs and endpoints by label/address/URL |

### Statistics & Dashboard

| Method | Endpoint | Query Params | Description |
|---|---|---|---|
| `GET` | `/api/monitor/dashboard/` | — | Overview counts (total, active, up, down) |
| `GET` | `/api/monitor/stats/<id>/` | `stat_type`, `target_type` | Detailed statistics for a specific target |

#### `stat_type` options:

| Value | Description |
|---|---|
| `five_minute` | Raw `MonitorCheck` records (most granular) |
| `hourly` | Hourly aggregated statistics |
| `daily` | Daily aggregated statistics |
| `all_time` | Combined view with all granularities + aggregated totals |

#### `target_type` options: `ENDPOINT` or `IP`

#### Dashboard Response Example

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

---

## 📁 Project Structure

```
PingGuard/
├── core/                        # Django project settings
│   ├── __init__.py              # Celery app initialization
│   ├── settings.py              # Django settings (DB, JWT, email, Celery, etc.)
│   ├── urls.py                  # Root URL configuration
│   ├── celery.py                # Celery app & beat schedule definition
│   ├── wsgi.py                  # WSGI entry point for Gunicorn
│   └── asgi.py                  # ASGI entry point
│
├── users/                       # Authentication & user management app
│   ├── models.py                # User model (custom), EmailVerificationOTP
│   ├── serializers.py           # Register, Login, OTP, Password Reset serializers
│   ├── views.py                 # Auth API views (register, login, verify, reset, etc.)
│   ├── urls.py                  # Auth URL routes
│   ├── utils.py                 # OTP generation, threaded email sending
│   ├── renderers.py             # Custom JSON renderer (wraps data/error)
│   └── admin.py                 # Admin registration for User, OTP
│
├── monitoring/                  # Core monitoring app
│   ├── models.py                # Group, IpAddress, Endpoint, MonitorCheck,
│   │                            #   HourlyStat, DailyStat, Incident, Settings
│   ├── serializers.py           # Serializers for all monitoring models
│   ├── views.py                 # ViewSets and API views for monitoring & stats
│   ├── urls.py                  # Monitoring URL routes (router + custom paths)
│   ├── tasks.py                 # Celery tasks: ping_ip, check_endpoint,
│   │                            #   hourly_aggregate, daily_aggregate
│   ├── notifications.py         # Email & webhook notification system
│   ├── permissions.py           # IsOwner custom permission
│   └── admin.py                 # Admin registration for monitoring models
│
├── utils/                       # Shared utilities
│   └── pagination.py            # StandardResultsSetPagination (page_size=10)
│
├── nginx/                       # Nginx configuration
│   └── default.conf             # Reverse proxy config for Django + static/media
│
├── manage.py                    # Django management script
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Container image definition (Python 3.13-slim)
├── docker-compose.yml           # Multi-service orchestration
├── .env.example                 # Environment variable template
├── .gitignore                   # Git ignore rules
└── .dockerignore                # Docker build context exclusions
```

---

## 📊 Data Aggregation Pipeline

PingGuard uses a three-tier data storage strategy to balance granularity and storage efficiency:

```
┌────────────────┐   (hourly)   ┌────────────────┐   (daily)   ┌────────────────┐
│  MonitorCheck  │ ──────────▶  │   HourlyStat   │ ──────────▶ │   DailyStat    │
│  (raw checks)  │   aggregate  │  (per hour)    │   aggregate │  (per day)     │
│                │   & delete   │                │   & delete  │                │
└────────────────┘              └────────────────┘             └────────────────┘
```

| Task | Schedule | Action |
|---|---|---|
| `hourly_aggregate_and_cleanup` | Every 1 hour | Aggregates raw `MonitorCheck` records older than the cutoff into `HourlyStat` entries, then deletes the raw records |
| `daily_aggregate_and_cleanup` | Every 24 hours | Aggregates `HourlyStat` records older than the cutoff into `DailyStat` entries, then deletes the hourly records |

Each aggregation computes:
- **Total checks** (count)
- **Up/Down counts**
- **Average response time** (weighted by check count)
- **Uptime percentage**

---

## 🔔 Notification System

PingGuard uses an **incident-driven** notification model:

```
Target goes DOWN
     │
     ▼
┌─────────────────────────┐
│ Is there an OPEN        │───No───▶ Create Incident
│ incident for this       │         Send DOWN email + webhook
│ target?                 │
└───────────┬─────────────┘
            │ Yes
            ▼
┌─────────────────────────┐
│ Has notification        │
│ interval elapsed since  │───Yes──▶ Send STILL DOWN email + webhook
│ last notification?      │         Update last_notification_sent_at
└───────────┬─────────────┘
            │ No
            ▼
        (do nothing)
```

```
Target comes back UP
     │
     ▼
┌─────────────────────────┐
│ Is there an OPEN        │───Yes──▶ Resolve Incident
│ incident for this       │         Send UP (resolved) email + webhook
│ target?                 │
└───────────┬─────────────┘
            │ No
            ▼
        (do nothing)
```

### Notification Channels

| Channel | Configuration | Payload |
|---|---|---|
| **Email** | Gmail SMTP; user can override recipient via `Settings.notification_email` | Subject-based alerts with downtime duration |
| **Webhook** | User-configurable URL via `Settings.webhook_url` | JSON payload with `content` field (compatible with Discord/Slack) |

### Notification Interval

Users can configure how often "STILL DOWN" reminders are sent via `Settings.notification_interval_minutes` (default: 30 minutes, range: 5–1440 minutes).

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

<div align="center">

**Built with ❤️ by [Timmy](https://github.com/timmyades3)**

</div>
]]>
