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
    assert ("GET", "/buckets") in routes
    assert ("GET", "/buckets/tree") in routes
    assert ("POST", "/buckets") in routes
    assert ("POST", "/buckets/bulk-move-documents") in routes
    assert ("POST", "/buckets/route-preview") in routes
    assert ("POST", "/buckets/{bucket_id}/move") in routes
    assert ("DELETE", "/buckets/{bucket_id}") in routes
