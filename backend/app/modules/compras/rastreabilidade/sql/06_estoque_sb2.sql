-- ---------------------------------------------------------------------
-- SALDO DE ESTOQUE - SB2
-- ---------------------------------------------------------------------

WITH chaves(filial, produto, local) AS (
    SELECT * FROM (VALUES {values}) AS v(filial, produto, local)
)
SELECT
    B2_FILIAL  = SB2.B2_FILIAL,
    B2_COD     = SB2.B2_COD,
    B2_LOCAL   = SB2.B2_LOCAL,
    B2_QATU    = SB2.B2_QATU,
    B2_RESERVA = SB2.B2_RESERVA,
    B2_QEMP    = SB2.B2_QEMP,
    B2_QPEDVEN = SB2.B2_QPEDVEN,
    B2_QACLASS = SB2.B2_QACLASS
FROM dbo.vwSB2010 SB2 WITH (NOLOCK)
INNER JOIN chaves C
    ON RTRIM(LTRIM(SB2.B2_FILIAL)) = C.filial
   AND RTRIM(LTRIM(SB2.B2_COD))    = C.produto
   AND RTRIM(LTRIM(SB2.B2_LOCAL))  = C.local
WHERE SB2.D_E_L_E_T_ = ' ';
