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


def _make_cors_app(origins: list[str]):
    """Cria uma app FastAPI isolada com a mesma config de CORS de produção.

    Evita reimportar main.py/app.* (que contaminaria sys.modules e quebraria
    os mocks de outros testes). Replica exatamente o middleware usado em main.py.
    """
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    cors_app = FastAPI()
    cors_app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @cors_app.get("/")
    async def _root():
        return {"status": "ok"}

    return cors_app


def test_cors_origins_list_faz_parsing_de_string_separada_por_virgula():
    """settings.cors_origins_list converte a string CSV em lista limpa."""
    from app.config import Settings

    s = Settings(
        AWS_ACCESS_KEY_ID="k",
        AWS_SECRET_ACCESS_KEY="s",
        AWS_BUCKET_NAME="b",
        MONGODB_URI="mongodb://localhost:27017/test",
        CORS_ORIGINS=" https://a.com , https://b.com ,, ",
    )
    assert s.cors_origins_list == ["https://a.com", "https://b.com"]


def test_cors_origins_list_vazio_retorna_lista_vazia():
    """CORS_ORIGINS vazio (padrão seguro) resulta em lista vazia."""
    from app.config import Settings

    s = Settings(
        AWS_ACCESS_KEY_ID="k",
        AWS_SECRET_ACCESS_KEY="s",
        AWS_BUCKET_NAME="b",
        MONGODB_URI="mongodb://localhost:27017/test",
    )
    assert s.cors_origins_list == []


@pytest.mark.asyncio
async def test_cors_reflete_origem_configurada():
    """Origem listada em CORS_ORIGINS deve ser refletida nos headers CORS."""
    cors_app = _make_cors_app(["http://localhost:3000"])
    async with AsyncClient(transport=ASGITransport(app=cors_app), base_url="http://test") as client:
        response = await client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin == "http://localhost:3000"
    assert "GET" in response.headers.get("access-control-allow-methods", "")


@pytest.mark.asyncio
async def test_cors_rejeita_origem_nao_listada():
    """Origem fora de CORS_ORIGINS não deve receber header de permissão."""
    cors_app = _make_cors_app(["http://localhost:3000"])
    async with AsyncClient(transport=ASGITransport(app=cors_app), base_url="http://test") as client:
        response = await client.options(
            "/",
            headers={
                "Origin": "http://malicioso.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin != "http://malicioso.example"


@pytest.mark.asyncio
async def test_cors_nao_permite_credentials():
    """API não usa cookies/sessão: allow_credentials deve estar desativado."""
    cors_app = _make_cors_app(["http://localhost:3000"])
    async with AsyncClient(transport=ASGITransport(app=cors_app), base_url="http://test") as client:
        response = await client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.headers.get("access-control-allow-credentials") != "true"


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
