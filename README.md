# galeria-s3-backend
🚀 API assíncrona desenvolvida em Python (FastAPI) integrada ao Amazon S3 para armazenamento seguro e categorização de arquivos (fotos, documentos, etc.) utilizando URLs pré-assinadas (Pre-signed URLs).

# 📂 Cloud File Gallery - Backend API

Esta é uma API REST assíncrona desenvolvida para gerenciar e organizar uploads de arquivos na nuvem, categorizando-os dinamicamente. O projeto demonstra a integração prática com serviços de infraestrutura da **AWS (Amazon S3)**, aplicando conceitos de segurança e gerenciamento de acessos (IAM).

## 🚀 Tecnologias Utilizadas
*   **Python 3.11+**
*   **FastAPI:** Framework web moderno e de alta performance.
*   **Boto3:** SDK oficial da AWS para Python.
*   **Uvicorn:** Servidor ASGI para rodar a aplicação.

## 🔒 Arquitetura e Segurança (AWS S3)
*   **Bucket Privado:** O bucket S3 é configurado como 100% privado. Nenhum arquivo fica exposto publicamente na internet.
*   **Pre-signed URLs:** Para permitir a visualização segura dos arquivos no Frontend, a API gera links temporários criptografados que expiram automaticamente em 10 minutos.
*   **Princípio do Menor Privilégio:** A autenticação é feita via credenciais do IAM limitadas exclusivamente à política `AmazonS3FullAccess`.

## 🛠️ Como Executar o Projeto

1. **Clone o repositório:**
   ```bash
   git clone [https://github.com/seu-usuario/galeria-s3-backend.git](https://github.com/seu-usuario/galeria-s3-backend.git)
   cd galeria-s3-backend

2. **Configure o ambiente virtual:**
    ```bash
    python -m venv venv
    source venv/Scripts/activate  # No Windows (Git Bash): source venv/Scripts/activate
    pip install -r requirements.txt

3. **Configuração das Variáveis de Ambiente:**
   Crie as variáveis de ambiente no seu sistema operacional (ou configure um arquivo `.env` localmente **sem** commitá-lo):
   ```env
   AWS_ACCESS_KEY_ID=sua_chave_aqui
   AWS_SECRET_ACCESS_KEY=seu_secret_aqui
   AWS_REGION=us-east-1

4. **Inicie o servidor:**

uvicorn main:app --reload

   A API estará disponível em `http://127.0.0.1:8000`.

## 📌 Endpoints Principais
A documentação interativa (Swagger) pode ser acessada em `http://127.0.0.1:8000/docs`.

*   `POST /upload/` - Realiza o upload de um arquivo passando a `categoria` (Form) e o arquivo binário.
*   `GET /arquivos/{categoria}` - Lista todos os arquivos salvos em uma categoria específi
