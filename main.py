"""Application Entry Point - Composição da aplicação FastAPI.

Inicializa a aplicação, configura CORS e inclui rotas do Router_Module.
Importa settings do Config_Module para trigger fail-fast na validação
de variáveis de ambiente antes de aceitar tráfego.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.router import router

app = FastAPI(
    title="Cloud Gallery API",
    description="API para gerenciamento e categorização de arquivos utilizando Amazon S3 de forma segura.",
    version="1.0.0",
)

# Origens permitidas via variável de ambiente CORS_ORIGINS (separadas por vírgula).
# allow_credentials=False pois a API não usa cookies/sessão — apenas dados públicos
# de origem controlada. Isso evita a combinação inválida de "*" com credenciais.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/galeria")


@app.get("/", tags=["Health Check"])
async def health_check():
    """Endpoint simples para verificar se a API está online."""
    return {"status": "ok"}
