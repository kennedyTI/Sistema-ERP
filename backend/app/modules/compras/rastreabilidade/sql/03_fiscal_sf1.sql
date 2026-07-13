-- ---------------------------------------------------------------------
-- LANCAMENTO FISCAL - SF1
-- ---------------------------------------------------------------------

WITH nfs(filial, documento_nf, serie_nf, fornecedor, loja_fornecedor) AS (
    SELECT * FROM (VALUES {values}) AS v(filial, documento_nf, serie_nf, fornecedor, loja_fornecedor)
)
SELECT
    F1_FILIAL  = SF1.F1_FILIAL,
    F1_DOC     = SF1.F1_DOC,
    F1_SERIE   = SF1.F1_SERIE,
    F1_FORNECE = SF1.F1_FORNECE,
    F1_LOJA    = SF1.F1_LOJA,
    F1_EMISSAO = SF1.F1_EMISSAO,
    F1_DTDIGIT = SF1.F1_DTDIGIT,
    F1_DTLANC  = SF1.F1_DTLANC,
    F1_STATUS  = SF1.F1_STATUS,
    F1_CHVNFE  = SF1.F1_CHVNFE
FROM dbo.vwSF1010 SF1 WITH (NOLOCK)
INNER JOIN nfs NF
    ON RTRIM(LTRIM(SF1.F1_FILIAL))  = NF.filial
   AND RTRIM(LTRIM(SF1.F1_DOC))     = NF.documento_nf
   AND RTRIM(LTRIM(SF1.F1_SERIE))   = NF.serie_nf
   AND RTRIM(LTRIM(SF1.F1_FORNECE)) = NF.fornecedor
   AND RTRIM(LTRIM(SF1.F1_LOJA))    = NF.loja_fornecedor
WHERE SF1.D_E_L_E_T_ = ' ';
