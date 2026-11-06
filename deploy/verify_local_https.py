"""Verify the local TLS chain without modifying Windows certificate stores."""
import http.cookiejar
import json
from pathlib import Path
import ssl
import urllib.error
import urllib.request

root = Path(__file__).resolve().parents[1] / "work" / "day10"
context = ssl.create_default_context(cafile=str(root / "caddy-data/pki/authorities/local/root.crt"))
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), urllib.request.HTTPCookieProcessor(jar))
result = {}
for path in ("/health/", "/accounts/login/", "/static/admin/css/base.css"):
    response = opener.open("https://localhost:9443" + path, timeout=15)
    assert response.status == 200
    result[path] = response.status
assert any(cookie.name == "library_local_https_csrf" and cookie.secure for cookie in jar)
for request, accepted in [
    (urllib.request.Request("https://localhost:9443/accounts/login/", data=b"username=invalid&password=invalid",
                            headers={"Origin": "https://untrusted.example.invalid"}), {403}),
    (urllib.request.Request("https://localhost:9443/", headers={"Host": "untrusted.example.invalid"}), {400, 421}),
]:
    try:
        opener.open(request, timeout=15)
        raise AssertionError("Invalid request was accepted")
    except urllib.error.HTTPError as error:
        assert error.code in accepted
        result["foreign_origin_post" if 403 in accepted else "invalid_host"] = error.code
result.update(certificate_verified_with_local_ca=True, csrf_cookie_secure=True,
              root_ca_installed_in_windows=False)
(root / "https-verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))
