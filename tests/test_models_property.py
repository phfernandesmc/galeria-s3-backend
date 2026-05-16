"""Property-based tests for ArquivoEntity serialization round-trip.

Feature: cloud-gallery-microservice, Property 4: ArquivoEntity serialization round-trip

Validates: Requirements 7.2, 7.3, 7.4, 7.5
"""

from datetime import datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models import ArquivoEntity, CategoriaEnum

# Strategies for generating valid ArquivoEntity fields
nome_original_st = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=255,
)

caminho_s3_st = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=512,
)

categoria_st = st.sampled_from(list(CategoriaEnum))

tamanho_bytes_st = st.integers(min_value=1, max_value=10_485_760)

data_upload_st = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2100, 1, 1),
)

arquivo_entity_st = st.builds(
    ArquivoEntity,
    nome_original=nome_original_st,
    caminho_s3=caminho_s3_st,
    categoria=categoria_st,
    tamanho_bytes=tamanho_bytes_st,
    data_upload=data_upload_st,
)


class TestArquivoEntityRoundTrip:
    """Property 4: ArquivoEntity serialization round-trip.

    For any valid ArquivoEntity instance, calling
    from_mongodb(entity.para_mongodb()) SHALL produce a new instance
    where every field value equals the corresponding field value
    of the original instance.

    **Validates: Requirements 7.2, 7.3, 7.4, 7.5**
    """

    @given(entity=arquivo_entity_st)
    @settings(max_examples=100)
    def test_round_trip_preserves_all_fields(self, entity: ArquivoEntity) -> None:
        """from_mongodb(para_mongodb()) produces equal entity."""
        doc = entity.para_mongodb()
        reconstructed = ArquivoEntity.from_mongodb(doc)

        assert reconstructed.nome_original == entity.nome_original
        assert reconstructed.caminho_s3 == entity.caminho_s3
        assert reconstructed.categoria == entity.categoria
        assert reconstructed.tamanho_bytes == entity.tamanho_bytes
        assert reconstructed.data_upload == entity.data_upload

    @given(entity=arquivo_entity_st)
    @settings(max_examples=100)
    def test_round_trip_produces_equal_instance(self, entity: ArquivoEntity) -> None:
        """from_mongodb(para_mongodb()) produces instance equal to original."""
        doc = entity.para_mongodb()
        reconstructed = ArquivoEntity.from_mongodb(doc)

        assert reconstructed == entity

    @given(entity=arquivo_entity_st)
    @settings(max_examples=100)
    def test_para_mongodb_returns_dict_with_expected_keys(
        self, entity: ArquivoEntity
    ) -> None:
        """para_mongodb() returns dict with all expected keys."""
        doc = entity.para_mongodb()

        assert set(doc.keys()) == {
            "nome_original",
            "caminho_s3",
            "categoria",
            "tamanho_bytes",
            "data_upload",
        }

    @given(entity=arquivo_entity_st)
    @settings(max_examples=100)
    def test_para_mongodb_serializes_categoria_as_string_value(
        self, entity: ArquivoEntity
    ) -> None:
        """para_mongodb() converts categoria to its string value."""
        doc = entity.para_mongodb()

        assert doc["categoria"] == entity.categoria.value
        assert isinstance(doc["categoria"], str)

    @given(entity=arquivo_entity_st)
    @settings(max_examples=100)
    def test_para_mongodb_serializes_data_upload_as_iso8601(
        self, entity: ArquivoEntity
    ) -> None:
        """para_mongodb() converts data_upload to ISO 8601 string."""
        doc = entity.para_mongodb()

        assert isinstance(doc["data_upload"], str)
        # Verify it can be parsed back
        parsed = datetime.fromisoformat(doc["data_upload"])
        assert parsed == entity.data_upload
