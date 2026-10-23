"""Simula a operação de uma loja: vai gravando no banco os pedidos, as entregas
e as avaliações, na ordem em que aconteceram de verdade.

Usa pedidos reais da Olist a partir de 27/05/2018 (o período de teste do projeto
olist-avaliacao-negativa, que o modelo nunca viu). Um "relógio simulado" avança
algumas horas a cada passo:
  - pedidos comprados até o relógio entram na tabela pedidos (sem data de entrega);
  - pedidos entregues até o relógio ganham a data de entrega;
  - avaliações respondidas até o relógio entram na tabela avaliacoes.

Exemplos (com o ambiente ativo, na pasta do projeto):
  python src/simulador.py                      avança 1 dia
  python src/simulador.py --horas 6            avança 6 horas
  python src/simulador.py --loop               avança 1 dia a cada 10 segundos, até o fim
  python src/simulador.py --loop --intervalo 30 --horas 12
  python src/simulador.py --reiniciar          apaga tudo e volta ao início
"""
import argparse
import json
import time

import numpy as np
import pandas as pd
from sqlalchemy import text

from conexao import PASTA_PROJETO, criar_engine

PASTA_OLIST = PASTA_PROJETO / "data" / "olist"
ARQ_PEDIDOS = PASTA_PROJETO / "data" / "pedidos_simulacao.csv"
ARQ_AVALIACOES = PASTA_PROJETO / "data" / "avaliacoes_simulacao.csv"
ARQ_ESTADO = PASTA_PROJETO / "data" / "estado_simulador.json"
INICIO = pd.Timestamp("2018-05-27 11:41:00")  # início do período de teste do projeto 1

DATAS = ["data_compra", "data_aprovacao", "data_envio", "data_prometida", "data_entrega"]


# ---------------------------------------------------------------------------
# Preparação: transforma as tabelas da Olist em "pedidos da loja"
# ---------------------------------------------------------------------------
def preparar_dados():
    if ARQ_PEDIDOS.exists() and ARQ_AVALIACOES.exists():
        return
    print("Preparando os dados da Olist (só na primeira vez)...")
    ler = lambda nome: pd.read_csv(PASTA_OLIST / f"olist_{nome}_dataset.csv")
    pedidos, itens, produtos = ler("orders"), ler("order_items"), ler("products")
    vendedores, pagamentos, clientes = ler("sellers"), ler("order_payments"), ler("customers")
    avaliacoes = ler("order_reviews")

    for c in ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
              "order_estimated_delivery_date", "order_delivered_customer_date"]:
        pedidos[c] = pd.to_datetime(pedidos[c])
    pedidos = pedidos[pedidos["order_purchase_timestamp"] >= INICIO]

    det = itens.merge(produtos, on="product_id", how="left").merge(vendedores, on="seller_id", how="left")
    por_pedido = det.groupby("order_id").agg(
        valor_produtos=("price", "sum"), valor_frete=("freight_value", "sum"),
        n_itens=("order_item_id", "count"), n_produtos=("product_id", "nunique"),
        n_vendedores=("seller_id", "nunique"), uf_vendedor=("seller_state", "first"),
        categoria=("product_category_name", "first"), peso_g=("product_weight_g", "sum"),
        fotos_media=("product_photos_qty", "mean"),
        tam_descricao_media=("product_description_lenght", "mean")).reset_index()
    pag = pagamentos.groupby("order_id").agg(
        n_parcelas=("payment_installments", "max"), n_formas_pagamento=("payment_type", "nunique"),
        forma_pagamento=("payment_type", "first")).reset_index()

    base = (pedidos.merge(por_pedido, on="order_id", how="left")
                   .merge(pag, on="order_id", how="left")
                   .merge(clientes[["customer_id", "customer_state"]], on="customer_id", how="left"))
    loja = pd.DataFrame({
        "pedido_id": base["order_id"],
        "cliente_id": base["customer_id"],
        "data_compra": base["order_purchase_timestamp"],
        "data_aprovacao": base["order_approved_at"],
        "data_envio": base["order_delivered_carrier_date"],
        "data_prometida": base["order_estimated_delivery_date"],
        "data_entrega": base["order_delivered_customer_date"],
        "valor_produtos": base["valor_produtos"].round(2),
        "valor_frete": base["valor_frete"].round(2),
        "n_itens": base["n_itens"], "n_produtos": base["n_produtos"], "n_vendedores": base["n_vendedores"],
        "uf_cliente": base["customer_state"], "uf_vendedor": base["uf_vendedor"],
        "forma_pagamento": base["forma_pagamento"], "n_parcelas": base["n_parcelas"],
        "n_formas_pagamento": base["n_formas_pagamento"], "categoria": base["categoria"],
        "peso_g": base["peso_g"], "fotos_media": base["fotos_media"],
        "tam_descricao_media": base["tam_descricao_media"],
    }).sort_values("data_compra")
    # Um pedido sem prazo prometido não existe num sistema de loja: fica de fora
    loja = loja[loja["data_prometida"].notna()]
    loja.to_csv(ARQ_PEDIDOS, index=False)

    # Uma avaliação por pedido (a mais recente), como no projeto 1
    avaliacoes["review_answer_timestamp"] = pd.to_datetime(avaliacoes["review_answer_timestamp"])
    aval = (avaliacoes[avaliacoes["order_id"].isin(loja["pedido_id"])]
            .sort_values("review_answer_timestamp").drop_duplicates("order_id", keep="last"))
    pd.DataFrame({"pedido_id": aval["order_id"], "nota": aval["review_score"],
                  "data_avaliacao": aval["review_answer_timestamp"]}).to_csv(ARQ_AVALIACOES, index=False)
    print(f"Pronto: {len(loja)} pedidos e {len(aval)} avaliações para simular.")


def carregar_dados():
    preparar_dados()
    pedidos = pd.read_csv(ARQ_PEDIDOS, parse_dates=DATAS)
    avaliacoes = pd.read_csv(ARQ_AVALIACOES, parse_dates=["data_avaliacao"])
    return pedidos, avaliacoes


# ---------------------------------------------------------------------------
# Relógio simulado
# ---------------------------------------------------------------------------
def ler_relogio():
    try:
        return pd.Timestamp(json.loads(ARQ_ESTADO.read_text())["relogio"])
    except (OSError, ValueError, KeyError):
        return INICIO


def salvar_relogio(relogio):
    ARQ_ESTADO.write_text(json.dumps({"relogio": relogio.isoformat()}))


def sem_nan(valor):
    """Converte NaN/NaT em None (NULL no banco) e números do numpy em números do Python."""
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return None
    if isinstance(valor, pd.Timestamp):
        return valor.to_pydatetime()
    if isinstance(valor, np.generic):
        return valor.item()
    return valor


# ---------------------------------------------------------------------------
# Um passo da simulação
# ---------------------------------------------------------------------------
def passo(engine, pedidos, avaliacoes, antes, agora):
    """Grava no banco tudo o que aconteceu entre `antes` e `agora`."""
    # Datas que ainda não aconteceram ficam vazias
    visivel = pedidos.copy()
    for c in ["data_aprovacao", "data_envio", "data_entrega"]:
        visivel.loc[visivel[c] > agora, c] = pd.NaT

    novos = visivel[(visivel["data_compra"] > antes) & (visivel["data_compra"] <= agora)]
    eventos = pd.Series(False, index=pedidos.index)
    for c in ["data_aprovacao", "data_envio", "data_entrega"]:
        eventos |= (pedidos[c] > antes) & (pedidos[c] <= agora)
    atualizados = visivel[(visivel["data_compra"] <= antes) & eventos]
    entregues = int(((pedidos["data_entrega"] > antes) & (pedidos["data_entrega"] <= agora)).sum())
    aval = avaliacoes[(avaliacoes["data_avaliacao"] > antes) & (avaliacoes["data_avaliacao"] <= agora)]

    colunas = list(pedidos.columns)
    with engine.begin() as con:
        if len(novos):
            con.execute(
                text(f"INSERT INTO pedidos ({', '.join(colunas)}) VALUES ({', '.join(':' + c for c in colunas)}) "
                     "ON CONFLICT (pedido_id) DO NOTHING"),
                [{c: sem_nan(v) for c, v in linha.items()} for linha in novos[colunas].to_dict("records")])
        if len(atualizados):
            con.execute(
                text("UPDATE pedidos SET data_aprovacao = :data_aprovacao, data_envio = :data_envio, "
                     "data_entrega = :data_entrega, atualizado_em = now() WHERE pedido_id = :pedido_id"),
                [{c: sem_nan(linha[c]) for c in ["pedido_id", "data_aprovacao", "data_envio", "data_entrega"]}
                 for linha in atualizados.to_dict("records")])
        if len(aval):
            con.execute(
                text("INSERT INTO avaliacoes (pedido_id, nota, data_avaliacao) "
                     "SELECT :pedido_id, :nota, :data_avaliacao "
                     "WHERE EXISTS (SELECT 1 FROM pedidos WHERE pedido_id = :pedido_id) "
                     "ON CONFLICT (pedido_id) DO NOTHING"),
                [{c: sem_nan(v) for c, v in linha.items()} for linha in aval.to_dict("records")])
    return len(novos), entregues, len(aval)


def reiniciar(engine):
    with engine.begin() as con:
        con.execute(text("TRUNCATE risco_pedidos, avaliacoes, execucoes, pedidos RESTART IDENTITY"))
    salvar_relogio(INICIO)
    print("Simulação reiniciada: tabelas vazias e relógio em", INICIO.strftime("%d/%m/%Y %H:%M"))


def main():
    p = argparse.ArgumentParser(description="Simula a operação de uma loja gravando pedidos no banco.")
    p.add_argument("--horas", type=float, default=24, help="quantas horas o relógio avança a cada passo")
    p.add_argument("--loop", action="store_true", help="continua avançando até o fim dos dados")
    p.add_argument("--intervalo", type=float, default=10, help="segundos entre os passos no modo --loop")
    p.add_argument("--reiniciar", action="store_true", help="apaga os dados do banco e volta ao início")
    a = p.parse_args()

    engine = criar_engine()
    if a.reiniciar:
        reiniciar(engine)
        return

    pedidos, avaliacoes = carregar_dados()
    fim = max(pedidos[DATAS].max().max(), avaliacoes["data_avaliacao"].max())
    relogio = ler_relogio()
    try:
        while True:
            if relogio >= fim:
                print("Fim dos dados: todos os pedidos já foram simulados. Use --reiniciar para começar de novo.")
                break
            novo = min(relogio + pd.Timedelta(hours=a.horas), fim)
            n_novos, n_entregues, n_aval = passo(engine, pedidos, avaliacoes, relogio, novo)
            salvar_relogio(novo)
            print(f"Relógio: {novo:%d/%m/%Y %H:%M} | {n_novos} pedidos novos | "
                  f"{n_entregues} entregues | {n_aval} avaliações")
            relogio = novo
            if not a.loop:
                break
            time.sleep(a.intervalo)
    except KeyboardInterrupt:
        print("\nSimulação pausada. Rode de novo para continuar de onde parou.")


if __name__ == "__main__":
    main()
