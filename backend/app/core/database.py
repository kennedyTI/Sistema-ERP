"""
Arquivo: backend/app/database/connection.py

Descrição:
Responsável por toda a configuração de conexão com o banco de dados PostgreSQL.

Este módulo centraliza:
- Carregamento de variáveis de ambiente (.env)
- Criação do engine SQLAlchemy
- Gerenciamento de sessões de banco (SessionLocal)
- Base declarativa dos models
- Dependency injection do FastAPI (get_db)

Responsabilidades:
- Garantir conexão estável com PostgreSQL
- Evitar falhas de encoding no ambiente Windows
- Fornecer sessão segura para transações no banco
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


# ---------------------------------------------------------------------
# 📌 LOCALIZAÇÃO DO ARQUIVO .ENV
# ---------------------------------------------------------------------
# O .env está localizado na raiz do backend.
# Usamos Path para garantir compatibilidade entre Windows/Linux/Mac.

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BACKEND_DIR / ".env"


# ---------------------------------------------------------------------
# 📌 CARREGAMENTO DAS VARIÁVEIS DE AMBIENTE
# ---------------------------------------------------------------------
# Só carrega se o arquivo existir para evitar crashes em produção.

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
# Em containers/produção, as variáveis podem vir diretamente do ambiente.
# Portanto, a ausência do arquivo .env não deve impedir o bootstrap.


# ---------------------------------------------------------------------
# 📌 URL DO BANCO DE DADOS
# ---------------------------------------------------------------------
# Variável obrigatória para conexão com PostgreSQL.
# Exemplo:
# postgresql://postgres:postgres@localhost:5432/portal_industria_db

DATABASE_URL = os.getenv("DATABASE_URL")
OPERATIONS_SCHEMA = os.getenv("DB_OPERATIONS_SCHEMA", "portal_industria")
FASTAPI_SEARCH_PATH = os.getenv(
    "FASTAPI_SEARCH_PATH",
    f"{OPERATIONS_SCHEMA},public",
)
APP_TIME_ZONE = os.getenv("TIME_ZONE", os.getenv("TZ", "America/Sao_Paulo"))

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL não encontrada. Configure a variável de ambiente ou o arquivo .env."
    )


# ---------------------------------------------------------------------
# 📌 ENGINE SQLALCHEMY
# ---------------------------------------------------------------------
# Configuração de conexão com PostgreSQL.
# pool_pre_ping evita conexões mortas.
# client_encoding garante compatibilidade UTF-8.

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={
        "options": (
            f"-c client_encoding=utf8 "
            f"-c search_path={FASTAPI_SEARCH_PATH} "
            f"-c timezone={APP_TIME_ZONE}"
        )
    },
)


# ---------------------------------------------------------------------
# 📌 SESSION FACTORY
# ---------------------------------------------------------------------
# Cria sessões isoladas para transações no banco.
# Cada request do FastAPI deve usar uma sessão independente.

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ---------------------------------------------------------------------
# 📌 BASE DECLARATIVA DOS MODELS
# ---------------------------------------------------------------------
# Todos os models do SQLAlchemy devem herdar desta Base.

Base = declarative_base()


# ---------------------------------------------------------------------
# 📌 DEPENDÊNCIA DO FASTAPI
# ---------------------------------------------------------------------
# Responsável por abrir e fechar conexão automaticamente.
# Evita vazamento de conexões no banco.

def get_db():
    """
    Fornece uma sessão de banco de dados para uso nas rotas.

    Fluxo:
    1. Cria sessão
    2. Injeta no endpoint
    3. Fecha automaticamente após uso

    Retorno:
        Session SQLAlchemy ativa
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
