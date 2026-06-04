"""
S3 Service - Comunicação com AWS S3.

Responsável por upload de arquivos (streaming) e geração de
Pre-signed URLs temporárias sob demanda.
"""

from typing import BinaryIO

import logging

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)


def get_s3_client():
    """Inicializa e retorna um cliente Boto3 S3 com credenciais do Config_Module."""
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )


def upload_arquivo(file_stream: BinaryIO, caminho_s3: str) -> str:
    """
    Faz upload de um arquivo para o bucket S3 privado via streaming.

    Args:
        file_stream: Stream binário do arquivo a ser enviado.
        caminho_s3: Chave S3 no formato '{categoria}/{nome_original}'.

    Returns:
        O caminho_s3 utilizado no upload.

    Raises:
        HTTPException: 500 se ocorrer erro de comunicação com S3.
    """
    try:
        client = get_s3_client()
        client.upload_fileobj(
            file_stream,
            settings.AWS_BUCKET_NAME,
            caminho_s3,
        )
        return caminho_s3
    except ClientError as e:
        logger.error("Erro ao fazer upload para S3 (%s): %s", caminho_s3, str(e))
        raise HTTPException(
            status_code=500,
            detail="Erro ao fazer upload do arquivo.",
        )
    except NoCredentialsError as e:
        logger.error("Credenciais S3 ausentes/inválidas no upload (%s): %s", caminho_s3, str(e))
        raise HTTPException(
            status_code=500,
            detail="Erro ao fazer upload do arquivo.",
        )


def gerar_presigned_url(caminho_s3: str) -> str:
    """
    Gera uma URL temporária (Pre-signed) para download de um objeto S3.

    Args:
        caminho_s3: Chave S3 do objeto.

    Returns:
        URL pre-signed válida por 600 segundos.

    Raises:
        HTTPException: 500 se ocorrer erro na geração da URL.
    """
    try:
        client = get_s3_client()
        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.AWS_BUCKET_NAME,
                "Key": caminho_s3,
            },
            ExpiresIn=600,
        )
        return url
    except ClientError as e:
        logger.error("Erro ao gerar URL de download (%s): %s", caminho_s3, str(e))
        raise HTTPException(
            status_code=500,
            detail="Erro ao gerar URL de download.",
        )
    except NoCredentialsError as e:
        logger.error("Credenciais S3 ausentes/inválidas ao gerar URL (%s): %s", caminho_s3, str(e))
        raise HTTPException(
            status_code=500,
            detail="Erro ao gerar URL de download.",
        )
