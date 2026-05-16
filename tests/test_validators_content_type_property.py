"""
Property-Based Test: Content-Type validation correctness.

Feature: cloud-gallery-microservice, Property 2: Content-Type validation correctness

Validates: Requirements 3.1, 3.2, 3.3, 3.4

Usa Hypothesis para gerar pares (MIME type aleatório, CategoriaEnum),
verificando determinismo: blocked → 400, allowed → aceito, outros → 400.
Também verifica case-insensitivity e stripping de parâmetros de media-type.
"""

import pytest
from hypothesis import given, settings as hyp_settings, assume
from hypothesis import strategies as st
from fastapi import HTTPException

from app.models import CategoriaEnum
from app.validators import (
    BLOCKED_CONTENT_TYPES,
    CONTENT_TYPE_MAP,
    validar_content_type,
)

# --- Strategies ---

# Gera um CategoriaEnum aleatório
categoria_strategy = st.sampled_from(list(CategoriaEnum))

# Todos os MIME types permitidos (união de todas as categorias, excluindo OUTROS que é derivado)
ALL_ALLOWED_TYPES: set[str] = set()
for cat in CategoriaEnum:
    ALL_ALLOWED_TYPES |= CONTENT_TYPE_MAP[cat]

# Gera MIME types aleatórios no formato "type/subtype"
random_mime_type = st.from_regex(
    r"[a-z]{1,20}/[a-z0-9\-\.\+]{1,40}", fullmatch=True
)

# Gera MIME types que não estão em nenhuma whitelist nem na blocklist
unrecognized_mime_type = random_mime_type.filter(
    lambda m: m not in ALL_ALLOWED_TYPES and m not in BLOCKED_CONTENT_TYPES
)


# --- Property Tests ---


class TestContentTypeValidationCorrectness:
    """Property 2: Content-Type validation correctness."""

    @given(
        blocked_type=st.sampled_from(sorted(BLOCKED_CONTENT_TYPES)),
        categoria=categoria_strategy,
    )
    @hyp_settings(max_examples=100)
    def test_blocked_types_always_rejected_with_400(self, blocked_type, categoria):
        """
        Para qualquer MIME type na lista de bloqueados e qualquer categoria,
        validar_content_type deve levantar HTTPException 400.

        **Validates: Requirements 3.3**
        """
        with pytest.raises(HTTPException) as exc_info:
            validar_content_type(blocked_type, categoria)
        assert exc_info.value.status_code == 400

    @given(categoria=categoria_strategy)
    @hyp_settings(max_examples=100)
    def test_allowed_types_accepted_for_matching_category(self, categoria):
        """
        Para qualquer categoria e qualquer MIME type na whitelist dessa categoria,
        validar_content_type não deve levantar exceção.

        **Validates: Requirements 3.2**
        """
        allowed = CONTENT_TYPE_MAP[categoria]
        for mime_type in allowed:
            # Não deve levantar exceção
            validar_content_type(mime_type, categoria)

    @given(
        mime_type=unrecognized_mime_type,
        categoria=categoria_strategy,
    )
    @hyp_settings(max_examples=100)
    def test_unrecognized_types_rejected_with_400(self, mime_type, categoria):
        """
        Para qualquer MIME type que não está na whitelist da categoria
        e não está na blocklist, validar_content_type deve levantar HTTPException 400.

        **Validates: Requirements 3.4**
        """
        assume(mime_type not in CONTENT_TYPE_MAP[categoria])

        with pytest.raises(HTTPException) as exc_info:
            validar_content_type(mime_type, categoria)
        assert exc_info.value.status_code == 400

    @given(
        blocked_type=st.sampled_from(sorted(BLOCKED_CONTENT_TYPES)),
        categoria=categoria_strategy,
        case_transform=st.sampled_from(["upper", "title", "mixed"]),
    )
    @hyp_settings(max_examples=100)
    def test_case_insensitive_blocked_types(
        self, blocked_type, categoria, case_transform
    ):
        """
        A validação deve ser case-insensitive: variações de caixa de MIME types
        bloqueados devem ser igualmente rejeitadas com 400.

        **Validates: Requirements 3.1**
        """
        if case_transform == "upper":
            transformed = blocked_type.upper()
        elif case_transform == "title":
            transformed = blocked_type.title()
        else:
            # Mixed case: alterna maiúsculas/minúsculas
            transformed = "".join(
                c.upper() if i % 2 == 0 else c.lower()
                for i, c in enumerate(blocked_type)
            )

        with pytest.raises(HTTPException) as exc_info:
            validar_content_type(transformed, categoria)
        assert exc_info.value.status_code == 400

    @given(categoria=categoria_strategy)
    @hyp_settings(max_examples=100)
    def test_case_insensitive_allowed_types(self, categoria):
        """
        A validação deve ser case-insensitive: variações de caixa de MIME types
        permitidos devem ser igualmente aceitas.

        **Validates: Requirements 3.1**
        """
        allowed = CONTENT_TYPE_MAP[categoria]
        for mime_type in allowed:
            # Uppercase deve ser aceito
            validar_content_type(mime_type.upper(), categoria)
            # Title case deve ser aceito
            validar_content_type(mime_type.title(), categoria)

    @given(
        categoria=categoria_strategy,
        params=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "S"),
                blacklist_characters=";",
            ),
            min_size=1,
            max_size=30,
        ),
    )
    @hyp_settings(max_examples=100)
    def test_parameter_stripping_allowed_types(self, categoria, params):
        """
        Parâmetros de media-type (após ";") devem ser ignorados na validação.
        Ex: "image/jpeg; charset=utf-8" deve ser tratado como "image/jpeg".

        **Validates: Requirements 3.1**
        """
        allowed = CONTENT_TYPE_MAP[categoria]
        for mime_type in allowed:
            # Adiciona parâmetros após ";"
            with_params = f"{mime_type}; {params}"
            validar_content_type(with_params, categoria)

    @given(
        blocked_type=st.sampled_from(sorted(BLOCKED_CONTENT_TYPES)),
        categoria=categoria_strategy,
        params=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "S"),
                blacklist_characters=";",
            ),
            min_size=1,
            max_size=30,
        ),
    )
    @hyp_settings(max_examples=100)
    def test_parameter_stripping_blocked_types(
        self, blocked_type, categoria, params
    ):
        """
        Parâmetros de media-type não devem impedir a detecção de tipos bloqueados.
        Ex: "application/x-executable; charset=utf-8" deve ser rejeitado.

        **Validates: Requirements 3.1, 3.3**
        """
        with_params = f"{blocked_type}; {params}"
        with pytest.raises(HTTPException) as exc_info:
            validar_content_type(with_params, categoria)
        assert exc_info.value.status_code == 400
