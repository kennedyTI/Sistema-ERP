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

A migration `20260713_compras_rastreio` cria:

- `compras_rastreabilidade_execucoes`: controle de execucao, status e erro sanitizado;
- `compras_rastreabilidade_itens`: snapshot consultivo dos itens rastreados.

Cada importacao grava itens vinculados a uma nova execucao. A API usa apenas a ultima
execucao `concluida`, preservando o snapshot anterior se uma nova carga ficar em andamento
ou terminar com erro. As execucoes preservam auditoria basica de inicio, fim, origem, status,
totais e mensagem sanitizada em falhas.

## Comando

```powershell
.\.venv\Scripts\python.exe manage.py importar_rastreabilidade_compras
```

A saida do comando deve manter apenas contagens e status gerais. Nao deve imprimir connection
string, usuario, senha, servidor, payload completo ou dados sensiveis.

## Fase 3 - API e atualizacao agendada

A Fase 3 adiciona consulta operacional e atualizacao assincrona do snapshot.

### Rotas

Todas as rotas ficam sob `/api/v2`:

- `GET /compras/rastreabilidade/resumo`
- `GET /compras/rastreabilidade/itens`
- `GET /compras/rastreabilidade/itens/{id}`
- `GET /compras/rastreabilidade/execucoes`
- `POST /compras/rastreabilidade/atualizar`

### Snapshot Atual

O snapshot atual e sempre a ultima execucao com status `concluida`, ordenada por
`finalizado_em` e `id`. Execucoes `em_andamento` ou `erro` nao substituem o snapshot valido
anterior e nao sao usadas pela listagem, detalhe ou resumo.

Se nao houver execucao concluida, o resumo retorna `possui_dados=false` com mensagem segura.

### Resumo Executivo

O resumo retorna contadores de:

- total de itens;
- SC aprovada;
- item com pedido;
- pedido liberado;
- compra efetivada;
- recebido 100%;
- recebido parcial;
- aguardando entrada;
- fora do prazo;
- NF lancada;
- titulo financeiro gerado;
- titulo pago;
- saldo atende;
- saldo parcial;
- sem saldo;
- consumo direto.

### Listagem e Filtros

A listagem e paginada por `page` e `page_size`, com limite maximo de 200 itens por pagina.
A ordenacao padrao e:

```text
data_emissao_sc desc
numero_sc desc
item_sc asc
```

Filtros disponiveis:

- `filial`
- `numero_sc`
- `numero_pedido`
- `produto`
- `centro_custo`
- `solicitante`
- `situacao_compra`
- `status_prazo_entrega`
- `status_estoque_executivo`
- `nf_lancada_fiscal`
- `virou_titulo_financeiro`
- `status_pagamento_financeiro`
- `local_estoque_consultado`

A listagem nao retorna `payload_completo`.

### Detalhe

O detalhe retorna apenas itens pertencentes ao snapshot atual. Um item de execucao antiga,
em andamento ou com erro retorna 404 seguro.

### Execucoes

A rota de execucoes lista importacoes mais recentes primeiro e retorna:

- `id`
- `status`
- `origem`
- `iniciado_em`
- `finalizado_em`
- `total_registros`
- `total_com_erro`
- `mensagem_erro_sanitizada`
- `criado_em`

`origem` pode ser `manual`, `agendada` ou `comando`.

### Atualizacao Manual Assincrona

`POST /compras/rastreabilidade/atualizar` valida permissao, cria uma execucao `em_andamento`,
enfileira a task Celery e retorna 202 sem aguardar a importacao terminar.

Se ja existir importacao em andamento, retorna status `em_andamento` e nao cria outra carga.

### Task e Agendamento

A task Celery oficial e:

```text
compras_rastreabilidade_importar
```

O Celery Beat agenda a task por cron fixo nos horarios:

```text
00:00
06:00
12:00
18:00
```

O timezone segue a configuracao `TIME_ZONE` do projeto, com `enable_utc=False`.

### Lock de Concorrencia

O lock Redis usa a chave:

```text
compras:rastreabilidade:importacao
```

O TTL e de 3 horas (`10800` segundos). O lock e liberado no final com sucesso ou erro. Em queda
inesperada, o TTL evita lock eterno.

### Permissoes

As rotas de leitura exigem `compras.ver_rastreabilidade`.

A atualizacao manual exige `compras.atualizar_rastreabilidade`.

Nesta fase, `Equipe Tecnica` e `Gestor` recebem acesso de leitura e atualizacao. `Operador` e
`Integracao Protheus` nao recebem acesso ao modulo Compras.

### Validacoes da Fase 3

- Testes de snapshot atual, resumo, filtros, detalhe, execucoes, permissao e seguranca.
- Testes de POST assincrono sem importacao sincrona no request.
- Testes da task, lock Redis e schedule 00h/06h/12h/18h.
- Validacao real com Docker/Postgres/Redis/Celery quando o ambiente estiver ativo.

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
