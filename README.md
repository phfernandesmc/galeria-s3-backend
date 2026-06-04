# galeria-s3-backend
🚀 API assíncrona desenvolvida em Python (FastAPI) integrada ao Amazon S3 para armazenamento seguro e categorização de arquivos (fotos, documentos, etc.) utilizando URLs pré-assinadas (Pre-signed URLs).

# 📂 Cloud File Gallery - Backend API

Esta é uma API REST assíncrona desenvolvida para gerenciar e organizar uploads de arquivos na nuvem, categorizando-os dinamicamente. O projeto demonstra a integração prática com serviços de infraestrutura da **AWS (Amazon S3)**, aplicando conceitos de segurança e gerenciamento de acessos (IAM).

## 🚀 Tecnologias Utilizadas
*   **Python 3.11+**
*   **FastAPI:** Framework web moderno e de alta performance.
*   **Boto3:** SDK oficial da AWS para Python.
*   **Motor (MongoDB):** Driver assíncrono para persistência dos metadados.
*   **Uvicorn:** Servidor ASGI para rodar a aplicação.

## 🔒 Arquitetura e Segurança (AWS S3)
*   **Bucket Privado:** O bucket S3 é configurado como 100% privado. Nenhum arquivo fica exposto publicamente na internet.
*   **Pre-signed URLs:** Para permitir a visualização segura dos arquivos no Frontend, a API gera links temporários criptografados que expiram automaticamente em 10 minutos.
*   **Princípio do Menor Privilégio:** A credencial IAM utilizada deve ter permissão restrita apenas às ações necessárias (`s3:PutObject` e `s3:GetObject`) no bucket específico da aplicação — evite políticas amplas como `AmazonS3FullAccess`.
*   **CORS restrito:** As origens permitidas são configuradas via variável de ambiente `CORS_ORIGINS` (lista separada por vírgula). Por padrão (vazio), nenhuma origem de browser é permitida.
*   **Mensagens de erro sanitizadas:** Detalhes técnicos (S3/Mongo) são registrados no log do servidor, mas o cliente recebe apenas mensagens genéricas.

## 🛠️ Como Executar o Projeto

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/seu-usuario/galeria-s3-backend.git
   cd galeria-s3-backend
   ```

2. **Configure o ambiente virtual:**
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # No Windows (Git Bash)
   pip install -r requirements.txt
   ```

3. **Configuração das Variáveis de Ambiente:**
   Copie `.env.example` para `.env` e preencha (o `.env` é ignorado pelo git).
   Em produção, defina estas variáveis no painel do host de deploy:
   ```env
   AWS_ACCESS_KEY_ID=sua_chave_aqui
   AWS_SECRET_ACCESS_KEY=seu_secret_aqui
   AWS_REGION=us-east-1
   AWS_BUCKET_NAME=seu_bucket_aqui
   MONGODB_URI=mongodb+srv://...
   # Origens permitidas (separadas por vírgula, sem barra final)
   CORS_ORIGINS=https://seu-front.vercel.app,http://localhost:5173
   ```

4. **Inicie o servidor (desenvolvimento):**
   ```bash
   uvicorn main:app --reload
   ```
   A API estará disponível em `http://127.0.0.1:8000`.

5. **Execução em produção (exemplo):**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

## 🧪 Testes
```bash
pytest -q
```

## 📌 Endpoints Principais
A documentação interativa (Swagger) pode ser acessada em `http://127.0.0.1:8000/docs`.
Todas as rotas usam o prefixo `/galeria`.

*   `GET /` — Health check (`{"status": "ok"}`).
*   `POST /galeria/upload/` — Upload de um arquivo, passando `categoria` (Form) e o arquivo binário (Form `file`).
*   `GET /galeria/arquivos/` — Lista metadados de arquivos. Query params opcionais: `categoria`, `nome` (busca parcial), `ordenar_por` (`nome`|`data`|`tamanho`), `ordem` (`asc`|`desc`).
*   `GET /galeria/arquivos/{arquivo_id}/download` — Gera uma Pre-signed URL temporária para download.
