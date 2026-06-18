# Monitoramento de conectividade de impressoras

## Etapa 3.5.1

Esta etapa adiciona a infraestrutura mínima para responder, a cada 60 segundos:

- se uma impressora ativa está online ou offline;
- qual método confirmou o estado;
- se o estado confirmado mudou;
- quando a mudança ocorreu.

O frontend apresenta somente `online` e `offline`. O estado transitório
`offline_suspeito` existe apenas no código e no Redis.

## Fluxo de conectividade

A cascata interrompe no primeiro método que responder:

1. ICMP, com timeout padrão de 1 segundo;
2. TCP 443 e depois TCP 80, com uma tentativa por porta;
3. SNMP leve usando `sysName` (`1.3.6.1.2.1.1.5.0`);
4. HTML/HTTP leve em `/home/status.html`;
5. fallback quando todos os métodos falham.

Não existe retry interno no mesmo ciclo. A community SNMP vem exclusivamente da
variável `PRINTER_SNMP_COMMUNITY` e não é registrada em logs ou histórico.

## Confirmação de offline

Na primeira falha completa, o Redis registra `offline_suspeito`. O banco e o
histórico não são alterados.

Na segunda falha completa consecutiva, o estado `offline` é confirmado. Qualquer
resposta posterior confirma `online` imediatamente e zera o contador de falhas.

## Persistência

### Redis

A chave `printers:connectivity:{maquina_id}` tem TTL padrão de 90 segundos e
guarda o resultado mais recente, contador de falhas, método, latência e resumo
sanitizado das tentativas.

Redis também atua como broker e result backend do Celery e mantém:

- lock global `printers:lock:connectivity:global`;
- lock por máquina `printers:lock:connectivity:machine:{maquina_id}`.

Os locks usam token único, TTL configurável e liberação atômica com Lua.

### PostgreSQL

`status_impressoras` é a fotografia atual. Ela é atualizada em toda confirmação,
mesmo quando o estado permanece igual.

`historico_status_impressoras` registra somente mudanças confirmadas. Os eventos
permitidos são:

- `online_confirmado`;
- `offline_confirmado`;
- `desconhecido_para_online`;
- `desconhecido_para_offline`.

O histórico está disponível no Django Admin somente para consulta.

## Celery

Tasks disponíveis:

- `printers_connectivity_all`: lote de todas as máquinas ativas;
- `printers_connectivity_one`: execução manual para uma máquina;
- `printer_monitor_debug_ping`: diagnóstico ICMP manual;
- `printer_monitor_healthcheck`: diagnóstico Redis e PostgreSQL.

O Celery Beat agenda `printers_connectivity_all` a cada 60 segundos. Máquinas
inativas não entram no lote.

Execução manual no container:

```bash
docker compose --env-file .env.docker exec celery-worker \
  celery -A backend.app.core.celery_app.celery_app call \
  printers_connectivity_one --args='[1]'
```

## Etapa 3.5.2.0 - Backend de regras de alertas

Esta microetapa porta para a arquitetura modular da v2 a base conceitual de
alertas consolidada na v1. Ela adiciona somente a configuração e a classificação
de mensagens; nenhuma coleta periódica ou atualização operacional é executada.

### Tabela de regras

O Alembic administra a tabela `regras_alertas_impressoras`, com os campos:

- `id`;
- `codigo`;
- `descricao`;
- `severidade`;
- `tipo_regra`;
- `padrao`;
- `prioridade`;
- `ativo`;
- `criado_em`;
- `atualizado_em`.

O seed oficial é idempotente: cria as 18 regras iniciais quando ausentes e
atualiza seus campos controlados quando já existem. A execução ocorre no serviço
de migrations e também pode ser feita manualmente:

```bash
python backend/scripts/seed_printer_alert_rules.py
```

### Rules Engine

A classificação normaliza acentos, caixa e espaços, ignora regras inativas e
ordena por menor prioridade. Empates são resolvidos pelo código da regra.

Os tipos aceitos são:

- `contains`;
- `equals`;
- `regex`.

As severidades persistidas continuam compatíveis com a v1:

- `green`;
- `low`;
- `medium`;
- `high`;
- `unknown`.

Na apresentação visual futura, `green` será convertido em verde, `low` e
`medium` em amarelo, `high` em vermelho e `unknown` em cinza. Essa conversão
ainda não integra a tela Status.

Quando nenhuma regra reconhece a mensagem, a Rules Engine retorna `unknown`,
com severidade `unknown`, e preserva a mensagem original para diagnóstico.

As regras podem ser consultadas e administradas pelo Django Admin conforme as
permissões padrão. A Equipe Técnica recebe as permissões administrativas; o
grupo Operador não recebe permissão de edição.

## Etapa 3.5.2.1 - Configuracao SNMP/OIDs

Esta microetapa porta da v1 a base de configuracao de OIDs por modelo e
metrica. A entrega prepara a proxima etapa de alertas via SNMP, mas ainda nao
consulta equipamentos reais, nao cria alertas ativos e nao altera a tela Status.

### Tabela de configuracao

O Alembic administra a tabela `oids_snmp_impressoras`, com os campos:

- `id`;
- `modelo_id`;
- `chave_metrica`;
- `oid`;
- `tipo_valor`;
- `versao_snmp`;
- `modo_consulta`;
- `ativo`;
- `criado_em`;
- `atualizado_em`.

`modelo_id` referencia a tabela existente `printers_models`. Nao foi criada
nenhuma tabela paralela de modelos.

A constraint unica `modelo_id + chave_metrica` evita duplicidade. Tambem foram
criados indices para `modelo_id`, `chave_metrica`, `ativo` e para a combinacao
`modelo_id + chave_metrica`.

### Seed idempotente

O seed oficial sincroniza OIDs seguros para os modelos auditados na v1:

- Brother DCP-L1632W;
- Brother DCP-L2540DW;
- Canon IR-C3326I;
- HP MFP-4303;
- Samsung K-4350.

As metricas iniciais sao:

- `alert_raw`;
- `name`;
- `location`;
- `page_count_total`.

Na v1 havia o alias historico `page_count` apontando para o mesmo contador de
`page_count_total`. Na v2 desta microetapa foi mantida apenas a chave canonica
`page_count_total`, para respeitar a constraint por modelo e metrica sem criar
duplicidade.

Se um modelo do seed ainda nao existir no banco local, a linha e ignorada e a
execucao continua. O seed nao contem IPs, nomes de maquinas, community SNMP,
dados reais ou arquivos locais.

Os OIDs privados de toner abaixo seguem fora do seed ativo porque foram
invalidados na auditoria da v1:

- `DCP-L1632W / toner_black`:
  `1.3.6.1.4.1.2435.2.3.9.4.2.1.5.5.52.31.1.2.1`;
- `DCP-L2540DW / toner_black`:
  `1.3.6.1.4.1.2435.2.3.9.4.2.1.3.3.1.11.0`.

Execucao manual:

```bash
python backend/scripts/seed_printer_snmp_oids.py
```

### Service interno

O service `backend.app.modules.printers.monitoring.snmp.oids` permite:

- buscar OID ativo por `modelo_id + chave_metrica`;
- listar OIDs ativos de um modelo;
- ignorar OIDs inativos;
- retornar `None` quando a metrica nao existe;
- serializar `modo_consulta` para uso interno futuro.

Exemplo de uso futuro:

```python
oid_config = get_active_oid_for_model(
    db,
    model_id=model_id,
    metric_key="alert_raw",
)
```

O fluxo planejado para a proxima etapa sera:

```text
modelo da maquina
-> buscar OID ativo alert_raw
-> tentar SNMP
-> aplicar regras_alertas_impressoras
```

As configuracoes podem ser administradas no Django Admin pela Equipe Tecnica.
O grupo Operador nao recebe permissoes administrativas para OIDs.

## Etapa 3.5.2.1a - Diagnostico SNMP real dos alertas

Esta etapa adiciona um script manual para descobrir, com evidencia de rede real,
como cada modelo entrega alertas brutos via SNMP. O objetivo e responder se a
metrica `alert_raw` funciona como um GET unico ou se algum modelo exige WALK em
uma base de alertas para enxergar multiplos alertas ativos.

O script fica em:

```bash
backend/pyteste/diagnostico_snmp_alertas.py
```

Ele nao roda automaticamente no `pytest` e nao faz parte da coleta operacional.
Para evitar execucao acidental em impressoras reais, sem `--confirmar` ele faz
apenas dry-run:

```bash
python backend/pyteste/diagnostico_snmp_alertas.py
```

Execucao real, quando a rede e a community SNMP estiverem disponiveis:

```bash
python backend/pyteste/diagnostico_snmp_alertas.py --confirmar
python backend/pyteste/diagnostico_snmp_alertas.py --confirmar --modelo "Brother DCP-L1632W"
python backend/pyteste/diagnostico_snmp_alertas.py --confirmar --maquina-id 12
```

O script descobre dinamicamente os modelos com OID ativo `alert_raw` em
`oids_snmp_impressoras` e seleciona, por padrao, uma maquina ativa por modelo.
Antes de consultar SNMP, ele verifica se a maquina esta online reaproveitando a
cascata de conectividade da 3.5.1. Maquinas offline ou sem maquina ativa sao
registradas como ignoradas.

Consultas comparadas:

- GET no OID `alert_raw` configurado;
- WALK em `prtAlertDescription` (`1.3.6.1.2.1.43.18.1.1.8`);
- WALK em `hrPrinterStatus` (`1.3.6.1.2.1.25.3.5.1.1`);
- WALK em `hrPrinterDetectedErrorState` (`1.3.6.1.2.1.25.3.5.1.2`).

Cada valor SNMP e salvo em forma bruta, incluindo tipo, string, `repr`, tamanho,
hex quando houver bytes e decodificacoes possiveis. A Rules Engine nao e usada
como transformacao principal nesta etapa.

Arquivos gerados por execucao confirmada:

```text
tmp/diagnosticos/snmp_alertas/diagnostico_snmp_alertas_YYYYMMDD_HHMMSS.json
tmp/diagnosticos/snmp_alertas/diagnostico_snmp_alertas_YYYYMMDD_HHMMSS.md
```

A pasta `tmp/` e ignorada pelo Git. Os relatorios podem conter IPs, nomes de
maquinas e valores brutos retornados pelos equipamentos; por isso nao devem ser
versionados. O script sanitiza a community SNMP e nao registra senhas,
credenciais, tokens, cookies ou headers sensiveis.

O resultado deste diagnostico deve orientar a 3.5.2.2:

- usar o diagnostico real como evidencia tecnica;
- tratar `alert_raw` como metrica potencialmente multipla;
- consolidar, na 3.5.2.1b, o uso de WALK na base `prtAlertDescription` para
  todos os modelos do seed.

## Etapa 3.5.2.1b - Modo de consulta dos OIDs SNMP

Esta microetapa adiciona o campo obrigatorio `modo_consulta` na tabela
`oids_snmp_impressoras`. A decisao veio do diagnostico real da 3.5.2.1a e de
uma regra arquitetural da v2: `alert_raw` nao deve ser tratado como valor unico.

Mesmo que um modelo tenha retornado apenas um valor no diagnostico atual, isso
nao garante que ele seja incapaz de expor multiplos alertas em outro momento.
Um GET em um OID exato, como `1.3.6.1.2.1.43.18.1.1.8.1.1`, nao descobre um
segundo alerta em um OID irmao, como `1.3.6.1.2.1.43.18.1.1.8.1.2`. Por isso,
todas as impressoras devem ser consideradas potencialmente capazes de evoluir
para multiplos alertas.

Valores permitidos:

- `get`: consulta um OID exato e espera um valor de origem;
- `walk`: consulta uma base OID e pode retornar 0, 1 ou varios OIDs filhos.

O valor padrao para registros existentes e `get`. As metricas escalares seguem
sempre com `get`:

- `name`;
- `location`;
- `page_count_total`.

Estrategia final por metrica:

| Metrica | modo_consulta |
| --- | --- |
| `name` | `get` |
| `location` | `get` |
| `page_count_total` | `get` |
| `alert_raw` | `walk` |

Para `alert_raw`, como o modo e `walk`, o OID salvo deve ser a base da coluna de
alertas `1.3.6.1.2.1.43.18.1.1.8`, e nao uma instancia especifica como
`1.3.6.1.2.1.43.18.1.1.8.1.1`.

O seed aplica essa regra a todos os modelos iniciais:

- Brother DCP-L1632W;
- Brother DCP-L2540DW;
- Canon IR-C3326I;
- HP MFP-4303;
- Samsung K-4350.

Decisoes funcionais registradas para a 3.5.2.2:

1. GET sera usado para metricas escalares.
2. WALK sera usado para `alert_raw`.
3. O service futuro deve retornar lista de alertas.
4. Para GET, a futura coleta deve embrulhar o retorno em lista com 0 ou 1 item.
5. Para WALK, a futura coleta pode retornar lista com 0, 1 ou varios itens.
6. Resposta vazia de alerta nao sera classificada automaticamente como
   OK/verde.
7. Resposta vazia sera tratada como cinza/inconclusivo na coleta futura.
8. `unknown` sera cinza.
9. `unknown` nao e falha de coleta.
10. `unknown` representa mensagem recebida, mas nao catalogada em
   `regras_alertas_impressoras`.
11. Falha de coleta representa erro tecnico de comunicacao, timeout, OID
   invalido, community invalida ou ausencia de resposta.
12. Mensagem `unknown` devera ser registrada futuramente em
    `historico_alertas_impressoras` quando aparecer pela primeira vez para
    aquele modelo de maquina.

A 3.5.2.2 ainda nao deve persistir alertas. Ela deve apenas coletar
`alert_raw`, aplicar regras e devolver resultado operacional controlado. A
persistencia em `alertas_impressoras` e `historico_alertas_impressoras` fica
reservada para a 3.5.2.3.

## Etapa 3.5.2.2 - Coleta SNMP de alert_raw

Esta microetapa cria o service oficial de coleta SNMP de `alert_raw`. A coleta
usa a configuracao existente em `oids_snmp_impressoras`, respeita
`modo_consulta`, aplica a Rules Engine de `regras_alertas_impressoras` e retorna
um resultado operacional em memoria. Ela ainda nao cria endpoint publico, nao
altera a tela Status e nao persiste alertas.

Fluxo da coleta:

```text
maquina ativa e online
-> identifica modelo
-> busca OID ativo alert_raw
-> verifica modo_consulta
-> executa SNMP GET ou WALK
-> preserva retorno bruto
-> aplica Rules Engine
-> retorna lista de alertas normalizados
-> calcula classificacao geral
```

O `alert_raw` da v2 usa `walk` na base `1.3.6.1.2.1.43.18.1.1.8`.
Mesmo assim, o service respeita `modo_consulta` para manter o contrato tecnico:

- `get`: retorna lista com 0 ou 1 item;
- `walk`: retorna lista com 0, 1 ou varios itens.

O retorno bruto preserva, quando disponivel:

- `oid_retornado`;
- `valor_original`;
- `valor_repr`;
- `tipo_snmp`;
- `valor_bytes_hex`.

Classificacao visual:

| Severidade/regra | Classificacao |
| --- | --- |
| `green` | `verde` |
| `low` / `medium` | `amarelo` |
| `high` | `vermelho` |
| `unknown` | `cinza` |
| sem retorno util | `cinza` |

Quando houver multiplos alertas, a classificacao geral usa a pior situacao
conhecida:

```text
vermelho > amarelo > cinza > verde
```

Casos controlados:

- `unknown`: a impressora respondeu uma mensagem, mas nenhuma regra catalogada
  reconheceu o texto. O resultado e cinza e nao representa falha tecnica.
- `sem_retorno_alerta`: SNMP respondeu, mas GET/WALK nao retornou valor util de
  alerta. O resultado e cinza/inconclusivo e nao deve virar OK/verde
  automaticamente.
- falha tecnica: timeout, sem resposta, community invalida, OID invalido, erro
  de conexao ou erro inesperado do cliente SNMP. A falha tecnica retorna
  `sucesso=false` e nao vira `unknown`.

Validacoes antes da coleta:

- maquina inexistente;
- maquina inativa;
- maquina sem IP;
- maquina sem modelo;
- maquina sabidamente offline pelo status atual;
- modelo sem OID ativo `alert_raw`.

A community SNMP vem da configuracao de ambiente e nao e retornada em JSON,
logs ou erros serializados. Detalhes tecnicos devem ser sanitizados.

Persistencia:

- esta etapa nao cria `alertas_impressoras`;
- esta etapa nao cria `historico_alertas_impressoras`;
- a persistencia fica para a 3.5.2.3.

Na etapa futura, mensagens `unknown` deverao ser registradas em
`historico_alertas_impressoras` somente quando aparecerem pela primeira vez para
aquele modelo. A chave conceitual sera:

```text
modelo_id + mensagem_original_normalizada
```

O fallback HTML/HTTP autenticado fica para etapa posterior. As credenciais HTML
deverao ser criptografadas no banco quando esse fallback for implementado.

## Etapa 3.5.2.3 - Persistencia de alertas atuais e historico

Esta microetapa adiciona a persistencia do resultado consolidado da coleta de
alertas. Ela usa o retorno ja produzido por `collect_snmp_alerts_for_machine`,
nao cria endpoint publico, nao cria frontend, nao cria task Celery e ainda nao
implementa fallback HTML/HTTP.

### Estado atual e historico

Foram criadas duas tabelas fisicas:

- `alertas_impressoras`: fotografia atual consolidada dos alertas da maquina;
- `historico_alertas_impressoras`: eventos relevantes derivados da mudanca de
  classificacao geral ou de unknown novo por modelo.

A decisao segue o mesmo conceito de `historico_status_impressoras`: o historico
nao registra toda tentativa de coleta. Ele registra somente transicoes
confirmadas ou eventos que precisam de auditoria tecnica.

### Tabela alertas_impressoras

Campos principais:

- `maquina_id`;
- `regra_alerta_id`, obrigatorio;
- `oid_snmp_id`, nullable para suportar HTML futuro;
- `mensagem_original`;
- `mensagem_original_normalizada`;
- `origem_coleta`;
- `metodo_confirmacao`;
- `metodo_coleta`;
- `oid_retornado`;
- `chave_alerta`;
- `verificado_em`;
- `criado_em`;
- `atualizado_em`.

A constraint `UNIQUE(maquina_id, chave_alerta)` evita duplicidade e permite que
o service sincronize alertas ativos sem apagar registros de outra origem por
engano.

### Tabela historico_alertas_impressoras

Campos principais:

- `maquina_id`;
- `regra_alerta_id`;
- `oid_snmp_id`;
- `codigo_alerta`;
- `severidade`;
- `classificacao_anterior`;
- `classificacao_nova`;
- `origem_coleta`;
- `metodo_confirmacao`;
- `metodo_coleta`;
- `oid_retornado`;
- `chave_alerta`;
- `mensagem_original`;
- `mensagem_original_normalizada`;
- `codigo_evento`;
- `descricao_evento`;
- `detalhes`;
- `verificado_em`;
- `criado_em`.

O historico salva snapshot minimo da regra (`codigo_alerta` e `severidade`) para
preservar o significado do evento mesmo se uma regra for editada futuramente.
O campo `detalhes` e gerado pelo codigo e deve conter apenas dados sanitizados.

Eventos permitidos nesta etapa:

- `estado_inicial_alerta`;
- `classificacao_alterada`;
- `alerta_nao_catalogado`.

### Valores controlados

`origem_coleta` aceita:

- `snmp`;
- `html`;
- `sistema`.

`metodo_coleta` aceita:

- `get`;
- `walk`;
- `html_autenticado`;
- `cascata`.

`metodo_confirmacao` aceita:

- `snmp_get`;
- `snmp_walk`;
- `html_autenticado`;
- `falha_cascata`.

### Classificacao geral

A classificacao geral continua usando a pior situacao conhecida:

```text
vermelho > amarelo > cinza > verde
```

Mapeamento visual:

| Severidade/regra | Classificacao |
| --- | --- |
| `green` | `verde` |
| `low` / `medium` | `amarelo` |
| `high` | `vermelho` |
| `unknown` | `cinza` |
| `sem_retorno_alerta` | `cinza` |

### Regra de historico

O historico e criado quando a classificacao geral muda:

- `verde` para `amarelo`, `vermelho` ou `cinza`;
- `amarelo` para `vermelho`, `verde` ou `cinza`;
- `vermelho` para `verde`, `amarelo` ou `cinza`;
- `cinza` para `verde`, `amarelo` ou `vermelho`.

Quando a classificacao geral nao muda, nenhum historico e criado.

Na primeira coleta da maquina, `estado_inicial_alerta` e criado somente quando a
classificacao inicial for `amarelo`, `vermelho` ou `cinza`. Primeira coleta
`verde` nao gera historico para evitar ruido.

### Unknown novo por modelo

Quando uma mensagem `unknown` aparece pela primeira vez para um modelo de
maquina, o service cria o evento `alerta_nao_catalogado`.

A chave conceitual e:

```text
modelo da maquina + mensagem_original_normalizada
```

O `modelo_id` nao e salvo no historico. O service obtem o modelo pela propria
maquina. A mesma mensagem unknown em outra maquina do mesmo modelo nao gera
evento repetido; a mesma mensagem em modelo diferente gera um novo evento.

### Regras tecnicas garantidas

O seed de `regras_alertas_impressoras` garante de forma idempotente:

- `unknown`, severidade `unknown`, classificacao visual cinza;
- `sem_retorno_alerta`, severidade `unknown`, classificacao visual cinza;
- `falha_coleta_alertas`, severidade `high`, classificacao visual vermelha.

### Sincronizacao

O service `sync_machine_alerts_from_collection_result` recebe o resultado
consolidado da coleta, gera `chave_alerta`, atualiza ou insere os alertas atuais
da maquina, remove alertas que desapareceram da coleta atual e cria historico
apenas quando houver evento relevante.

Para SNMP, o OID retornado e validado:

- `get`: `oid_retornado` deve ser igual ao OID configurado;
- `walk`: `oid_retornado` deve ser filho da base configurada.

OID retornado fora da base esperada vira falha tecnica consolidada, e nao alerta
normal.

### Tentativas e lock

Enquanto HTML ainda nao existe, o orquestrador interno
`collect_and_sync_machine_alerts` faz no maximo duas tentativas SNMP por maquina.
Se ambas falharem, persiste `falha_coleta_alertas` com:

- `origem_coleta = sistema`;
- `metodo_coleta = cascata`;
- `metodo_confirmacao = falha_cascata`.

O lock por maquina usa o mesmo padrao Redis do monitoramento:

```text
printers:lock:alerts:machine:{maquina_id}
```

Isso evita escrita concorrente e historico duplicado para a mesma maquina.

Quando o fallback HTML existir, a regra planejada passa a ser:

```text
1 tentativa SNMP
1 tentativa HTML autenticado
falha_coleta_alertas apenas se ambas falharem
```

### Admin

`ALERTAS_IMPRESSORAS` e `HISTORICO_ALERTAS_IMPRESSORAS` ficam no grupo
`IMPRESSORAS` do Django Admin e sao somente leitura. O usuario pode consultar,
mas nao criar, editar ou excluir manualmente.

### Fora desta microetapa

Esta etapa nao cria:

- tabela `tentativas_coleta_impressoras`;
- API publica;
- task Celery de 5 minutos;
- frontend;
- fallback HTML/HTTP;
- credenciais HTML;
- toner;
- papel;
- dashboard.

## Etapa 3.5.2.4 - Agendamento Celery dos alertas

Esta microetapa agenda a coleta e persistencia de alertas em Celery Beat. Ela
nao altera API publica, frontend, tela Status, fallback HTML/HTTP, toner, papel
ou dashboard.

### Verificacao da task 60s

A task de conectividade/status da etapa 3.5.1 ja existia e foi mantida sem
redesenho:

- task: `printers_connectivity_all`;
- schedule Beat: `printers-connectivity-every-60-seconds`;
- periodicidade padrao: `60` segundos;
- variavel: `PRINTER_CONNECTIVITY_INTERVAL_SECONDS`;
- broker/result backend: Redis;
- lock global: `printers:lock:connectivity:global`;
- lock por maquina: `printers:lock:connectivity:machine:{maquina_id}`.

Ela processa apenas maquinas ativas, atualiza `status_impressoras` quando ha
estado confirmado e grava `historico_status_impressoras` somente quando ha
transicao confirmada. O estado `offline_suspeito` continua apenas no Redis.

### Task de alertas 5min

Foi adicionada a task:

```text
printers_alerts_all
```

Schedule Beat:

```text
printers-alerts-every-5-minutes
```

Periodicidade padrao:

```text
300 segundos
```

Variavel:

```text
PRINTER_ALERTS_INTERVAL_SECONDS=300
```

A task abre uma sessao de banco, obtem Redis, aplica lock global e chama
`run_alerts_batch`, que por sua vez chama o orquestrador ja existente
`collect_and_sync_machine_alerts`.

### Maquinas elegiveis

O lote considera somente maquinas:

- ativas;
- com IP;
- com modelo;
- com OID `alert_raw` ativo;
- que nao estejam `offline` em `status_impressoras`, quando esse status atual
  estiver disponivel.

Maquinas sem IP, sem modelo, sem OID ou offline entram no resumo como ignoradas.

### Locks

O lote de alertas usa lock global:

```text
printers:lock:alerts:global
```

Cada maquina continua usando o lock por maquina criado na etapa 3.5.2.3:

```text
printers:lock:alerts:machine:{maquina_id}
```

Esses locks evitam execucoes sobrepostas, escrita concorrente e historico
duplicado.

### Falhas e resumo

Falha em uma maquina nao interrompe o lote. O erro e registrado de forma
sanitizada no resumo e a task continua na proxima maquina.

Resumo retornado:

- `total_maquinas`;
- `processadas`;
- `ignoradas`;
- `sucesso`;
- `falha`;
- `resultados`.

O resumo nao inclui community SNMP, credenciais, tokens, cookies, headers
sensiveis ou HTML bruto.

### Tentativas e HTML futuro

Enquanto HTML ainda nao existe, o fluxo de alertas usa ate duas tentativas SNMP
por maquina. Se ambas falharem, `falha_coleta_alertas` e persistida como falha
tecnica consolidada.

Quando HTML autenticado for implementado, a estrategia planejada sera:

```text
1 tentativa SNMP
1 tentativa HTML autenticado
falha_coleta_alertas apenas se ambas falharem
```

### Comandos uteis

Verificar worker:

```bash
docker compose --env-file .env.docker logs celery-worker
```

Verificar Beat:

```bash
docker compose --env-file .env.docker logs celery-beat
```

Inspecionar tasks registradas:

```bash
docker compose --env-file .env.docker exec celery-worker \
  celery -A backend.app.core.celery_app.celery_app inspect registered
```

Executar task manualmente:

```bash
docker compose --env-file .env.docker exec celery-worker \
  celery -A backend.app.core.celery_app.celery_app call printers_alerts_all
```

### Fora desta microetapa

Esta etapa nao implementa fallback HTML/HTTP, credenciais HTML, API publica,
frontend, dashboard, toner, papel, coleta rica ou tabela
`tentativas_coleta_impressoras`.

## Etapa 3.5.2.5 - Credenciais criptografadas para HTML autenticado

Esta microetapa cria apenas a base segura para credenciais de coleta HTML
autenticada. Ela nao executa login em paginas de impressoras, nao cria parser
HTML, nao altera tasks, nao adiciona endpoint publico e nao muda frontend.

### Escopo da credencial

As credenciais ficam na tabela:

```text
credenciais_coleta_impressoras
```

O escopo e sempre por modelo de impressora:

- `modelo_id` aponta para `printers_models`;
- nao existe credencial por maquina;
- nao existe coluna `maquina_id`;
- nao existe coluna `fabricante`;
- nao existe coluna `escopo`.

Essa decisao evita duplicar senha por equipamento e prepara a futura cascata de
coleta por modelo.

### Tipos de autenticacao

Os tipos aceitos sao controlados:

```text
basic
digest
form
cookie
```

A tabela aceita no maximo uma credencial ativa por modelo por meio de indice
unico parcial. Credenciais inativas duplicadas podem permanecer como historico
administrativo.

### Criptografia

A senha real nunca e gravada em texto puro. O campo persistido e:

```text
senha_criptografada
```

A criptografia usa Fernet, da biblioteca `cryptography`, e depende da variavel:

```text
PRINTER_CREDENTIALS_SECRET_KEY
```

Os arquivos `.env.example`, `.env.docker.example` e `backend/.env.example`
mantem apenas placeholder vazio. Segredos reais devem ser definidos somente no
ambiente local, homologacao ou producao.

Se a chave nao estiver configurada, operacoes sensiveis como criar, alterar,
criptografar ou descriptografar senha falham de forma controlada. Consultas de
metadados e listagem administrativa continuam seguras.

### Admin

`CREDENCIAIS_COLETA_IMPRESSORAS` fica no grupo `IMPRESSORAS` do Django Admin.

A listagem exibe apenas metadados:

- nome;
- modelo;
- tipo de autenticacao;
- usuario;
- ativo;
- datas de criacao e atualizacao.

A senha descriptografada nunca e exibida. A senha criptografada completa tambem
nao aparece na listagem nem no formulario. O formulario possui somente um campo
de senha para definir ou trocar o segredo.

Permissoes:

- superuser pode criar, alterar e desativar credenciais;
- Equipe Tecnica pode consultar metadados;
- Operador nao acessa esta area administrativa.

### Cascata futura

Quando o fallback HTML for implementado, a estrategia planejada passa a ser:

```text
1 tentativa SNMP
1 tentativa HTML autenticado usando credencial ativa do modelo
falha_coleta_alertas apenas se ambas falharem
```

Esta microetapa nao implementa essa cascata; apenas deixa a credencial segura
disponivel para uso interno futuro.

### Fora desta microetapa

Esta etapa nao implementa:

- login HTML;
- sessao, cookies, CSRF ou formularios de impressoras;
- requests HTTP autenticados;
- parser HTML;
- fallback de coleta;
- API publica;
- frontend;
- credencial por maquina;
- tabela `tentativas_coleta_impressoras`;
- seed com senhas ou dados reais.

## Etapa 3.5.2.6 - Configuracao de acesso HTML por modelo e cliente HTML seguro

Esta microetapa prepara a configuracao de acesso HTML autenticado por modelo e
cria um cliente interno seguro para uso futuro no fallback HTML. Ela nao integra
HTML na cascata de alertas, nao persiste HTML bruto, nao cria API publica e nao
altera frontend.

### Tabela reutilizada

Nao foi criada nova tabela de endpoints HTML. A tabela existente
`credenciais_coleta_impressoras` passa a representar:

```text
credencial criptografada + configuracao de acesso HTML por modelo
```

O escopo continua sempre por modelo:

- `modelo_id` referencia `printers_models`;
- nao existe credencial por maquina;
- nao existe coluna `maquina_id`;
- nao existe tabela `tentativas_coleta_impressoras`;
- nao existe tabela nova de endpoints HTML.

### Ajuste do campo nome

O campo `nome` foi removido da estrutura funcional porque era redundante com o
modelo da impressora. A descricao passa a ser gerada pelo codigo.

Exemplo:

```text
Coleta HTML autenticada para Brother DCP-L1632W - status: /home/status.html
```

`usuario` passou a ser opcional, pois alguns paineis usam usuario e senha,
enquanto outros usam apenas senha.

### Campos HTML por modelo

Foram adicionados:

- `caminho_status`;
- `caminho_informacoes`;
- `caminho_login`;
- `timeout_segundos`;
- `protocolo_preferencial`;
- `validar_ssl`.

`timeout_segundos` tem padrao seguro `5` e deve ficar entre `1` e `30`.

`protocolo_preferencial` aceita:

```text
auto
http
https
```

Regras:

- `auto`: tenta HTTPS primeiro e HTTP depois;
- `http`: usa somente HTTP;
- `https`: usa somente HTTPS.

`validar_ssl` tem padrao `false` para redes internas, pois paineis de
impressoras frequentemente usam certificados proprios, vencidos ou internos.

### Caminhos relativos e URL segura

Os caminhos HTML devem ser relativos:

```text
/home/status.html
/general/information.html?kind=item
```

Nao sao aceitos:

```text
http://10.0.0.1/home/status.html
https://10.0.0.1/home/status.html
//10.0.0.1/home/status.html
```

A URL final e montada pelo sistema usando o IP da maquina:

```text
protocolo + "://" + ip_da_maquina + caminho
```

Essa regra reduz risco de URL arbitraria e evita configurar destino completo no
Admin.

### Cliente HTML interno

Foi criado o modulo interno:

```text
backend/app/modules/printers/monitoring/html_client/
```

O cliente:

- monta URL segura a partir de IP e caminho relativo;
- respeita `protocolo_preferencial`;
- respeita `timeout_segundos`;
- respeita `validar_ssl`;
- usa autenticacao `basic` e `digest`;
- retorna erro controlado para `form` e `cookie` nesta etapa;
- retorna conteudo HTML apenas em memoria;
- nao faz log de senha, Authorization, cookie, CSRF ou HTML bruto autenticado.

`form` e `cookie` foram preparados, mas ainda nao implementam login real. Isso
fica para uma etapa especifica, pois depende de endpoint de login, campos do
formulario, CSRF, cookies, redirecionamentos e validacao de sessao por
fabricante/modelo.

### Service de configuracao ativa

O service de credenciais foi ajustado para buscar a configuracao ativa por
modelo e separar:

- metadados seguros;
- configuracao interna com senha descriptografada em memoria.

Senha descriptografada nao e exposta em Admin, API, logs ou documentacao.

### Admin

`credenciais_coleta_impressoras` lista apenas metadados seguros:

- modelo;
- tipo de autenticacao;
- protocolo preferencial;
- validar SSL;
- caminho de status;
- caminho de informacoes;
- ativo;
- atualizado em.

A senha descriptografada e o token criptografado completo continuam escondidos.

### Coluna REGRA no Admin de alertas

O Admin de `alertas_impressoras` e `historico_alertas_impressoras` passou a
exibir a coluna `REGRA` no formato resumido:

```text
#ID - codigo
```

Exemplo:

```text
#13 - idle
```

No historico, `codigo_alerta` e `severidade` continuam preservados como snapshot
minimo do momento do evento.

### Fluxo futuro

A proxima etapa de fallback HTML deve seguir:

```text
SNMP OK -> usa SNMP.
SNMP falhou -> tenta HTML autenticado.
HTML OK -> usa HTML.
SNMP + HTML falharam -> falha_coleta_alertas / vermelho.
```

Esta microetapa nao ativa esse fluxo ainda.

## Fora do escopo

As etapas 3.5.1 e 3.5.2.0 não implementam a coleta de alertas em cinco minutos,
toner, papel, coleta rica, dashboard, Protheus, Telegram ou tabela detalhada de
tentativas. A etapa 3.5.2.1 tambem nao implementa fallback HTML/HTTP de
alertas, endpoint publico, frontend, coleta real SNMP ou tabelas de alertas
ativos e historico. A etapa 3.5.2.1a tambem nao altera modelagem, nao adiciona
`modo_consulta` e nao grava resultado operacional no banco. A etapa 3.5.2.1b
adiciona apenas a configuracao GET/WALK dos OIDs e nao implementa coleta
oficial, Celery, frontend ou persistencia de alertas. A etapa 3.5.2.2 cria
apenas o service interno de coleta SNMP de `alert_raw`; ela nao cria task
Celery, endpoint publico, frontend, fallback HTML/HTTP, toner, papel, dashboard
ou persistencia de alertas. A etapa 3.5.2.3 cria a persistencia de alertas
atuais e historico, mas nao cria API publica, task Celery, frontend, fallback
HTML/HTTP, toner, papel ou dashboard. A etapa 3.5.2.4 agenda a task Celery de
alertas em cinco minutos, sem criar API publica, frontend, fallback HTML/HTTP,
toner, papel ou dashboard. A etapa 3.5.2.5 cria somente credenciais
criptografadas por modelo para uso futuro do HTML autenticado, sem implementar
login HTML, parser, fallback, API publica, frontend ou seeds de credenciais. A
etapa 3.5.2.6 configura caminhos HTML por modelo e cria cliente interno
basic/digest, mas ainda nao integra HTML na cascata de alertas, nao cria parser
final, nao cria API publica, nao altera frontend e nao persiste HTML bruto.

## Próximas etapas

- implementar fallback HTML/HTTP posterior usando credencial ativa do modelo;
- expor consultas publicas dos alertas quando houver necessidade de frontend;
- 3.5.3: coleta rica em 60 minutos;
- 3.5.4: papel, toner e históricos;
- 3.5.5: dashboard.
