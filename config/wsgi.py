"""
WSGI config for config project.
"""

import os

from decouple import config
from django.core.wsgi import get_wsgi_application

os.environ["DJANGO_SETTINGS_MODULE"] = config("DJANGO_SETTINGS_MODULE")

application = get_wsgi_application()
