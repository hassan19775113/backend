#!/bin/bash

# Vercel Build Script for Django
echo "Building Django application for Vercel..."

# Install Python dependencies
pip install -r backend/requirements.txt

# Change to backend directory
cd backend

# Collect static files
python manage.py collectstatic --noinput --settings=praxi_backend.settings.prod

echo "Build completed successfully!"
