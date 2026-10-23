-- =====================================================================
-- Monitoramento de risco de avaliação negativa
-- Script 01: cria as tabelas do banco "risco_pedidos"
-- Rode no Query Tool do pgAdmin, conectado ao banco risco_pedidos.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) PEDIDOS: o que o sistema da loja registra (uma linha por pedido).
--    O pedido entra no banco na compra, com data_entrega vazia,
--    e é atualizado quando é entregue.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedidos (
    pedido_id            TEXT PRIMARY KEY,
    cliente_id           TEXT,
    data_compra          TIMESTAMP NOT NULL,
    data_aprovacao       TIMESTAMP,
    data_envio           TIMESTAMP,          -- entrega à transportadora
    data_prometida       TIMESTAMP NOT NULL, -- prazo informado ao cliente
    data_entrega         TIMESTAMP,          -- fica vazia até o pedido ser entregue
    valor_produtos       NUMERIC(10, 2),
    valor_frete          NUMERIC(10, 2),
    n_itens              INTEGER,
    n_produtos           INTEGER,
    n_vendedores         INTEGER,
    uf_cliente           CHAR(2),
    uf_vendedor          CHAR(2),
    forma_pagamento      TEXT,
    n_parcelas           INTEGER,
    n_formas_pagamento   INTEGER,
    categoria            TEXT,
    peso_g               NUMERIC,
    fotos_media          NUMERIC,
    tam_descricao_media  NUMERIC,
    inserido_em          TIMESTAMP NOT NULL DEFAULT now(),
    atualizado_em        TIMESTAMP NOT NULL DEFAULT now()
);

-- Acelera a busca por pedidos entregues
CREATE INDEX IF NOT EXISTS idx_pedidos_data_entrega ON pedidos (data_entrega);

-- ---------------------------------------------------------------------
-- 2) RISCO_PEDIDOS: o resultado do modelo (uma linha por pedido avaliado).
--    É aqui que o atendimento e o Power BI vão buscar quem contatar.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS risco_pedidos (
    pedido_id      TEXT PRIMARY KEY REFERENCES pedidos (pedido_id),
    risco          NUMERIC(4, 3) NOT NULL,   -- de 0 a 1
    nivel          TEXT NOT NULL CHECK (nivel IN ('ALTO', 'MÉDIO', 'BAIXO')),
    motivo         TEXT,
    acao_sugerida  TEXT,
    versao_modelo  TEXT NOT NULL,
    calculado_em   TIMESTAMP NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 3) AVALIACOES: a nota que o cliente deu, quando ela chega.
--    Permite conferir, ao longo do tempo, se os alertas acertaram.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS avaliacoes (
    pedido_id       TEXT PRIMARY KEY REFERENCES pedidos (pedido_id),
    nota            INTEGER NOT NULL CHECK (nota BETWEEN 1 AND 5),
    data_avaliacao  TIMESTAMP NOT NULL
);

-- ---------------------------------------------------------------------
-- 4) EXECUCOES: registro de cada vez que o processo de previsão rodou.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS execucoes (
    execucao_id         SERIAL PRIMARY KEY,
    inicio              TIMESTAMP NOT NULL DEFAULT now(),
    fim                 TIMESTAMP,
    pedidos_avaliados   INTEGER,
    alertas             INTEGER,
    status              TEXT,      -- 'sucesso' ou 'erro'
    mensagem            TEXT
);
