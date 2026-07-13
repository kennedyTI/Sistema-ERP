-- ---------------------------------------------------------------------
-- TITULOS FINANCEIROS - SE2
-- ---------------------------------------------------------------------

WITH nfs(filial, documento_nf, serie_nf, fornecedor, loja_fornecedor) AS (
    SELECT * FROM (VALUES {values}) AS v(filial, documento_nf, serie_nf, fornecedor, loja_fornecedor)
)
SELECT
    E2_FILIAL  = SE2.E2_FILIAL,
    E2_PREFIXO = SE2.E2_PREFIXO,
    E2_NUM     = SE2.E2_NUM,
    E2_PARCELA = SE2.E2_PARCELA,
    E2_TIPO    = SE2.E2_TIPO,
    E2_FORNECE = SE2.E2_FORNECE,
    E2_LOJA    = SE2.E2_LOJA,
    E2_EMISSAO = SE2.E2_EMISSAO,
    E2_VENCTO  = SE2.E2_VENCTO,
    E2_VENCREA = SE2.E2_VENCREA,
    E2_VALOR   = SE2.E2_VALOR,
    E2_SALDO   = SE2.E2_SALDO,
    E2_BAIXA   = SE2.E2_BAIXA
FROM dbo.vwSE2010 SE2 WITH (NOLOCK)
INNER JOIN nfs NF
    ON RTRIM(LTRIM(SE2.E2_FILIAL))  = NF.filial
   AND RTRIM(LTRIM(SE2.E2_NUM))     = NF.documento_nf
   AND RTRIM(LTRIM(SE2.E2_PREFIXO)) = NF.serie_nf
   AND RTRIM(LTRIM(SE2.E2_FORNECE)) = NF.fornecedor
   AND RTRIM(LTRIM(SE2.E2_LOJA))    = NF.loja_fornecedor
WHERE SE2.D_E_L_E_T_ = ' ';
