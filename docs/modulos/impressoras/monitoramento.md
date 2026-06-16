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

O seed oficial é idempotente: cria as 16 regras iniciais quando ausentes e
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
- `high`.

Na apresentação visual futura, `green` será convertido em verde, `low` e
`medium` em amarelo, e `high` em vermelho. Essa conversão ainda não integra a
tela Status.

Quando nenhuma regra reconhece a mensagem, a Rules Engine retorna `unknown`,
com severidade `medium`, e preserva a mensagem original para diagnóstico.

As regras podem ser consultadas e administradas pelo Django Admin conforme as
permissões padrão. A Equipe Técnica recebe as permissões administrativas; o
grupo Operador não recebe permissão de edição.

## Etapa 3.5.2.1 - Configuracao SNMP/OIDs

Esta microetapa porta da v1 a base de configuracao de OIDs por modelo e
metrica. A entrega prepara a proxima etapa de alertas via SNMP, mas ainda nao
consulta equipamentos reais, nao cria alertas ativos e nao altera a tela Status.

### Tabela de configuracao

O Alembic administra a tabela `configuracoes_oids_impressoras`, com os campos:

- `id`;
- `modelo_id`;
- `chave_metrica`;
- `oid`;
- `tipo_valor`;
- `versao_snmp`;
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
- retornar `None` quando a metrica nao existe.

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

## Fora do escopo

As etapas 3.5.1 e 3.5.2.0 não implementam a coleta de alertas em cinco minutos,
toner, papel, coleta rica, dashboard, Protheus, Telegram ou tabela detalhada de
tentativas. A etapa 3.5.2.1 tambem nao implementa fallback HTML/HTTP de
alertas, endpoint publico, frontend, coleta real SNMP ou tabelas de alertas
ativos e historico.

## Próximas etapas

- criar `alertas_impressoras`;
- criar `historico_alertas_impressoras`;
- implementar a task de alertas em cinco minutos;
- implementar a coleta SNMP de `alert_raw`;
- implementar fallback HTML/HTTP posterior;
- suportar múltiplos alertas ativos;
- calcular a classificação geral da máquina;
- 3.5.3: coleta rica em 60 minutos;
- 3.5.4: papel, toner e históricos;
- 3.5.5: dashboard.
