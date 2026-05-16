"""
Integration Tests - Fluxos end-to-end com moto (S3) e mocks de DB.

Testa cenários completos que atravessam múltiplos módulos:
- Upload válido → 201 com campos corretos
- Upload + Download → url_download presente
- Listagem filtrada → apenas matching
- Falha parcial (S3 OK + DB falha) → 500 com mensagem de inconsistência

Validates: Requirements 9.2, 9.3, 10.4, 11.5, 9.7
"""

import io
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import boto3
import pytest
import pytest_asyncio
from bson import ObjectId
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from moto import mock_aws

# Env vars válidas para importar módulos sem sys.exit
_TEST_ENV = {
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_REGION": "us-east-1",
    "AWS_BUCKET_NAME": "test-bucket",
    "MONGODB_URI": "mongodb://localhost:27017/test",
}

# Configurar env antes de importar app
with patch.dict(os.environ, _TEST_ENV, clear=False):
    if "app.config" in sys.modules:
        del sys.modules["app.config"]
    if "app.database" in sys.modules:
        del sys.modules["app.database"]
    if "app.s3_service" in sys.modules:
        del sys.modules["app.s3_service"]
    if "app.router" in sys.modules:
        del sys.modules["app.router"]

    from main import app
    import app.database as database_module
    import app.router as router_module


class InMemoryDB:
    """Simula operações MongoDB em memória para testes de integração."""

    def __init__(self):
        self.storage: list[dict] = []

    async def inserir(self, entity):
        """Simula inserção no MongoDB."""
        doc = entity.para_mongodb()
        doc["_id"] = ObjectId()
        self.storage.append(doc)
        return str(doc["_id"])

    async def listar(self, categoria=None):
        """Simula listagem com filtro opcional."""
        if categoria is None:
            return list(self.storage)
        return [
            doc for doc in self.storage
            if doc.get("categoria") == categoria.value
        ]

    async def buscar_por_id(self, arquivo_id: str):
        """Simula busca por ID."""
        try:
            oid = ObjectId(arquivo_id)
        except Exception:
            raise HTTPException(status_code=400, detail=f"ID inválido: {arquivo_id}")
        for doc in self.storage:
            if doc["_id"] == oid:
                return doc
        return None


@pytest.fixture
def in_memory_db():
    """Cria instância do banco em memória."""
    return InMemoryDB()


@pytest.fixture
def s3_mock():
    """Cria bucket S3 mockado via moto."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="test-bucket")
        yield client


@pytest_asyncio.fixture
async def client(s3_mock, in_memory_db):
    """httpx AsyncClient com S3 mockado (moto) e DB em memória.

    Patcha as funções de database diretamente no módulo router (onde são
    importadas via 'from app.database import ...') para evitar problemas
    com o Motor client e event loop.
    """
    with patch("app.s3_service.get_s3_client", return_value=s3_mock):
        with patch.object(
            router_module, "inserir_arquivo", side_effect=in_memory_db.inserir
        ):
            with patch.object(
                router_module, "listar_arquivos", side_effect=in_memory_db.listar
            ):
                with patch.object(
                    router_module, "buscar_arquivo_por_id", side_effect=in_memory_db.buscar_por_id
                ):
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as ac:
                        yield ac


class TestUploadCompletoIntegration:
    """Fluxo completo: upload válido → 201 com campos corretos.

    Validates: Requirements 9.2, 9.3
    """

    @pytest.mark.asyncio
    async def test_upload_valido_retorna_201_com_campos_corretos(self, client):
        """POST /upload/ com arquivo válido retorna 201 com nome_original,
        caminho_s3, categoria e tamanho_bytes."""
        file_content = b"conteudo de imagem jpeg fake" * 100
        files = {"file": ("foto_teste.jpg", io.BytesIO(file_content), "image/jpeg")}
        data = {"categoria": "fotos"}

        response = await client.post("/upload/", files=files, data=data)

        assert response.status_code == 201
        body = response.json()
        assert body["nome_original"] == "foto_teste.jpg"
        assert body["caminho_s3"] == "fotos/foto_teste.jpg"
        assert body["categoria"] == "fotos"
        assert body["tamanho_bytes"] == len(file_content)


class TestUploadDownloadIntegration:
    """Fluxo: upload → obter ID → download → url_download presente.

    Validates: Requirements 9.3, 11.5
    """

    @pytest.mark.asyncio
    async def test_upload_e_download_retorna_url_download(
        self, s3_mock, in_memory_db
    ):
        """Upload de arquivo seguido de download retorna url_download."""
        with patch("app.s3_service.get_s3_client", return_value=s3_mock):
            with patch.object(
                router_module, "inserir_arquivo", side_effect=in_memory_db.inserir
            ):
                with patch.object(
                    router_module, "listar_arquivos", side_effect=in_memory_db.listar
                ):
                    with patch.object(
                        router_module, "buscar_arquivo_por_id", side_effect=in_memory_db.buscar_por_id
                    ):
                        transport = ASGITransport(app=app)
                        async with AsyncClient(
                            transport=transport, base_url="http://test"
                        ) as ac:
                            # 1. Upload
                            file_content = b"pdf content for testing" * 50
                            files = {
                                "file": (
                                    "documento.pdf",
                                    io.BytesIO(file_content),
                                    "application/pdf",
                                )
                            }
                            data = {"categoria": "documentos"}

                            upload_response = await ac.post(
                                "/upload/", files=files, data=data
                            )
                            assert upload_response.status_code == 201

                            # 2. Obter ID do documento inserido
                            assert len(in_memory_db.storage) == 1
                            arquivo_id = str(in_memory_db.storage[0]["_id"])

                            # 3. Download
                            download_response = await ac.get(
                                f"/arquivos/{arquivo_id}/download"
                            )

                            assert download_response.status_code == 200
                            body = download_response.json()
                            assert "url_download" in body
                            assert body["url_download"].startswith("https://")


class TestListagemFiltradaIntegration:
    """Fluxo: upload múltiplos → listar por categoria → apenas matching.

    Validates: Requirements 10.4
    """

    @pytest.mark.asyncio
    async def test_listagem_filtrada_retorna_apenas_categoria_especificada(
        self, s3_mock, in_memory_db
    ):
        """Upload de arquivos em categorias diferentes, listagem filtrada
        retorna apenas os da categoria solicitada."""
        with patch("app.s3_service.get_s3_client", return_value=s3_mock):
            with patch.object(
                router_module, "inserir_arquivo", side_effect=in_memory_db.inserir
            ):
                with patch.object(
                    router_module, "listar_arquivos", side_effect=in_memory_db.listar
                ):
                    with patch.object(
                        router_module, "buscar_arquivo_por_id", side_effect=in_memory_db.buscar_por_id
                    ):
                        transport = ASGITransport(app=app)
                        async with AsyncClient(
                            transport=transport, base_url="http://test"
                        ) as ac:
                            # 1. Upload foto
                            files_foto = {
                                "file": (
                                    "foto1.jpg",
                                    io.BytesIO(b"jpeg data" * 100),
                                    "image/jpeg",
                                )
                            }
                            resp1 = await ac.post(
                                "/upload/",
                                files=files_foto,
                                data={"categoria": "fotos"},
                            )
                            assert resp1.status_code == 201

                            # 2. Upload documento
                            files_doc = {
                                "file": (
                                    "doc1.pdf",
                                    io.BytesIO(b"pdf data" * 100),
                                    "application/pdf",
                                )
                            }
                            resp2 = await ac.post(
                                "/upload/",
                                files=files_doc,
                                data={"categoria": "documentos"},
                            )
                            assert resp2.status_code == 201

                            # 3. Upload outra foto
                            files_foto2 = {
                                "file": (
                                    "foto2.png",
                                    io.BytesIO(b"png data" * 100),
                                    "image/png",
                                )
                            }
                            resp3 = await ac.post(
                                "/upload/",
                                files=files_foto2,
                                data={"categoria": "fotos"},
                            )
                            assert resp3.status_code == 201

                            # 4. Listar apenas fotos
                            list_response = await ac.get(
                                "/arquivos/?categoria=fotos"
                            )

                            assert list_response.status_code == 200
                            body = list_response.json()
                            assert body["total"] == 2
                            nomes = [a["nome"] for a in body["arquivos"]]
                            assert "foto1.jpg" in nomes
                            assert "foto2.png" in nomes
                            assert "doc1.pdf" not in nomes


class TestFalhaParcialIntegration:
    """Fluxo: S3 OK + DB falha → 500 com mensagem de inconsistência.

    Validates: Requirements 9.7
    """

    @pytest.mark.asyncio
    async def test_s3_ok_db_falha_retorna_500_com_mensagem_inconsistencia(
        self, s3_mock
    ):
        """Quando S3 upload sucede mas DB insertion falha, retorna 500
        com mensagem indicando inconsistência."""

        async def mock_inserir_falha(entity):
            raise HTTPException(
                status_code=500,
                detail="Erro de banco de dados ao inserir arquivo: connection timeout",
            )

        with patch("app.s3_service.get_s3_client", return_value=s3_mock):
            with patch.object(
                router_module, "inserir_arquivo", side_effect=mock_inserir_falha
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as ac:
                    file_content = b"imagem valida para upload" * 100
                    files = {
                        "file": (
                            "foto_inconsistente.jpg",
                            io.BytesIO(file_content),
                            "image/jpeg",
                        )
                    }
                    data = {"categoria": "fotos"}

                    response = await ac.post("/upload/", files=files, data=data)

                    assert response.status_code == 500
                    body = response.json()
                    assert (
                        "Arquivo enviado ao S3 mas falha ao registrar metadados"
                        in body["detail"]
                    )
