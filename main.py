"""Application Entry Point - Composição da aplicação FastAPI.

Inicializa a aplicação, configura CORS e inclui rotas do Router_Module.
Importa settings do Config_Module para trigger fail-fast na validação
de variáveis de ambiente antes de aceitar tráfego.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings  # noqa: F401 — trigger fail-fast validation
from app.router import router

app = FastAPI(
    title="Cloud Gallery API",
    description="API para gerenciamento e categorização de arquivos utilizando Amazon S3 de forma segura.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", tags=["Health Check"])
async def health_check():
    """Endpoint simples para verificar se a API está online."""
    return {"status": "ok"}
