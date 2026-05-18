"""Testes unitários para o entry point main.py.

Valida: health-check, CORS middleware e metadados da aplicação.
Requirements: 12.1, 12.2, 12.3, 12.4
"""

import os
import sys
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


def _get_app():
    """Importa a app FastAPI garantindo env vars válidas para o Config_Module."""
    valid_env = {
        "AWS_ACCESS_KEY_ID": "test-key-id",
        "AWS_SECRET_ACCESS_KEY": "test-secret-key",
        "AWS_REGION": "us-east-1",
        "AWS_BUCKET_NAME": "test-bucket",
        "MONGODB_URI": "mongodb://localhost:27017/test",
    }

    # Se o módulo já foi importado, reutiliza
    if "main" in sys.modules:
        from main import app
        return app

    with patch.dict(os.environ, valid_env, clear=False):
        # Força reimportação limpa do config se necessário
        if "app.config" in sys.modules:
            del sys.modules["app.config"]

        from main import app
        return app


app = _get_app()


@pytest.mark.asyncio
async def test_health_check_retorna_status_ok():
    """GET / deve retornar 200 com {"status": "ok"}."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_cors_headers_presentes():
    """Requisição com Origin deve receber headers CORS na resposta."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    # Com allow_credentials=True, Starlette reflete o Origin ao invés de "*"
    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin in ("*", "http://localhost:3000")
    assert "GET" in response.headers.get("access-control-allow-methods", "")


@pytest.mark.asyncio
async def test_cors_allow_credentials():
    """CORS deve permitir credentials."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.headers.get("access-control-allow-credentials") == "true"


def test_app_metadata():
    """FastAPI app deve ter title, description e version configurados."""
    assert app.title == "Cloud Gallery API"
    assert app.version == "1.0.0"
    assert app.description != ""


def test_router_incluido():
    """O router do Router_Module deve estar incluído na app."""
    paths = [route.path for route in app.routes]
    assert "/galeria/upload/" in paths
    assert "/galeria/arquivos/" in paths
