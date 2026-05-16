"""Property-Based Test: Invalid categoria rejection at API boundary.

Feature: cloud-gallery-microservice, Property 5: Invalid categoria rejection at API boundary

Validates: Requirements 2.3, 9.6, 10.7

Usa Hypothesis para gerar strings que não são membros do CategoriaEnum,
verificando que endpoints retornam 422 com mensagem listando valores permitidos.
"""

import io
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given, settings as hyp_settings, assume
from hypothesis import strategies as st

from app.models import CategoriaEnum

# Valores válidos do enum para filtrar
VALID_CATEGORIA_VALUES = {e.value for e in CategoriaEnum}


# Strategy: gera strings que NÃO são membros válidos do CategoriaEnum
# Inclui strings aleatórias, excluindo os 4 valores válidos (case-insensitive)
invalid_categoria_st = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=50,
).filter(lambda s: s.lower() not in VALID_CATEGORIA_VALUES)


# Variáveis de ambiente válidas para permitir importação do config
_VALID_ENV = {
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_REGION": "us-east-1",
    "AWS_BUCKET_NAME": "test-bucket",
    "MONGODB_URI": "mongodb://localhost:27017/test",
}


def _get_test_app():
    """Cria uma instância isolada do FastAPI app para testes.

    Importa o router com env vars válidas para evitar sys.exit(1) do config.
    Mocks S3 e Database para focar apenas na validação de categoria
    na camada de API boundary.
    """
    from fastapi import FastAPI

    # Garantir que app.config pode ser importado sem sys.exit
    with patch.dict(os.environ, _VALID_ENV, clear=False):
        # Limpar módulos cacheados que podem ter falhado
        modules_to_clear = [
            m for m in sys.modules if m.startswith("app.") and m != "app.models"
        ]
        saved_modules = {}
        for m in modules_to_clear:
            saved_modules[m] = sys.modules.pop(m)

        try:
            from app.router import router

            test_app = FastAPI()
            test_app.include_router(router)
            return test_app
        finally:
            # Restaurar módulos
            for m, mod in saved_modules.items():
                if m not in sys.modules:
                    sys.modules[m] = mod


# Criar app uma única vez para evitar re-imports repetidos
with patch.dict(os.environ, _VALID_ENV, clear=False):
    # Limpar módulos cacheados que podem ter falhado
    _modules_to_clear = [
        m for m in list(sys.modules.keys()) if m.startswith("app.") and m != "app.models"
    ]
    for _m in _modules_to_clear:
        sys.modules.pop(_m, None)

    from app.router import router  # noqa: E402
    from fastapi import FastAPI

    _test_app = FastAPI()
    _test_app.include_router(router)


class TestInvalidCategoriaRejection:
    """Property 5: Invalid categoria rejection at API boundary.

    For any string value that does not match any CategoriaEnum member,
    the API endpoints accepting categoria SHALL return HTTP status 422
    with a validation error listing the allowed values.

    **Validates: Requirements 2.3, 9.6, 10.7**
    """

    @given(invalid_cat=invalid_categoria_st)
    @hyp_settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_post_upload_rejects_invalid_categoria(self, invalid_cat: str) -> None:
        """POST /upload/ retorna 422 para categoria inválida.

        **Validates: Requirements 2.3, 9.6**
        """
        from httpx import ASGITransport, AsyncClient

        with (
            patch("app.router.validar_content_type"),
            patch("app.router.validar_tamanho", new_callable=AsyncMock, return_value=100),
            patch("app.router.upload_arquivo", return_value="test/path.txt"),
            patch("app.router.inserir_arquivo", new_callable=AsyncMock, return_value="fake_id"),
        ):
            transport = ASGITransport(app=_test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/upload/",
                    data={"categoria": invalid_cat},
                    files={"file": ("test.txt", io.BytesIO(b"content"), "text/plain")},
                )

        assert response.status_code == 422, (
            f"Expected 422 for invalid categoria '{invalid_cat}', got {response.status_code}"
        )

        # Verifica que a resposta contém informação sobre valores permitidos
        body = response.json()
        assert "detail" in body

    @given(invalid_cat=invalid_categoria_st)
    @hyp_settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_get_arquivos_rejects_invalid_categoria(self, invalid_cat: str) -> None:
        """GET /arquivos/?categoria=... retorna 422 para categoria inválida.

        **Validates: Requirements 2.3, 10.7**
        """
        from httpx import ASGITransport, AsyncClient

        with patch("app.router.listar_arquivos", new_callable=AsyncMock, return_value=[]):
            transport = ASGITransport(app=_test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/arquivos/",
                    params={"categoria": invalid_cat},
                )

        assert response.status_code == 422, (
            f"Expected 422 for invalid categoria '{invalid_cat}', got {response.status_code}"
        )

        # Verifica que a resposta contém informação sobre valores permitidos
        body = response.json()
        assert "detail" in body
