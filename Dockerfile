# Start from a lightweight Python image
FROM python:3.13-slim

# Create the app directory
RUN mkdir /app

# Set the working directory inside the container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y libpq-dev gcc iputils-ping && rm -rf /var/lib/apt/lists/*

# Install dependencies

COPY requirements.txt  /app/
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy the Django project to the container
COPY . /app/

# Expose port
EXPOSE 8000

# Run Django with makemigrations and migrations
CMD ["sh", "-c", "python manage.py makemigrations --noinput && python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn core.wsgi:application --reload --bind 0.0.0.0:8000"]