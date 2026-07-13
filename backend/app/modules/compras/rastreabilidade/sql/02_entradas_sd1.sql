-- ---------------------------------------------------------------------
-- ENTRADAS NO ALMOXARIFADO - SD1
-- ---------------------------------------------------------------------

WITH chaves(filial, numero_pedido, item_pedido) AS (
    SELECT * FROM (VALUES {values}) AS v(filial, numero_pedido, item_pedido)
)
SELECT
    D1_FILIAL  = SD1.D1_FILIAL,
    D1_PEDIDO  = SD1.D1_PEDIDO,
    D1_ITEMPC  = SD1.D1_ITEMPC,
    D1_ITEM    = SD1.D1_ITEM,
    D1_COD     = SD1.D1_COD,
    D1_UM      = SD1.D1_UM,
    D1_QUANT   = SD1.D1_QUANT,
    D1_VUNIT   = SD1.D1_VUNIT,
    D1_TOTAL   = SD1.D1_TOTAL,
    D1_CC      = SD1.D1_CC,
    D1_LOCAL   = SD1.D1_LOCAL,
    D1_DOC     = SD1.D1_DOC,
    D1_SERIE   = SD1.D1_SERIE,
    D1_FORNECE = SD1.D1_FORNECE,
    D1_LOJA    = SD1.D1_LOJA,
    D1_EMISSAO = SD1.D1_EMISSAO,
    D1_DTDIGIT = SD1.D1_DTDIGIT,
    D1_RECNO   = SD1.R_E_C_N_O_
FROM dbo.vwSD1010 SD1 WITH (NOLOCK)
INNER JOIN chaves C
    ON RTRIM(LTRIM(SD1.D1_FILIAL)) = C.filial
   AND RTRIM(LTRIM(SD1.D1_PEDIDO)) = C.numero_pedido
   AND RTRIM(LTRIM(SD1.D1_ITEMPC)) = C.item_pedido
WHERE SD1.D_E_L_E_T_ = ' '
  AND RTRIM(LTRIM(SD1.D1_PEDIDO)) <> '';
