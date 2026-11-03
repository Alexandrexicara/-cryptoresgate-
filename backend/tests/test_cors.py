from app.main import build_cors_origins


def test_production_frontend_is_allowed_by_default():
    origins = build_cors_origins(None)

    assert "https://cryptoresgate.netlify.app" in origins
    assert "http://localhost:5173" in origins


def test_custom_origins_are_preserved_and_normalized():
    origins = build_cors_origins("https://preview.example.com/, https://cryptoresgate.netlify.app")

    assert "https://preview.example.com" in origins
    assert origins.count("https://cryptoresgate.netlify.app") == 1
