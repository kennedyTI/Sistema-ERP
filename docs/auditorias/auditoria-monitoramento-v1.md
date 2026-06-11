# Auditoria da arquitetura de monitoramento da v1

Data da auditoria: 11/06/2026

## Objetivo

Esta auditoria registra a engenharia de monitoramento existente na v1 para
orientar a Etapa 3.5 do Sistema ERP v2. Nenhuma funcionalidade de monitoramento
foi migrada ou implementada nesta atividade.

O levantamento cobriu banco, migrations, seeds, OIDs, alertas, services,
Celery, Redis, locks, toner, papel, históricos e a estrutura já disponível na
v2. Dados reais de rede e negócio foram deliberadamente omitidos.

## Escopo e segurança

- A v1 foi localizada em um projeto local separado da v2.
- A branch da v2 usada para este relatório foi
  `feature/auditoria-monitoramento-v1`, criada a partir de `develop`.
- A v2 não recebeu alteração funcional.
- O banco inspecionado foi o banco local isolado criado pelas migrations da v1,
  não uma cópia do banco de produção.
- O seed real de impressoras foi apenas inspecionado de forma agregada. Não foi
  executado e seus nomes, IPs, setores e centros de custo não são reproduzidos
  neste documento.
- O Celery Beat não foi iniciado, para impedir coleta periódica contra
  equipamentos reais.
- O worker Celery foi iniciado com a fila vazia e recebeu apenas as tasks
  seguras `debug_ping` e `celery_healthcheck`.
- Não foram executados ping, SNMP, HTTP ou HTTPS contra impressoras.
- Nenhum `.env`, certificado, dump ou seed local foi copiado para a v2.

## Como a v1 foi executada

Comandos principais usados no projeto da v1:

```powershell
docker compose --env-file .env.docker up -d --build postgres redis migrations api admin frontend
docker compose --env-file .env.docker up -d celery-worker
docker compose --env-file .env.docker ps -a
docker compose --env-file .env.docker exec -T api pytest -q
docker compose --env-file .env.docker exec -T admin python manage.py check
docker compose --env-file .env.docker exec -T redis redis-cli ping
docker compose --env-file .env.docker exec -T api celery -A backend.app.core.celery_app.celery_app inspect ping --timeout=10
```

Resultado:

- Postgres e Redis ficaram saudáveis.
- Migrations terminaram com código `0`.
- API, Admin, frontend e worker ficaram ativos.
- Django Admin respondeu com redirecionamento para login.
- O frontend respondeu e redirecionou para sua rota inicial.
- O endpoint tentado em `/health` retornou `404`; a v1 não expõe esse caminho
  como healthcheck HTTP.
- O worker respondeu `pong`.
- As duas tasks seguras retornaram sucesso.

## Containers identificados

| Serviço Compose | Função | Resultado da auditoria |
|---|---|---|
| `postgres` | PostgreSQL 16 | Executado e saudável |
| `redis` | Broker, result backend e locks | Executado e saudável |
| `migrations` | Schemas, Alembic, Django e grupos | Executado, exit `0` |
| `api` | FastAPI | Executado |
| `admin` | Django Admin | Executado |
| `frontend` | Frontend da v1 | Executado |
| `celery-worker` | Execução assíncrona | Executado com fila segura |
| `celery-beat` | Agenda periódica | Identificado, não iniciado por segurança |

## Tabelas de Impressoras

O schema operacional é `printers_monitor`. Foram encontradas 13 tabelas de
domínio, além de `alembic_version`. A inspeção encontrou 51 índices no schema.

| Tabela | Colunas principais | Constraints e índices relevantes | Registros locais | Papel |
|---|---|---|---:|---|
| `printers_models` | `id`, `nome`, `fabricante`, `tipo`, `is_active`, `created_at` | PK; `nome` único; índice em `is_active` | 0 | Catálogo estrutural |
| `printers` | `id`, `nome`, `ip`, `local`, `centro_custo`, `serial`, `model_id`, `foto_url`, `is_active`, timestamps | PK; IP único/indexado; FK para modelo | 0 | Cadastro operacional |
| `alerts` | `id`, `code`, `description`, `severity`, `rule_type`, `pattern`, `priority`, `is_active` | PK; `code` único; checks de severidade e tipo de regra | 16 após seed seguro | Regras/seed |
| `snmp_oids` | `id`, `model_id`, `metric_key`, `oid`, `value_type`, `snmp_version`, `is_active`, timestamps | PK; FK; único por modelo+métrica; checks; índices por modelo, métrica e ativo | 0 | Configuração de coleta |
| `printer_status` | status de conexão/operação, alerta, severidade, páginas, nome/local SNMP, inconsistência, timestamps | Uma linha por impressora; FKs; checks; índices de status/severidade | 0 | Fotografia operacional |
| `printer_status_history` | valores antigos/novos de conexão, operação, alerta, severidade e alerta bruto | PK; FK e índice por impressora | 0 | Histórico de transições |
| `paper_status` | `printer_id`, total, A4, A3, timestamps | Uma linha por impressora; FK e índice | 0 | Contadores atuais |
| `paper_history` | data, contadores inicial/final, páginas impressas, timestamp | Único por impressora+data; FK; índices por impressora e data | 0 | Histórico diário imutável |
| `toner_status` | métrica, cor, nível, bruto, `supply_index`, tipo, origem, descrição, presença, timestamps | Único por impressora+métrica+índice; checks; índices | 0 | Suprimentos atuais |
| `toner_history` | cor/métrica, instalação/remoção, níveis, contadores total/A4/A3, técnico, notas | FK; checks; índices por impressora, métrica e cor | 0 | Histórico de ciclo |
| `printer_supplies` | modelo, tipo de produto, número C.A., ativo, timestamps | Único por modelo+produto; check; índices de integração | 0 | Integração de suprimentos |
| `logs` | impressora, tipo, mensagem, valor anterior/novo, timestamp | FK para impressora | 0 | Log técnico operacional |
| `audit_logs` | tabela, registro, ação, JSON antigo/novo, autor, origem, timestamp | Checks; índices simples e composto | 0 | Auditoria genérica |

Não foi encontrada tabela relacionada a Telegram.

### Constraints de domínio confirmadas

- Conexão: `online`, `offline`, `no_snmp`, `unknown`.
- Operação: `ok`, `warning`, `error`, `unknown`.
- Severidade: `green`, `low`, `medium`, `high`.
- Regra de alerta: `contains`, `equals`, `regex`.
- Métricas SNMP: identificação, status, papel, toner, bandejas, uptime,
  cilindro e rede.
- Cores de toner: `black`, `cyan`, `magenta`, `yellow`, `unknown`.
- Fontes de auditoria: Admin, Django Admin, service, task e API interna.

### Dados disponíveis

O ambiente isolado não continha dados operacionais. O seed de impressoras da v1
possui 39 registros distribuídos por 7 modelos, mas contém informações locais
sensíveis e não foi executado. O seed de suprimentos possui 11 itens. Os
exemplos seguros desta auditoria são:

- um modelo de catálogo sem identificação de equipamento;
- uma métrica como `page_count_total`;
- um alerta como `paper_jam`;
- um status inicial conceitual como `unknown`.

## Tabela de OIDs

### Estado do cadastro

- A tabela local iniciou vazia.
- O seed padrão define 25 entradas: cinco métricas para cinco modelos.
- O arquivo de OIDs validados existe, mas continha zero entradas validadas.
- O schema não possui coluna de descrição ou categoria; essas informações são
  inferidas pela `metric_key`.
- O ID não existe antes da aplicação do seed e, por isso, é indicado como
  “gerado no banco”.

### Matriz por modelo

| Modelo | Fabricante | Métrica | OID | Tipo | Uso na v1 | Recomendação v2 | Observação |
|---|---|---|---|---|---|---|---|
| DCP-L1632W | Brother | `page_count` | `1.3.6.1.2.1.43.10.2.1.4.1.1` | counter | Status/papel | Adaptar | Duplicada com `page_count_total`; manter uma chave canônica |
| DCP-L1632W | Brother | `page_count_total` | `1.3.6.1.2.1.43.10.2.1.4.1.1` | counter | Papel | Migrar após validação | Printer-MIB |
| DCP-L1632W | Brother | `alert_raw` | `1.3.6.1.2.1.43.18.1.1.8.1.1` | string | Estado/alerta | Migrar após validação | Necessita fallback HTML |
| DCP-L1632W | Brother | `name` | `1.3.6.1.2.1.1.5.0` | string | Identificação/conectividade | Adaptar | Útil como probe leve |
| DCP-L1632W | Brother | `location` | `1.3.6.1.2.1.1.6.0` | string | Consistência cadastral | Postergar | Dado rico, não necessário a cada 5 min |
| DCP-L2540DW | Brother | `page_count` | `1.3.6.1.2.1.43.10.2.1.4.1.1` | counter | Status/papel | Adaptar | Remover alias duplicado |
| DCP-L2540DW | Brother | `page_count_total` | `1.3.6.1.2.1.43.10.2.1.4.1.1` | counter | Papel | Migrar após validação | Printer-MIB |
| DCP-L2540DW | Brother | `alert_raw` | `1.3.6.1.2.1.43.18.1.1.8.1.1` | string | Estado/alerta | Migrar após validação | Validar comportamento real |
| DCP-L2540DW | Brother | `name` | `1.3.6.1.2.1.1.5.0` | string | Identificação/conectividade | Adaptar | Probe SNMP |
| DCP-L2540DW | Brother | `location` | `1.3.6.1.2.1.1.6.0` | string | Consistência cadastral | Postergar | Coleta rica |
| IR-C3326I | Canon | `page_count` | `1.3.6.1.2.1.43.10.2.1.4.1.1` | counter | Status/papel | Adaptar | SNMP v1 no seed |
| IR-C3326I | Canon | `page_count_total` | `1.3.6.1.2.1.43.10.2.1.4.1.1` | counter | Papel | Migrar após validação | SNMP v1 no seed |
| IR-C3326I | Canon | `alert_raw` | `1.3.6.1.2.1.43.18.1.1.8.1.1` | string | Estado/alerta | Migrar após validação | SNMP v1 |
| IR-C3326I | Canon | `name` | `1.3.6.1.2.1.1.5.0` | string | Identificação/conectividade | Adaptar | Probe SNMP |
| IR-C3326I | Canon | `location` | `1.3.6.1.2.1.1.6.0` | string | Consistência cadastral | Postergar | Coleta rica |
| MFP-4303 | HP | `page_count` | `1.3.6.1.2.1.43.10.2.1.4.1.1` | counter | Status/papel | Adaptar | Remover alias duplicado |
| MFP-4303 | HP | `page_count_total` | `1.3.6.1.2.1.43.10.2.1.4.1.1` | counter | Papel | Migrar após validação | Printer-MIB |
| MFP-4303 | HP | `alert_raw` | `1.3.6.1.2.1.25.3.5.1.1.1` | string | Estado/alerta | Migrar após validação | Host Resources MIB |
| MFP-4303 | HP | `name` | `1.3.6.1.2.1.1.5.0` | string | Identificação/conectividade | Adaptar | Probe SNMP |
| MFP-4303 | HP | `location` | `1.3.6.1.2.1.1.6.0` | string | Consistência cadastral | Postergar | Coleta rica |
| K-4350 | Samsung | `page_count` | `1.3.6.1.2.1.43.10.2.1.4.1.1` | counter | Status/papel | Adaptar | Remover alias duplicado |
| K-4350 | Samsung | `page_count_total` | `1.3.6.1.2.1.43.10.2.1.4.1.1` | counter | Papel | Migrar após validação | Printer-MIB |
| K-4350 | Samsung | `alert_raw` | `1.3.6.1.2.1.25.3.5.1.1.1` | string | Estado/alerta | Migrar após validação | Host Resources MIB |
| K-4350 | Samsung | `name` | `1.3.6.1.2.1.1.5.0` | string | Identificação/conectividade | Adaptar | Probe SNMP |
| K-4350 | Samsung | `location` | `1.3.6.1.2.1.1.6.0` | string | Consistência cadastral | Postergar | Coleta rica |

Todas essas métricas possuem cobertura indireta nos testes de monitoramento,
papel, alinhamento do banco e retry SNMP. O seed aceita OIDs de toner somente
quando vêm de fonte validada.

### OIDs explicitamente invalidados

| Modelo | Métrica | OID | Decisão |
|---|---|---|---|
| DCP-L1632W | `toner_black` | `1.3.6.1.4.1.2435.2.3.9.4.2.1.5.5.52.31.1.2.1` | Não migrar; retornou falso 100% em validação de campo |
| DCP-L2540DW | `toner_black` | `1.3.6.1.4.1.2435.2.3.9.4.2.1.3.3.1.11.0` | Não migrar sem nova validação cruzada |

## Tabela de Alertas

A Rules Engine carrega regras ativas do banco, normaliza acentos e caixa,
aceita `contains`, `equals` e `regex`, ordena pela menor prioridade e desempata
pelo código. Um alerta não reconhecido preserva a mensagem original.

| Alerta | Categoria | Severidade | Padrões originais resumidos | Mensagem ao operador | Nível visual | Uso/migração |
|---|---|---|---|---|---|---|
| `error` | Erro | high | error, fatal, print unable | Verificar falha da máquina | Vermelho | Migrar |
| `offline` | Conectividade | high | offline, not responding | Verificar rede/energia | Vermelho | Adaptar ao novo status |
| `replace_toner` | Toner | high | replace/substituir/trocar toner, toner empty | Substituir toner | Vermelho | Migrar |
| `replace_drum` | Cilindro | high | replace/substituir cilindro | Substituir cilindro | Vermelho | Migrar |
| `paper_jam` | Papel | high | paper jam, atolamento, document jam | Remover atolamento | Vermelho | Migrar |
| `cover_open` | Estado | high | cover/door open, tampa aberta | Fechar tampa | Vermelho | Migrar |
| `no_paper` | Papel | high | no paper, sem papel, no tray | Abastecer papel | Vermelho | Migrar |
| `maintenance` | Manutenção | medium | maintenance, service required | Solicitar manutenção | Amarelo | Migrar |
| `memory_full` | Erro | medium | out of memory, memory full | Liberar fila/reiniciar | Amarelo | Migrar |
| `paper_low` | Papel | medium | paper low, papel baixo | Repor papel | Amarelo | Migrar |
| `drum_low` | Cilindro | medium | drum near end/low e equivalentes | Planejar cilindro | Amarelo | Migrar |
| `toner_low` | Toner | medium | toner low, near end, quase vazio | Planejar toner | Amarelo | Migrar |
| `idle` | Estado normal | green | idle, standby, espera | Nenhuma ação | Verde | Adaptar como estado |
| `sleep` | Estado normal | green | sleep, energy save | Nenhuma ação | Verde | Adaptar como estado |
| `ok` | Estado normal | green | ready, online, operational | Nenhuma ação | Verde | Migrar como normal |
| `unknown` | Fallback | medium | sem padrão | Verificar mensagem bruta | Amarelo/cinza | Migrar com telemetria |

Na v1, `low` e `medium` resultam em `warning`; `high` resulta em `error`.
O frontend converte `green` para verde, `low/medium` para amarelo e `high` para
vermelho. O banco é a fonte de verdade das regras.

## Services de Monitoramento

| Service | Responsabilidade | Lê | Escreve | Chamador/frequência | Reuso recomendado |
|---|---|---|---|---|---|
| `ping_service.py` | Um ICMP com timeout nominal de 1 s | Rede | Nada | Conectividade e coleta detalhada | Adaptar; adicionar TCP e timeout efetivo no Linux |
| `snmp_service.py` | GET, GET múltiplo e WALK v1/v2c | Rede SNMP | Nada | Todos os coletores | Migrar conceito e testes; encapsular credenciais por equipamento |
| `printer_monitor_service.py` | Seleção de OIDs, probe leve, normalização | `snmp_oids` | Nada | 60 s e 5 min | Separar conectividade de dados detalhados |
| `printer_status_service.py` | Regras, status atual, histórico e logs | status, alertas, papel | status, history, logs, papel e opcionalmente toner | 60 s/5 min/manual | Adaptar às tabelas em português da v2 |
| `alert_service.py` | Rules Engine dinâmica | `alerts` | Nada | Coleta de estado | Migrar quase integralmente |
| `paper_service.py` | OIDs de papel, fallback de versão, upsert atual | OIDs/papel | `paper_status` | Na v1: 5 min | Mover para coleta rica de 60 min |
| `paper_history_service.py` | Fechamento diário e agregações | impressoras/papel/history | `paper_history`, logs | 00:10 | Migrar após papel atual |
| `toner_service.py` | Printer-MIB, OID validado, HTML e estado atual | OIDs/modelos/papel/toner | `toner_status`, logs | Na v1: 30 min | Adaptar para 60 min e adapters por modelo |
| `toner_history_service.py` | Consulta read-only | `toner_history` | Nada | API/Admin | Postergar; fluxo automático de ciclo está incompleto |
| `printer_supply_service.py` | Projeção read-only para Protheus | impressoras/modelos/suprimentos | Nada | Integração sob demanda | Postergar para módulo de integração |
| `audit_service.py` | Auditoria genérica | Nada | `audit_logs` | Services/Admin | Manter o audit genérico da v2 |
| `frontend_dashboard_service.py` | BFF, agregações e severidade visual | várias tabelas operacionais | Nada | Requests do frontend | Não copiar inteiro; adaptar contratos da v2 |

### Tratamento de erro

- Falha em uma impressora faz rollback apenas daquela iteração e o lote segue.
- Falhas são incluídas no resumo da task.
- GET/WALK SNMP usam duas tentativas externas, timeout de 1 s por tentativa,
  zero retry interno e espera de 0,5 s.
- HTML usa timeout de 5 s e tenta caminhos em sequência.
- Logs estruturados registram eventos, equipamento e motivo.
- O lock é removido somente quando o token armazenado ainda pertence à task.
- A remoção de lock usa `GET` seguido de `DELETE`; o próprio código reconhece
  que Lua seria mais atômico.

## Tasks Celery

| Task | Agenda v1 | Escopo | Lock | Tabelas afetadas | Decisão v2 |
|---|---|---|---|---|---|
| `printer_monitor.debug_ping` | Manual | Diagnóstico | Não | Nenhuma | Manter como healthcheck seguro |
| `printer_monitor.celery_healthcheck` | Manual | Diagnóstico | Não | Nenhuma | Manter |
| `printer_monitor.monitor_printer` | Manual | Uma impressora ativa, coleta completa | Não | status, logs, history, papel, toner | Adaptar; adicionar lock por máquina |
| `printer_monitor.check_connectivity_all` | 60 s | Todas as ativas | Sim, global | status, logs, history | Migrar para ciclo de 60 s |
| `printer_monitor.monitor_status_paper_all` | 300 s | Somente ativas previamente online | Sim, global | status, logs, history, papel | Separar: estado em 5 min; papel em 60 min |
| `printer_monitor.monitor_toner_all` | 1.800 s | Somente ativas previamente online | Sim, global | toner status e logs | Adaptar para 3.600 s |
| `printer_monitor.monitor_all_printers` | Manual/legado | Alias de estado+papel | Lock de estado | Mesmo da task de 5 min | Descartar alias |
| `printer_monitor.generate_paper_history_daily` | 00:10 | Todas as ativas com contador | Sim, global | paper history e logs | Migrar após módulo de papel |

## Redis e Locks

Configuração confirmada:

- Redis DB 0: broker Celery.
- Redis DB 1: result backend.
- AOF habilitado no container.
- Redis também é usado para locks distribuídos.
- Não há cache do status operacional na v1.

| Rotina | Chave padrão | TTL |
|---|---|---:|
| Conectividade | `connectivity_check_lock` | 120 s |
| Estado e papel | `status_paper_monitor_lock` | 600 s |
| Toner | `toner_monitor_lock` | 1.800 s |
| Histórico diário de papel | `paper_history_daily_lock` | 600 s |

Configurações adicionais:

- `worker_prefetch_multiplier=1`.
- `task_acks_late=true`.
- Resultados expiram por padrão em 3.600 s.
- Retry de conexão do broker no startup está habilitado.
- O worker da auditoria usou quatro processos e executou duas tasks seguras.
- Foi observado aviso de worker executando como root no container; corrigir na
  v2 com usuário não privilegiado.

## Regras de Status

### Conectividade leve

1. Processa somente impressoras ativas.
2. Se o ping falha: `offline`.
3. Se o ping responde, mas não há OID para probe: `no_snmp`.
4. Se o OID existe, mas não retorna valor: `no_snmp`.
5. Se ping e SNMP respondem: `online`.

Não existe teste TCP. Também não existe fallback HTML/HTTPS para conectividade.

### Coleta detalhada

- Ping falhou: conexão `offline`, severidade `high`.
- SNMP sem resposta: `no_snmp`, severidade `medium`.
- Métricas obrigatórias sem valor: conexão `online`, severidade `medium`.
- Modelo/OIDs incompletos: `unknown`, severidade `medium`.
- SNMP completo: `online`; o estado operacional é calculado pela regra de
  alerta.

### Persistência e transição

- Existe uma única fotografia atual por impressora.
- O primeiro resultado cria status, histórico e log inicial.
- Histórico e log de transição são gravados somente quando conexão, operação,
  alerta ou severidade mudam.
- Campos de telemetria são atualizados no status atual.
- O banco é a fonte principal; Redis não guarda a fotografia atual.
- A v1 não edita status por uma API pública de escrita.

## Regras de Toner

Ordem da v1:

1. WALK da Printer-MIB.
2. OID de fallback ativo e validado em `snmp_oids`.
3. Página web de status.

Bases Printer-MIB:

- tipo: `1.3.6.1.2.1.43.11.1.1.5`;
- descrição: `1.3.6.1.2.1.43.11.1.1.6`;
- capacidade máxima: `1.3.6.1.2.1.43.11.1.1.8`;
- nível atual: `1.3.6.1.2.1.43.11.1.1.9`.

A v1:

- identifica múltiplos suprimentos;
- usa `supply_index`;
- normaliza cor, nível e capacidade;
- exclui itens que não são toner;
- aceita fontes `printer_mib`, `snmp_oids`, `web_status` e `unavailable`;
- remove da exibição leituras antigas de OIDs desativados;
- registra falhas e fallback em logs.

Os caminhos HTML existentes são `/home/status.html`, `/general/status.html` e
`/`. O caminho `/general/information.html?kind=item`, já identificado para a
DCP-L1632W, não existe na v1 e deve entrar no adapter Brother da v2.

`toner_history` e helpers de abertura/fechamento existem, mas não foi encontrado
um fluxo automático completo de troca. Portanto, o modelo é reaproveitável,
mas o ciclo deve ser especificado antes da migração.

## Regras de Papel

- OIDs aceitos: total, A4 e A3.
- O contador total usa a Printer-MIB no seed padrão.
- A4/A3 só são preenchidos quando houver OID validado.
- Se a versão SNMP configurada falha, o service tenta a alternativa v1/v2c.
- `paper_status` contém a fotografia atual, uma linha por impressora.
- Na v1 o papel é coletado junto do estado a cada 5 minutos.
- `paper_history` registra um snapshot diário imutável.
- O primeiro fechamento cria baseline com consumo zero.
- Queda de contador é tratada como reset e consumo zero.
- O fechamento ignora máquina inativa, registro já existente e máquina sem
  status atual, registrando o motivo.
- A tela soma ao histórico fechado um delta vivo do contador atual.

Para a v2, papel deve sair da task de 5 minutos e entrar na coleta rica de
60 minutos. O fechamento diário pode ser mantido.

## Histórico e Logs

| Estrutura | Comportamento | Avaliação |
|---|---|---|
| `printer_status_history` | Transições antigas/novas de status, alerta e severidade | Consolidado; adaptar para `logs_impressoras` ou histórico dedicado |
| `logs` | Eventos técnicos por impressora | Útil, mas parcialmente sobreposto aos logs da v2 |
| `audit_logs` | Alterações administrativas/genéricas | Já existe na v2; manter |
| `paper_history` | Histórico diário imutável | Consolidado |
| `toner_history` | Ciclo de instalação/remoção e rendimento | Estrutura boa, fluxo automático incompleto |

Status e logs operacionais devem continuar somente para consulta no frontend e
no Django Admin. Escritas devem ocorrer exclusivamente pelos serviços e tasks.

## O que está consolidado

- Separação entre cadastro, status atual e histórico.
- OIDs por modelo e métrica, administráveis no banco.
- Rules Engine de alertas com prioridade e fallback.
- SNMP v1/v2c com retry externo controlado.
- Separação de conectividade leve e coletas mais pesadas.
- Processamento somente de máquinas ativas.
- Coletas pesadas somente para máquinas previamente online.
- Locks distintos por rotina.
- Continuidade do lote quando uma impressora falha.
- Toner com Printer-MIB, múltiplos suprimentos e fallback.
- Papel atual mais histórico diário imutável.
- Testes unitários para tasks, locks, alertas, papel, toner e contratos.

## O que deve ser migrado

- Conceito de `snmp_oids`, com nomes de tabela/colunas em português na v2.
- Rules Engine de alertas e seu seed.
- Cliente SNMP e testes de retry, após atualizar dependências.
- Ciclo de conectividade de 60 segundos.
- Ciclo de estado/alerta de 5 minutos.
- Locks com token e isolamento por rotina.
- Estado atual, transições e logs auditáveis.
- Coleta Printer-MIB e múltiplos `supply_index`.
- Papel atual e fechamento diário.
- Healthchecks seguros do worker.

## O que deve ser melhorado

- Acrescentar TCP e HTML/HTTPS à conectividade.
- Tornar a remoção de lock atômica com script Lua.
- Adicionar lock por máquina nas coletas individuais/profundas.
- Executar worker como usuário não root.
- Separar papel da task de estado.
- Alterar toner de 30 para 60 minutos.
- Criar adapters por fabricante/modelo.
- Registrar origem, tentativas, latência e motivo do fallback.
- Usar Redis como cache rápido com TTL, sem torná-lo fonte única.
- Evitar duplicidade `page_count`/`page_count_total`.
- Validar os OIDs por modelo antes de cadastrá-los como ativos.
- Definir retenção/particionamento para logs e históricos.
- Implementar healthcheck HTTP explícito na API.

## O que deve ser descartado

- Alias legado `monitor_all_printers`.
- OIDs privados marcados como inválidos.
- Cópia direta do BFF e da estrutura antiga.
- Mistura de papel com a task de estado de 5 minutos.
- Nome técnico legado da app Celery.
- Escrita manual de status/logs.
- Dados reais contidos nos seeds locais.

## Comparativo v1 x v2

| Item v1 | Estado na v1 | Existe na v2? | Ação recomendada | Motivo | Risco |
|---|---|---|---|---|---|
| Redis | Broker, backend e locks | Não | Reintroduzir na Etapa 3.5 | Necessário para filas, locks e cache rápido | Médio |
| Celery worker | Estável e testado | Não | Reintroduzir | Coleta fora do request HTTP | Médio |
| Celery Beat | Quatro agendas | Não | Reintroduzir com novas frequências | Agenda distribuída | Médio |
| Locks | Globais por rotina | Não | Adaptar | Evita sobreposição; precisa atomicidade | Médio |
| `check_connectivity_all` | 60 s, ping+SNMP | Não | Adaptar | Frequência já coincide | Médio |
| `monitor_status_paper_all` | 5 min, estado+papel | Não | Dividir | Papel deve ir para 60 min | Médio |
| `monitor_toner_all` | 30 min | Não | Adaptar para 60 min | Regra definida para v2 | Baixo |
| `snmp_oids` | Flexível por modelo/métrica | Não | Migrar com schema em português | Evita hardcode | Médio |
| `alerts` | Rules Engine dinâmica | Não | Migrar/adaptar | Regras maduras | Baixo |
| `printer_status` | Fotografia atual | `status_impressoras` | Mapear para modelo atual | V2 já tem contrato em português | Médio |
| `printer_status_history` | Histórico de transições | `logs_impressoras` parcialmente | Consolidar | Evitar históricos duplicados | Médio |
| `logs` | Log técnico | `logs_impressoras` e log genérico | Adaptar | Separar operação de auditoria | Médio |
| `audit_logs` | Auditoria genérica | Sim | Manter v2 | Já está modular | Baixo |
| `toner_status` | Atual, múltiplos supplies | Não | Postergar para coleta rica | Depende de adapter e modelo | Médio |
| `toner_history` | Estrutura parcial | Não | Postergar | Fluxo de troca precisa definição | Alto |
| `paper_status` | Atual total/A4/A3 | Placeholder | Implementar na coleta rica | Base estável | Médio |
| `paper_history` | Diário imutável | Não | Migrar após papel atual | Boa base analítica | Baixo |
| `printer_supplies` | Protheus | Não | Postergar | Fora da Etapa 3.5 | Baixo |
| Fallback web | Apenas toner | Não | Expandir por adapter | Brother depende de HTML confiável | Médio |

## Proposta para Etapa 3.5 na v2

### Estrutura sugerida

```text
backend/app/modules/printers/
  monitoring/
    connectivity/
      services.py
      tasks.py
    state/
      services.py
      rules.py
      tasks.py
    rich_data/
      services.py
      tasks.py
    adapters/
      base.py
      snmp.py
      html.py
      brother_dcp_l1632w.py
    locks.py
    cache.py
    telemetry.py
    tests/
```

Não é necessário copiar arquivos inteiros da v1. Services pequenos e regras
testadas devem ser portados para os contratos e tabelas atuais da v2.

### Agenda proposta

| Fila/task | Frequência | Máquinas | Estratégia |
|---|---:|---|---|
| `printers.connectivity` | 60 s | Ativas | Ping/TCP -> SNMP -> HTML/HTTPS |
| `printers.state` | 5 min | Ativas e preferencialmente online | SNMP -> HTML/HTTPS |
| `printers.rich_data` | 60 min | Ativas e online | Adapter por modelo; HTML/HTTPS primeiro para DCP-L1632W |
| `printers.paper_history` | Diário, 00:10 | Ativas com contador | Fechamento idempotente |

### Adapter Brother DCP-L1632W

- Conectividade:
  1. ICMP, quando permitido pela rede.
  2. TCP curto em porta configurável, inicialmente 80/443.
  3. Probe SNMP leve.
  4. GET HTML/HTTPS com leitura mínima.
- Estado/alertas:
  1. `alert_raw` por SNMP.
  2. `/home/status.html` quando SNMP falhar ou for inconclusivo.
- Dados ricos:
  1. `/general/information.html?kind=item`.
  2. `/home/status.html`.
  3. Printer-MIB/OIDs validados para completar lacunas.

O adapter deve devolver um resultado normalizado, sem persistir diretamente:

```text
origem: ping | tcp | snmp | html | fallback
sucesso: boolean
latencia_ms: inteiro
tentativas: inteiro
dados: objeto normalizado
erro_codigo: texto opcional
erro_detalhe: texto sanitizado opcional
coletado_em: data/hora
```

### Redis e persistência

- Redis recebe o último resultado rápido de conectividade com TTL ligeiramente
  superior a 60 segundos.
- O banco continua como fonte histórica e transacional.
- Gravar `status_impressoras` somente quando houver mudança relevante ou quando
  for necessário atualizar timestamps operacionais.
- Gravar `logs_impressoras` em transições, falhas relevantes e recuperação.
- Criar snapshots programados para dados ricos, evitando escrita a cada probe.
- Usar lock global curto por agenda e lock por máquina para impedir concorrência
  entre coletas.
- Processar somente `printer_machines.is_active=true`.
- Coletas profundas só entram na fila quando o estado rápido não for offline.

### Tabelas futuras sugeridas em português

- `configuracoes_oids_impressoras`;
- `regras_alertas_impressoras`;
- `tentativas_coleta_impressoras`;
- `status_suprimentos_impressoras`;
- `historico_suprimentos_impressoras`;
- `status_papel_impressoras`;
- `historico_papel_impressoras`.

`status_impressoras` e `logs_impressoras` já existem e devem ser evoluídas por
migration, sem criar tabelas paralelas em inglês.

## Riscos e cuidados

- ICMP pode ser bloqueado apesar de a impressora estar disponível.
- Porta HTTP aberta não garante que o equipamento esteja operacional.
- HTML de firmware pode mudar por versão, idioma ou fabricante.
- SNMP v1/v2c usa community; segredos não podem ficar no código ou nos logs.
- OIDs privados Brother já produziram falso positivo de toner.
- Um lock global longo pode atrasar toda a frota.
- `task_acks_late` exige idempotência real.
- Históricos sem política de retenção podem crescer rapidamente.
- Respostas HTML/SNMP brutas podem conter dados sensíveis e devem ser
  sanitizadas ou limitadas.
- O schema da v2 usa termos em português e não deve receber tabelas antigas por
  cópia direta.
- O Compose atual da v2 ainda não possui Redis/Celery; a reintrodução deve vir
  acompanhada de healthchecks, usuário não root e testes de integração.

## Validações executadas

| Validação | Resultado |
|---|---|
| Build dos containers selecionados da v1 | OK |
| Postgres | Healthy |
| Redis `PING` | `PONG` |
| Migrations | Exit `0` |
| Inspeção de tabelas/colunas/constraints/índices | OK |
| Seed seguro de alertas | 16 regras |
| API | Container ativo |
| Django Admin | Respondeu com redirect para login |
| Frontend | Respondeu com redirect para rota inicial |
| Worker Celery | Online |
| `celery inspect ping` | 1 nó, `pong` |
| `debug_ping` | OK |
| `celery_healthcheck` | OK |
| Celery Beat | Não iniciado por segurança |
| Testes v1 | 190 passed, 34 warnings |
| `python manage.py check` | Sem problemas |
| Coleta real de impressoras | Não executada |

Os 34 warnings são de depreciações em `pysnmp`, `asyncore` e no atalho antigo do
HTTPX. Eles não bloquearam os testes, mas reforçam a necessidade de atualizar a
camada SNMP na v2.

## Próximos passos recomendados

1. Aprovar o modelo de dados em português para OIDs, regras e tentativas.
2. Criar a infraestrutura Redis/Celery da v2 com healthchecks e usuário não
   privilegiado.
3. Implementar somente o ciclo de conectividade de 60 segundos.
4. Validar a DCP-L1632W com mocks/fixtures HTML antes de qualquer teste em rede.
5. Implementar o adapter Brother com os dois caminhos HTML identificados.
6. Portar a Rules Engine e o ciclo de estado de 5 minutos.
7. Adicionar a coleta rica de 60 minutos.
8. Só então migrar papel, toner e seus históricos.

## Conclusão

A v1 possui uma base de monitoramento aproveitável e bem testada, especialmente
na separação de status atual/histórico, Rules Engine, SNMP, locks e isolamento
de falhas por impressora. A v2 não deve reconstruir isso do zero, mas também não
deve copiar a estrutura antiga inteira.

O caminho de menor risco é portar os conceitos e testes em três ciclos
independentes, adicionar adapters por modelo e ampliar a cascata para
Ping/TCP, SNMP e HTML/HTTPS. Para a Brother DCP-L1632W, o HTML deve ser tratado
como fonte de primeira classe para dados ricos.
