# Rastreabilidade de Compras

Este documento descreve o backend inicial de rastreabilidade de compras. O escopo entregue
cria a persistencia interna do snapshot, reaproveita a integracao `bdTotvs` e preserva as
consultas SQL como fonte operacional da leitura Protheus.

## Objetivo

Permitir que o ERP acompanhe a jornada de uma solicitacao de compra ate pedido, entrada no
almoxarifado, lancamento fiscal, titulo financeiro e saldo de estoque consultado, sem tornar
arquivos JSON parte do contrato oficial do sistema.

## Arquitetura

- `repository.py` executa SQLs versionados no modulo usando `bdTotvs.execute_query`.
- `services.py` agrega entradas, notas, titulos, produtos, saldos e locais.
- `rules.py` concentra os status executivos de compra, recebimento, prazo e estoque.
- `importer.py` grava um snapshot interno nas tabelas do ERP.
- `importar_rastreabilidade_compras` e o comando operacional sanitizado para carga controlada.

## Fonte Protheus

As consultas usam as views Protheus ja conhecidas no estudo de referencia:

- `vwSC1010` e `vwSC7010` para SC e pedido;
- `vwSD1010` para entrada no almoxarifado;
- `vwSF1010` para lancamento fiscal;
- `vwSE2010` para titulo financeiro;
- `vwSB1010` para cadastro do produto;
- `vwSB2010` para saldo de estoque;
- `vwNNR010` para descricao de locais.

O filtro de filial, periodo e unidade requisitante fica no SQL `01_base_sc_pedido.sql`.
Alteracoes de recorte operacional devem ser feitas ali, nao duplicadas em Python.

## Persistencia

A migration `20260713_compras_rastreabilidade_backend` cria:

- `compras_rastreabilidade_execucoes`: controle de execucao, status e erro sanitizado;
- `compras_rastreabilidade_itens`: snapshot consultivo dos itens rastreados.

O snapshot atual e regravado a cada importacao concluida. As execucoes preservam auditoria
basica de inicio, fim, status, totais e mensagem sanitizada em falhas.

## Comando

```powershell
.\.venv\Scripts\python.exe manage.py importar_rastreabilidade_compras
```

A saida do comando deve manter apenas contagens e status gerais. Nao deve imprimir connection
string, usuario, senha, servidor, payload completo ou dados sensiveis.

## Regras Executivas

- Compra efetivada pode ser confirmada por entrada no almoxarifado mesmo quando o pedido ainda
  nao aparece como emitido.
- Pedido liberado e emitido, sem entrada, fica como `Comprado - aguardando entrada no almoxarifado`.
- Entrega total ate a data prevista fica como `Recebido 100% no prazo`.
- Local `06` com entrada registrada fica como `Entrada em consumo direto`.
- Saldo disponivel e calculado pelo saldo atual menos reservado e empenhado.

## Fora do Escopo

- Nenhuma tela frontend foi criada.
- Nenhum dashboard foi criado.
- Nenhum arquivo JSON de saida foi tornado contrato oficial.
- Nenhum arquivo `.env`, log, payload bruto ou pasta `saida` foi versionado.
- O modulo Impressoras nao foi alterado.

## Validacoes Esperadas

- Testes unitarios do modulo de rastreabilidade.
- `compileall` do backend.
- `manage.py check`.
- Migration Alembic ate `head`.
- Importacao real controlada quando o banco e a integracao `bdTotvs` estiverem acessiveis.

## Proximos Passos

- Expor endpoints consultivos depois que o contrato de tela for definido.
- Definir permissoes do modulo Compras antes de qualquer frontend.
- Avaliar incrementalidade do snapshot se o volume operacional crescer.
