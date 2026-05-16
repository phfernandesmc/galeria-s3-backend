"""
Config Module - Carregamento e validação de variáveis de ambiente.

Utiliza Pydantic V2 BaseSettings para configuração type-safe.
Termina o processo (exit 1) se variáveis obrigatórias estiverem
ausentes ou inválidas (fail-fast).
"""

import sys
import logging

from pydantic import field_validator, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Configurações da aplicação carregadas de variáveis de ambiente."""

    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "us-east-1"
    AWS_BUCKET_NAME: str
    MONGODB_URI: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("MONGODB_URI")
    @classmethod
    def validar_mongodb_uri(cls, v: str) -> str:
        """Valida que MONGODB_URI começa com prefixo válido."""
        if not v.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError(
                "MONGODB_URI deve começar com 'mongodb://' ou 'mongodb+srv://'"
            )
        return v


try:
    settings = Settings()  # type: ignore[call-arg]
except ValidationError as e:
    campos_com_erro = [err["loc"][0] for err in e.errors() if err.get("loc")]
    logger.error(
        "Falha na validação de configuração. Variáveis com problema: %s",
        ", ".join(str(c) for c in campos_com_erro),
    )
    for err in e.errors():
        campo = err.get("loc", ("desconhecido",))[0]
        msg = err.get("msg", "erro desconhecido")
        logger.error("  - %s: %s", campo, msg)
    sys.exit(1)
