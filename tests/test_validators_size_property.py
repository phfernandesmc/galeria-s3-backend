"""Property-based tests for file size validation correctness.

Feature: cloud-gallery-microservice, Property 3: File size validation correctness

Validates: Requirements 4.2, 4.3, 4.4
"""

import io
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, UploadFile
from hypothesis import given, settings
from hypothesis import strategies as st

from app.validators import MAX_FILE_SIZE, validar_tamanho


def create_mock_upload_file(size: int) -> UploadFile:
    """Create a mock UploadFile that simulates a file of the given size.

    Uses a real BytesIO stream so that read() and seek() behave
    like a real file, matching the chunked reading in validar_tamanho.
    """
    content = b"\x00" * size
    stream = io.BytesIO(content)
    file = UploadFile(filename="test_file.bin", file=stream)
    return file


class TestFileSizeValidation:
    """Property 3: File size validation correctness.

    For any file with size in bytes, the Validator_Module SHALL accept
    the file if and only if 1 ≤ size ≤ 10_485_760. Files with size = 0
    SHALL be rejected with 400, and files with size > 10_485_760 SHALL
    be rejected with 413.

    **Validates: Requirements 4.2, 4.3, 4.4**
    """

    @given(size=st.integers(min_value=1, max_value=MAX_FILE_SIZE))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_valid_size_returns_total_bytes(self, size: int) -> None:
        """Files with 1 ≤ size ≤ 10_485_760 are accepted and return size."""
        file = create_mock_upload_file(size)
        result = await validar_tamanho(file)
        assert result == size

    @pytest.mark.asyncio
    async def test_empty_file_raises_400(self) -> None:
        """Files with size == 0 are rejected with HTTP 400."""
        file = create_mock_upload_file(0)
        with pytest.raises(HTTPException) as exc_info:
            await validar_tamanho(file)
        assert exc_info.value.status_code == 400

    @given(
        size=st.integers(min_value=MAX_FILE_SIZE + 1, max_value=MAX_FILE_SIZE + 500_000)
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_oversized_file_raises_413(self, size: int) -> None:
        """Files with size > 10_485_760 are rejected with HTTP 413."""
        file = create_mock_upload_file(size)
        with pytest.raises(HTTPException) as exc_info:
            await validar_tamanho(file)
        assert exc_info.value.status_code == 413

    @given(size=st.just(0))
    @settings(max_examples=10)
    @pytest.mark.asyncio
    async def test_zero_size_always_raises_400(self, size: int) -> None:
        """Property: size == 0 always results in HTTP 400."""
        file = create_mock_upload_file(size)
        with pytest.raises(HTTPException) as exc_info:
            await validar_tamanho(file)
        assert exc_info.value.status_code == 400
        assert "vazios" in exc_info.value.detail.lower()

    @given(size=st.integers(min_value=1, max_value=MAX_FILE_SIZE))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_valid_size_seeks_back_to_start(self, size: int) -> None:
        """After validation, the file stream is reset to position 0."""
        file = create_mock_upload_file(size)
        await validar_tamanho(file)
        # After successful validation, stream should be at position 0
        content = await file.read()
        assert len(content) == size
