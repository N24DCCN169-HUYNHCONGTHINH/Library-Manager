"""Start only the private application backend; Caddy terminates HTTPS."""
import os
from waitress import serve
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.local_https")
if __name__ == "__main__":
    serve(get_wsgi_application(), listen="127.0.0.1:9080", threads=4,
          trusted_proxy="127.0.0.1", trusted_proxy_headers={"x-forwarded-proto", "x-forwarded-for"},
          clear_untrusted_proxy_headers=True)
