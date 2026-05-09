# Kolliq Backend — Django Service

> Fintech infrastructure for Nigeria's informal economy. Connecting gig workers, street traders, and employers through digital identity, payments, and progressive financial services.

---

## Table of Contents

1. [What This Is](#what-this-is)
2. [Architecture Overview](#architecture-overview)
3. [Complete .env Reference](#complete-env-reference)
4. [Getting Started](#getting-started)
5. [App Structure](#app-structure)
6. [Economic Identity Score](#economic-identity-score)
7. [Loan Eligibility Logic](#loan-eligibility-logic)
8. [Squad Payment Integration](#squad-payment-integration)
9. [Integration Testing (Django + Node)](#integration-testing-django--node)
10. [Running Tests](#running-tests)
11. [Celery Scheduled Tasks](#celery-scheduled-tasks)
12. [Django Admin](#django-admin)
13. [One-Time Setup Commands](#one-time-setup-commands)
---

## What This Is

Kolliq is a two-service backend:

| Service | Language | Owns |
|---|---|---|
| **This repo** | Django (Python) | User data, financial logic, job matching, scoring engine, loans, insurance, marketplace, Squad payment integration, Django Admin |
| **Partner repo** | Node.js | OTP auth gateway, USSD flows, WhatsApp bot, Claude API intent detection, SMS + push notifications, Squad webhook receiver, Redis job feed cache |

Both services share one Supabase PostgreSQL database and one Upstash Redis instance.

---

## Architecture Overview

```
                    ┌─────────────────────────────────┐
                    │        Supabase PostgreSQL        │
                    │   (shared by Django + Node)       │
                    └──────────────┬──────────────────┘
                                   │
          ┌────────────────────────┼──────────────────────┐
          │                        │                      │
   Django (Cloud Run)        Node (Cloud Run)       Upstash Redis
   - REST API                - OTP + USSD           - Session store
   - Celery tasks            - WhatsApp bot         - Job feed cache
   - Squad payouts           - AT SMS               - Celery broker
   - Admin dashboard         - Webhook relay
          │                        │
          └────────────┬───────────┘
                       │
              Squad (GTBank VAs)
              Africa's Talking
              Cloudflare R2 (images)
```

**Money flow:**
```
Employer → Kolliq Escrow VA (GTBank) → Squad webhook fires
→ Django matches payment to job → job goes live
→ Worker accepts → Employer confirms → Django releases:
  95% → Worker's personal VA (GTBank)
   5% → Kolliq Platform VA (GTBank)
```

---

## Complete .env Reference

Copy this to `.env` and fill in every value before running anything.

```env
# ══════════════════════════════════════════════════════════════
# DJANGO CORE
# ══════════════════════════════════════════════════════════════
SECRET_KEY=your-django-secret-key-min-50-chars
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# ══════════════════════════════════════════════════════════════
# DATABASE — Supabase PostgreSQL
# Get from: supabase.com → project → Settings → Database → Connection string
# ══════════════════════════════════════════════════════════════
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres

# ══════════════════════════════════════════════════════════════
# REDIS — Upstash
# Get from: upstash.com → your Redis database → REST API
# ══════════════════════════════════════════════════════════════
REDIS_URL=rediss://default:[PASSWORD]@[HOST].upstash.io:6379

# ══════════════════════════════════════════════════════════════
# SQUAD PAYMENTS
# Get from: dashboard.squadco.com → Settings → API & Webhook
# Sandbox: sandbox.squadco.com | Live: dashboard.squadco.com
# ══════════════════════════════════════════════════════════════
SQUAD_SECRET_KEY=sandbox_sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SQUAD_PUBLIC_KEY=sandbox_pk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SQUAD_BASE_URL=https://sandbox-api-d.squadco.com
# Your Merchant ID shown on Squad dashboard homepage
SQUAD_MERCHANT_ID=SBXXXXXXXX
# Your GTBank 10-digit account number (settlement account — REQUIRED for VA creation)
SQUAD_BENEFICIARY_ACCOUNT=0123456789

# System virtual accounts — fill AFTER running: python manage.py create_system_accounts
KOLLIQ_ESCROW_VIRTUAL_ACCOUNT=
KOLLIQ_ESCROW_CUSTOMER_ID=kolliq-escrow-main
KOLLIQ_PLATFORM_VIRTUAL_ACCOUNT=
KOLLIQ_PLATFORM_CUSTOMER_ID=kolliq-platform-fees

# ══════════════════════════════════════════════════════════════
# AFRICA'S TALKING — SMS
# Get from: africastalking.com → Settings → API Key
# Sandbox username is always: sandbox
# ══════════════════════════════════════════════════════════════
AT_USERNAME=sandbox
AT_API_KEY=your-africastalking-api-key
AT_SENDER_ID=KOLLIQ

# ══════════════════════════════════════════════════════════════
# PLATFORM CONFIG
# ══════════════════════════════════════════════════════════════
PLATFORM_FEE_PERCENT=5
# Platform wallet ID in DB (created by seed_pilot command)
ARISE_WALLET_ID=1

# ══════════════════════════════════════════════════════════════
# FINANCIAL SERVICES
# ══════════════════════════════════════════════════════════════
# Demo float seeds ₦500,000 for simulated loans + insurance
DEMO_FLOAT_WALLET_ID=2
DEMO_FLOAT_INITIAL_BALANCE=500000

# Score thresholds for service unlocks
SAVINGS_SCORE_THRESHOLD=20
LOAN_SCORE_THRESHOLD=50
INSURANCE_SCORE_THRESHOLD=70

# Loan settings
LOAN_INTEREST_RATE_MONTHLY=5.0

# Insurance settings
INSURANCE_DAILY_PREMIUM=200
INSURANCE_COVERAGE_LIMIT=50000

# Savings interest
SAVINGS_ANNUAL_INTEREST_RATE=5.0

# Partner mode: 'simulated' uses demo float, 'live' routes to partner capital
FINANCIAL_PARTNER_MODE=simulated

# ══════════════════════════════════════════════════════════════
# PARTNER API
# Share this secret with microfinance / insurance partners
# ══════════════════════════════════════════════════════════════
PARTNER_API_SECRET=change-me-to-random-64-char-string

# ══════════════════════════════════════════════════════════════
# INTERNAL SERVICE AUTH (Django ↔ Node)
# Node includes this header when forwarding Squad events to Django
# ══════════════════════════════════════════════════════════════
INTERNAL_WEBHOOK_SECRET=change-me-to-random-64-char-string
```

**Variables Node.js service also needs** (share these with your partner):

```env
# Node needs these to call Django APIs
DJANGO_BASE_URL=http://localhost:8000          # local dev
# DJANGO_BASE_URL=https://api.kolliq.app       # production
INTERNAL_WEBHOOK_SECRET=same-as-above

# Node needs these directly
SQUAD_SECRET_KEY=same-as-above
SQUAD_WEBHOOK_SECRET=same-as-above
AT_USERNAME=sandbox
AT_API_KEY=same-as-above
REDIS_URL=same-as-above
ANTHROPIC_API_KEY=your-claude-api-key         # for WhatsApp intent detection
TWILIO_ACCOUNT_SID=your-twilio-sid            # for WhatsApp
TWILIO_AUTH_TOKEN=your-twilio-token
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL (via Supabase) or local Postgres
- Redis (via Upstash) or local Redis
- Node.js 18+ (for partner service)

### Local setup

```bash
# 1. Clone and enter project
cd Kolliq_config

# 2. Create virtual environment
python -m venv venv && source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Edit .env — fill in all values above

# 5. Run migrations
python manage.py makemigrations
python manage.py migrate

# 6. Create Django superuser (for Admin access)
python manage.py createsuperuser

# 7. One-time: create Squad system virtual accounts
python manage.py create_system_accounts
# → copy printed account numbers into .env
# → restart server after updating .env

# 8. Seed pilot demo data (categories + demo float + tiered test users)
python manage.py seed_pilot

# 9. Start services
# Terminal 1 — Django
python manage.py runserver

# Terminal 2 — Celery worker
celery -A kolliq worker -l info

# Terminal 3 — Celery beat (scheduled tasks)
celery -A kolliq beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Verify everything works

```bash
curl http://localhost:8000/api/health/
# Expected: {"success":true,"data":{"status":"ok","service":"kolliq-django"},"error":null}
```

---

## App Structure

```
Kolliq_config/
├── kolliq/                    # Django project config
│   ├── settings.py            # All settings + env loading
│   ├── urls.py                # Root URL routing
│   ├── celery.py              # Celery app + beat schedule
│   └── utils.py               # success_response(), error_response(), custom exception handler
│
├── apps/
│   ├── users/                 # User model (phone auth), onboarding, roles
│   ├── wallets/               # Wallet model, Squad VA provisioning
│   ├── jobs/                  # Job model, weighted SQL matching engine, applications, ratings
│   ├── payments/              # Transactions, virtual account escrow, Squad webhook handler
│   ├── scoring/               # Economic Identity Score engine (deterministic rules)
│   ├── financial_services/    # Savings, simulated loans, simulated insurance, demo float
│   ├── marketplace/           # Trader listings, enquiries, images, categories
│   └── partner/               # Partner API — eligible borrowers, score reports, platform summary
│
├── services/
│   ├── squad.py               # Squad API wrapper (all endpoints)
│   ├── africas_talking.py     # SMS service
│   └── notifications.py       # Platform notification helpers (Celery tasks)
│
└── tests/
    ├── conftest.py            # Shared fixtures (users, wallets, jobs, scores)
    ├── test_users.py
    ├── test_scoring.py
    ├── test_jobs.py
    ├── test_escrow.py
    ├── test_financial.py
    ├── test_marketplace.py
    └── test_partner.py
```

---

## Economic Identity Score

The score is the core of Kolliq. It is calculated deterministically from real economic activity — no self-reported data, no manual assessment.

### How points are earned

| Activity | Points |
|---|---|
| Account created | 10 (base) |
| Each gig completed | +5 |
| Each payment received (credit transaction) | +2 |
| Each loan installment repaid | +8 |
| Each rating received | +3 |
| Each insurance premium day paid | +1 |
| Each active marketplace listing | +3 |
| Each enquiry received on listings | +1 (capped at 15) |

**Maximum score: 100. Score never decreases** (only increases with activity).

### Service unlock thresholds

| Score | Unlocks |
|---|---|
| 0–19 | Job matching feed only |
| 20+ | Micro-savings (deposits, withdrawals, 5% p.a. interest) |
| 50+ | Micro-loans (demo float funded, amounts scale with score) |
| 70+ | Micro-insurance (₦200/day premium, up to ₦50,000 coverage) |

### When score recalculates

Score recalculates asynchronously (Celery task) after every scoring event:
- Gig marked complete
- Payment received on virtual account
- Loan installment repaid
- Rating submitted
- Insurance premium deducted
- Marketplace listing created

### Score tiers

| Score | Tier |
|---|---|
| 0–19 | Starter |
| 20–39 | Active |
| 40–59 | Trusted |
| 60–79 | Established |
| 80–100 | Champion |

---

## Loan Eligibility Logic

Loans are **not** given to anyone who asks. Eligibility is gated by real usage:

```
1. Score must be ≥ 50 (requires completing gigs, receiving payments,
   building verified transaction history)

2. No existing active loan (one at a time only)

3. Loan amount is capped by score tier:
   Score 50–59  →  max ₦10,000
   Score 60–74  →  max ₦25,000
   Score 75–89  →  max ₦50,000
   Score 90–100 →  max ₦100,000

4. Repayment: 4 weekly installments, 5% monthly interest
   Auto-deducted every Monday via Celery beat

5. Missed 2+ installments → loan marked DEFAULTED →
   user flagged for review → score stops growing

6. Successful repayment → score jumps (8 pts per installment) →
   next loan limit increases
```

A brand-new user cannot get a loan. They must earn their way to score 50 through genuine economic activity. This is what makes the data valuable to microfinance partners.

---

## Squad Payment Integration

### Virtual account model (no native escrow API)

```
User registration → Django creates Squad VA per user (GTBank account number)
Job posted        → Django returns Kolliq Escrow VA number + job reference
Employer pays     → Squad webhook fires → Django matches payment to job
Job complete      → Django credits 95% to worker VA, 5% to platform VA
```

### Key constraints from Squad docs

- **GTBank settlement account required** — `SQUAD_BENEFICIARY_ACCOUNT` must be a GTBank 10-digit account
- **Merchant ID prefix on transfers** — all payout references must be `{MERCHANT_ID}_{your_ref}`
- **BVN not required** — we skip BVN validation (sandbox is lenient; production requires CBN compliance discussion)
- **Webhook signature** — v3 method: HMAC-SHA512 of 6 pipe-joined fields, not full body hash
- **424 errors** — always requery before creating a new transfer reference

### Test payments in sandbox

```bash
python manage.py shell
>>> from services.squad import SquadService
>>> from decimal import Decimal
>>> squad = SquadService()
>>> squad.simulate_payment('0123456789', Decimal('3500'))
# This fires your webhook exactly as a real payment would
```

---

## Integration Testing (Django + Node)

This section explains how to run a complete end-to-end test with both services running.

### Setup

```bash
# Both services need these shared values in their .env files:
# DATABASE_URL         ← same Supabase database
# REDIS_URL            ← same Redis instance
# INTERNAL_WEBHOOK_SECRET ← same value both sides
# SQUAD_SECRET_KEY     ← same Squad credentials
```

### Start both services

```bash
# Terminal A — Django
cd Kolliq_config
source venv/bin/activate
python manage.py runserver 8000

# Terminal B — Celery (Django async tasks)
celery -A kolliq worker -l info

# Terminal C — Node
cd kolliq-node
npm start   # or: node server.js

# Terminal D — ngrok (expose localhost to Squad + Africa's Talking)
ngrok http 8000   # copy the https URL
# Set it as your webhook URL in Squad dashboard and AT dashboard
```

### Full Tunde flow (gig worker)

```bash
# Step 1: Node registers Tunde (after OTP verify, Node calls Django)
curl -X POST http://localhost:8000/api/users/create/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+2348011111111",
    "role": "worker",
    "full_name": "Tunde Adeyemi",
    "skills": ["delivery"],
    "has_vehicle": true,
    "vehicle_type": "bike",
    "location_city": "Lagos",
    "location_area": "Surulere",
    "location_lat": "6.5009",
    "location_lng": "3.3564",
    "channel": "app"
  }'
# Save access_token from response → TUNDE_TOKEN

# Step 2: Create employer + job (run as employer user)
curl -X POST http://localhost:8000/api/users/create/ \
  -d '{"phone":"+2348033333333","role":"employer","full_name":"Alhaji Musa","business_name":"Musa Stores"}'
# Save EMPLOYER_TOKEN

curl -X POST http://localhost:8000/api/jobs/create/ \
  -H "Authorization: Bearer $EMPLOYER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Delivery Rider Needed",
    "skill_required": "delivery",
    "pay_per_worker": "3500",
    "location_area": "Surulere, Lagos",
    "location_city": "Lagos",
    "location_lat": "6.5009",
    "location_lng": "3.3564"
  }'
# Note escrow_instructions.reference from response → JOB_REF
# Note job_id → JOB_ID

# Step 3: Simulate escrow payment (triggers Squad webhook)
python manage.py shell -c "
from services.squad import SquadService
from django.conf import settings
from decimal import Decimal
squad = SquadService()
# Simulate employer paying escrow (include job reference in narration)
squad.simulate_payment(settings.KOLLIQ_ESCROW_VIRTUAL_ACCOUNT, Decimal('3500'))
"
# Check Celery worker logs — should see: 'Escrow matched and funded: job=...'
# Check job in admin: escrow_funded should be True

# Step 4: Tunde sees job in feed
curl http://localhost:8000/api/jobs/feed/ \
  -H "Authorization: Bearer $TUNDE_TOKEN"
# Job should appear with match_score

# Step 5: Tunde accepts job
curl -X POST http://localhost:8000/api/jobs/accept/ \
  -H "Authorization: Bearer $TUNDE_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"job_id\": \"$JOB_ID\"}"
# Employer should receive SMS (check AT sandbox dashboard)

# Step 6: Employer confirms complete
curl -X POST http://localhost:8000/api/jobs/complete/ \
  -H "Authorization: Bearer $EMPLOYER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"job_id\": \"$JOB_ID\"}"
# Tunde should receive SMS with payment confirmation
# Check Tunde's wallet: balance should be ₦3,325 (95%)

# Step 7: Check Tunde's score grew
curl http://localhost:8000/api/users/profile/ \
  -H "Authorization: Bearer $TUNDE_TOKEN"
# economic_score should be 15 (base 10 + 5 for completed gig)
```

### Full Amina flow (USSD trader)

```bash
# Amina registers via USSD — Node handles USSD session, calls Django to create user
curl -X POST http://localhost:8000/api/users/create/ \
  -d '{
    "phone": "+2347022222222",
    "role": "trader",
    "full_name": "Amina Bello",
    "trade_category": "food",
    "market_name": "Kano Central Market",
    "location_city": "Kano",
    "channel": "ussd"
  }'
# Save AMINA_TOKEN, note wallet account_number from GET /api/wallets/

# Customer pays Amina directly (simulate)
python manage.py shell -c "
from services.squad import SquadService
from decimal import Decimal
squad = SquadService()
squad.simulate_payment('AMINA_VA_NUMBER_HERE', Decimal('2000'))
"
# Amina should receive SMS: 'You received ₦2,000'
# Her score should tick up

# After enough transactions, check loan eligibility
curl http://localhost:8000/api/financial/loans/eligibility/ \
  -H "Authorization: Bearer $AMINA_TOKEN"
```

### Full Alhaji Musa flow (WhatsApp employer)

This flow is driven from the Node service. Test it via Twilio sandbox:
1. WhatsApp "I need a delivery rider in Surulere" to your Twilio sandbox number
2. Node's Claude intent detection classifies as "post_job"
3. Node collects details via multi-turn conversation
4. Node calls `POST /api/jobs/create/` on Django
5. Returns escrow instructions to employer in WhatsApp
6. Employer pays → webhook fires → job goes live
7. Employer WhatsApps "job done {ref}" → Node calls `POST /api/jobs/complete/`

### Verifying Node → Django calls

```bash
# Node calls Django with INTERNAL_WEBHOOK_SECRET header
# Test the internal webhook endpoint directly:
curl -X POST http://localhost:8000/api/payments/webhook/internal/ \
  -H "Content-Type: application/json" \
  -H "x-internal-secret: $INTERNAL_WEBHOOK_SECRET" \
  -d '{
    "transaction_reference": "TEST001",
    "virtual_account_number": "YOUR_ESCROW_VA",
    "principal_amount": "3500.00",
    "settled_amount": "3500.00",
    "fee_charged": "0.00",
    "customer_identifier": "kolliq-escrow-main",
    "sender_name": "ALHAJI MUSA",
    "remarks": "Payment YOURJOBREF001",
    "currency": "NGN",
    "channel": "virtual-account"
  }'
```

---

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-django pytest-cov pytest-mock factory-boy faker freezegun responses

# Run full test suite
pytest

# Run with coverage report
pytest --cov=apps --cov-report=html
open htmlcov/index.html

# Run specific module
pytest tests/test_escrow.py -v
pytest tests/test_scoring.py -v
pytest tests/test_marketplace.py -v

# Run fast (no DB reset between runs)
pytest --reuse-db

# Run a single test
pytest tests/test_financial.py::TestLoans::test_loan_apply_disburses_to_wallet -v
```

### Coverage targets

| Module | Target |
|---|---|
| scoring engine | 95%+ |
| escrow logic | 90%+ |
| financial services | 85%+ |
| marketplace | 80%+ |
| overall | 75%+ |

---

## Celery Scheduled Tasks

All tasks run automatically when `celery beat` is running.

| Task | Schedule | What it does |
|---|---|---|
| `accrue_daily_savings_interest` | Midnight daily | Adds 5% p.a. daily interest to all savings pots with balance > 0 |
| `deduct_daily_insurance_premiums` | 6am daily | Deducts ₦200 from active policy holders. Pauses policy if wallet empty. |
| `process_weekly_loan_repayments` | Monday 8am | Auto-deducts weekly installment. Flags users with 2+ missed payments. |
| `fraud_detection_sweep` | Every hour | Checks for fast job completions, high-frequency payments, early loan applications. |
| `expire_old_listings` | 1am daily | Pauses marketplace listings older than 30 days. |
| `flag_suspicious_listings` | Every hour (offset 30min) | Checks for spam keywords and high-frequency posting. |

---

## Django Admin

Access at `http://localhost:8000/admin/` with your superuser credentials.

### Key admin views

| Model | Key actions |
|---|---|
| **Users** | Filter by role, is_flagged, city. View score + wallet from profile. |
| **EconomicIdentityScore** | See score distribution. Filter by unlocked services. |
| **Jobs** | Filter by status, skill, city. See escrow_funded status. |
| **Transactions** | Full audit trail. Filter by type, status. |
| **Loans** | See active loans, repayment status. Demo float audit. |
| **InsuranceClaims** | Approve manual review claims directly (action: "Approve selected claims"). |
| **DemoFloat** | Monitor float balance vs disbursed vs repaid. |
| **Listings** | Feature listings, clear fraud flags, remove spam. |

---

## One-Time Setup Commands

```bash
# Create Squad system virtual accounts (escrow + platform)
python manage.py create_system_accounts

# Seed pilot demo data (categories, demo float, 12 tiered test users)
python manage.py seed_pilot

# Create Django superuser
python manage.py createsuperuser
```
```