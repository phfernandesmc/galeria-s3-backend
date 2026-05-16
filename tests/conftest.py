"""Configuração global de testes.

Define o modo asyncio e garante que cada teste async recebe
um event loop limpo, evitando conflitos com Motor/PyMongo.
"""

import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
