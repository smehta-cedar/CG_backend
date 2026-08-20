# Senior Health Backend

Django 5.2 API backend. Local development uses SQLite.

## Prerequisites

- Python 3.12+ (3.13 is fine)
- `pip`

## Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd seniorhealth_backend
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
```

macOS / Linux:

```bash
source venv/bin/activate
```

Windows:

```bash
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example env file:

```bash
cp .env.example .env
```

Or create `.env` in the project root with:

```env
DJANGO_SETTINGS_MODULE=config.settings.local
SECRET_KEY=django-insecure-#-(4a)6r@!fu7jxt_jz*xgv2#_1q_%=eg!x$xce5c&iy1f*%ie
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

| Variable | Description |
|---|---|
| `DJANGO_SETTINGS_MODULE` | Settings module. Use `config.settings.local` for development. |
| `SECRET_KEY` | Django secret key used locally. |
| `DEBUG` | `True` for local development. |
| `ALLOWED_HOSTS` | Comma-separated hosts, e.g. `localhost,127.0.0.1`. |

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. (Optional) Create a superuser

```bash
python manage.py createsuperuser
```

### 7. Start the development server

```bash
python manage.py runserver
```

The app is available at [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Admin is at [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/).

## CSS (Tailwind)

Rebuild on template changes with the Tailwind standalone CLI (no npm):

```bash
tailwindcss -i static/src/input.css -o static/css/tailwind.css --watch
```

## Project layout

```
config/          Django project (settings, urls, wsgi/asgi)
apps/            Feature apps (`python manage.py startapp <name>` creates them here)
manage.py
requirements.txt
.env.example
```

New Django apps go in `apps/` unless you pass an explicit destination to `startapp`. After creating an app, add it to `LOCAL_APPS` in `config/settings/base.py`.
