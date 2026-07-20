"""Phase 3 hardening (2026-07-20): script-src no longer needs 'unsafe-inline' now that every
inline <script> and on*= handler in frontend/ has been moved to an external file — this is the
regression test that keeps it from silently creeping back in. style-src keeps 'unsafe-inline'
deliberately (see main.py's comment); this test only asserts on script-src.
"""


def test_csp_script_src_has_no_unsafe_inline(client):
    resp = client.get("/")
    csp = resp.headers.get("content-security-policy", "")
    assert csp, "CSP header must be present"

    script_src_directive = next((d for d in csp.split(";") if d.strip().startswith("script-src")), None)
    assert script_src_directive is not None, "script-src directive must be present"
    assert "'unsafe-inline'" not in script_src_directive


def test_security_headers_present(client):
    resp = client.get("/")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
