"""Transforma os pedidos do banco nas 24 variáveis que o modelo usa.

A lógica é a mesma do notebook 02_features.ipynb do projeto olist-avaliacao-negativa,
para que o modelo receba as informações exatamente como no treino.
"""
import pandas as pd

CATEGORICAS = ["categoria", "estado_vendedor", "estado_cliente", "forma_pagamento"]
NUMERICAS = ["dias_entrega", "dias_prometidos", "dias_atraso", "atrasado", "horas_aprovacao",
             "dias_ate_transportadora", "mes_compra", "dia_semana_compra",
             "n_itens", "n_produtos", "n_vendedores", "valor_total", "frete_total", "frete_sobre_valor",
             "peso_total_g", "fotos_media", "tam_descricao_media", "n_parcelas", "n_formas_pagamento",
             "mesmo_estado"]


def calcular_variaveis(pedidos):
    """Recebe as linhas da tabela pedidos e devolve um DataFrame com as variáveis do modelo."""
    p = pedidos.copy()
    for c in ["data_compra", "data_aprovacao", "data_envio", "data_prometida", "data_entrega"]:
        p[c] = pd.to_datetime(p[c])
    for c in ["valor_produtos", "valor_frete", "n_itens", "n_produtos", "n_vendedores", "n_parcelas",
              "n_formas_pagamento", "peso_g", "fotos_media", "tam_descricao_media"]:
        p[c] = pd.to_numeric(p[c].astype(float), errors="coerce")  # NUMERIC do banco vem como Decimal

    v = pd.DataFrame(index=p.index)
    # Tempos e prazos (tudo conhecido até a entrega)
    v["dias_entrega"] = (p["data_entrega"] - p["data_compra"]).dt.days
    v["dias_prometidos"] = (p["data_prometida"] - p["data_compra"]).dt.days
    v["dias_atraso"] = (p["data_entrega"] - p["data_prometida"]).dt.days
    v["atrasado"] = (v["dias_atraso"] > 0).astype(int)
    v["horas_aprovacao"] = (p["data_aprovacao"] - p["data_compra"]).dt.total_seconds() / 3600
    v["dias_ate_transportadora"] = (p["data_envio"] - p["data_compra"]).dt.days
    # Calendário da compra
    v["mes_compra"] = p["data_compra"].dt.month
    v["dia_semana_compra"] = p["data_compra"].dt.dayofweek
    # Pedido
    v["n_itens"] = p["n_itens"]
    v["n_produtos"] = p["n_produtos"]
    v["n_vendedores"] = p["n_vendedores"]
    v["valor_total"] = p["valor_produtos"]
    v["frete_total"] = p["valor_frete"]
    v["frete_sobre_valor"] = p["valor_frete"] / p["valor_produtos"]
    v["peso_total_g"] = p["peso_g"]
    v["fotos_media"] = p["fotos_media"]
    v["tam_descricao_media"] = p["tam_descricao_media"]
    # Pagamento
    v["n_parcelas"] = p["n_parcelas"]
    v["n_formas_pagamento"] = p["n_formas_pagamento"]
    # Categorias e localização
    v["categoria"] = p["categoria"]
    v["estado_vendedor"] = p["uf_vendedor"].str.strip()
    v["estado_cliente"] = p["uf_cliente"].str.strip()
    v["forma_pagamento"] = p["forma_pagamento"]
    v["mesmo_estado"] = (v["estado_cliente"] == v["estado_vendedor"]).astype(int)
    for c in CATEGORICAS:  # texto, com vazio como NaN (igual ao treino)
        v[c] = v[c].astype(object).where(v[c].notna(), float("nan"))
    return v


def motivo_e_acao(linha):
    """Explica em linguagem simples por que o pedido tem risco e o que o atendimento deve fazer."""
    motivos, acoes = [], []
    atraso = linha["dias_atraso"]
    if pd.notna(atraso) and atraso > 0:
        motivos.append(f"Entregue com {int(atraso)} dia(s) de atraso")
        acoes.append("pedir desculpas pelo atraso e oferecer um cupom")
    if pd.notna(linha["n_vendedores"]) and linha["n_vendedores"] >= 2:
        motivos.append(f"{int(linha['n_vendedores'])} vendedores: pode ter chegado só parte do pedido")
        acoes.append("confirmar se o cliente recebeu todos os itens")
    elif pd.notna(linha["n_itens"]) and linha["n_itens"] >= 3:
        motivos.append(f"Pedido com {int(linha['n_itens'])} itens")
        acoes.append("confirmar se todos os itens chegaram em ordem")
    if not motivos:
        motivos.append("Combinação de fatores (prazo, frete, produto)")
        acoes.append("verificar se está satisfeito com a compra")
    return " | ".join(motivos), "Contatar o cliente: " + "; ".join(acoes)
