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

## Etapa 3.5.2.7 - Parser HTML da pagina de status por modelo

Esta microetapa cria o parser interno da pagina HTML de status, com suporte
inicial ao modelo Brother DCP-L1632W e a pagina `/home/status.html`. Ela apenas
transforma o HTML autenticado recebido em um resultado normalizado em memoria.
Nao ha persistencia, API publica, frontend, task Celery nova ou integracao na
cascata SNMP -> HTML nesta etapa.

### Entrada e saida

O parser recebe uma string HTML ja obtida pelo cliente HTML seguro. Ele nao faz
request HTTP, nao depende de IP, nao acessa banco e nao usa senha.

A saida e um DTO interno com:

- `sucesso`;
- `modelo_nome`;
- `fabricante`;
- `mensagens_brutas`;
- `mensagens_normalizadas`;
- `estado_principal`;
- `erro_codigo`;
- `erro_detalhe_sanitizado`;
- `metadados`.

Exemplo de sucesso:

```json
{
  "sucesso": true,
  "modelo_nome": "DCP-L1632W",
  "fabricante": "Brother",
  "mensagens_brutas": ["Em espera"],
  "mensagens_normalizadas": ["em espera"],
  "estado_principal": "Em espera",
  "erro_codigo": null,
  "erro_detalhe_sanitizado": null,
  "metadados": {
    "parser": "brother_dcp_l1632w_status",
    "origem": "html_status"
  }
}
```

Exemplo de falha controlada:

```json
{
  "sucesso": false,
  "mensagens_brutas": [],
  "mensagens_normalizadas": [],
  "estado_principal": null,
  "erro_codigo": "html_status_nao_encontrado",
  "erro_detalhe_sanitizado": "Estado da maquina nao encontrado no HTML de status."
}
```

### Mensagens e normalizacao

`mensagens_brutas` sempre e uma lista para manter compatibilidade com o fluxo
futuro de multiplos alertas. Mesmo quando a pagina retorna apenas um estado
principal, o resultado usa uma lista, por exemplo:

```text
["Em espera"]
```

`mensagens_normalizadas` reaproveita a normalizacao da Rules Engine atual,
removendo diferencas de caixa, acentos, entidades HTML, quebras de linha e
espacos duplicados:

```text
"Em espera" -> "em espera"
```

Nesta etapa o parser nao classifica a mensagem. A classificacao pela Rules
Engine fica para a proxima microetapa de fallback HTML na cascata de alertas.

### Registry de parsers

Foi criado um registry/factory em:

```text
backend/app/modules/printers/monitoring/html_parsers/
```

Ele permite localizar o parser por fabricante/modelo usando:

```python
get_status_parser_for_model(model)
parse_status_html_for_model(model, html)
parse_html_status_response(model, html_client_response)
```

O primeiro parser registrado e `BrotherDcpL1632wStatusParser`. Modelos sem
parser retornam erro controlado `html_status_parser_nao_configurado`.

### Fixture sanitizada

A fixture versionada fica em:

```text
backend/app/modules/printers/monitoring/html_parsers/tests/fixtures/brother_dcp_l1632w_status.html
```

Ela contem apenas HTML sanitizado para teste. Nao possui IP real, senha, cookie,
CSRF, Authorization, nome de empresa real ou dado interno sensivel.

### Seguranca

O parser nao registra logs, nao persiste HTML bruto e nao inclui HTML bruto ou
segredos em erros serializados. Tambem nao acessa rede, banco ou task Celery.

### Cascata futura

A cascata planejada para a proxima etapa passa a ser:

```text
SNMP OK -> usa SNMP.
SNMP falhou -> tenta HTML autenticado.
HTML OK + parser OK -> usa mensagens HTML.
SNMP + HTML/parser falharam -> falha_coleta_alertas / vermelho.
```

## Etapa 3.5.2.8 - Diagnostico seguro dos caminhos HTML por modelo

Esta microetapa cria o diagnostico manual dos caminhos HTML cadastrados em
`credenciais_coleta_impressoras`. O objetivo e testar, por modelo e por maquina
representativa, se `caminho_status` e `caminho_informacoes` conseguem retornar
HTML util para as proximas etapas de fallback HTML e coleta rica.

O script fica em:

```bash
backend/pyteste/diagnostico_html_modelos.py
```

Ele nao roda em Celery, nao cria API publica, nao altera frontend e nao integra
HTML na cascata de alertas.

### Modo dry-run

Sem `--confirmar`, o diagnostico nao faz requisicao HTTP real. Ele lista:

- modelos com credencial ativa;
- maquina candidata por modelo;
- IP planejado;
- `caminho_status`;
- `caminho_informacoes`;
- tipo de autenticacao;
- protocolo preferencial;
- validacao SSL;
- timeout;
- parser de status disponivel ou ausente.

Execucao:

```bash
py -3.11 backend/pyteste/diagnostico_html_modelos.py
```

### Modo confirmado

Com `--confirmar`, o diagnostico usa o cliente HTML seguro existente para
consultar os caminhos configurados:

```bash
py -3.11 backend/pyteste/diagnostico_html_modelos.py --confirmar
```

Filtros disponiveis:

```bash
py -3.11 backend/pyteste/diagnostico_html_modelos.py --modelo "Brother DCP-L1632W"
py -3.11 backend/pyteste/diagnostico_html_modelos.py --maquina-id 4
py -3.11 backend/pyteste/diagnostico_html_modelos.py --incluir-offline
```

O diagnostico escolhe apenas maquinas ativas, com IP, e prefere uma maquina
online quando `status_impressoras` tiver essa informacao. Maquinas offline sao
ignoradas por padrao.

### Teste de caminho_status

Para `caminho_status`, o diagnostico monta a URL segura pelo IP da maquina e
caminho relativo, respeita `protocolo_preferencial`, `validar_ssl` e
`timeout_segundos`, usa autenticacao `basic` ou `digest`, retorna erro
controlado para `form` e `cookie`, valida `status_code`, verifica se recebeu
HTML e executa parser de status quando houver parser para o modelo.

Quando nao ha parser para o modelo, o resultado usa
`html_parser_nao_configurado`.

### Teste de caminho_informacoes

Para `caminho_informacoes`, o diagnostico nao cria parser completo. Ele apenas
faz uma deteccao segura de capacidades por termos/padroes em memoria:

- `modelo`;
- `numero_serie`;
- `firmware`;
- `contador_total`;
- `toner`;
- `tambor`;
- `papel`;
- `bandejas`;
- `paginas_por_tamanho`;
- `paginas_por_tipo`;
- `digitalizacoes`;
- `erros`.

A etapa responde se a tela parece conter as informacoes necessarias. A extracao
estruturada de valores fica para a etapa futura de coleta rica.

### Relatorios sanitizados

Quando relatorios forem gravados, ficam em:

```text
tmp/diagnosticos/html_modelos/
```

Arquivos gerados:

```text
diagnostico_html_modelos_YYYYMMDD_HHMMSS.json
diagnostico_html_modelos_YYYYMMDD_HHMMSS.md
```

`tmp/` ja e ignorado pelo Git. Os relatorios nao devem conter senha, senha
descriptografada, token criptografado completo, Authorization, Cookie, CSRF,
headers sensiveis ou HTML bruto autenticado.

### Cascata futura

A cascata planejada para a proxima etapa passa a ser:

```text
SNMP OK -> usa SNMP.
SNMP falhou -> tenta HTML autenticado.
HTML OK + parser OK -> usa mensagens HTML.
SNMP + HTML/parser falharam -> falha_coleta_alertas / vermelho.
```

## Etapa 3.5.2.9 - Diagnostico HTML real controlado por modelo

Esta microetapa executou o diagnostico HTML real, de forma controlada, usando
as credenciais e caminhos ja cadastrados em `credenciais_coleta_impressoras`.
O objetivo foi confirmar, com evidencia real de rede e relatorios
sanitizados, quais modelos conseguem acessar `caminho_status` e
`caminho_informacoes`, alem de identificar quais modelos ja possuem parser de
status aplicavel.

Ainda nao houve integracao com a cascata SNMP -> HTML, nao houve alteracao de
Celery, nao houve persistencia de alertas vindos de HTML, nao foi criada tabela
nova, nao foi criada credencial por maquina e nao foi salva nenhuma pagina
HTML bruta.

### Comandos executados

O dry-run foi executado no container `admin`:

```bash
docker compose --env-file .env.docker exec -T admin python backend/pyteste/diagnostico_html_modelos.py
```

O diagnostico real foi executado por modelo, um por vez:

```bash
docker compose --env-file .env.docker exec -T admin python backend/pyteste/diagnostico_html_modelos.py --confirmar --modelo "Brother DCP-L1632W" --saida-json --saida-md
docker compose --env-file .env.docker exec -T admin python backend/pyteste/diagnostico_html_modelos.py --confirmar --modelo "Brother DCP-L2540DW" --saida-json --saida-md
docker compose --env-file .env.docker exec -T admin python backend/pyteste/diagnostico_html_modelos.py --confirmar --modelo "Canon IR-C3326I" --saida-json --saida-md
docker compose --env-file .env.docker exec -T admin python backend/pyteste/diagnostico_html_modelos.py --confirmar --modelo "HP MFP-4303" --saida-json --saida-md
docker compose --env-file .env.docker exec -T admin python backend/pyteste/diagnostico_html_modelos.py --confirmar --modelo "HP T-2530" --saida-json --saida-md
docker compose --env-file .env.docker exec -T admin python backend/pyteste/diagnostico_html_modelos.py --confirmar --modelo "Samsung K-4350" --saida-json --saida-md
docker compose --env-file .env.docker exec -T admin python backend/pyteste/diagnostico_html_modelos.py --confirmar --modelo "Brother ADS-4700W" --saida-json --saida-md
```

### Resultado do dry-run

O dry-run encontrou sete modelos com credencial ativa:

| Modelo | Caminho status | Caminho informacoes | Parser status |
| --- | --- | --- | --- |
| Brother DCP-L1632W | configurado | configurado | disponivel |
| Brother DCP-L2540DW | configurado | configurado | sem parser |
| Canon IR-C3326I | configurado | configurado | sem parser |
| HP MFP-4303 | configurado | nao configurado | sem parser |
| HP T-2530 | nao configurado | nao configurado | sem parser |
| Samsung K-4350 | configurado | nao configurado | sem parser |
| Brother ADS-4700W | nao configurado | nao configurado | sem parser |

### Matriz real consolidada

| Modelo | Status HTML | Estado detectado | Informacoes HTML | Capacidades | Parser status |
| --- | --- | --- | --- | --- | --- |
| Brother DCP-L1632W | HTTP 200 com HTML | nao | HTTP 200 com HTML | falha | disponivel |
| Brother DCP-L2540DW | HTTP 200 com HTML | nao, sem parser | HTTP 200 com HTML | OK | sem parser |
| Canon IR-C3326I | HTTP 404 | nao executado | HTTP 404 | falha | nao executado |
| HP MFP-4303 | HTTP 200 com HTML | nao, sem parser | nao configurado | falha | sem parser |
| HP T-2530 | sem maquina elegivel | nao executado | sem maquina elegivel | falha | sem parser |
| Samsung K-4350 | HTTP 200 com HTML | nao, sem parser | nao configurado | falha | sem parser |
| Brother ADS-4700W | sem maquina elegivel | nao executado | sem maquina elegivel | falha | sem parser |

### Leitura tecnica

Modelos que ja retornaram HTML de status:

- Brother DCP-L1632W;
- Brother DCP-L2540DW;
- HP MFP-4303;
- Samsung K-4350.

Modelos que ja retornaram HTML de informacoes:

- Brother DCP-L1632W;
- Brother DCP-L2540DW.

Modelo com informacoes HTML mais promissoras nesta execucao:

- Brother DCP-L2540DW, com deteccao de modelo, numero de serie, firmware,
  contador total, toner, tambor, papel, bandejas, paginas por tamanho,
  digitalizacoes e erros.

Modelos que precisam de parser de status antes de entrar no fallback HTML:

- Brother DCP-L2540DW;
- HP MFP-4303;
- Samsung K-4350.

Modelo com parser ja disponivel, mas ainda sem estado detectado no HTML real:

- Brother DCP-L1632W.

Modelos com caminho de status ou informacoes a revisar:

- Canon IR-C3326I, pois os caminhos testados retornaram HTTP 404;
- HP MFP-4303, pois ainda nao possui `caminho_informacoes`;
- Samsung K-4350, pois ainda nao possui `caminho_informacoes`;
- HP T-2530, pois nao possui caminhos configurados e nao teve maquina
  elegivel sem `--incluir-offline`;
- Brother ADS-4700W, pois nao possui caminhos configurados e nao teve maquina
  elegivel sem `--incluir-offline`.

Nenhum modelo apresentou autenticacao `form` ou `cookie` nesta execucao. Todas
as credenciais avaliadas estavam em autenticacao suportada pelo cliente atual.

### Relatorios gerados

Os relatorios foram gerados em:

```text
tmp/diagnosticos/html_modelos/
```

Foram criados relatorios individuais por modelo e um consolidado local:

```text
diagnostico_html_modelos_20260619_112632.json
diagnostico_html_modelos_20260619_112632.md
diagnostico_html_modelos_20260619_112650.json
diagnostico_html_modelos_20260619_112650.md
diagnostico_html_modelos_20260619_112706.json
diagnostico_html_modelos_20260619_112706.md
diagnostico_html_modelos_20260619_112716.json
diagnostico_html_modelos_20260619_112716.md
diagnostico_html_modelos_20260619_112725.json
diagnostico_html_modelos_20260619_112725.md
diagnostico_html_modelos_20260619_112756.json
diagnostico_html_modelos_20260619_112756.md
diagnostico_html_modelos_20260619_112808.json
diagnostico_html_modelos_20260619_112808.md
diagnostico_html_modelos_consolidado_20260619_112927.json
diagnostico_html_modelos_consolidado_20260619_112927.md
```

Os relatorios permanecem em `tmp/`, que e ignorado pelo Git. A busca de
seguranca nos relatorios nao encontrou HTML bruto, senha, senha
criptografada completa, Authorization, Cookie, CSRF, token ou header sensivel.

### Proxima etapa recomendada

A proxima etapa deve corrigir ou completar os caminhos HTML por modelo e criar
parsers especificos antes de integrar o fallback HTML na cascata de alertas.
O primeiro candidato tecnico e o Brother DCP-L2540DW, porque retornou HTML de
status e informacoes com capacidades detectaveis.

## Etapa 3.5.2.10 - Parsers HTML minimos de status por modelo

Esta microetapa cria parsers HTML minimos para extrair somente mensagens
operacionais de status/alertas dos paineis HTML ja mapeados. O objetivo e
preparar a base para o fallback HTML futuro, sem acionar a cascata SNMP -> HTML
e sem persistir alertas vindos de HTML.

### Regra cadastral

Dados cadastrais oficiais continuam vindo das tabelas do ERP:

```text
printer_machines
printers_models
```

HTML e SNMP nao substituem nem atualizam automaticamente fabricante, modelo,
nome da maquina, IP, setor, centro de custo, numero de serie, firmware, MAC,
UUID, imagem ou qualquer descricao administrativa. Nesta etapa, HTML serve
apenas como fonte operacional para mensagens de status.

### Modelos suportados

| Modelo cadastrado | Caminho status | Porta | Parser |
| --- | --- | --- | --- |
| Brother DCP-L1632W | /home/status.html | 80 | brother_dcp_l1632w_status |
| Brother DCP-L2540DW | /general/status.html | 80 | brother_dcp_l2540dw_status |
| Canon IR-C3326I | / | 8000 | canon_ir_c3326i_status |
| Samsung K-4350 | /sws/index.sws | 80 | samsung_k4350_status |
| Samsung K4250LX | /sws/index.sws | 80 | alias do parser Samsung K-4350 |
| HP MFP-4303 | /index.html | 80 | hp_mfp_4303_status |

Foi adicionada a coluna `porta` em `credenciais_coleta_impressoras`, com valor
padrao 80 e validacao entre 1 e 65535. Isso permite configurar o Canon
IR-C3326I em HTTP na porta 8000 sem criar nova tabela e sem criar credencial
por maquina.

### Mensagens extraidas

| Modelo | Mensagens operacionais esperadas |
| --- | --- |
| Brother DCP-L1632W | `Subs. o toner`, `Substituir toner`, `Em espera`, `Dormindo`, `Pronto`, `Sem papel`, `Atolamento`, `Tampa aberta`, `Erro` |
| Brother DCP-L2540DW | `Ha pouco toner`, `Trocar Toner`, `Papel Preso`, `Trocar Cilindro`, `Ready`, `Sleep`, `Deep Sleep`, `Em espera`, `Pronto`, `Erro` |
| Canon IR-C3326I | `Ocorreu um erro.`, `O toner Magenta esta baixo.`, `O toner Amarelo esta baixo.`, `Podera ter ocorrido um erro.` |
| Samsung K-4350/K4250LX | `Erro`, `1 Alerta(s) ocorridos` |
| HP MFP-4303 | estados dos cards de papel, como `Band. 1 ... - Aviso` e `Band. 2 ... - OK` |

A prioridade interna dos parsers serve apenas para escolher
`estado_principal`:

```text
erro/vermelho > aviso/toner baixo/amarelo > ok/pronto/espera/verde
```

A Rules Engine oficial ainda nao e aplicada nesta etapa.

### Fixtures sanitizadas

Foram criadas fixtures HTML minimas e sanitizadas em:

```text
backend/app/modules/printers/monitoring/html_parsers/tests/fixtures/
```

Arquivos:

```text
brother_dcp_l1632w_status.html
brother_dcp_l2540dw_status.html
canon_ir_c3326i_status.html
samsung_k4350_status.html
hp_mfp_4303_status.html
```

As fixtures contem apenas trechos minimos para testes de parser. Elas nao
incluem senha, senha criptografada, Cookie, CSRF, Authorization, IP real, MAC
real, numero de serie real, UUID, host real, localizacao real, e-mail,
administrador, certificado, chave ou HTML bruto autenticado.

### Fora desta microetapa

Esta microetapa nao integra HTML na cascata SNMP -> HTML, nao altera
`collect_and_sync_machine_alerts`, nao altera task Celery, nao persiste alertas
HTML, nao cria API publica, nao altera frontend, nao faz coleta rica, nao
extrai contador, toner percentual, papel estruturado, numero de serie,
firmware, UUID, MAC ou qualquer dado cadastral.

Tambem nao cria nova tabela de endpoints HTML, nao cria credencial por maquina,
nao cria `tentativas_coleta_impressoras` e nao salva HTML bruto.

### Proxima etapa recomendada

A proxima etapa deve integrar o fallback HTML autenticado na cascata de alertas
de forma controlada:

```text
HTML autenticado -> parser -> mensagens_brutas -> Rules Engine -> sincronizacao de alertas
```

### Diagnostico real apos parsers minimos

Depois da criacao dos parsers minimos, foi executado novo diagnostico real com
`--confirmar`, usando os caminhos, porta e credenciais ja cadastrados no banco,
o cliente HTML seguro e os parsers disponiveis.

Comando executado:

```bash
docker compose --env-file .env.docker exec -T admin python backend/pyteste/diagnostico_html_modelos.py --confirmar --saida-json --saida-md
```

Relatorios sanitizados gerados localmente em `tmp/diagnosticos/html_modelos/`:

```text
diagnostico_html_modelos_20260619_144004.json
diagnostico_html_modelos_20260619_144004.md
```

Matriz real consolidada:

| Modelo | Status HTML | Estado detectado | Informacoes HTML | Parser status | Observacao |
| --- | --- | --- | --- | --- | --- |
| Brother DCP-L1632W | HTTP 200 com HTML | nao detectado | HTTP 200 sem capacidades detectadas | disponivel | parser precisa ser refinado contra HTML real |
| Canon IR-C3326I | HTTP 200 com HTML na porta 8000 | nao detectado | HTTP 200 sem capacidades detectadas | disponivel | caminho/HTML real difere da fixture minima |
| Brother DCP-L2540DW | OK | Trocar Cilindro | OK | disponivel | pronto para proxima avaliacao de fallback |
| HP MFP-4303 | HTTP 200 com HTML | nao detectado | HTTP 200 sem capacidades detectadas | disponivel | parser precisa ser refinado contra HTML real |
| HP T-2530 | sem maquina elegivel | nao executado | sem maquina elegivel | sem parser | manter fora ate haver alvo elegivel |
| Samsung K-4350 | HTTP 200 com HTML | nao detectado | nao configurado | disponivel | parser precisa ser refinado contra HTML real |
| Brother ADS-4700W | sem maquina elegivel | nao executado | sem maquina elegivel | sem parser | manter fora ate haver alvo elegivel |

Leitura tecnica:

- O primeiro modelo com parser e extracao real bem-sucedida foi Brother
  DCP-L2540DW, com estado principal `Trocar Cilindro`.
- Brother DCP-L1632W, Canon IR-C3326I, HP MFP-4303 e Samsung K-4350 acessaram
  HTML real, mas os parsers minimos ainda nao reconheceram mensagens no HTML
  recebido.
- O Canon IR-C3326I passou a responder HTTP 200 usando porta 8000 e caminho
  `/`, confirmando que o suporte a porta esta funcionando no cliente.
- Os relatorios continuaram sanitizados; a busca de seguranca nao encontrou
  HTML bruto, senha, Authorization, Cookie, CSRF, token ou senha criptografada.
- Nao houve integracao com a cascata, nao houve persistencia de alertas HTML,
  nao houve alteracao de Celery/task, nao houve alteracao da Rules Engine e nao
  houve ampliacao para coleta rica.

## Etapa 3.5.2.11 - Diagnostico real dos parsers HTML minimos

Esta microetapa validou, com acesso real controlado, se os parsers HTML
minimos conseguem detectar o estado operacional dos modelos ja mapeados. A
etapa foi apenas diagnostica: HTML ainda nao foi integrado na cascata SNMP ->
HTML, alertas HTML nao foram persistidos, Celery/task nao foi alterado, Rules
Engine nao foi alterada e nao houve ampliacao para coleta rica.

Branch usada:

```text
feature/printers-html-parsers-real-diagnostic
```

Base usada:

```text
feature/printers-html-status-parsers-minimal
commit base: 71d3593
parsers minimos: d3436e0
```

Comando executado:

```bash
docker compose --env-file .env.docker exec -T admin python backend/pyteste/diagnostico_html_modelos.py --confirmar --saida-json --saida-md
```

Relatorios sanitizados gerados localmente em pasta ignorada pelo Git:

```text
tmp/diagnosticos/html_modelos/diagnostico_html_modelos_20260619_160542.json
tmp/diagnosticos/html_modelos/diagnostico_html_modelos_20260619_160542.md
```

### Resultado sanitizado

| Modelo cadastrado | Maquina analisada | Caminho status | Porta | Parser | Resultado status | Estado principal | Resultado informacoes | Observacao |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Brother DCP-L1632W | MAQUINA_BROTHER_L1632W | /home/status.html | 80 | disponivel | html_status_nao_detectado | - | html_capacidades_nao_detectadas | parser precisa refinamento contra HTML real |
| Canon IR-C3326I | MAQUINA_CANON_IR_C3326I | / | 8000 | disponivel | html_status_nao_detectado | - | html_capacidades_nao_detectadas | porta 8000 confirmada; parser precisa refinamento |
| Brother DCP-L2540DW | MAQUINA_BROTHER_L2540DW | /general/status.html | 80 | disponivel | OK | Trocar Cilindro | OK | parser passou com HTML real |
| HP MFP-4303 | MAQUINA_HP_MFP_4303 | /index.html | 80 | disponivel | html_status_nao_detectado | - | html_capacidades_nao_detectadas | parser precisa refinamento contra HTML real |
| Samsung K-4350 | MAQUINA_SAMSUNG_K4350 | /sws/index.sws | 80 | disponivel | html_status_nao_detectado | - | html_caminho_informacoes_nao_configurado | parser precisa refinamento contra HTML real |

Tambem foram listados modelos sem alvo elegivel ou sem parser configurado,
apenas como diagnostico cadastral, sem ampliar o escopo desta etapa.

### Decisoes e seguranca

- Os dados cadastrais continuam vindo das tabelas do ERP.
- O diagnostico usa identificador de maquina sanitizado e nao grava IP real no
  relatorio.
- A senha criptografada e descriptografada somente em memoria pelo fluxo ja
  existente.
- O script manual silencia apenas o aviso de certificado self-signed do
  `urllib3`, evitando que o console exponha IP real durante o diagnostico.
- A busca de seguranca no JSON/Markdown gerado nao encontrou HTML bruto, senha,
  Authorization, Cookie, CSRF, token, senha criptografada, nome real de maquina
  ou IP real.
- Nao houve migration, tabela nova, credencial por maquina ou
  `tentativas_coleta_impressoras`.

### Proxima etapa recomendada

Refinar os parsers minimos contra o HTML real dos modelos que retornaram
`html_status_nao_detectado`, com prioridade para manter o escopo em mensagens
operacionais. A integracao com a cascata deve continuar para uma etapa futura,
quando os parsers estiverem suficientemente confiaveis.

## Etapa 3.5.2.12 - Refinamento dos parsers HTML minimos com base no diagnostico real

Esta microetapa refinou os parsers HTML minimos a partir do diagnostico real
da etapa 3.5.2.11. O objetivo foi melhorar a tolerancia dos parsers a
estruturas reais de tela, sem integrar HTML na cascata SNMP -> HTML e sem
persistir alertas HTML.

Branch usada:

```text
feature/printers-html-parsers-real-fixes
```

Base usada:

```text
feature/printers-html-parsers-real-diagnostic
commit base: 6df6fc2
```

### Ajustes feitos

- Brother DCP-L1632W: parser passa a procurar mensagens conhecidas em janelas
  de texto, cobrindo label e valor separados em varios elementos.
- Canon IR-C3326I: parser passa a procurar mensagens em janelas de texto e
  continua ignorando `Scanner: Modo de espera` como estado principal quando ha
  erro da impressora.
- HP MFP-4303: parser passa a limpar labels de card, como `Status`, `Papel` e
  `Cartuchos`, preservando somente bandeja e estado operacional.
- Samsung K-4350/K4250LX: parser passa a aceitar `Estado`/`Alerta` e seus
  valores em elementos separados.
- Diagnostico HTML: em falhas de parser, o relatorio agora inclui somente
  amostras de texto visivel sanitizadas, candidatos de status, labels seguros
  e motivo provavel da falha. O diagnostico nao salva HTML bruto.
- Fixtures sinteticas e sanitizadas foram adicionadas para os formatos reais
  esperados, sem dados reais, IP, MAC, serial, credencial, host ou localizacao.

### Resultado anterior

| Modelo | Resultado anterior |
| --- | --- |
| Brother DCP-L1632W | html_status_nao_detectado |
| Canon IR-C3326I | html_status_nao_detectado |
| Brother DCP-L2540DW | OK, estado `Trocar Cilindro` |
| HP MFP-4303 | html_status_nao_detectado |
| Samsung K-4350 | html_status_nao_detectado |

### Novo diagnostico real

Comando executado:

```bash
docker compose --env-file .env.docker exec -T admin python backend/pyteste/diagnostico_html_modelos.py --confirmar --saida-json --saida-md
```

Relatorios sanitizados gerados localmente em pasta ignorada pelo Git:

```text
tmp/diagnosticos/html_modelos/diagnostico_html_modelos_20260619_165037.json
tmp/diagnosticos/html_modelos/diagnostico_html_modelos_20260619_165037.md
```

| Modelo cadastrado | Maquina analisada | Porta | Parser | Resultado novo | Estado principal | Motivo sanitizado |
| --- | --- | --- | --- | --- | --- | --- |
| Brother DCP-L1632W | MAQUINA_BROTHER_L1632W | 80 | disponivel | html_status_nao_detectado | - | texto visivel sem padrao de estado; caminho retornou `Device Status` e `Toner Level`, sem mensagem operacional de estado |
| Canon IR-C3326I | MAQUINA_CANON_IR_C3326I | 8000 | disponivel | html_status_nao_detectado | - | raiz `/` retornou tela inicial/autenticacao sem texto operacional de status |
| Brother DCP-L2540DW | MAQUINA_BROTHER_L2540DW | 80 | disponivel | OK | Trocar Cilindro | parser continua funcionando |
| HP MFP-4303 | MAQUINA_HP_MFP_4303 | 80 | disponivel | html_status_nao_detectado | - | `/index.html` retornou shell do EWS sem cards operacionais visiveis |
| Samsung K-4350 | MAQUINA_SAMSUNG_K4350 | 80 | disponivel | html_status_nao_detectado | - | `/sws/index.sws` retornou shell/carregamento e selecao de idioma, sem estado/alerta visivel |

### Leitura tecnica

- Os parsers refinados passaram nos testes com fixtures sinteticas que simulam
  os formatos esperados.
- O diagnostico real final mostrou que as falhas restantes nao decorrem apenas
  do parser: os caminhos atuais de Brother DCP-L1632W, Canon IR-C3326I,
  HP MFP-4303 e Samsung K-4350 nao entregaram texto operacional suficiente para
  extrair `estado_principal`.
- O Brother DCP-L2540DW continuou funcionando no HTML real.
- A busca de seguranca no JSON/Markdown final nao encontrou HTML bruto, senha,
  Authorization, Cookie, CSRF, token, senha criptografada, nome real de
  maquina, IP real ou setor real.

### Proxima etapa recomendada

Validar caminhos HTML de status que entreguem texto operacional real para os
modelos ainda pendentes. O primeiro foco deve ser encontrar endpoint seguro de
status para Canon, HP e Samsung sem usar parametros dinamicos artificiais e sem
coleta rica. A integracao com a cascata deve continuar fora do escopo ate que
os caminhos e parsers estejam confiaveis.

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
final, nao cria API publica, nao altera frontend e nao persiste HTML bruto. A
etapa 3.5.2.7 cria apenas o parser HTML de status por modelo em memoria; ela
nao integra HTML na cascata de alertas, nao cria tabela nova, nao cria
credencial por maquina, nao cria `tentativas_coleta_impressoras`, nao altera
Celery, nao cria API publica, nao altera frontend e nao persiste HTML bruto. A
etapa 3.5.2.8 cria apenas o diagnostico seguro dos caminhos HTML cadastrados,
com dry-run obrigatorio por padrao e relatorios sanitizados; ela nao integra
HTML na cascata, nao cria tabela nova, nao cria credencial por maquina, nao
cria `tentativas_coleta_impressoras`, nao altera Celery, nao cria API publica,
nao altera frontend e nao persiste HTML bruto. A etapa 3.5.2.9 executa o
diagnostico HTML real controlado por modelo e documenta uma matriz consolidada,
mas ainda nao integra HTML na cascata, nao cria parser novo, nao cria tabela
nova, nao cria credencial por maquina, nao cria `tentativas_coleta_impressoras`,
nao altera Celery, nao cria API publica, nao altera frontend, nao persiste
alertas HTML e nao salva HTML bruto. A etapa 3.5.2.10 cria apenas parsers HTML
minimos de status por modelo e suporte a porta na credencial HTML; ela ainda
nao integra HTML na cascata, nao altera Celery, nao persiste alertas HTML, nao
cria API publica, nao altera frontend, nao cria nova tabela de endpoints, nao
cria credencial por maquina, nao cria `tentativas_coleta_impressoras`, nao
extrai coleta rica e nao salva HTML bruto. A etapa 3.5.2.11 executa somente o
diagnostico real dos parsers HTML minimos; ela nao integra HTML na cascata, nao
persiste alertas HTML, nao altera Celery/task, nao altera Rules Engine, nao cria
tabela nova, nao cria credencial por maquina, nao cria
`tentativas_coleta_impressoras`, nao extrai dados cadastrais do HTML/SNMP e nao
salva HTML bruto. A etapa 3.5.2.12 refina apenas parsers minimos, fixtures
sinteticas e diagnostico sanitizado; ela nao integra HTML na cascata, nao
persiste alertas HTML, nao altera Celery/task, nao altera Rules Engine, nao cria
tabela nova, nao cria credencial por maquina, nao cria
`tentativas_coleta_impressoras`, nao extrai dados cadastrais do HTML/SNMP e nao
salva HTML bruto.

## Próximas etapas

- integrar o fallback HTML autenticado na cascata de alertas;
- expor consultas publicas dos alertas quando houver necessidade de frontend;
- 3.5.3: coleta rica em 60 minutos;
- 3.5.4: papel, toner e históricos;
- 3.5.5: dashboard.
