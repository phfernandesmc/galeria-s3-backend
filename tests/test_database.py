"""
Unit Tests: Database Module - Operações CRUD assíncronas no MongoDB.

Testa as funções do módulo app/database.py usando mocks do Motor async client.
Valida inserção, busca por ID, listagem com filtro e tratamento de erros.

Validates: Requirements 8.2, 8.5, 8.7
"""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import ServerSelectionTimeoutError

from app.models import ArquivoEntity, CategoriaEnum

# Garante que app.config pode ser importado sem sys.exit
_TEST_ENV = {
    "AWS_ACCESS_KEY_ID": "test-key",
    "AWS_SECRET_ACCESS_KEY": "test-secret",
    "AWS_REGION": "us-east-1",
    "AWS_BUCKET_NAME": "test-bucket",
    "MONGODB_URI": "mongodb://localhost:27017/test",
}

# Importa o módulo com env válido (sem deletar do cache para evitar conflitos
# com outros test files que também importam app.database)
with patch.dict(os.environ, _TEST_ENV, clear=False):
    if "app.config" not in sys.modules:
        import app.config  # noqa: F401
    if "app.database" not in sys.modules:
        import app.database  # noqa: F401


@pytest.fixture
def arquivo_entity():
    """Cria uma instância válida de ArquivoEntity para testes."""
    return ArquivoEntity(
        nome_original="foto_teste.jpg",
        caminho_s3="fotos/foto_teste.jpg",
        categoria=CategoriaEnum.FOTOS,
        tamanho_bytes=245760,
        data_upload=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def mock_collection():
    """Cria um mock da collection Motor com métodos async."""
    collection = MagicMock()
    collection.insert_one = AsyncMock()
    collection.find_one = AsyncMock()
    collection.find = MagicMock()
    return collection


class TestInserirArquivo:
    """Testes para a função inserir_arquivo."""

    @pytest.mark.asyncio
    async def test_inserir_arquivo_retorna_id_string(
        self, arquivo_entity, mock_collection
    ):
        """
        Insert retorna string do inserted_id gerado pelo MongoDB.

        **Validates: Requirements 8.2**
        """
        fake_id = ObjectId()
        mock_result = MagicMock()
        mock_result.inserted_id = fake_id
        mock_collection.insert_one.return_value = mock_result

        with patch("app.database.get_collection", return_value=mock_collection):
            import app.database
            result = await app.database.inserir_arquivo(arquivo_entity)

        assert isinstance(result, str)
        assert result == str(fake_id)

    @pytest.mark.asyncio
    async def test_inserir_arquivo_chama_insert_one_com_documento(
        self, arquivo_entity, mock_collection
    ):
        """
        Insert passa o documento serializado via para_mongodb() ao MongoDB.

        **Validates: Requirements 8.2**
        """
        fake_id = ObjectId()
        mock_result = MagicMock()
        mock_result.inserted_id = fake_id
        mock_collection.insert_one.return_value = mock_result

        with patch("app.database.get_collection", return_value=mock_collection):
            import app.database
            await app.database.inserir_arquivo(arquivo_entity)

        mock_collection.insert_one.assert_called_once_with(
            arquivo_entity.para_mongodb()
        )

    @pytest.mark.asyncio
    async def test_inserir_arquivo_erro_pymongo_levanta_http_500(
        self, arquivo_entity, mock_collection
    ):
        """
        Erro de conexão/operação PyMongo resulta em HTTPException 500
        com detalhes do erro Motor/PyMongo na mensagem.

        **Validates: Requirements 8.7**
        """
        error_msg = "connection timeout to cluster0.mongodb.net:27017"
        mock_collection.insert_one.side_effect = ServerSelectionTimeoutError(
            error_msg
        )

        with patch("app.database.get_collection", return_value=mock_collection):
            import app.database
            with pytest.raises(HTTPException) as exc_info:
                await app.database.inserir_arquivo(arquivo_entity)

        assert exc_info.value.status_code == 500
        assert "Erro de banco de dados ao inserir arquivo" in exc_info.value.detail
        assert error_msg in exc_info.value.detail


class TestBuscarArquivoPorId:
    """Testes para a função buscar_arquivo_por_id."""

    @pytest.mark.asyncio
    async def test_buscar_arquivo_id_inexistente_retorna_none(self, mock_collection):
        """
        Busca com ID válido mas inexistente no banco retorna None.

        **Validates: Requirements 8.5**
        """
        mock_collection.find_one.return_value = None
        valid_id = str(ObjectId())

        with patch("app.database.get_collection", return_value=mock_collection):
            import app.database
            result = await app.database.buscar_arquivo_por_id(valid_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_buscar_arquivo_id_existente_retorna_documento(
        self, mock_collection
    ):
        """
        Busca com ID existente retorna o documento correspondente.

        **Validates: Requirements 8.5**
        """
        fake_id = ObjectId()
        documento = {
            "_id": fake_id,
            "nome_original": "planilha.xlsx",
            "caminho_s3": "planilhas/planilha.xlsx",
            "categoria": "planilhas",
            "tamanho_bytes": 102400,
            "data_upload": "2024-02-10T14:00:00+00:00",
        }
        mock_collection.find_one.return_value = documento

        with patch("app.database.get_collection", return_value=mock_collection):
            import app.database
            result = await app.database.buscar_arquivo_por_id(str(fake_id))

        assert result == documento

    @pytest.mark.asyncio
    async def test_buscar_arquivo_id_invalido_levanta_http_400(self, mock_collection):
        """
        ID com formato inválido (não é ObjectId) resulta em HTTPException 400.

        **Validates: Requirements 8.5**
        """
        with patch("app.database.get_collection", return_value=mock_collection):
            import app.database
            with pytest.raises(HTTPException) as exc_info:
                await app.database.buscar_arquivo_por_id("id-invalido-xyz")

        assert exc_info.value.status_code == 400
        assert "ID de arquivo inválido" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_buscar_arquivo_erro_pymongo_levanta_http_500(self, mock_collection):
        """
        Erro de conexão/operação PyMongo na busca resulta em HTTPException 500
        com detalhes do erro Motor/PyMongo.

        **Validates: Requirements 8.7**
        """
        error_msg = "connection closed by remote host"
        mock_collection.find_one.side_effect = ServerSelectionTimeoutError(error_msg)
        valid_id = str(ObjectId())

        with patch("app.database.get_collection", return_value=mock_collection):
            import app.database
            with pytest.raises(HTTPException) as exc_info:
                await app.database.buscar_arquivo_por_id(valid_id)

        assert exc_info.value.status_code == 500
        assert "Erro de banco de dados ao buscar arquivo" in exc_info.value.detail
        assert error_msg in exc_info.value.detail


class TestListarArquivos:
    """Testes para a função listar_arquivos."""

    @pytest.mark.asyncio
    async def test_listar_com_filtro_categoria_retorna_apenas_matching(
        self, mock_collection
    ):
        """
        Listagem com filtro de categoria retorna apenas documentos
        que correspondem à categoria especificada.

        **Validates: Requirements 8.2**
        """
        documentos_fotos = [
            {
                "_id": ObjectId(),
                "nome_original": "foto1.jpg",
                "caminho_s3": "fotos/foto1.jpg",
                "categoria": "fotos",
                "tamanho_bytes": 100000,
                "data_upload": "2024-01-15T10:00:00+00:00",
            },
            {
                "_id": ObjectId(),
                "nome_original": "foto2.png",
                "caminho_s3": "fotos/foto2.png",
                "categoria": "fotos",
                "tamanho_bytes": 200000,
                "data_upload": "2024-01-16T11:00:00+00:00",
            },
        ]

        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=documentos_fotos)
        mock_collection.find.return_value = mock_cursor

        with patch("app.database.get_collection", return_value=mock_collection):
            import app.database
            result = await app.database.listar_arquivos(categoria=CategoriaEnum.FOTOS)

        # Verifica que o filtro correto foi passado
        mock_collection.find.assert_called_once_with({"categoria": "fotos"})
        assert result == documentos_fotos
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_listar_sem_filtro_retorna_todos(self, mock_collection):
        """
        Listagem sem filtro de categoria retorna todos os documentos.

        **Validates: Requirements 8.2**
        """
        todos_documentos = [
            {
                "_id": ObjectId(),
                "nome_original": "foto.jpg",
                "categoria": "fotos",
            },
            {
                "_id": ObjectId(),
                "nome_original": "planilha.csv",
                "categoria": "planilhas",
            },
        ]

        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=todos_documentos)
        mock_collection.find.return_value = mock_cursor

        with patch("app.database.get_collection", return_value=mock_collection):
            import app.database
            result = await app.database.listar_arquivos(categoria=None)

        mock_collection.find.assert_called_once_with({})
        assert result == todos_documentos

    @pytest.mark.asyncio
    async def test_listar_erro_pymongo_levanta_http_500(self, mock_collection):
        """
        Erro de conexão/operação PyMongo na listagem resulta em HTTPException 500
        com detalhes do erro Motor/PyMongo.

        **Validates: Requirements 8.7**
        """
        error_msg = "cursor not found on server, cursor id: 12345"
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(
            side_effect=ServerSelectionTimeoutError(error_msg)
        )
        mock_collection.find.return_value = mock_cursor

        with patch("app.database.get_collection", return_value=mock_collection):
            import app.database
            with pytest.raises(HTTPException) as exc_info:
                await app.database.listar_arquivos()

        assert exc_info.value.status_code == 500
        assert "Erro de banco de dados ao listar arquivos" in exc_info.value.detail
        assert error_msg in exc_info.value.detail
