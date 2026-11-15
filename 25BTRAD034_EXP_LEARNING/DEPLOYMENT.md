# CityOS Production Deployment & Operations Guide

Welcome to the **CityOS** production deployment guide. This document provides step-by-step instructions for running CityOS in local development, containerized environments (Docker), and production servers (Linux with Gunicorn and Nginx, or Windows with Waitress).

---

## 1. Environment Configuration

CityOS uses `python-dotenv` to load environment variables from a `.env` file.

### Step 1: Create your `.env` file
Copy the `.env.example` template:
```bash
cp .env.example .env
```

### Step 2: Configure Production Variables
Open `.env` and set the following parameters:

```ini
# Flask Core
FLASK_APP=app.py
FLASK_ENV=production
FLASK_DEBUG=0
PORT=5000

# Security Key (Generate a random 64-char key)
# Command: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your_generated_64_character_hex_key_here

# Set to 1 when running behind HTTPS/SSL
SESSION_COOKIE_SECURE=1

# Initial Administrator Credentials
ADMIN_EMAIL=admin@cityos.com
ADMIN_PASSWORD=your_secure_admin_password_here

# Database Path
DATABASE_PATH=instance/cityos.db
```

> [!IMPORTANT]
> In `FLASK_ENV=production`, CityOS will refuse to start if `SECRET_KEY` is omitted or set to an insecure default placeholder.

---

## 2. Local Development Startup

To run CityOS locally in development mode:

```bash
# 1. Activate virtual environment
source .venv/bin/activate       # Linux / macOS
# or
.\.venv\Scripts\Activate.ps1    # Windows PowerShell

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run application
python app.py
```
Access the application at `http://localhost:5000`.

---

## 3. Production WSGI Server (Gunicorn / Waitress)

Never run the Flask built-in development server in production. Use a dedicated WSGI server.

### A. Linux Production Server (Gunicorn)
Run CityOS using Gunicorn with the pre-configured `gunicorn.conf.py`:

```bash
gunicorn -c gunicorn.conf.py wsgi:app
```

Or specify custom worker parameters directly:
```bash
gunicorn --workers 4 --threads 2 --bind 0.0.0.0:5000 wsgi:app
```

### B. Windows Production Server (Waitress)
On Windows hosts where Gunicorn is not natively supported, use Waitress:

```powershell
waitress-serve --port=5000 wsgi:app
```

---

## 4. Docker Deployment

CityOS includes a lightweight, secure production `Dockerfile` based on `python:3.11-slim`.

### Step 1: Build the Docker Image
```bash
docker build -t cityos:latest .
```

### Step 2: Run the Docker Container
Run the container with your `.env` file and volume mounts for persistent data:

```bash
docker run -d \
  --name cityos_app \
  --restart unless-stopped \
  -p 5000:5000 \
  --env-file .env \
  -v $(pwd)/instance:/app/instance \
  -v $(pwd)/uploads:/app/uploads \
  cityos:latest
```

### Step 3: Verify Container Health
```bash
docker ps
curl http://localhost:5000/api/health
```

---

## 5. Nginx Reverse Proxy Setup (Linux)

In production, place Nginx in front of Gunicorn to handle static assets, request buffering, and SSL termination.

### Step 1: Copy Configuration Template
```bash
sudo cp deployment/nginx.conf.template /etc/nginx/sites-available/cityos
```

### Step 2: Customize Domain and Paths
Edit `/etc/nginx/sites-available/cityos`:
- Update `server_name` to your domain (e.g. `cityos.example.com`).
- Ensure `/static/` and `/uploads/` aliases point to your app directory (e.g. `/var/www/cityos/static/`).

### Step 3: Enable Site & Test Nginx
```bash
sudo ln -s /etc/nginx/sites-available/cityos /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 6. Future HTTPS / SSL Setup (Let's Encrypt / Certbot)

To secure CityOS with free automated SSL certificates from Let's Encrypt:

1. Install Certbot for Nginx:
   ```bash
   sudo apt update
   sudo apt install certbot python3-certbot-nginx -y
   ```
2. Obtain and install certificate:
   ```bash
   sudo certbot --nginx -d cityos.example.com
   ```
3. Set `SESSION_COOKIE_SECURE=1` in your `.env` file and restart Gunicorn.

---

## 7. Operational Health & Monitoring

- **Health Check Endpoint**: `GET /api/health`
  - Returns `{"status": "online", "database": {"status": "connected"}}` with HTTP 200.
  - Safe for load balancer probes and uptime monitors.
- **Error Recovery Pages**:
  - `403` Access Denied
  - `404` Page / Report Not Found
  - `413` Payload Too Large (exceeds 16MB)
  - `500` Internal Server Error
- **Logs**:
  - Gunicorn and Flask output structured logs to stdout/stderr.
