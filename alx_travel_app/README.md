# ALX Travel App - Background Email Notifications with Celery

This project demonstrates the implementation of asynchronous background task processing using Celery with RabbitMQ as the message broker for sending booking confirmation emails.

## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Technical Details](#technical-details)

## Features

- **Asynchronous Email Notifications**: Booking confirmation emails are sent in the background without blocking the user request
- **RabbitMQ Integration**: Uses RabbitMQ as a reliable message broker
- **Celery Task Queue**: Distributed task processing for scalability
- **Django REST Framework**: RESTful API for booking management
- **User Authentication**: Secure booking endpoints with user authentication

## Prerequisites

- Python 3.8 or higher
- Django 4.2+
- RabbitMQ Server
- Virtual environment (recommended)
- Git

## Installation

### Step 1: Clone the Repository
```bash
git clone <repository-url>
cd alx_travel_app_0x03/alx_travel_app
```

### Step 2: Install RabbitMQ

#### Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install rabbitmq-server
sudo systemctl start rabbitmq-server
sudo systemctl enable rabbitmq-server
```

#### macOS (Homebrew):
```bash
brew install rabbitmq
brew services start rabbitmq
```

#### Windows:
Download from https://www.rabbitmq.com/download.html

Verify RabbitMQ is running:
```bash
sudo rabbitmqctl status
```

### Step 3: Set Up Virtual Environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate      # Windows
```

### Step 4: Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Required packages:
- Django>=4.2.0
- djangorestframework>=3.14.0
- celery>=5.3.0
- amqp>=5.1.1

### Step 5: Run Migrations
```bash
python manage.py migrate
```

### Step 6: Create Superuser
```bash
python manage.py createsuperuser
```

## Configuration

### Celery Configuration

The Celery configuration is in `alx_travel_app/celery.py`:
```python
CELERY_BROKER_URL = 'amqp://guest:guest@localhost:5672//'
CELERY_RESULT_BACKEND = 'rpc://'
```

### Email Configuration

For development, the console email backend is used (emails print to console):
```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

For production with Gmail SMTP:
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
DEFAULT_FROM_EMAIL = 'your-email@gmail.com'
```

**Note**: For Gmail, you need to generate an [App Password](https://support.google.com/accounts/answer/185833).

## Running the Application

You need **three separate terminal windows** running simultaneously:

### Terminal 1: Django Development Server
```bash
# Activate virtual environment
source venv/bin/activate

# Run Django server
python manage.py runserver

# Server available at: http://localhost:8000
```

### Terminal 2: RabbitMQ Server

RabbitMQ should already be running. Verify with:
```bash
sudo rabbitmqctl status
```

If not running:
```bash
sudo systemctl start rabbitmq-server  # Linux
brew services start rabbitmq          # macOS
```

### Terminal 3: Celery Worker
```bash
# Activate virtual environment
source venv/bin/activate

# Start Celery worker
celery -A alx_travel_app worker -l info

# On Windows:
celery -A alx_travel_app worker -l info --pool=solo
```

## Testing

### Test 1: Verify RabbitMQ Connection
```bash
# Check RabbitMQ status
sudo rabbitmqctl status

# List queues
sudo rabbitmqctl list_queues
```

### Test 2: Verify Celery Worker
```bash
# Ping Celery workers
celery -A alx_travel_app inspect ping

# Check registered tasks
celery -A alx_travel_app inspect registered
```

Expected output should include:
```
- listings.tasks.send_booking_confirmation_email
```

### Test 3: Create a Booking via API

#### Using curl:
```bash
# Login to get authentication token (if using token auth)
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass123"}'

# Create a booking
curl -X POST http://localhost:8000/api/bookings/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "listing": 1,
    "check_in_date": "2025-12-01",
    "check_out_date": "2025-12-05"
  }'
```

#### Using Django Shell:
```bash
python manage.py shell
```
```python
from django.contrib.auth.models import User
from listings.models import Listing, Booking
from listings.tasks import send_booking_confirmation_email
from datetime import date

# Get or create a user
user = User.objects.first()

# Get or create a listing
listing = Listing.objects.first()

# Create a booking
booking = Booking.objects.create(
    user=user,
    listing=listing,
    check_in_date=date(2025, 12, 1),
    check_out_date=date(2025, 12, 5)
)

# Test the email task manually
send_booking_confirmation_email.delay(
    booking_id=booking.id,
    user_email=user.email,
    listing_name=listing.name,
    check_in_date=str(booking.check_in_date),
    check_out_date=str(booking.check_out_date)
)
```

### Test 4: Monitor Email Output

When using the console email backend, check the **Django server terminal** for email output:
```
Content-Type: text/plain; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Subject: Booking Confirmation - Beautiful Beach House
From: noreply@alxtravelapp.com
To: user@example.com
Date: Mon, 01 Nov 2025 10:30:00 -0000

Dear Customer,

Thank you for your booking!

Booking Details:
----------------
Booking ID: 1
Property: Beautiful Beach House
Check-in Date: 2025-12-01
Check-out Date: 2025-12-05
...
```

### Test 5: Monitor Celery Tasks

In the Celery worker terminal, you should see:
```
[2025-11-01 10:30:00,123: INFO/MainProcess] Task listings.tasks.send_booking_confirmation_email[...] received
[2025-11-01 10:30:00,456: INFO/ForkPoolWorker-1] Booking confirmation email sent successfully for booking 1
[2025-11-01 10:30:00,789: INFO/ForkPoolWorker-1] Task listings.tasks.send_booking_confirmation_email[...] succeeded
```

## Project Structure
```
alx_travel_app/
├── alx_travel_app/
│   ├── __init__.py          # Celery app initialization
│   ├── celery.py            # Celery configuration
│   ├── settings.py          # Django settings with Celery config
│   ├── urls.py              # URL routing
│   └── wsgi.py
├── listings/
│   ├── models.py            # Booking and Listing models
│   ├── serializers.py       # DRF serializers
│   ├── views.py             # BookingViewSet with email trigger
│   ├── tasks.py             # Celery tasks for emails
│   └── urls.py
├── manage.py
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Technical Details

### How It Works

1. **User Creates a Booking**: User sends a POST request to `/api/bookings/`
2. **Booking is Saved**: Django saves the booking to the database
3. **Task is Queued**: The view triggers `send_booking_confirmation_email.delay()` which queues the task in RabbitMQ
4. **Immediate Response**: Django immediately returns a success response to the user
5. **Background Processing**: Celery worker picks up the task from RabbitMQ
6. **Email Sent**: The worker executes the task and sends the email
7. **Logging**: Success/failure is logged for monitoring

### Benefits of Asynchronous Processing

- **Improved User Experience**: Users don't wait for email sending
- **Better Performance**: Main application thread is not blocked
- **Scalability**: Can add more Celery workers to handle increased load
- **Reliability**: RabbitMQ ensures tasks are not lost
- **Retry Capability**: Failed tasks can be automatically retried

### Architecture
```
User Request → Django View → Database Save → RabbitMQ Queue
                    ↓
            Immediate Response
                    
RabbitMQ Queue → Celery Worker → Send Email → Log Result
```

## Troubleshooting

### Issue: RabbitMQ Connection Refused
```bash
# Check if RabbitMQ is running
sudo systemctl status rabbitmq-server

# Start RabbitMQ
sudo systemctl start rabbitmq-server
```

### Issue: Celery Worker Not Processing Tasks

1. Ensure RabbitMQ is running
2. Check `CELERY_BROKER_URL` in settings.py
3. Restart Celery worker
4. Check worker logs for errors

### Issue: Emails Not Sending

1. Verify email backend configuration in settings.py
2. For console backend, check Django server terminal output
3. For SMTP backend, verify credentials and network access
4. Check Celery worker logs

### Issue: Task Not Found
```bash
# Verify tasks are registered
celery -A alx_travel_app inspect registered

# Restart Celery worker after code changes
```

## Production Deployment

### Use a Process Manager

Use Supervisor or systemd to keep Celery workers running:
```bash
# Example supervisor config
[program:celery-worker]
command=/path/to/venv/bin/celery -A alx_travel_app worker -l info
directory=/path/to/project
user=www-data
autostart=true
autorestart=true
stdout_logfile=/var/log/celery/worker.log
stderr_logfile=/var/log/celery/worker_err.log
```

### Configure Production Email Backend

Use a production-ready email service:

- Gmail SMTP
- SendGrid
- Amazon SES
- Mailgun

### Secure RabbitMQ

1. Change default credentials
2. Enable SSL/TLS
3. Configure firewall rules
4. Use authentication and authorization

## Additional Resources

- [Celery Documentation](https://docs.celeryproject.org/)
- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)
- [Django Email Documentation](https://docs.djangoproject.com/en/stable/topics/email/)
- [Django REST Framework](https://www.django-rest-framework.org/)

## License

[Your License Here]

---

**Project:** ALX Backend Specialization
**Module:** Background Task Management
**Version:** 1.0