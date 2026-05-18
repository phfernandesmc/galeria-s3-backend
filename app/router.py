"""Router Module - Endpoints HTTP da API.

Orquestra chamadas aos módulos de Validator, S3 Service e Database,
delegando lógica de negócio aos módulos especializados.

Importa de: app.validators, app.s3_service, app.database, app.models.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.database import buscar_arquivo_por_id, inserir_arquivo, listar_arquivos
from app.models import ArquivoEntity, CategoriaEnum
from app.s3_service import gerar_presigned_url, upload_arquivo
from app.validators import validar_content_type, validar_tamanho

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload/", status_code=201, tags=["Galeria"])
async def upload_arquivo_endpoint(
    categoria: Annotated[CategoriaEnum, Form(description="Categoria do arquivo: fotos, planilhas, documentos, outros")],
    file: Annotated[UploadFile, File(description="Arquivo para upload")],
):
    """Recebe um arquivo e uma categoria, valida, envia ao S3 e registra metadados.

    Fluxo: validação Content-Type → validação tamanho → upload S3 →
    criação ArquivoEntity → inserção DB → retorno 201.
    """
    # 1. Validar Content-Type contra a categoria
    validar_content_type(file.content_type, categoria)

    # 2. Validar tamanho do arquivo
    tamanho_bytes = await validar_tamanho(file)

    # 3. Upload para S3
    caminho_s3 = f"{categoria.value}/{file.filename}"
    upload_arquivo(file.file, caminho_s3)

    # 4. Criar entidade e inserir no banco
    entity = ArquivoEntity(
        nome_original=file.filename,
        caminho_s3=caminho_s3,
        categoria=categoria,
        tamanho_bytes=tamanho_bytes,
        data_upload=datetime.now(timezone.utc),
    )

    try:
        await inserir_arquivo(entity)
    except HTTPException as e:
        logger.error(
            "Arquivo enviado ao S3 mas falha ao registrar metadados: %s",
            str(e.detail),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Arquivo enviado ao S3 mas falha ao registrar metadados: {e.detail}",
        )

    # 5. Retorno de sucesso
    return {
        "nome_original": entity.nome_original,
        "caminho_s3": entity.caminho_s3,
        "categoria": entity.categoria.value,
        "tamanho_bytes": entity.tamanho_bytes,
    }


@router.get("/arquivos/", tags=["Galeria"])
async def listar_arquivos_endpoint(
    categoria: Annotated[CategoriaEnum | None, Query(description="Filtrar por categoria")] = None,
    nome: Annotated[str | None, Query(description="Busca parcial por nome do arquivo")] = None,
    ordenar_por: Annotated[str | None, Query(description="Campo para ordenação: nome, data, tamanho")] = None,
    ordem: Annotated[str, Query(description="Direção da ordenação: asc ou desc")] = "desc",
):
    """Lista metadados de arquivos com filtros opcionais.

    Retorna total e array de objetos com id, nome, data e tamanho.
    Não gera Pre-signed URLs na listagem.
    """
    documentos = await listar_arquivos(categoria, nome, ordenar_por, ordem)

    arquivos = [
        {
            "id": str(doc["_id"]),
            "nome": doc["nome_original"],
            "data": doc["data_upload"],
            "tamanho": doc["tamanho_bytes"],
        }
        for doc in documentos
    ]

    return {
        "total": len(arquivos),
        "arquivos": arquivos,
    }


@router.get("/arquivos/{arquivo_id}/download", tags=["Galeria"])
async def download_arquivo_endpoint(arquivo_id: str):
    """Gera uma URL temporária para download de um arquivo específico.

    Busca metadados no banco, gera Pre-signed URL sob demanda e retorna.
    """
    # 1. Buscar documento no banco
    documento = await buscar_arquivo_por_id(arquivo_id)

    if documento is None:
        raise HTTPException(
            status_code=404,
            detail="Arquivo não encontrado",
        )

    # 2. Gerar Pre-signed URL
    caminho_s3 = documento["caminho_s3"]
    url_download = gerar_presigned_url(caminho_s3)

    return {"url_download": url_download}
