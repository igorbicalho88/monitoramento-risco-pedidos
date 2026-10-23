"""Calcula o risco de avaliação negativa dos pedidos que acabaram de ser entregues.

A cada execução:
  1. busca no banco os pedidos já entregues que ainda não têm risco calculado;
  2. calcula as variáveis e a probabilidade com o modelo treinado;
  3. grava o risco, o nível, o motivo e a ação sugerida na tabela risco_pedidos;
  4. registra a execução na tabela execucoes (e no arquivo logs/previsoes.log).

Exemplos (com o ambiente ativo, na pasta do projeto):
  python src/prever_novos.py                    roda uma vez (é assim que o agendador do Windows usa)
  python src/prever_novos.py --loop             verifica o banco a cada 60 segundos, até Ctrl+C
  python src/prever_novos.py --loop --intervalo 15

Para rodar sozinho no Windows, veja agendar_tarefa.ps1 (Agendador de Tarefas).
"""
import argparse
import logging
import sys
import time

import joblib
import pandas as pd
from sqlalchemy import text

from conexao import PASTA_PROJETO, criar_engine
from variaveis import calcular_variaveis, motivo_e_acao

ARQ_MODELO = PASTA_PROJETO / "models" / "modelo_avaliacao_negativa.joblib"
VERSAO_MODELO = "olist-avaliacao-negativa/gradient-boosting-v1"
CORTE_ALTO = 0.8
CORTE_MEDIO = 0.6

(PASTA_PROJETO / "logs").mkdir(exist_ok=True)
saidas = [logging.FileHandler(PASTA_PROJETO / "logs" / "previsoes.log", encoding="utf-8")]
if sys.stderr is not None:  # rodando pelo agendador (pythonw) não existe terminal
    saidas.append(logging.StreamHandler())
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%d/%m/%Y %H:%M:%S",
    handlers=saidas)
log = logging.getLogger("previsoes")

PENDENTES = text("""
    SELECT p.*
    FROM pedidos p
    LEFT JOIN risco_pedidos r ON r.pedido_id = p.pedido_id
    WHERE p.data_entrega IS NOT NULL
      AND r.pedido_id IS NULL
    ORDER BY p.data_entrega
""")


def nivel(prob):
    return "ALTO" if prob >= CORTE_ALTO else "MÉDIO" if prob >= CORTE_MEDIO else "BAIXO"


def executar(engine, modelo):
    """Uma execução completa. Retorna (pedidos avaliados, alertas)."""
    with engine.begin() as con:
        execucao_id = con.execute(text(
            "INSERT INTO execucoes (status) VALUES ('rodando') RETURNING execucao_id")).scalar()
    try:
        with engine.connect() as con:
            pedidos = pd.read_sql(PENDENTES, con)

        if pedidos.empty:
            avaliados, alertas = 0, 0
        else:
            variaveis = calcular_variaveis(pedidos)
            prob = modelo.predict_proba(variaveis[modelo.feature_names_in_])[:, 1]
            explicacoes = variaveis.apply(motivo_e_acao, axis=1, result_type="expand")
            resultado = pd.DataFrame({
                "pedido_id": pedidos["pedido_id"],
                "risco": prob.round(3),
                "nivel": [nivel(x) for x in prob],
                "motivo": explicacoes[0],
                "acao_sugerida": explicacoes[1],
                "versao_modelo": VERSAO_MODELO,
            })
            baixo = resultado["nivel"] == "BAIXO"
            resultado.loc[baixo, "motivo"] = "-"
            resultado.loc[baixo, "acao_sugerida"] = "Nenhuma ação necessária"

            with engine.begin() as con:
                con.execute(text(
                    "INSERT INTO risco_pedidos (pedido_id, risco, nivel, motivo, acao_sugerida, versao_modelo) "
                    "VALUES (:pedido_id, :risco, :nivel, :motivo, :acao_sugerida, :versao_modelo) "
                    "ON CONFLICT (pedido_id) DO NOTHING"),
                    [{**r, "risco": float(r["risco"])} for r in resultado.to_dict("records")])
            avaliados, alertas = len(resultado), int((resultado["nivel"] == "ALTO").sum())

        with engine.begin() as con:
            con.execute(text(
                "UPDATE execucoes SET fim = now(), pedidos_avaliados = :a, alertas = :b, status = 'sucesso' "
                "WHERE execucao_id = :id"), {"a": avaliados, "b": alertas, "id": execucao_id})
        log.info(f"Execução {execucao_id}: {avaliados} pedidos avaliados | {alertas} em alerta (risco alto)")
        return avaliados, alertas

    except Exception as erro:
        try:  # registra o erro no banco (se o banco estiver acessível)
            with engine.begin() as con:
                con.execute(text(
                    "UPDATE execucoes SET fim = now(), status = 'erro', mensagem = :m WHERE execucao_id = :id"),
                    {"m": str(erro)[:1000], "id": execucao_id})
        except Exception:
            pass
        raise


def main():
    p = argparse.ArgumentParser(description="Calcula o risco dos pedidos entregues que ainda não foram avaliados.")
    p.add_argument("--loop", action="store_true", help="continua verificando o banco até Ctrl+C")
    p.add_argument("--intervalo", type=float, default=60, help="segundos entre as verificações no modo --loop")
    a = p.parse_args()

    engine = criar_engine()
    modelo = joblib.load(ARQ_MODELO)
    try:
        while True:
            try:
                executar(engine, modelo)
            except Exception:
                # Fica registrado no log (inclusive quando o banco está fora do ar)
                log.exception("A execução falhou")
                if not a.loop:
                    raise SystemExit(1)
            if not a.loop:
                break
            time.sleep(a.intervalo)
    except KeyboardInterrupt:
        log.info("Interrompido pelo usuário.")


if __name__ == "__main__":
    main()
