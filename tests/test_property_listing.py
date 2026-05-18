"""Property-based tests for listing response transformation.

Feature: cloud-gallery-microservice, Property 7: Listing response transformation preserves metadata

Validates: Requirements 10.4, 10.5
"""

import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient
from hypothesis import given, settings
from hypothesis import strategies as st

from fastapi import FastAPI

# Garante env vars válidas antes de importar módulos da app
_TEST_ENV = {
    "AWS_ACCESS_KEY_ID": "test-key",
    "AWS_SECRET_ACCESS_KEY": "test-secret",
    "AWS_REGION": "us-east-1",
    "AWS_BUCKET_NAME": "test-bucket",
    "MONGODB_URI": "mongodb://localhost:27017/test",
}

with patch.dict(os.environ, _TEST_ENV, clear=False):
    if "app.config" in sys.modules:
        del sys.modules["app.config"]
    if "app.database" in sys.modules:
        del sys.modules["app.database"]
    if "app.router" in sys.modules:
        del sys.modules["app.router"]

    from app.router import router

# Cria app de teste com o router
_test_app = FastAPI()
_test_app.include_router(router, prefix="/galeria")


# --- Strategies ---

# Gera ObjectIds válidos como bytes aleatórios de 12 bytes
object_id_st = st.binary(min_size=12, max_size=12).map(lambda b: ObjectId(b))

nome_original_st = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=100,
)

data_upload_st = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2100, 1, 1),
).map(lambda dt: dt.isoformat())

tamanho_bytes_st = st.integers(min_value=1, max_value=10_485_760)

# Gera um documento MongoDB individual com campos válidos
mongodb_document_st = st.fixed_dictionaries({
    "_id": object_id_st,
    "nome_original": nome_original_st,
    "caminho_s3": st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P"), blacklist_characters="\x00"),
        min_size=1,
        max_size=100,
    ),
    "categoria": st.sampled_from(["fotos", "planilhas", "documentos", "outros"]),
    "tamanho_bytes": tamanho_bytes_st,
    "data_upload": data_upload_st,
})

# Gera listas de documentos MongoDB (0 a 20 documentos)
mongodb_documents_list_st = st.lists(mongodb_document_st, min_size=0, max_size=20)


class TestListingResponseTransformation:
    """Property 7: Listing response transformation preserves metadata.

    For any list of MongoDB documents containing valid arquivo metadata,
    the listing endpoint response SHALL contain a `total` field equal to
    the list length, and each item in the `arquivos` array SHALL have
    `id` (string of _id), `nome` (equal to nome_original), `data`
    (equal to data_upload), and `tamanho` (equal to tamanho_bytes)
    with no additional fields and no pre-signed URLs.

    **Validates: Requirements 10.4, 10.5**
    """

    @given(documentos=mongodb_documents_list_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_total_equals_document_count(self, documentos: list[dict]) -> None:
        """Response total field equals the number of documents returned by DB.

        **Validates: Requirements 10.4**
        """
        with patch("app.router.listar_arquivos", new_callable=AsyncMock) as mock_listar:
            mock_listar.return_value = documentos

            transport = ASGITransport(app=_test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/galeria/arquivos/")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == len(documentos)

    @given(documentos=mongodb_documents_list_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_each_item_maps_id_correctly(self, documentos: list[dict]) -> None:
        """Each item id equals str(_id) from the MongoDB document.

        **Validates: Requirements 10.4**
        """
        with patch("app.router.listar_arquivos", new_callable=AsyncMock) as mock_listar:
            mock_listar.return_value = documentos

            transport = ASGITransport(app=_test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/galeria/arquivos/")

            data = response.json()
            for i, arquivo in enumerate(data["arquivos"]):
                assert arquivo["id"] == str(documentos[i]["_id"])

    @given(documentos=mongodb_documents_list_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_each_item_maps_nome_correctly(self, documentos: list[dict]) -> None:
        """Each item nome equals nome_original from the MongoDB document.

        **Validates: Requirements 10.4**
        """
        with patch("app.router.listar_arquivos", new_callable=AsyncMock) as mock_listar:
            mock_listar.return_value = documentos

            transport = ASGITransport(app=_test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/galeria/arquivos/")

            data = response.json()
            for i, arquivo in enumerate(data["arquivos"]):
                assert arquivo["nome"] == documentos[i]["nome_original"]

    @given(documentos=mongodb_documents_list_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_each_item_maps_data_correctly(self, documentos: list[dict]) -> None:
        """Each item data equals data_upload from the MongoDB document.

        **Validates: Requirements 10.4**
        """
        with patch("app.router.listar_arquivos", new_callable=AsyncMock) as mock_listar:
            mock_listar.return_value = documentos

            transport = ASGITransport(app=_test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/galeria/arquivos/")

            data = response.json()
            for i, arquivo in enumerate(data["arquivos"]):
                assert arquivo["data"] == documentos[i]["data_upload"]

    @given(documentos=mongodb_documents_list_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_each_item_maps_tamanho_correctly(self, documentos: list[dict]) -> None:
        """Each item tamanho equals tamanho_bytes from the MongoDB document.

        **Validates: Requirements 10.4**
        """
        with patch("app.router.listar_arquivos", new_callable=AsyncMock) as mock_listar:
            mock_listar.return_value = documentos

            transport = ASGITransport(app=_test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/galeria/arquivos/")

            data = response.json()
            for i, arquivo in enumerate(data["arquivos"]):
                assert arquivo["tamanho"] == documentos[i]["tamanho_bytes"]

    @given(documentos=mongodb_documents_list_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_no_presigned_urls_in_listing(self, documentos: list[dict]) -> None:
        """Listing response items do not contain pre-signed URLs or extra fields.

        **Validates: Requirements 10.5**
        """
        with patch("app.router.listar_arquivos", new_callable=AsyncMock) as mock_listar:
            mock_listar.return_value = documentos

            transport = ASGITransport(app=_test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/galeria/arquivos/")

            data = response.json()
            # Response should only have "total" and "arquivos" keys
            assert set(data.keys()) == {"total", "arquivos"}

            for arquivo in data["arquivos"]:
                # Each item should only have id, nome, data, tamanho
                assert set(arquivo.keys()) == {"id", "nome", "data", "tamanho"}
                # No URL fields present
                assert "url_download" not in arquivo
                assert "url_acesso" not in arquivo
                assert "url" not in arquivo
