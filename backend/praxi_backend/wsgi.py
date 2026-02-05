"""
WSGI config for praxi_backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# Default to modular dev settings. Deployments should set DJANGO_SETTINGS_MODULE.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "praxi_backend.settings.dev")

application = get_wsgi_application()

# Vercel serverless handler
app = application
