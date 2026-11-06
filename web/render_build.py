"""Collect static files without changing the database."""
import os
import subprocess
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.render")
for args in (["check"], ["collectstatic", "--noinput"]):
    subprocess.run([sys.executable, "manage.py", *args], check=True)
