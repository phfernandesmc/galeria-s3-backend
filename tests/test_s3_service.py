"""
Unit tests for S3 Service (app/s3_service.py).

Usa moto para mockar AWS S3 e testa:
- upload_arquivo retorna caminho correto (Req 5.2)
- Erros incluem key S3 + mensagem AWS original (Req 5.4, 6.4)
- gerar_presigned_url usa 600s de expiração e operação get_object (Req 6.2)
"""

import io
import os
import sys
from unittest.mock import patch, MagicMock

import boto3
import pytest
from moto import mock_aws


# Garantir que app.config pode ser importado sem sys.exit(1)
# Patchamos o ambiente ANTES de qualquer import de app.*
_VALID_ENV = {
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_REGION": "us-east-1",
    "AWS_BUCKET_NAME": "test-bucket",
    "MONGODB_URI": "mongodb://localhost:27017/test",
}


def _import_s3_service():
    """Importa s3_service com env vars válidas para evitar sys.exit(1) do config."""
    module_name = "app.s3_service"
    if module_name in sys.modules:
        import app.s3_service
        return app.s3_service

    with patch.dict(os.environ, _VALID_ENV, clear=True):
        # Remover app.config do cache se existir com estado inválido
        if "app.config" in sys.modules:
            del sys.modules["app.config"]
        import app.s3_service
        return app.s3_service


s3_service = _import_s3_service()
upload_arquivo = s3_service.upload_arquivo
gerar_presigned_url = s3_service.gerar_presigned_url
get_s3_client = s3_service.get_s3_client


@pytest.fixture
def s3_mock():
    """Cria bucket S3 mockado via moto e patcha get_s3_client."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="test-bucket")
        with patch("app.s3_service.get_s3_client", return_value=client):
            yield client


class TestUploadArquivo:
    """Testes para upload_arquivo."""

    def test_upload_retorna_caminho_correto(self, s3_mock):
        """Upload bem-sucedido retorna o caminho_s3 fornecido. (Req 5.2)"""
        file_stream = io.BytesIO(b"conteudo do arquivo")
        caminho_s3 = "fotos/minha_foto.jpg"

        resultado = upload_arquivo(file_stream, caminho_s3)

        assert resultado == caminho_s3

    def test_upload_retorna_caminho_com_categoria_e_nome(self, s3_mock):
        """Upload retorna caminho no formato {categoria}/{nome_original}. (Req 5.2)"""
        file_stream = io.BytesIO(b"dados planilha")
        caminho_s3 = "planilhas/relatorio.xlsx"

        resultado = upload_arquivo(file_stream, caminho_s3)

        assert resultado == "planilhas/relatorio.xlsx"

    def test_upload_erro_inclui_key_e_mensagem_aws(self):
        """Erro de upload inclui chave S3 e mensagem original AWS. (Req 5.4)"""
        from botocore.exceptions import ClientError
        from fastapi import HTTPException

        file_stream = io.BytesIO(b"dados")
        caminho_s3 = "documentos/arquivo.pdf"

        mock_client = MagicMock()
        mock_client.upload_fileobj.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "PutObject",
        )

        with patch("app.s3_service.get_s3_client", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                upload_arquivo(file_stream, caminho_s3)

            assert exc_info.value.status_code == 500
            assert caminho_s3 in exc_info.value.detail
            assert "Access Denied" in exc_info.value.detail

    def test_upload_erro_no_credentials_inclui_key(self):
        """Erro NoCredentialsError inclui chave S3 na mensagem. (Req 5.4)"""
        from botocore.exceptions import NoCredentialsError
        from fastapi import HTTPException

        file_stream = io.BytesIO(b"dados")
        caminho_s3 = "fotos/sem_credencial.png"

        mock_client = MagicMock()
        mock_client.upload_fileobj.side_effect = NoCredentialsError()

        with patch("app.s3_service.get_s3_client", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                upload_arquivo(file_stream, caminho_s3)

            assert exc_info.value.status_code == 500
            assert caminho_s3 in exc_info.value.detail


class TestGerarPresignedUrl:
    """Testes para gerar_presigned_url."""

    def test_presigned_url_usa_get_object_e_600s(self):
        """Pre-signed URL usa operação get_object com expiração de 600s. (Req 6.2)"""
        caminho_s3 = "fotos/imagem.jpg"

        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = (
            "https://test-bucket.s3.amazonaws.com/fotos/imagem.jpg?signed"
        )

        with patch("app.s3_service.get_s3_client", return_value=mock_client):
            url = gerar_presigned_url(caminho_s3)

        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={
                "Bucket": "test-bucket",
                "Key": caminho_s3,
            },
            ExpiresIn=600,
        )
        assert url == "https://test-bucket.s3.amazonaws.com/fotos/imagem.jpg?signed"

    def test_presigned_url_retorna_url_valida(self, s3_mock):
        """Pre-signed URL retorna uma URL válida com moto. (Req 6.2)"""
        s3_mock.put_object(
            Bucket="test-bucket",
            Key="documentos/doc.pdf",
            Body=b"pdf content",
        )

        url = gerar_presigned_url("documentos/doc.pdf")

        assert "documentos/doc.pdf" in url
        assert url.startswith("https://")

    def test_presigned_url_erro_inclui_key_e_mensagem(self):
        """Erro na geração de URL inclui chave S3 e mensagem AWS. (Req 6.4)"""
        from botocore.exceptions import ClientError
        from fastapi import HTTPException

        caminho_s3 = "fotos/nao_existe.jpg"

        mock_client = MagicMock()
        mock_client.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}},
            "GetObject",
        )

        with patch("app.s3_service.get_s3_client", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                gerar_presigned_url(caminho_s3)

            assert exc_info.value.status_code == 500
            assert caminho_s3 in exc_info.value.detail
            assert "The specified key does not exist" in exc_info.value.detail

    def test_presigned_url_erro_no_credentials_inclui_key(self):
        """Erro NoCredentialsError na geração de URL inclui chave S3. (Req 6.4)"""
        from botocore.exceptions import NoCredentialsError
        from fastapi import HTTPException

        caminho_s3 = "planilhas/dados.csv"

        mock_client = MagicMock()
        mock_client.generate_presigned_url.side_effect = NoCredentialsError()

        with patch("app.s3_service.get_s3_client", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                gerar_presigned_url(caminho_s3)

            assert exc_info.value.status_code == 500
            assert caminho_s3 in exc_info.value.detail
