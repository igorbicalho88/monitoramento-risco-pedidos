"""Conexão com o banco PostgreSQL, usando os dados do arquivo .env."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

PASTA_PROJETO = Path(__file__).resolve().parents[1]
load_dotenv(PASTA_PROJETO / ".env")


def criar_engine():
    """Cria a conexão com o banco. A senha vem do .env, nunca do código."""
    faltando = [v for v in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD") if not os.getenv(v)]
    if faltando:
        raise SystemExit(f"Faltam no arquivo .env: {', '.join(faltando)}")
    url = URL.create(
        "postgresql+psycopg",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
    )
    return create_engine(url)


if __name__ == "__main__":
    # Teste rápido: python src/conexao.py
    engine = criar_engine()
    with engine.connect() as con:
        versao = con.execute(text("SELECT version()")).scalar()
        tabelas = con.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name")).scalars().all()
    print("Conectado!", versao.split(",")[0])
    print("Tabelas:", ", ".join(tabelas))
