-- ---------------------------------------------------------------------
-- DESCRICAO DOS LOCAIS - NNR
-- ---------------------------------------------------------------------

WITH locais(codigo) AS (
    SELECT * FROM (VALUES {values}) AS v(codigo)
)
SELECT
    NNR_FILIAL = NNR.NNR_FILIAL,
    NNR_CODIGO = NNR.NNR_CODIGO,
    NNR_DESCRI = NNR.NNR_DESCRI
FROM dbo.vwNNR010 NNR WITH (NOLOCK)
INNER JOIN locais L
    ON RTRIM(LTRIM(NNR.NNR_CODIGO)) = L.codigo
WHERE RTRIM(LTRIM(ISNULL(NNR.D_E_L_E_T_, ''))) = '';
