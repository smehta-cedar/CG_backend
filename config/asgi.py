"""
ASGI config for config project.
"""

import os

from decouple import config
from django.core.asgi import get_asgi_application

os.environ["DJANGO_SETTINGS_MODULE"] = config("DJANGO_SETTINGS_MODULE")

application = get_asgi_application()
