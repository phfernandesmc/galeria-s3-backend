"""
Property-Based Test: Configuration validation rejects invalid environments.

Feature: cloud-gallery-microservice, Property 1: Configuration validation rejects invalid environments

Validates: Requirements 1.2, 1.3

Usa Hypothesis para gerar subsets de variáveis ausentes/whitespace e URIs inválidas,
verificando que Settings rejeita com ValidationError em todos os casos inválidos.
"""

import os
import sys
from unittest.mock import patch

import pytest
from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st
from pydantic import ValidationError


def _get_settings_class():
    """Importa a classe Settings sem disparar o singleton module-level."""
    valid_env = {
        "AWS_ACCESS_KEY_ID": "test-key-id",
        "AWS_SECRET_ACCESS_KEY": "test-secret-key",
        "AWS_REGION": "us-east-1",
        "AWS_BUCKET_NAME": "test-bucket",
        "MONGODB_URI": "mongodb://localhost:27017/test",
    }

    module_name = "app.config"
    if module_name in sys.modules:
        from app.config import Settings

        return Settings

    # Importa com env vars válidas para evitar sys.exit(1)
    with patch.dict(os.environ, valid_env, clear=False):
        import app.config

        return app.config.Settings


Settings = _get_settings_class()

# --- Strategies ---

# Campos obrigatórios (sem default)
REQUIRED_FIELDS = [
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_BUCKET_NAME",
    "MONGODB_URI",
]

# Gera URIs inválidas que NÃO começam com "mongodb://" ou "mongodb+srv://"
# Filtra null characters pois não são válidos em variáveis de ambiente
invalid_mongodb_uri = st.text(
    alphabet=st.characters(blacklist_characters="\x00"),
    min_size=1,
    max_size=100,
).filter(
    lambda s: not s.startswith(("mongodb://", "mongodb+srv://"))
    and s.strip() != ""
)


# --- Property Test ---


class TestConfigValidationRejectsInvalid:
    """Property 1: Configuration validation rejects invalid environments."""

    @given(
        missing_fields=st.lists(
            st.sampled_from(REQUIRED_FIELDS),
            min_size=1,
            max_size=len(REQUIRED_FIELDS),
            unique=True,
        )
    )
    @hyp_settings(max_examples=100)
    def test_missing_required_fields_raises_validation_error(self, missing_fields):
        """
        Para qualquer subset não-vazio de campos obrigatórios ausentes,
        Settings deve rejeitar com ValidationError.

        **Validates: Requirements 1.2**
        """
        # Monta env com todos os campos válidos
        env = {
            "AWS_ACCESS_KEY_ID": "test-key-id",
            "AWS_SECRET_ACCESS_KEY": "test-secret-key",
            "AWS_REGION": "us-east-1",
            "AWS_BUCKET_NAME": "test-bucket",
            "MONGODB_URI": "mongodb://localhost:27017/test",
        }

        # Remove os campos selecionados
        for field in missing_fields:
            env.pop(field, None)

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError):
                Settings()

    @given(invalid_uri=invalid_mongodb_uri)
    @hyp_settings(max_examples=100)
    def test_invalid_mongodb_uri_raises_validation_error(self, invalid_uri):
        """
        Para qualquer MONGODB_URI que não começa com "mongodb://" ou "mongodb+srv://",
        Settings deve rejeitar com ValidationError.

        **Validates: Requirements 1.3**
        """
        env = {
            "AWS_ACCESS_KEY_ID": "test-key-id",
            "AWS_SECRET_ACCESS_KEY": "test-secret-key",
            "AWS_REGION": "us-east-1",
            "AWS_BUCKET_NAME": "test-bucket",
            "MONGODB_URI": invalid_uri,
        }

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError):
                Settings()

    @given(
        whitespace_value=st.text(
            alphabet=st.sampled_from([" ", "\t", "\n", "\r"]),
            min_size=1,
            max_size=10,
        )
    )
    @hyp_settings(max_examples=100)
    def test_mongodb_uri_whitespace_only_raises_validation_error(
        self, whitespace_value
    ):
        """
        Para MONGODB_URI preenchido apenas com whitespace (não-vazio),
        Settings deve rejeitar com ValidationError pois não começa com prefixo válido.

        **Validates: Requirements 1.2, 1.3**
        """
        env = {
            "AWS_ACCESS_KEY_ID": "test-key-id",
            "AWS_SECRET_ACCESS_KEY": "test-secret-key",
            "AWS_REGION": "us-east-1",
            "AWS_BUCKET_NAME": "test-bucket",
            "MONGODB_URI": whitespace_value,
        }

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError):
                Settings()
