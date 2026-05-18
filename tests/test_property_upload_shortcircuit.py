"""
Property-Based Test: Upload short-circuits on Content-Type validation failure.

Feature: cloud-gallery-microservice, Property 6: Upload short-circuits on Content-Type validation failure

**Validates: Requirements 9.4**

Usa Hypothesis para gerar content-types inválidos com mocks de S3/DB,
verificando que S3 e DB nunca são invocados quando Content-Type é inválido.
"""

import io
import os
import sys
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from hypothesis import given, settings as hyp_settings, assume
from hypothesis import strategies as st

# Garantir que app.config pode ser importado sem sys.exit(1)
_VALID_ENV = {
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_REGION": "us-east-1",
    "AWS_BUCKET_NAME": "test-bucket",
    "MONGODB_URI": "mongodb://localhost:27017/test",
}

# Patch env antes de importar módulos da app
_env_patch = patch.dict(os.environ, _VALID_ENV, clear=False)
_env_patch.start()

# Limpar cache de módulos se necessário
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith("app."):
        pass  # Manter se já importados com env válido

if "app.config" not in sys.modules:
    import app.config  # noqa: F401

from app.models import CategoriaEnum
from app.validators import BLOCKED_CONTENT_TYPES, CONTENT_TYPE_MAP

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.router import router

# Criar app de teste
_test_app = FastAPI(title="Cloud File Gallery API - Test")
_test_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
_test_app.include_router(router, prefix="/galeria")

# --- Strategies ---

# Gera um CategoriaEnum aleatório
categoria_strategy = st.sampled_from(list(CategoriaEnum))

# Todos os MIME types permitidos (união de todas as categorias)
ALL_ALLOWED_TYPES: set[str] = set()
for _cat in CategoriaEnum:
    ALL_ALLOWED_TYPES |= CONTENT_TYPE_MAP[_cat]

# Strategy: MIME types bloqueados (executáveis/scripts)
blocked_mime_strategy = st.sampled_from(sorted(BLOCKED_CONTENT_TYPES))

# Strategy: MIME types aleatórios que não estão em nenhuma whitelist nem na blocklist
random_mime_type = st.from_regex(
    r"[a-z]{1,15}/[a-z0-9\-\.]{1,30}", fullmatch=True
)

unrecognized_mime_strategy = random_mime_type.filter(
    lambda m: m not in ALL_ALLOWED_TYPES and m not in BLOCKED_CONTENT_TYPES
)


def invalid_content_type_for_categoria(categoria: CategoriaEnum) -> st.SearchStrategy[str]:
    """Gera content-types que são inválidos para a categoria dada.

    Combina:
    - Tipos bloqueados (executáveis/scripts) - sempre rejeitados
    - Tipos não reconhecidos (aleatórios que não estão em nenhuma whitelist)
    - Tipos de outras categorias que não são permitidos nesta
    """
    allowed_for_cat = CONTENT_TYPE_MAP[categoria]

    # Tipos de outras categorias que não são permitidos nesta
    other_cat_types = ALL_ALLOWED_TYPES - allowed_for_cat
    strategies = [unrecognized_mime_strategy, blocked_mime_strategy]
    if other_cat_types:
        strategies.append(
            st.sampled_from(sorted(other_cat_types)).filter(
                lambda m: m not in allowed_for_cat
            )
        )

    return st.one_of(*strategies)


# --- Property Tests ---


class TestUploadShortCircuitOnContentTypeFailure:
    """Property 6: Upload short-circuits on Content-Type validation failure.

    Para qualquer upload request onde o Content-Type não está na whitelist
    da categoria especificada, o Router_Module deve retornar HTTP 400
    sem invocar S3_Service upload ou Database_Module insertion.

    **Validates: Requirements 9.4**
    """

    @given(
        categoria=categoria_strategy,
        data=st.data(),
    )
    @hyp_settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_invalid_content_type_returns_400_without_s3_or_db(
        self, categoria, data
    ):
        """
        Para qualquer content-type inválido para a categoria dada,
        o endpoint POST /upload/ deve:
        1. Retornar HTTP 400
        2. NÃO invocar upload_arquivo (S3)
        3. NÃO invocar inserir_arquivo (DB)

        **Validates: Requirements 9.4**
        """
        invalid_ct = data.draw(
            invalid_content_type_for_categoria(categoria),
            label="invalid_content_type",
        )

        # Mocks para S3 e DB - devem NUNCA ser chamados
        mock_upload_s3 = MagicMock(return_value="fake/path.bin")
        mock_inserir_db = AsyncMock(return_value="fake_id_123")

        with patch("app.router.upload_arquivo", mock_upload_s3), \
             patch("app.router.inserir_arquivo", mock_inserir_db):

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=_test_app),
                base_url="http://test",
            ) as client:
                file_content = b"dummy file content for property test"
                files = {"file": ("test_file.bin", io.BytesIO(file_content), invalid_ct)}
                form_data = {"categoria": categoria.value}

                response = await client.post(
                    "/galeria/upload/",
                    files=files,
                    data=form_data,
                )

        # 1. Deve retornar HTTP 400
        assert response.status_code == 400, (
            f"Esperado 400 para content-type '{invalid_ct}' na categoria "
            f"'{categoria.value}', mas recebeu {response.status_code}"
        )

        # 2. S3 NUNCA deve ser invocado quando Content-Type é inválido
        mock_upload_s3.assert_not_called(), (
            f"S3 upload_arquivo foi chamado com content-type inválido "
            f"'{invalid_ct}' para categoria '{categoria.value}'"
        )

        # 3. DB NUNCA deve ser invocado quando Content-Type é inválido
        mock_inserir_db.assert_not_called(), (
            f"DB inserir_arquivo foi chamado com content-type inválido "
            f"'{invalid_ct}' para categoria '{categoria.value}'"
        )
