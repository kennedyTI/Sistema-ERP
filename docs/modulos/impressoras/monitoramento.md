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

O seed oficial é idempotente: cria as regras iniciais quando ausentes e
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

## Etapa 3.5.2.13 - Refinamento HTML Brother DCP-L1632W para alerta/status

Esta microetapa refinou especificamente o suporte HTML da Brother DCP-L1632W
usando os trechos reais informados de forma sanitizada. O foco continuou sendo
alerta/status da etapa 3.5.2: ainda nao foi aberta a etapa 3.5.3 de coleta
rica, HTML nao foi integrado na cascata SNMP -> HTML e nenhum dado foi
persistido em tabelas definitivas.

Branch usada:

```text
feature/printers-html-brother-l1632w-status-refine
```

Base usada:

```text
feature/printers-html-parsers-real-fixes
commit base: d6fbcc4
```

### HTMLs analisados de forma sanitizada

Foram usadas fixtures sinteticas, derivadas somente dos trechos relevantes:

```text
backend/app/modules/printers/monitoring/html_parsers/tests/fixtures/brother_dcp_l1632w_status_real_shape.html
backend/app/modules/printers/monitoring/html_parsers/tests/fixtures/brother_dcp_l1632w_maintenance_real_shape.html
```

A fixture de status contem apenas:

- `Estado do dispositivo` com valor `Em espera`;
- bloco `Nivel do toner`;
- label `BK`;
- indicador de barra/imagem `tonerremain`.

A fixture de manutencao contem apenas:

- `Total de paginas impressas > A4/Letter`;
- `Vida util restante > Unidade de tambor*`;
- `Vida util restante > Toner**`.

Nao foram versionados HTML bruto, IP real, serial real, token de formulario,
firmware real, localizacao real, URL absoluta real, credencial, Cookie ou
Authorization.

### Ajustes feitos

- O parser `BrotherDcpL1632wStatusParser` passou a ler a estrutura `dt/dd`.
- Para `Estado do dispositivo`, ele procura o `dt`, pega o `dd` seguinte e
  prefere o texto em `#moni_data .moni`.
- O estado extraido entra como primeira mensagem bruta e como
  `estado_principal`.
- O bloco `Nivel do toner` e detectado como metadado auxiliar.
- Labels como `BK` sao registradas em metadados.
- A barra/imagem de toner nao e convertida em percentual; `height=16` nao e
  usado como medida de toner.
- Foi criada a funcao `parse_brother_dcp_l1632w_maintenance_info`, limitada aos
  campos auxiliares permitidos.

Metadados esperados para status:

```json
{
  "nivel_toner_bloco_detectado": true,
  "nivel_toner_labels": ["BK"],
  "nivel_toner_percentual_disponivel": false
}
```

Informacao de manutencao esperada em fixture:

```json
{
  "total_paginas_impressas_a4_letter": 4556,
  "unidade_tambor_percentual": 55,
  "toner_percentual": 30
}
```

Esses campos sao apoio diagnostico. Eles nao atualizam cadastro e nao foram
persistidos como toner, tambor ou contador oficial.

### Resultado do diagnostico real

Comando executado:

```bash
docker compose --env-file .env.docker exec -T admin python backend/pyteste/diagnostico_html_modelos.py --confirmar --modelo "Brother DCP-L1632W" --saida-json --saida-md
```

Relatorios sanitizados gerados localmente em pasta ignorada pelo Git:

```text
tmp/diagnosticos/html_modelos/diagnostico_html_modelos_20260622_164521.json
tmp/diagnosticos/html_modelos/diagnostico_html_modelos_20260622_164521.md
```

| Item | Resultado |
| --- | --- |
| Caminho status | acessado pelo cliente HTML seguro |
| Parser | `brother_dcp_l1632w_status` |
| Estado operacional real | ainda nao detectado no caminho cadastrado |
| Bloco de toner | detectado |
| Label de toner | `BK` |
| Percentual por imagem/barra | nao calculado |
| Caminho informacoes | acessado, mas sem campos de manutencao reconhecidos no HTML retornado |
| Seguranca do relatorio | sem HTML bruto, IP real, senha, Cookie, Authorization, token de formulario, serial real ou localizacao real |

O parser passa nos testes com o formato real sanitizado informado. O
diagnostico real atual, porem, ainda nao recebeu no endpoint cadastrado o bloco
`Estado do dispositivo -> Em espera` nem a estrutura de manutencao com
`A4/Letter`, `Unidade de tambor*` e `Toner**`. Por isso, a leitura real ficou
como falha controlada para estado/manutencao, mas ja registrou o bloco de toner
`BK` sem inventar percentual.

### Proxima etapa recomendada

Validar se os caminhos cadastrados para a DCP-L1632W estao apontando para as
mesmas telas dos HTMLs reais enviados. Se necessario, ajustar somente o caminho
seguro que entrega `Estado do dispositivo` e a tela de manutencao esperada,
sem introduzir scraping agressivo, coleta rica ou persistencia.

## Etapa 3.5.2.14 - Ajuste de autenticacao HTML Brother DCP-L1632W

Esta microetapa ajustou o diagnostico/coleta HTML da Brother DCP-L1632W para
diferenciar pagina autenticada, pagina de login e pagina parcial/sem sessao
valida. O objetivo foi explicar por que o parser ja passa com o shape correto,
mas o diagnostico real ainda nao recebe o mesmo conteudo operacional visto no
navegador.

HTML continua fora da cascata SNMP -> HTML. Nenhum alerta HTML, toner, tambor
ou contador foi persistido.

Branch usada:

```text
feature/printers-html-brother-l1632w-auth-flow
```

Base usada:

```text
feature/printers-html-brother-l1632w-status-refine
commit base: 81331e7
```

### Problema identificado

A etapa 3.5.2.13 deixou o parser pronto para o HTML real sanitizado da
Brother DCP-L1632W, mas o diagnostico real ainda recebia uma pagina diferente
daquela salva pelo navegador.

Nesta etapa, o diagnostico passou a registrar um `auth_state` sanitizado para
separar:

- pagina autenticada com `#moni_data .moni`;
- pagina que exige login com `#LogInOutBox` e `#LogBox`;
- pagina parcial/sem sessao valida, quando ha marcadores Brother mas falta o
  texto operacional.

### Seletores de autenticacao, status e manutencao

Seletores de autenticacao:

- `#LogInOutBox`;
- `input#LogBox`;
- hidden `CSRFToken`, detectado apenas como booleano.

Seletores de status:

- `#moni_data`;
- `#moni_data .moni`;
- fallback por `dt Estado do dispositivo` e `dd` seguinte;
- bloco `Nivel do toner`;
- `#ink_level`;
- `#inkLevelMono`;
- `.tonerremain`;
- label `BK`.

Seletores de manutencao:

- `dl.items`;
- `dl.items_info_1line`;
- `Unidade de tambor*`;
- `Toner**`;
- `Contador pag.`;
- `Total de paginas impressas > A4/Letter`.

### Fluxo seguro e classificador Brother

O tipo de autenticacao `form`, ja existente em `credenciais_coleta_impressoras`,
representa o fluxo minimo e controlado da Brother. Nao houve migration, tabela
nova ou credencial por maquina.

O cliente HTML seguro executa:

```text
GET caminho_login ou caminho_status
detecta #LogInOutBox
detecta form dentro do container
detecta input #LogBox
coleta hidden inputs
valida action do form
POST com senha somente em memoria
mantem cookies somente na sessao em memoria
GET da pagina alvo
```

O `action` do formulario aceita caminhos relativos seguros. Actions absolutos
so sao aceitos quando apontam para o mesmo host e porta da maquina consultada.
Actions para outro host sao rejeitados com erro controlado.

O parser Brother ganhou o helper `classify_brother_html_auth_state`, que retorna
somente flags sanitizadas:

```json
{
  "autenticado": false,
  "login_requerido": false,
  "tem_log_in_out_box": true,
  "tem_logbox": false,
  "tem_csrf": true,
  "tem_moni_data": true,
  "tem_status_moni": false,
  "erro_codigo": "html_sessao_brother_invalida"
}
```

Regras aplicadas:

- se houver `#moni_data .moni` com texto, a pagina e considerada autenticada e
  util para status;
- se houver `#LogInOutBox` + `#LogBox` sem `#moni_data .moni`, o erro e
  `html_autenticacao_requerida`;
- se houver marcadores Brother, mas sem `.moni` operacional, o erro e
  `html_sessao_brother_invalida`;
- valores de CSRF, senha, cookie, Authorization e HTML bruto nunca entram no
  resultado.

O diagnostico tambem registra os metadados do fluxo de login sem valores:

```json
{
  "login_container_detected": true,
  "login_form_detected": true,
  "login_container_id": "LogInOutBox",
  "password_input_detected": true,
  "password_input_id": "LogBox",
  "csrf_detected": false,
  "hidden_fields_count": 1,
  "post_executado": true,
  "cookies_recebidos": true
}
```

### Fixtures e testes

Foram criadas fixtures sinteticas e sanitizadas em:

```text
backend/app/modules/printers/monitoring/html_parsers/tests/fixtures/brother_dcp_l1632w_status_authenticated.html
backend/app/modules/printers/monitoring/html_parsers/tests/fixtures/brother_dcp_l1632w_status_login_required.html
backend/app/modules/printers/monitoring/html_parsers/tests/fixtures/brother_dcp_l1632w_maintenance_authenticated.html
backend/app/modules/printers/monitoring/html_client/tests/fixtures/brother_l1632w_login_form.html
backend/app/modules/printers/monitoring/html_client/tests/fixtures/brother_l1632w_authenticated_status.html
```

Elas contem apenas a estrutura minima do formulario e da pagina autenticada.
Nao ha IP real, token real, senha, cookie, serial, MAC, hostname ou HTML bruto
salvo do navegador.

Os testes unitarios cobrem:

- classificacao de pagina autenticada, login requerido e sessao parcial;
- deteccao de `#LogInOutBox`;
- deteccao de `#LogBox`;
- deteccao de `CSRFToken` sem retorno de valor;
- uso de `#moni_data .moni` como seletor principal de estado;
- aceitacao de classes `moni`, `moniOk`, `moniWarning` ou equivalentes;
- fallback por `dt Estado do dispositivo`;
- deteccao de bloco de toner e label `BK`;
- nao conversao de `height=16` em percentual;
- extracao controlada de `Contador pag.`, `A4/Letter`, tambor e toner;
- exclusao de campos cadastrais como serial, firmware e localizacao;
- captura controlada de hidden inputs no fluxo de login;
- uso do atributo `name` do input de senha no payload;
- POST para action relativo seguro;
- rejeicao de action absoluto para host externo;
- ausencia de formulario como pagina ja autenticada ou sem formulario;
- erro controlado quando o input de senha nao existe;
- ausencia de senha, token, cookie, Authorization e HTML bruto no resultado;
- propagacao dos metadados sanitizados para o diagnostico;
- regressao dos parsers Brother DCP-L1632W.

Resultado focado:

```text
82 passed
```

Resultado completo desta branch:

```text
py -3.11 -m compileall -q backend
py -3.11 -m pytest -q
316 passed, 38 warnings
py -3.11 manage.py check
System check identified no issues
npm.cmd audit
found 0 vulnerabilities
npm.cmd run build
OK, com aviso conhecido de chunks grandes do Vite
```

### Resultado do diagnostico real

Antes da validacao real, a credencial ativa da Brother DCP-L1632W ainda estava
como `basic`. Para acionar o novo fluxo, o cadastro local do modelo foi
ajustado para:

```text
tipo_autenticacao=form
caminho_login=/home/status.html
```

A senha criptografada existente nao foi alterada, nao foi exibida e nenhuma
credencial por maquina foi criada.

Comando executado:

```bash
docker compose --env-file .env.docker exec -T admin python backend/pyteste/diagnostico_html_modelos.py --confirmar --modelo "Brother DCP-L1632W" --saida-json --saida-md
```

Relatorios sanitizados gerados localmente em pasta ignorada pelo Git:

```text
tmp/diagnosticos/html_modelos/diagnostico_html_modelos_20260623_115211.json
tmp/diagnosticos/html_modelos/diagnostico_html_modelos_20260623_115211.md
```

| Item | Resultado |
| --- | --- |
| Login por formulario | executado |
| Container `#LogInOutBox` | detectado |
| Formulario de login | detectado |
| Input `#LogBox` | detectado |
| Hidden fields | 1 campo detectado |
| POST do login | executado |
| Cookies de sessao | recebidos em memoria |
| `#moni_data` | detectado |
| `#moni_data .moni` | nao detectado |
| Estado do dispositivo | nao detectado |
| Auth state | `html_sessao_brother_invalida` |
| Nivel do toner | bloco detectado |
| Label de toner | `BK` |
| Percentual por imagem/barra | nao calculado |
| Manutencao `dl.items` | detectado |
| Manutencao `dl.items_info_1line` | detectado |
| A4/Letter | detectado como marcador |
| Contador/tambor/toner controlados | nao extraidos em `maintenance_info` real |
| HTML bruto/segredos no relatorio | nao encontrados |

O fluxo de login por formulario foi acionado corretamente. O diagnostico real,
porem, mostrou que a pagina de status retornada depois do POST fica em estado
parcial para a leitura operacional: ha `#LogInOutBox`, ha CSRF e ha
`#moni_data`, mas nao ha texto em `.moni`. Por isso o erro correto passou a ser
`html_sessao_brother_invalida`, em vez de uma falha generica do parser.

A pagina de informacoes retornou marcadores de manutencao, incluindo
`dl.items`, `dl.items_info_1line` e `A4/Letter`, mas os campos permitidos ainda
nao vieram no formato necessario para preencher:

```json
{
  "maintenance_info": {}
}
```

### Limites preservados

Esta etapa nao integrou HTML na cascata SNMP -> HTML, nao alterou
`collect_and_sync_machine_alerts`, nao alterou
`sync_machine_alerts_from_collection_result`, nao alterou Rules Engine, nao
alterou Celery/task, nao persistiu alertas HTML, nao gravou em
`alertas_impressoras`, nao gravou em `historico_alertas_impressoras`, nao
persistiu toner, tambor ou contador, nao criou API publica, nao criou
frontend, nao criou tabela nova, nao criou credencial por maquina, nao criou
`tentativas_coleta_impressoras`, nao salvou HTML bruto e nao usou HTML/SNMP
para alterar dados cadastrais.

### Proxima etapa recomendada

Descobrir, ainda de forma sanitizada, se o navegador faz uma requisicao
adicional apos o POST para preencher `.moni` dentro de `#moni_data`, ou se a
Brother exige algum parametro/cookie adicional de sessao. A proxima etapa deve
continuar diagnostica, sem salvar HTML bruto e sem integrar HTML na cascata.

## Etapa 3.5.2.15 - Comparacao segura do HTML Brother DCP-L1632W retornado

Esta microetapa comparou, de forma sanitizada, o shape esperado do HTML salvo
com o HTML retornado pelo diagnostico real da Brother DCP-L1632W. O foco foi
explicar por que o seletor prioritario `#moni_data .moni` existe no HTML de
referencia, mas o diagnostico real ainda nao extrai estado operacional.

Branch usada:

```text
feature/printers-html-brother-l1632w-status-compare
```

Base usada:

```text
feature/printers-html-brother-l1632w-auth-flow
commit base: ec32b79
```

HTML continua fora da cascata SNMP -> HTML. Nenhum alerta HTML, toner, tambor
ou contador foi persistido. Dados cadastrais continuam vindo das tabelas do
ERP, sem sobrescrita por HTML ou SNMP.

### Problema investigado

O HTML salvo pelo navegador continha o shape esperado:

```html
<div id="moni_data">
  <span class="moni moniOk">Em espera</span>
</div>
```

O diagnostico real anterior indicava `#moni_data` detectado, mas sem mensagem
operacional extraida. Nesta etapa, o diagnostico passou a registrar o shape
seguro de `#moni_data`:

- existencia de `#moni_data`;
- existencia de elemento com classe contendo `moni`;
- existencia de `span`;
- tags filhas;
- classes filhas;
- preview textual sanitizado e limitado;
- termos operacionais conhecidos detectados;
- comparacao entre shape esperado e shape real.

Nenhum HTML bruto, cookie, senha, Authorization, CSRF, IP, MAC ou serial entra
no relatorio.

### Fallbacks do parser Brother

A regra atual do parser da Brother DCP-L1632W ficou:

1. procurar primeiro `#moni_data .moni`;
2. aceitar qualquer classe que contenha `moni`, como `moni`, `moniOk`,
   `moniWarning` e `moniError`;
3. aceitar qualquer tag com essa classe, como `span`, `div` ou `p`;
4. se `#moni_data` existir sem classe `moni`, tentar texto visivel direto do
   proprio `#moni_data`;
5. se ainda nao houver estado, usar `dt Estado do dispositivo` e o `dd`
   seguinte como fallback final;
6. se houver `input#LogBox` sem estado, retornar
   `html_autenticacao_requerida`;
7. se `#moni_data` vier vazio ou sem texto operacional, retornar
   `html_sessao_brother_invalida`.

### Diagnostico sanitizado adicionado

O relatorio passou a incluir:

```json
{
  "moni_data_debug": {
    "tem_moni_data": true,
    "tem_moni_class": true,
    "tem_span": true,
    "tags_filhas": ["span"],
    "classes_filhas": ["moni", "moniOk"],
    "texto_visivel_preview": "",
    "texto_visivel_tamanho": 0,
    "parece_vazio": true
  },
  "status_terms_detected": [],
  "comparacao_shape_moni_data": {
    "expected_shape": {
      "seletor_prioritario": "#moni_data .moni",
      "esperado": true
    },
    "actual_shape": {
      "tem_moni_data": true,
      "tem_moni_class": true,
      "tem_texto_operacional": false
    },
    "provavel_causa": "moni_data_vazio"
  }
}
```

Tambem foi adicionado debug de manutencao para explicar marcadores presentes
sem extrair campos sensiveis ou cadastrais:

```json
{
  "maintenance_debug": {
    "tem_dl_items": true,
    "tem_dl_items_info_1line": true,
    "labels_detectados": ["Toner**", "A4/Letter"],
    "campos_extraidos": {
      "contador_paginas": false,
      "total_paginas_impressas_a4_letter": false,
      "unidade_tambor_percentual": false,
      "toner_percentual": false
    }
  }
}
```

### Fixtures e testes

Foram adicionadas fixtures sinteticas e sanitizadas para cobrir:

- `#moni_data` com `span.moni`;
- `#moni_data` com `div.moni`;
- `#moni_data` com texto direto sem classe;
- `#moni_data` vazio.

Os testes cobrem extracao de `Em espera`, `Toner baixo`, classes `moniOk`,
`moniWarning`, `moniError` e `moni`, fallback por texto direto, fallback por
`dt Estado do dispositivo`, erro `html_autenticacao_requerida`, erro
`html_sessao_brother_invalida`, diagnostico de tags/classes e sanitizacao de
preview sem HTML bruto ou segredos.

### Resultado do diagnostico real

Comando executado:

```bash
docker compose --env-file .env.docker exec -T admin python backend/pyteste/diagnostico_html_modelos.py --confirmar --modelo "Brother DCP-L1632W" --saida-json --saida-md
```

Relatorios sanitizados gerados localmente em pasta ignorada pelo Git:

```text
tmp/diagnosticos/html_modelos/diagnostico_html_modelos_20260623_131903.json
tmp/diagnosticos/html_modelos/diagnostico_html_modelos_20260623_131903.md
```

Resultado controlado:

| Item | Resultado |
| --- | --- |
| `#moni_data` | detectado |
| Classe contendo `moni` | detectada |
| `span` dentro de `#moni_data` | detectado |
| Classes filhas | `moni`, `moniOk` |
| Texto visivel dentro de `#moni_data` | vazio |
| Termo operacional conhecido | nao detectado |
| Estado principal | nao detectado |
| Erro controlado | `html_sessao_brother_invalida` |
| Causa sanitizada | `moni_data_vazio` |
| `maintenance_info` real | `{}` |
| HTML bruto/segredos | nao versionados e nao expostos |

O diagnostico real mostrou que o shape estrutural esperado esta presente, mas
o elemento operacional retornou sem texto visivel. A falha restante, portanto,
nao e falta de seletor: e ausencia de mensagem operacional no HTML retornado ao
cliente seguro naquele fluxo.

### Validacoes

Resultados executados nesta microetapa:

```text
py -3.11 -m pytest -q backend/app/modules/printers/monitoring/html_parsers/tests/test_status_parsers.py backend/app/modules/printers/monitoring/html_diagnostics/tests/test_html_paths_diagnostic.py
68 passed

py -3.11 -m compileall -q backend/app/modules/printers/monitoring/html_parsers backend/app/modules/printers/monitoring/html_diagnostics
OK

py -3.11 -m compileall -q backend
OK

py -3.11 -m pytest -q
328 passed, 38 warnings

py -3.11 manage.py check
System check identified no issues

npm.cmd audit
found 0 vulnerabilities

npm.cmd run build
OK, com aviso conhecido de chunks grandes do Vite

docker compose --env-file .env.docker up -d --no-build
OK

docker compose --env-file .env.docker ps -a
migrations Exited (0); stack Up
```

### Limites preservados

Esta etapa nao integrou HTML na cascata SNMP -> HTML, nao alterou
`collect_and_sync_machine_alerts`, nao alterou
`sync_machine_alerts_from_collection_result`, nao alterou Rules Engine, nao
alterou Celery/task, nao persistiu alertas HTML, nao gravou em
`alertas_impressoras`, nao gravou em `historico_alertas_impressoras`, nao
persistiu toner, tambor ou contador, nao criou API publica, nao criou
frontend, nao criou tabela nova, nao criou credencial por maquina, nao criou
`tentativas_coleta_impressoras`, nao salvou HTML bruto e nao usou HTML/SNMP
para alterar dados cadastrais.

### Proxima etapa recomendada

Investigar, ainda com relatorios sanitizados, se a Brother preenche o texto de
`.moni` por requisicao assincrona, parametro adicional ou estado de sessao
posterior ao login. Essa proxima etapa deve continuar diagnostica e nao deve
integrar HTML na cascata nem persistir alertas.

## Etapa 3.5.2.16 - Descoberta da atualizacao dinamica do status Brother DCP-L1632W

Esta microetapa investigou, de forma segura e sanitizada, se o texto de status
da Brother DCP-L1632W e preenchido por JavaScript, chamada assincrona ou fluxo
dinamico posterior ao carregamento inicial da pagina.

Branch usada:

```text
feature/printers-html-brother-l1632w-dynamic-status
```

Base usada:

```text
feature/printers-html-brother-l1632w-status-compare
commit base: 6454e58
```

O objetivo foi descobrir a origem do preenchimento de:

```html
<div id="moni_data">
  <span class="moni moniOk">...</span>
</div>
```

sem salvar HTML bruto, sem salvar JS bruto, sem expor credenciais e sem
integrar o HTML na cascata SNMP -> HTML.

### Problema identificado

A etapa 3.5.2.15 confirmou que o HTML retornado ao cliente seguro continha:

- `#moni_data`;
- `span.moni.moniOk`;
- texto visivel vazio;
- causa sanitizada `moni_data_vazio`.

Como o HTML salvo pelo navegador mostrava `Em espera` dentro do mesmo `span`, a
hipotese desta etapa foi que o texto poderia ser preenchido por JavaScript,
chamada assincrona, cookie/sessao complementar ou parametro adicional.

### Diagnostico opt-in

Foi criada a opcao opt-in:

```bash
python backend/pyteste/diagnostico_html_modelos.py --confirmar --modelo "Brother DCP-L1632W" --diagnosticar-status-dinamico
```

O diagnostico dinamico:

- reutiliza a mesma sessao/cookies em memoria do login Brother;
- lista scripts referenciados pela pagina de status;
- baixa scripts apenas em memoria;
- resume termos encontrados sem gravar JS bruto;
- extrai endpoints candidatos somente quando aparecem como caminhos relativos
  seguros;
- ignora endpoints administrativos ou fora de escopo;
- executa chamadas candidatas apenas quando sao seguras;
- grava relatorios sanitizados em `tmp/diagnosticos/html_modelos/`.

### Scripts inspecionados

O diagnostico real detectou e inspecionou:

```text
/common/js/ews.js
/common/js/cookie.js
/common/js/language.js
/common/js/lcddisplay.js
/common/js/mobilemenucontrl.js
inline_status_1
inline_status_2
```

Resumo sanitizado relevante:

| Script | Termos encontrados | Funcoes candidatas | Endpoints candidatos |
| --- | --- | --- | --- |
| `inline_status_1` | `judge_refresh`, `refresh` | `judge_refresh` | - |
| `/common/js/lcddisplay.js` | `moni_data`, `moni`, `refreshLCD`, `judge_refresh`, `XMLHttpRequest`, `GET`, `status`, `lcd`, `refresh` | `refreshLCD`, `judge_refresh`, `XMLHttpRequest` | - |
| `/common/js/mobilemenucontrl.js` | `GET`, `display` | - | - |

O script `lcddisplay.js` confirma que existe logica dinamica ligada ao bloco
LCD/status, mas nesta etapa nao apareceu endpoint relativo literal que pudesse
ser chamado de forma segura pelo diagnostico.

### Resultado do diagnostico real

Comando executado:

```bash
docker compose --env-file .env.docker exec -T admin python backend/pyteste/diagnostico_html_modelos.py --confirmar --modelo "Brother DCP-L1632W" --diagnosticar-status-dinamico
```

Relatorios sanitizados gerados localmente em pasta ignorada pelo Git:

```text
tmp/diagnosticos/html_modelos/diagnostico_brother_l1632w_dynamic_status_20260623_134401.json
tmp/diagnosticos/html_modelos/diagnostico_brother_l1632w_dynamic_status_20260623_134401.md
```

Resultado controlado:

| Item | Resultado |
| --- | --- |
| HTTP inicial | 200 |
| `#moni_data` | detectado |
| Classe contendo `moni` | detectada |
| `span` dentro de `#moni_data` | detectado |
| Texto inicial de `#moni_data` | vazio |
| Scripts detectados | 5 scripts externos e 2 inline |
| `lcddisplay.js` | inspecionado em memoria |
| `refreshLCD` | detectado |
| `judge_refresh` | detectado |
| `XMLHttpRequest` | detectado |
| Endpoints candidatos seguros | nenhum endpoint literal encontrado |
| Chamadas candidatas executadas | nenhuma |
| Mensagem `Em espera` encontrada | nao |
| Causa sanitizada | `scripts_sem_endpoint_candidato` |

Nenhum HTML bruto, JS bruto, IP real, hostname, senha, cookie, Authorization,
CSRFToken real, serial, MAC, URL absoluta real ou header sensivel foi
documentado ou versionado.

### Fixtures e testes

Foram criadas fixtures sinteticas e sanitizadas para:

- pagina de status com scripts relativos e `#moni_data` vazio;
- trecho sintetico de `lcddisplay.js` com `refreshLCD`;
- resposta dinamica com `Em espera`;
- resposta dinamica vazia.

Os testes cobrem:

- listagem de scripts relativos;
- sanitizacao de URL absoluta com IP para caminho relativo;
- deteccao de `lcddisplay.js`;
- deteccao de `refreshLCD`, `judge_refresh`, `moni_data` e `XMLHttpRequest`;
- extracao de endpoint relativo candidato em JS sintetico;
- ausencia de JS bruto no resumo;
- ignorar endpoint administrativo;
- uso de mesma sessao em memoria;
- ausencia de CSRFToken, Cookie, Authorization e senha em relatorios;
- resposta dinamica com `Em espera`;
- resposta dinamica vazia como falha controlada;
- causa `scripts_sem_endpoint_candidato` quando aplicavel;
- ausencia de rede real nos testes.

### Validacoes

Validacoes executadas:

```text
py -3.11 -m pytest -q backend/app/modules/printers/monitoring/html_diagnostics/tests/test_html_paths_diagnostic.py backend/app/modules/printers/monitoring/html_parsers/tests/test_status_parsers.py
77 passed

py -3.11 -m compileall -q backend/app/modules/printers/monitoring/html_diagnostics backend/pyteste
OK

py -3.11 -m compileall -q backend
OK

py -3.11 -m pytest -q
337 passed, 38 warnings

py -3.11 manage.py check
System check identified no issues

npm.cmd audit
found 0 vulnerabilities

npm.cmd run build
OK, com aviso conhecido de chunks grandes do Vite

docker compose --env-file .env.docker up -d --no-build
OK

docker compose --env-file .env.docker ps -a
migrations Exited (0); stack Up
```

### Limites preservados

Esta etapa nao integrou HTML na cascata SNMP -> HTML, nao alterou
`collect_and_sync_machine_alerts`, nao alterou
`sync_machine_alerts_from_collection_result`, nao alterou Rules Engine, nao
alterou Celery/task, nao persistiu alertas HTML, nao gravou em
`alertas_impressoras`, nao gravou em `historico_alertas_impressoras`, nao
persistiu toner, tambor ou contador, nao criou API publica, nao criou
frontend, nao criou dashboard, nao criou tabela nova, nao criou credencial por
maquina, nao criou `tentativas_coleta_impressoras`, nao salvou HTML bruto, nao
salvou JS bruto e nao usou HTML/SNMP para alterar dados cadastrais.

### Proxima etapa recomendada

Investigar de forma ainda controlada se `lcddisplay.js` monta a URL dinamica
em tempo de execucao por variavel global, parametro de pagina ou chamada
indireta. Se isso depender de execucao real de JavaScript no navegador, a etapa
seguinte deve tratar Playwright/headless apenas como diagnostico documentado,
sem integrar HTML na cascata e sem persistir alertas.

## Etapa 3.5.2.17 - Ultima tentativa Brother DCP-L1632W com status sem autenticacao

Esta microetapa executou a ultima tentativa diagnostica controlada para a
Brother DCP-L1632W antes de avancar para os demais modelos. A nova hipotese era
que `/home/status.html` pudesse expor o estado operacional sem login, enquanto
`/general/information.html?kind=item` continuaria sendo consultado em fluxo
autenticado apenas para manutencao.

Foi criada a opcao opt-in:

```bash
python backend/pyteste/diagnostico_html_modelos.py --confirmar --modelo "Brother DCP-L1632W" --diagnosticar-status-publico
```

O diagnostico de status publico:

- usa uma sessao HTTP limpa;
- nao envia credenciais;
- nao executa login;
- nao injeta cookies;
- nao executa POST;
- consulta somente o caminho de status configurado;
- mantem a consulta de manutencao em sessao separada e autenticada;
- grava somente relatorio sanitizado em `tmp/diagnosticos/html_modelos/`.

### Fixtures e testes

Foram adicionadas fixtures sinteticas e sanitizadas para:

- `/home/status.html` com `#moni_data` e texto operacional;
- `/home/status.html` com `#moni_data` vazio;
- tela de manutencao exigindo login.

Os testes cobrem:

- status publico resolvido sem autenticacao quando existe texto operacional;
- `#moni_data` vazio como falha controlada
  `html_status_publico_vazio`;
- ausencia de `#moni_data` como falha controlada
  `html_status_publico_nao_detectado`;
- manutencao autenticada em sessao separada;
- relatorios sem HTML bruto, IP, nome real de maquina, senha, cookie,
  Authorization, CSRFToken ou `senha_criptografada`;
- ausencia de chamada real de rede nos testes.

### Resultado do diagnostico real

Comando executado:

```bash
docker compose --env-file .env.docker exec -T admin python backend/pyteste/diagnostico_html_modelos.py --confirmar --modelo "Brother DCP-L1632W" --diagnosticar-status-publico
```

Relatorios sanitizados gerados localmente em pasta ignorada pelo Git:

```text
tmp/diagnosticos/html_modelos/diagnostico_brother_l1632w_public_status_20260623_160319.json
tmp/diagnosticos/html_modelos/diagnostico_brother_l1632w_public_status_20260623_160319.md
```

Resultado controlado:

| Item | Resultado |
| --- | --- |
| HTTP do status publico | 200 |
| Autenticacao no status | nao usada |
| Login no status | nao executado |
| POST no status | nao executado |
| Cookie autenticado no status | nao usado |
| `#moni_data` | detectado |
| Texto visivel em `#moni_data` | vazio |
| Estado principal | nao detectado |
| Erro controlado | `html_status_publico_vazio` |
| Causa sanitizada | `moni_data_vazio_sem_login` |
| Manutencao autenticada | sim |
| `maintenance_info` real | `{}` |
| Decisao final | pendencia tecnica nao bloqueante |
| Proxima etapa | avancar para os outros modelos de impressora |

A Brother DCP-L1632W fica, portanto, como pendencia tecnica nao bloqueante para
status HTML. Nao continuar investigando este modelo agora evita transformar uma
excecao local em desenho de arquitetura prematuro.

### Limites preservados

Esta etapa nao integrou HTML na cascata SNMP -> HTML, nao alterou
`collect_and_sync_machine_alerts`, nao alterou
`sync_machine_alerts_from_collection_result`, nao alterou Rules Engine, nao
alterou Celery/task, nao persistiu alertas HTML, nao gravou em
`alertas_impressoras`, nao gravou em `historico_alertas_impressoras`, nao
persistiu toner, tambor ou contador, nao criou API publica, nao criou
frontend, nao criou dashboard, nao criou tabela nova, nao criou credencial por
maquina, nao criou `tentativas_coleta_impressoras`, nao salvou HTML bruto, nao
salvou JS bruto e nao usou HTML/SNMP para alterar dados cadastrais.

### Proxima etapa recomendada

Avancar para os outros modelos de impressora. Uma integracao futura do HTML
publico como fallback so deve acontecer em etapa propria, com contrato separado
e sem persistir dados de diagnostico.

## Etapa 3.5.2.18 - Finalizar Status com Redis/Celery e ativar frontend

Esta microetapa consolidou a fase de Status operacional do modulo Impressoras
sem ampliar o escopo para coleta rica. A branch usada foi
`feature/printers-status-final-celery-frontend`, criada a partir de
`feature/printers-html-brother-l1632w-public-status`.

A limpeza inicial procurou bancos e dumps locais antigos associados a v1 ou ao
nome antigo do projeto. Nenhum banco/dump antigo foi identificado dentro do
workspace, portanto nenhum arquivo foi removido. Os volumes Docker nao foram
tocados e o banco valido permaneceu sendo o PostgreSQL do ambiente Docker.

### Decisao tecnica

O Status passa a exibir dados reais da base atual:

- conectividade operacional continua sendo processada por Redis/Celery em
  `printers_connectivity_all`, com agenda de 60 segundos;
- mensagens de alerta continuam sendo coletadas por `printers_alerts_all`, com
  agenda de 300 segundos;
- a API de Status passa a projetar os alertas atuais persistidos em
  `alertas_impressoras` sobre a resposta de `status_impressoras`;
- o resumo de Status passa a calcular `com_alerta` e `substituir_toner` a
  partir dos alertas atuais persistidos;
- o frontend `/impressoras/status` passa a consumir a API real de Status,
  exibindo a classificacao na coluna `Alerta` e a mensagem operacional na
  coluna `Mensagem`.

Nao foi criada migracao nesta etapa, porque as tabelas necessarias ja existiam.
As tabelas envolvidas sao:

- `status_impressoras`;
- `historico_status_impressoras`;
- `alertas_impressoras`;
- `historico_alertas_impressoras`.

### Diagnostico real sanitizado

Foi executado diagnostico operacional real via Docker, mantendo relatorios em
pasta ignorada pelo Git:

```text
tmp/diagnosticos/status_final/diagnostico_status_final_20260623_170837.json
tmp/diagnosticos/status_final/diagnostico_status_final_20260623_170837.md
```

Resultado consolidado sanitizado:

| Item | Resultado |
| --- | --- |
| Status atuais | 37 |
| Alertas atuais | 49 |
| Historico de status | 818 |
| Historico de alertas | 401 |
| Maquinas processadas na coleta de alertas | 35 |
| Maquinas ignoradas na coleta de alertas | 2 |
| Coletas de alerta com sucesso | 33 |
| Coletas de alerta com falha | 2 |

A task global de conectividade encontrou lock Redis ativo no momento da
validacao, evidenciando protecao de concorrencia. A coleta individual de uma
maquina ativa foi executada com sucesso e confirmou status `online` por ICMP.

### Modelos validados

| Modelo | Maquinas | Alertas atuais |
| --- | ---: | ---: |
| Brother DCP-L1632W | 18 | 25 |
| Brother DCP-L2540DW | 7 | 9 |
| Canon IR-C3326I | 9 | 12 |
| HP MFP-4303 | 2 | 2 |
| Samsung K-4350 | 1 | 1 |

### Endpoints validados

- `GET /api/v2/printers/status`;
- `GET /api/v2/printers/status/summary`;
- `GET /api/v2/printers/status/{machine_id}`.

O resumo retornou dados reais do ambiente Docker, incluindo total de
impressoras ativas, online/offline, quantidade com alerta e quantidade com
acao de substituicao de toner.

### Limites preservados

Esta etapa nao continuou a investigacao do `#moni_data` da Brother DCP-L1632W,
nao integrou HTML na cascata de alertas, nao persistiu alertas HTML, nao criou
tabela nova, nao criou credencial por maquina, nao criou
`tentativas_coleta_impressoras`, nao implementou percentual de toner, nao
implementou quantidade de papel, nao implementou dashboard real, nao usou
headless/Playwright, nao salvou HTML bruto, nao salvou JS bruto e nao alterou
Rules Engine.

## Etapa 3.5.2.19 - Ajustes finais da tela Status e regras operacionais de atualizacao

Esta microetapa aplicou ajustes operacionais e visuais na tela
`/impressoras/status`, usando como base a branch
`feature/printers-status-final-celery-frontend`. A branch de trabalho foi
`feature/printers-status-ui-operational-fixes`.

### Objetivo

Finalizar a leitura operacional do Status antes das proximas fases de toner e
papel, mantendo a coleta atual em Redis/Celery e sem retomar a investigacao
HTML publica da Brother DCP-L1632W.

### Regras aplicadas

- impressora offline passa a sobrescrever qualquer alerta antigo;
- offline e exibido como `Sem servico`;
- offline usa severidade interna `high` e nivel visual `vermelho`;
- offline e ignorado no lote atual de coleta de alertas;
- a mesma regra ficou centralizada para ser reutilizada por futuras coletas de
  toner e papel;
- o lote de alertas passou a retornar `ignoradas_offline`;
- `Atualizado em` usa a ultima verificacao operacional do status atual;
- a tela refaz a consulta automaticamente a cada 60 segundos;
- a coluna textual de severidade foi removida da tabela;
- a coluna `Alerta` passou a exibir a mensagem operacional da impressora;
- a severidade permanece apenas para estilo visual, cards e ordenacao;
- a coluna `Modelo` passou a exibir `Fabricante - Modelo`;
- o cabecalho da tabela ficou sticky para permanecer visivel durante a rolagem.

### Contrato de API

A API de Status preserva os campos ja utilizados pelo frontend e tambem expõe
aliases de leitura para a tela:

- `status_operacional` e `status`;
- `nivel_alerta` e `severidade`;
- `mensagem_alerta`, `alerta` e `mensagem`;
- `manufacturer`, `model` e `modelo_exibicao`;
- `ultima_verificacao_em` e `verificado_em`.

Os dados cadastrais continuam vindo do banco do ERP. HTML/SNMP nao alteram
modelo, fabricante, nome, IP, setor, centro de custo, serial, MAC, firmware ou
imagem cadastrada.

### Aliases de alertas confirmados

A seed de `regras_alertas_impressoras` continua idempotente e agora garante os
aliases aprovados sem criar uma regra por variacao textual. As regras canonicas
mais relevantes para esta etapa sao:

| Mensagem | Codigo canonico | Severidade | Visual |
| --- | --- | --- | --- |
| `Subst. toner` | `replace_toner` | `high` | vermelho |
| `subst toner` | `replace_toner` | `high` | vermelho |
| `subs. o toner` | `replace_toner` | `high` | vermelho |
| `toner replace` | `replace_toner` | `high` | vermelho |
| `Subst. cilindro` | `replace_drum` | `high` | vermelho |
| `subst cilindro` | `replace_drum` | `high` | vermelho |
| `subs. cilindro` | `replace_drum` | `high` | vermelho |
| `substitua cilindro` | `replace_drum` | `high` | vermelho |
| `troque cilindro` | `replace_drum` | `high` | vermelho |
| `Imprimindo` | `ok` | `green` | verde |
| `Em impressao` | `ok` | `green` | verde |
| `Sem servico` | `sem_servico` | `high` | vermelho |

A regra `sem_servico` existe para consistencia de diagnostico e mensagens
externas. A sobrescrita visual de offline, porem, continua baseada no status
operacional atual e nao depende da mensagem coletada.

### Frontend Status

A tabela final de `/impressoras/status` exibe somente:

- `Status`;
- `Alerta`;
- `Local`;
- `Maquina`;
- `Modelo`;
- `IP`;
- `Atualizado em`.

Nao ha coluna textual de severidade. A severidade interna alimenta apenas a cor
leve da linha, a bolinha da coluna `Alerta`, cards e ordenacao. A area de
Status usa altura de viewport: os cards, a barra de atualizacao automatica e o
cabecalho das colunas permanecem visiveis, enquanto apenas as linhas da tabela
rolam no container interno.

O frontend nao possui suite de testes automatizados dedicada nesta base. A
validacao desta microetapa no frontend e feita por `npm.cmd audit`,
`npm.cmd run build` e verificacao HTTPS local.

### Validacoes da microetapa

Validacoes executadas ou previstas para fechamento:

- `py -3.11 -m compileall -q backend`;
- `py -3.11 -m pytest -q`;
- `py -3.11 manage.py check`;
- `npm.cmd audit`;
- `npm.cmd run build`;
- `docker compose --env-file .env.docker up -d --no-build`;
- `docker compose --env-file .env.docker ps -a`;
- inspeção das tasks registradas do Celery.

### Limites preservados

Esta etapa nao implementou percentual de toner, quantidade de papel, frontend
de toner, frontend de papel, dashboard, headless/Playwright, tabela nova,
credencial por maquina, `tentativas_coleta_impressoras`, HTML na cascata,
persistencia de alertas HTML, HTML bruto, JS bruto ou retomada do `#moni_data`
Brother.

### Proxima etapa recomendada

Avancar para percentual de toner ou quantidade de papel somente depois de
validar a regra operacional de Status em uso real por alguns ciclos de coleta.

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
salva HTML bruto. A etapa 3.5.2.13 refina apenas a leitura HTML da Brother
DCP-L1632W para alerta/status e apoio diagnostico controlado; ela nao integra
HTML na cascata, nao persiste alertas HTML, nao persiste toner/tambor/contador,
nao altera Celery/task, nao altera Rules Engine, nao cria tabela nova, nao cria
credencial por maquina, nao cria `tentativas_coleta_impressoras`, nao extrai
dados cadastrais do HTML/SNMP e nao salva HTML bruto. A etapa 3.5.2.14 adiciona
somente ajuste de autenticacao e classificacao HTML Brother no cliente seguro,
parser e diagnostico;
ela nao integra HTML na cascata, nao persiste alertas HTML, nao persiste
toner/tambor/contador, nao altera Celery/task, nao altera Rules Engine, nao
cria tabela nova, nao cria credencial por maquina, nao cria
`tentativas_coleta_impressoras`, nao cria API publica, nao altera frontend, nao
extrai dados cadastrais do HTML/SNMP e nao salva HTML bruto.

A etapa 3.5.2.17 executa apenas diagnostico opt-in do status publico Brother
DCP-L1632W; ela nao integra HTML publico na cascata, nao persiste alertas HTML,
nao cria tabela, nao altera Celery/task, nao altera Rules Engine, nao cria API
publica, nao altera frontend e nao salva HTML bruto.

A etapa 3.5.2.18 finaliza a tela Status com API real, Redis/Celery e alertas
atuais persistidos, mas ainda nao implementa dashboard real, percentual de
toner, quantidade de papel, coleta rica, HTML na cascata, headless/Playwright
ou novas tabelas de tentativa.

A etapa 3.5.2.19 ajusta somente Status, API, coleta de alertas e tabela
operacional; ela nao implementa toner, papel, dashboard, HTML na cascata ou
novas tabelas de tentativa.

## Etapa 3.5.2.20 - Ajuste final do modal de Status

Esta microetapa finaliza o modal de detalhes da impressora na tela
`/impressoras/status`, mantendo a fase Status / Alertas pronta para uso
operacional e para merge em `develop`.

### Ajustes do modal

- o campo visual `Alerta operacional` foi removido;
- o campo `Mensagem de alerta` foi substituido por `Alerta`;
- a severidade deixou de ser exibida como texto principal no modal;
- `Status operacional` representa apenas conectividade e usa badge proprio:
  `Online` em verde e `Offline` em vermelho;
- `Alerta` passa a exibir a mensagem operacional do alerta em badge discreto,
  colorido pela severidade interna;
- impressoras offline exibem `Alerta: Sem servico` com severidade
  `high/vermelho`, sobrescrevendo alertas antigos no detalhe;
- `Mensagem operacional` permanece separada de `Alerta`;
- `Resposta tecnica` e `Ultimos logs` permanecem somente consultivos.

### Multiplos alertas

O modal usa o mesmo conceito da tabela de Status:

- se houver apenas um alerta, ele e exibido diretamente;
- se houver mais de um alerta da maior criticidade, as mensagens alternam a
  cada quatro segundos;
- quando houver alternancia, o indicador `1/2`, `2/2` e equivalentes e exibido;
- se houver alertas de criticidades diferentes, apenas a criticidade mais grave
  entra na exibicao principal;
- a cor do badge de `Alerta` acompanha a severidade do alerta exibido.

### Consistencia com a tabela

A tabela principal permanece com as colunas:

```text
Status | Alerta | Local | Maquina | Modelo | IP | Atualizado em
```

Os cards e o cabecalho continuam preservados com rolagem interna das linhas,
polling automatico e busca por IP, local, maquina, modelo, status ou alerta.

### Validacoes da microetapa

A validacao final da etapa executa:

- `py -3.11 -m compileall -q backend`;
- `py -3.11 -m pytest -q`;
- `py -3.11 manage.py check`;
- `npm.cmd audit`;
- `npm.cmd run build`;
- `docker compose --env-file .env.docker up -d --no-build`;
- `docker compose --env-file .env.docker ps -a`;
- inspecao das tasks registradas do Celery.

### Limites preservados

Esta etapa nao implementa percentual de toner, quantidade de papel, dashboard,
headless, coleta rica, tabela nova, credencial por maquina,
`tentativas_coleta_impressoras`, fallback HTML na cascata ou retomada do
diagnostico `#moni_data` Brother. Tambem nao versiona HTML bruto, JS bruto,
relatorios locais, dumps, certificados ou dados reais.

## Etapa 3.5.2.21 - Estrategia de status por modelo

Esta microetapa corrige a coleta de mensagem operacional usando a v1 apenas
como referencia conceitual de apresentacao de status e severidade. Nao houve
copia de arquivos inteiros da v1.

### Decisao tecnica

A v2 passa a selecionar a metrica SNMP conforme o modelo/fabricante:

| Modelos | Estrategia |
| --- | --- |
| Brother e Canon | `alert_raw` via WALK em `prtAlertDescription` (`1.3.6.1.2.1.43.18.1.1.8`) |
| HP e Samsung | `hr_printer_status` via GET em `hrPrinterStatus` (`1.3.6.1.2.1.25.3.5.1.1.1`) |

A chave `hr_printer_status` foi adicionada a configuracao de OIDs SNMP e ao
seed oficial apenas para HP MFP-4303 e Samsung K-4350. Brother e Canon
continuam com `alert_raw`.

### Normalizacao antes das regras

Valores SNMP em hexadecimal, como `0x...`, sao decodificados antes de passar
pela Rules Engine. O frontend e a API nao devem receber hexadecimal como
mensagem operacional.

Estados de `hrPrinterStatus` sao convertidos para mensagens controladas:

| Valor | Mensagem |
| --- | --- |
| `3` | `Em espera` |
| `4` | `Imprimindo` |
| `5` | `Aquecendo` |

As regras oficiais tambem reconhecem aliases como `Ha pouco toner`,
`Toner is low`, `Imprimindo`, `Aquecendo` e `Em espera`.

### Sem alerta

Quando a impressora esta online e a coleta nao retorna alerta real, a API de
Status projeta:

```json
{
  "status": "online",
  "alerta": "Sem alerta",
  "severidade": "unknown"
}
```

Esse estado e neutro/cinza no frontend e nao e persistido como alerta real em
`alertas_impressoras`. Se existiam alertas atuais antigos para a maquina, eles
sao limpos na sincronizacao.

### Limites preservados

Esta etapa nao implementa percentual de toner, quantidade de papel, dashboard,
HTML `#moni_data`, credencial por maquina, tabela nova,
`tentativas_coleta_impressoras`, coleta rica, alteracao de Celery/task ou
alteracao da Rules Engine para fora dos aliases necessarios. O fallback HTML
autenticado foi integrado somente para Canon IR-C3326I: ele e acionado depois
de falha tecnica ou ausencia de alerta real no SNMP e nao persiste HTML bruto.

## Etapa 3.5.2.22 - Priorizacao de alertas por severidade

Esta microetapa corrige a escolha do alerta principal quando uma impressora
retorna simultaneamente um estado operacional verde e um alerta real. A v1 ja
usava severidade nas regras; na v2, a fonte oficial permanece o campo
`regras_alertas_impressoras.severidade`, relacionado por `regra_alerta_id`.

Nao foi criada coluna nem snapshot de severidade em `alertas_impressoras` e nao
houve migration. A API apenas projeta a severidade e a prioridade atuais da
regra em cada item de `alertas[]`.

### Ordenacao da API

A ordem de exibicao usa os seguintes pesos:

| Severidade | Peso |
| --- | ---: |
| `high` | 50 |
| `medium` | 40 |
| `low` | 30 |
| `unknown` | 20 |
| `green` | 10 |

Valores nao reconhecidos sao tratados como `unknown`. Quanto maior o peso,
mais cedo o alerta aparece. Dentro da mesma severidade, a menor prioridade
numerica da regra vence, seguindo a direcao ja adotada pela Rules Engine. O
desempate final usa mensagem e codigo para manter a resposta deterministica.

O primeiro item ordenado define `alerta`, `mensagem`, `mensagem_alerta`,
`severidade` e `nivel_alerta` no status principal. O array `alertas[]` preserva
os demais alertas reais, tambem ordenados, e cada item contem `codigo`,
`mensagem`, `severidade`, `prioridade` e `nivel_alerta`.

### Exibicao no frontend

A tabela Status e o modal usam o mesmo seletor compartilhado. Ambos exibem ou
alternam somente os alertas pertencentes a maior severidade presente. Quando
existem dois alertas `high`, por exemplo substituicao de toner e de cilindro,
eles alternam a cada quatro segundos com indicador `1/2` e `2/2`. Um alerta de
severidade inferior permanece no payload e na busca, mas nao entra nessa
alternancia.

Assim, `Sleep/green` nao esconde `Ha pouco toner/medium` ou `low`. Se `Sleep`
for o unico estado recebido, ele continua verde. Online sem alerta real
continua `Sem alerta/unknown`, e offline continua `Sem servico/high`.

### Validacoes

Foram mantidas as validacoes de compilacao e testes completos do backend,
`manage.py check`, auditoria e build do frontend, stack Docker, tasks Celery e
Beat, API real e navegacao HTTPS local. Nenhum segredo, HTML bruto ou JS bruto
e exposto por esta mudanca.

## Etapa 3.5.2.22.1 - Fallback IPP para HP MFP-4303

O diagnostico real confirmou que o `hrPrinterStatus` via SNMP das HP MFP-4303
retorna um estado generico sem mensagem operacional util. Os endpoints EWS
testados entregam apenas o shell da interface web. O IPP, por outro lado,
responde em `/ipp/print` com `printer-state`, `printer-state-reasons` e
`printer-state-message`.

### Cascata por modelo

Para HP MFP-4303, a coleta de alertas agora segue:

```text
SNMP com alerta real -> persiste SNMP
SNMP sem alerta real ou com falha tecnica -> consulta IPP
IPP com estado util -> persiste origem/metodo/confirmacao ipp
SNMP e IPP sem resultado -> preserva o tratamento anterior da cascata
```

O fallback continua em `collect_and_sync_machine_alerts`. O coletor SNMP de
baixo nivel permanece exclusivamente SNMP. Canon IR-C3326I continua usando o
fallback HTML autenticado ja existente.

### Estado e seguranca

O cliente usa `Get-Printer-Attributes` por meio de `pyipp` e nao envia
trabalhos de impressao. Estados conhecidos sao apresentados em portugues:

| Estado IPP | Mensagem |
| --- | --- |
| `idle` | `Em espera` |
| `processing` | `Imprimindo` |
| `stopped` | `Erro: impressora parada` |

Motivos IPP conhecidos com severidade `error` ou `warning` tambem sao
traduzidos. Motivos com sufixo `report` sao mantidos apenas nos metadados da
coleta e nao viram falso alerta critico. Host, resposta binaria e dados brutos
nao sao persistidos nem retornados no resultado sanitizado.

As tabelas de alertas passam a aceitar `ipp` em `origem_coleta`,
`metodo_coleta` e `metodo_confirmacao` por meio da migration
`20260629_hp_ipp_fallback`.

### Validacao real

As duas HP MFP-4303 ativas responderam ao IPP com estado `idle`. Depois da
cascata completa, ambas foram persistidas com mensagem `Em espera`, nivel
verde e origem `ipp`; o mesmo estado foi projetado pelo payload consumido pela
tela Status.

## Etapa 3.5.2.23 - Modal de Status e logs operacionais das ultimas 24h

Esta microetapa remove a `Resposta tecnica` do modal operacional. O conteudo
era um JSON de diagnostico interno sem utilidade para o usuario da central e
poderia expor detalhes de tentativas de conectividade. A coluna permanece no
banco para compatibilidade interna, mas nao faz mais parte dos schemas nem do
payload da API de Status.

### Linha do tempo operacional

O endpoint `/api/v2/printers/status/{machine_id}/logs` passa a unir eventos de:

- `historico_status_impressoras`;
- `historico_alertas_impressoras`.

Somente eventos com `verificado_em` dentro das ultimas 24 horas entram na
resposta. A linha do tempo e ordenada do mais recente para o mais antigo e
limitada a 10 eventos. O modal apresenta data/hora, mensagem operacional e a
origem `status` ou `alerta`.

Quando nao existem eventos recentes, o modal informa:

```text
Nenhum evento operacional registrado nas ultimas 24h.
```

### Seguranca do payload

A projecao usa mensagens controladas pelo backend. Nao sao retornados
`resposta_bruta`, `detalhes`, mensagem SNMP/HTML bruta, JSON tecnico, token,
cookie, senha, cabecalho de autorizacao ou stack trace. Nenhuma migration
destrutiva foi criada e os historicos existentes foram preservados.

### Validacoes

Os testes cobrem as duas fontes historicas, exclusao de eventos com mais de
24 horas, ordenacao decrescente, limite de 10, resposta vazia e ausencia de
conteudo tecnico. Tambem sao preservados os cenarios de online sem alerta,
offline, priorizacao por severidade e alternancia de alertas equivalentes.

A validacao final inclui compilacao e testes backend, `manage.py check`,
auditoria e build frontend, stack Docker, Redis, Celery Worker/Beat, tasks
registradas e acesso HTTPS local. A branch principal nao faz parte desta
microetapa.

### Alertas simultaneos na Brother DCP-L2540DW

O HTML real desse modelo separa o estado principal do aviso de suprimento. O
texto `Trocar Cilindro` aparece em `Device Status`, enquanto o toner baixo e
representado pelo arquivo `low.gif` dentro do bloco `#ink_level`. O parser le
os dois pontos de forma controlada e produz `Trocar Cilindro` e `Subs. toner`.
As requisicoes HTML usam `Cache-Control: no-cache` e `Pragma: no-cache` para
evitar que a interface embarcada devolva um estado operacional antigo.

Para esse modelo, a coleta HTML complementa o resultado SNMP sem alterar o
coletor SNMP de baixo nivel. Os dois alertas possuem severidade `high`, sao
persistidos simultaneamente e o seletor compartilhado do frontend alterna
entre eles a cada quatro segundos. O indicador visual fora de `#ink_level` e
ignorado para evitar falso positivo, e nenhum HTML bruto e persistido.

## Próximas etapas

- ampliar fallbacks somente para modelos validados em diagnostico real;
- expor consultas publicas dos alertas quando houver necessidade de frontend;
- 3.5.3: coleta rica em 60 minutos;
- 3.5.4: papel, toner e históricos;
- 3.5.5: dashboard.
