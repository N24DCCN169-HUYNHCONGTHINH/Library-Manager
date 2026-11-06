import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


class QASettingsSafetyTests(SimpleTestCase):
    def check_config(self, argv, qa_host, live_host, should_pass):
        script = f'''
import runpy,sys
from unittest.mock import patch
from django.core.exceptions import ImproperlyConfigured
sys.argv=['manage.py', {argv!r}]
qa='postgresql://qa_user:fake-test-password@{qa_host}/neondb'
live='postgresql://app_user:fake-test-password@{live_host}/neondb'
def values(path):
    return {{'LIBRARY_QA_DATABASE_URL':qa}} if str(path).endswith('.env.qa.local') else {{'LIBRARY_APP_DATABASE_URL':live}}
with patch('dotenv.dotenv_values', side_effect=values):
    try:
        result=runpy.run_module('config.qa')
    except ImproperlyConfigured:
        assert not {should_pass!r}
    else:
        assert {should_pass!r}
        assert result['DATABASES']['default']['TEST']['NAME']=='test_library_day11'
        assert result['EMAIL_BACKEND']=='django.core.mail.backends.locmem.EmailBackend'
'''
        result = subprocess.run([sys.executable, "-c", script], cwd=settings.BASE_DIR,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_qa_host_only_allows_explicit_test_database(self):
        self.check_config("test", "ep-cool-sea-a127a2za.ap-southeast-1.aws.neon.tech", "live.invalid", True)

    def test_qa_config_cannot_serve_app(self):
        self.check_config("runserver", "ep-cool-sea-a127a2za.ap-southeast-1.aws.neon.tech", "live.invalid", False)

    def test_wrong_endpoint_is_rejected(self):
        self.check_config("test", "unexpected.invalid", "live.invalid", False)

    def test_live_pooled_endpoint_is_rejected(self):
        self.check_config("test", "ep-cool-sea-a127a2za.ap-southeast-1.aws.neon.tech",
                          "ep-cool-sea-a127a2za-pooler.ap-southeast-1.aws.neon.tech", False)
