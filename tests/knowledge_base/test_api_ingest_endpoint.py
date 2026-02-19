from app.main import app


def test_ingest_endpoint_is_registered() -> None:
    routes = {
        (method, route.path)
        for route in app.routes
        if hasattr(route, "methods")
        for method in (route.methods or set())
    }
    assert ("POST", "/ingest") in routes
    assert ("POST", "/upload") in routes
