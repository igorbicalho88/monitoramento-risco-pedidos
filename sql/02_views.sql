-- =====================================================================
-- Script 02: views para o painel (Power BI) e para o atendimento
-- Rode no Query Tool do pgAdmin, conectado ao banco risco_pedidos.
-- Pode rodar de novo sempre que quiser: as views são recriadas.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Um pedido avaliado por linha, com o risco e o que aconteceu depois
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_pedidos_risco AS
SELECT
    p.pedido_id,
    p.data_compra,
    p.data_entrega,
    p.data_entrega::date                                   AS dia_entrega,
    date_trunc('week', p.data_entrega)::date               AS semana_entrega,
    (p.data_entrega::date - p.data_prometida::date)        AS dias_atraso,
    (p.data_entrega > p.data_prometida)                    AS atrasado,
    p.n_itens,
    p.n_vendedores,
    p.valor_produtos,
    p.valor_frete,
    p.uf_cliente,
    p.categoria,
    r.risco,
    r.nivel,
    r.motivo,
    r.acao_sugerida,
    r.calculado_em,
    a.nota,
    a.data_avaliacao,
    CASE WHEN a.nota IS NULL THEN NULL ELSE (a.nota <= 2) END AS avaliacao_negativa,
    CASE
        WHEN r.nivel <> 'ALTO' THEN NULL
        WHEN a.nota IS NULL    THEN 'Aguardando avaliação'
        WHEN a.nota <= 2       THEN 'Acertou (avaliação negativa)'
        ELSE                        'Alarme falso (avaliação boa)'
    END AS resultado_alerta
FROM risco_pedidos r
JOIN pedidos p          ON p.pedido_id = r.pedido_id
LEFT JOIN avaliacoes a  ON a.pedido_id = r.pedido_id;

-- ---------------------------------------------------------------------
-- 2) Fila do atendimento: alertas que ainda não receberam avaliação
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_fila_atendimento AS
SELECT pedido_id, risco, motivo, acao_sugerida, data_entrega, dias_atraso, n_itens, n_vendedores, uf_cliente
FROM vw_pedidos_risco
WHERE nivel = 'ALTO' AND nota IS NULL
ORDER BY risco DESC;

-- ---------------------------------------------------------------------
-- 3) Desempenho do modelo por semana de entrega (monitoramento)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_desempenho_semanal AS
SELECT
    semana_entrega,
    COUNT(*)                                                          AS pedidos_avaliados,
    COUNT(*) FILTER (WHERE nivel = 'ALTO')                            AS alertas,
    COUNT(*) FILTER (WHERE nivel = 'ALTO' AND nota IS NOT NULL)       AS alertas_com_avaliacao,
    COUNT(*) FILTER (WHERE nivel = 'ALTO' AND avaliacao_negativa)     AS alertas_que_acertaram,
    ROUND(100.0 * COUNT(*) FILTER (WHERE nivel = 'ALTO' AND avaliacao_negativa)
          / NULLIF(COUNT(*) FILTER (WHERE nivel = 'ALTO' AND nota IS NOT NULL), 0), 1) AS acerto_alertas_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE avaliacao_negativa)
          / NULLIF(COUNT(*) FILTER (WHERE nota IS NOT NULL), 0), 1)  AS taxa_negativas_geral_pct
FROM vw_pedidos_risco
GROUP BY semana_entrega
ORDER BY semana_entrega;
