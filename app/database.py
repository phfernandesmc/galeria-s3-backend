"""
Database Module - Operações CRUD assíncronas no MongoDB Atlas.

Utiliza Motor (async driver) para operações não-bloqueantes no event loop
do FastAPI. Conecta ao database "galeria", collection "arquivos".

Importa apenas de app.config e app.models (Clean Architecture).
"""

import logging

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from pymongo.errors import PyMongoError

from app.config import settings
from app.models import ArquivoEntity, CategoriaEnum

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None


def _get_client() -> AsyncIOMotorClient:
    """Retorna o cliente Motor, criando-o na primeira chamada (lazy init).

    Isso evita problemas com event loop em testes quando o módulo é
    importado antes do loop asyncio estar configurado.
    """
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=5000,
        )
    return _client


def get_collection() -> AsyncIOMotorCollection:
    """Retorna a collection 'arquivos' do database 'galeria'.

    Utiliza o cliente Motor configurado com serverSelectionTimeoutMS=5000.
    """
    client = _get_client()
    db = client["galeria"]
    return db["arquivos"]


async def inserir_arquivo(entity: ArquivoEntity) -> str:
    """Insere metadados de arquivo no MongoDB.

    Args:
        entity: ArquivoEntity com os metadados do arquivo.

    Returns:
        String do inserted_id gerado pelo MongoDB.

    Raises:
        HTTPException: 500 se ocorrer erro de conexão ou operação.
    """
    try:
        collection = get_collection()
        documento = entity.para_mongodb()
        result = await collection.insert_one(documento)
        return str(result.inserted_id)
    except PyMongoError as e:
        logger.error("Erro ao inserir arquivo no MongoDB: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Erro de banco de dados ao inserir arquivo.",
        )


async def listar_arquivos(
    categoria: CategoriaEnum | None = None,
    nome: str | None = None,
    ordenar_por: str | None = None,
    ordem: str = "desc",
) -> list[dict]:
    """Lista metadados de arquivos com filtros opcionais.

    Args:
        categoria: Se fornecido, filtra documentos pela categoria especificada.
        nome: Se fornecido, busca parcial (case-insensitive) no nome do arquivo.
        ordenar_por: Campo para ordenação: "nome", "data" ou "tamanho".
        ordem: Direção da ordenação: "asc" ou "desc".

    Returns:
        Lista de dicionários com os documentos encontrados.

    Raises:
        HTTPException: 500 se ocorrer erro de conexão ou operação.
    """
    try:
        collection = get_collection()
        filtro: dict = {}
        if categoria is not None:
            filtro["categoria"] = categoria.value
        if nome:
            filtro["nome_original"] = {"$regex": nome, "$options": "i"}

        # Mapeamento de campos para ordenação
        campo_map = {
            "nome": "nome_original",
            "data": "data_upload",
            "tamanho": "tamanho_bytes",
        }
        sort_field = campo_map.get(ordenar_por, "data_upload") if ordenar_por else "data_upload"
        sort_direction = 1 if ordem == "asc" else -1

        cursor = collection.find(filtro).sort(sort_field, sort_direction)
        documentos = await cursor.to_list(length=None)
        return documentos
    except PyMongoError as e:
        logger.error("Erro ao listar arquivos no MongoDB: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Erro de banco de dados ao listar arquivos.",
        )


async def buscar_arquivo_por_id(arquivo_id: str) -> dict | None:
    """Busca metadados de um arquivo pelo seu ID MongoDB.

    Args:
        arquivo_id: String representando o ObjectId do documento.

    Returns:
        Dicionário com o documento encontrado ou None se não existir.

    Raises:
        HTTPException: 400 se o arquivo_id não for um ObjectId válido.
        HTTPException: 500 se ocorrer erro de conexão ou operação.
    """
    try:
        oid = ObjectId(arquivo_id)
    except (InvalidId, Exception):
        raise HTTPException(
            status_code=400,
            detail="ID de arquivo inválido.",
        )

    try:
        collection = get_collection()
        documento = await collection.find_one({"_id": oid})
        return documento
    except PyMongoError as e:
        logger.error(
            "Erro ao buscar arquivo por ID no MongoDB: %s - %s", arquivo_id, str(e)
        )
        raise HTTPException(
            status_code=500,
            detail="Erro de banco de dados ao buscar arquivo.",
        )
