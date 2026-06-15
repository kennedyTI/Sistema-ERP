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

## Fora do escopo

As etapas 3.5.1 e 3.5.2.0 não implementam a coleta de alertas em cinco minutos,
toner, papel, coleta rica, dashboard, Protheus, Telegram ou tabela detalhada de
tentativas. Também não foram criadas as tabelas de alertas ativos e histórico.

## Próximas etapas

- criar `alertas_impressoras`;
- criar `historico_alertas_impressoras`;
- implementar a task de alertas em cinco minutos;
- implementar a cascata SNMP para HTML;
- suportar múltiplos alertas ativos;
- calcular a classificação geral da máquina;
- 3.5.3: coleta rica em 60 minutos;
- 3.5.4: papel, toner e históricos;
- 3.5.5: dashboard.
