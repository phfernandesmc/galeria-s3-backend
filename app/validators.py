"""Validator Module - Content-Type and file size validation.

Este módulo implementa validação de segurança do payload antes de
qualquer operação de I/O externo. Valida Content-Type vinculado à
CategoriaEnum e tamanho máximo de arquivo.

Importa apenas de app.models (CategoriaEnum) entre módulos internos.
"""

from fastapi import HTTPException, UploadFile

from app.models import CategoriaEnum

# MIME types permitidos por categoria
CONTENT_TYPE_MAP: dict[CategoriaEnum, set[str]] = {
    CategoriaEnum.FOTOS: {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/svg+xml",
    },
    CategoriaEnum.PLANILHAS: {
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
    },
    CategoriaEnum.DOCUMENTOS: {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    },
}

# OUTROS aceita a união de todos os tipos das outras categorias
CONTENT_TYPE_MAP[CategoriaEnum.OUTROS] = (
    CONTENT_TYPE_MAP[CategoriaEnum.FOTOS]
    | CONTENT_TYPE_MAP[CategoriaEnum.PLANILHAS]
    | CONTENT_TYPE_MAP[CategoriaEnum.DOCUMENTOS]
)

# MIME types sempre rejeitados (executáveis e scripts)
BLOCKED_CONTENT_TYPES: set[str] = {
    "application/x-executable",
    "application/x-msdownload",
    "application/x-sh",
    "application/x-bat",
    "application/x-msdos-program",
    "application/javascript",
    "application/x-httpd-php",
}

# Limite máximo de tamanho de arquivo: 10 MB
MAX_FILE_SIZE: int = 10_485_760


def validar_content_type(content_type: str | None, categoria: CategoriaEnum) -> None:
    """Valida o Content-Type do arquivo contra a categoria especificada.

    Raises HTTPException 400 se:
    - content_type é None ou vazio
    - content_type está na lista de bloqueados
    - content_type não está na whitelist da categoria

    A comparação é case-insensitive e ignora parâmetros de media-type
    (ex: charset=utf-8).
    """
    if not content_type or not content_type.strip():
        raise HTTPException(
            status_code=400,
            detail="Um Content-Type válido é obrigatório",
        )

    # Normalizar: lowercase e remover parâmetros após ";"
    normalized = content_type.split(";")[0].strip().lower()

    if normalized in BLOCKED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Arquivos executáveis e scripts não são permitidos",
        )

    allowed = CONTENT_TYPE_MAP[categoria]
    if normalized not in allowed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Content-Type '{normalized}' não é permitido para a categoria "
                f"'{categoria.value}'. Tipos permitidos: {sorted(allowed)}"
            ),
        )


async def validar_tamanho(file: UploadFile) -> int:
    """Lê o stream do arquivo e valida o tamanho total.

    Retorna o total de bytes lidos.

    Raises HTTPException:
    - 400 se o arquivo está vazio (0 bytes)
    - 413 se o arquivo excede MAX_FILE_SIZE (10 MB)

    Após a leitura, faz seek(0) para permitir reutilização do stream.
    """
    total_bytes = 0
    chunk_size = 64 * 1024  # 64 KB chunks

    while chunk := await file.read(chunk_size):
        total_bytes += len(chunk)
        if total_bytes > MAX_FILE_SIZE:
            await file.seek(0)
            raise HTTPException(
                status_code=413,
                detail="Tamanho máximo permitido: 10 MB",
            )

    if total_bytes == 0:
        raise HTTPException(
            status_code=400,
            detail="Arquivos vazios não são permitidos",
        )

    await file.seek(0)
    return total_bytes
