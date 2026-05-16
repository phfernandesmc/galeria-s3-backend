"""Models Module - Domain entities and enumerations.

Este módulo define os tipos de domínio compartilhados pela aplicação:
CategoriaEnum para classificação de arquivos e ArquivoEntity para
representação de metadados de arquivo.

Não importa de nenhum módulo interno (app/*).
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class CategoriaEnum(str, Enum):
    """Enumeração de categorias de arquivo.

    Herda de str para ser usável diretamente como string value
    em path construction e database queries.
    """

    FOTOS = "fotos"
    PLANILHAS = "planilhas"
    DOCUMENTOS = "documentos"
    OUTROS = "outros"


class ArquivoEntity(BaseModel):
    """Entidade representando metadados de um arquivo no sistema.

    Campos validados com constraints Pydantic V2 para garantir
    integridade de dados em todas as camadas.
    """

    nome_original: str = Field(..., min_length=1, max_length=255)
    caminho_s3: str = Field(..., min_length=1, max_length=512)
    categoria: CategoriaEnum
    tamanho_bytes: int = Field(..., ge=1, le=10_485_760)
    data_upload: datetime

    def para_mongodb(self) -> dict:
        """Converte a entidade para um dicionário compatível com MongoDB.

        - data_upload é convertido para string ISO 8601
        - categoria é convertido para seu valor string
        """
        return {
            "nome_original": self.nome_original,
            "caminho_s3": self.caminho_s3,
            "categoria": self.categoria.value,
            "tamanho_bytes": self.tamanho_bytes,
            "data_upload": self.data_upload.isoformat(),
        }

    @classmethod
    def from_mongodb(cls, doc: dict) -> "ArquivoEntity":
        """Reconstrói uma instância de ArquivoEntity a partir de um dicionário MongoDB.

        Espera que data_upload seja uma string ISO 8601 e categoria seja
        o valor string do enum.
        """
        return cls(
            nome_original=doc["nome_original"],
            caminho_s3=doc["caminho_s3"],
            categoria=CategoriaEnum(doc["categoria"]),
            tamanho_bytes=doc["tamanho_bytes"],
            data_upload=datetime.fromisoformat(doc["data_upload"]),
        )
