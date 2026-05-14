# CHARBT API

Flask backend for CHARBT, a trading-analysis platform with authenticated market sessions, screenshots, subscription billing, account management, and admin tooling.

## Features

- Public and authenticated API blueprints for account, trading, screenshot, blog, and subscription workflows.
- JWT-based authentication with user session validation.
- PostgreSQL persistence through SQLAlchemy models.
- Redis-backed Flask caching.
- Stripe checkout, subscription, and webhook handling.
- AWS S3 integration for market data and uploaded screenshots.
- Email confirmation, password recovery, and support ticket emails.
- Telegram notification helper.
- Docker Compose setup for API, Redis, and nginx deployment.

## Tech Stack

- Python / Flask
- SQLAlchemy
- Flask-JWT-Extended
- PostgreSQL
- Redis / Flask-Caching
- Stripe SDK
- boto3 / AWS S3
- Docker, nginx, GitHub Actions

## Configuration

Create a local `.env` file from `.env.example`:

```bash
cp .env.example .env
```

Required values depend on the deployment environment:

```env
SECRET_KEY=replace-with-a-random-secret
DATABASE_URL=postgresql://charbt:charbt@postgres:5432/charbt_db
AWS_ACCES_KEY=
AWS_SECRET_KEY=
EMAIL_SMTP_HOST=smtp.example.com
EMAIL_SMTP_PORT=465
EMAIL_PASSWORD=
STRIPE_KEY=
STRIPE_SECRET=
STRIPE_ENDPOINT_DELETED=
STRIPE_ENDPOINT_CANCELED=
STRIPE_ENDPOINT_COMPLITE=
TELEGRAM_API=
```

Secrets must be provided through environment variables or GitHub Actions secrets. Do not commit live database credentials, SMTP passwords, Stripe secrets, AWS keys, or Telegram bot tokens.

## Development

Install dependencies:

```bash
cd api
pip install -r requirements.txt
```

Run with Docker Compose:

```bash
docker compose -f docker-compose.dev.yml up --build
```

Run the Flask app directly:

```bash
cd api
flask --app main run --host 0.0.0.0 --port 5000
```

## Deployment

The production Compose file expects runtime environment variables for the API, Stripe, AWS, email, and Telegram integrations. The GitHub Actions workflow connects to the deployment host and runs Docker Compose with secrets sourced from GitHub Actions.
