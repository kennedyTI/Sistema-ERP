-- ---------------------------------------------------------------------
-- CADASTRO DE PRODUTOS - SB1
-- ---------------------------------------------------------------------

WITH produtos(codigo) AS (
    SELECT * FROM (VALUES {values}) AS v(codigo)
)
SELECT
    B1_FILIAL  = SB1.B1_FILIAL,
    B1_COD     = SB1.B1_COD,
    B1_DESC    = SB1.B1_DESC,
    B1_YDESCNF = SB1.B1_YDESCNF,
    B1_UM      = SB1.B1_UM,
    B1_LOCPAD  = SB1.B1_LOCPAD,
    B1_GRUPO   = SB1.B1_GRUPO
FROM dbo.vwSB1010 SB1 WITH (NOLOCK)
INNER JOIN produtos P
    ON RTRIM(LTRIM(SB1.B1_COD)) = P.codigo
WHERE SB1.D_E_L_E_T_ = ' ';
