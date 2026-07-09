# Integracao GLPI - abertura de chamados

## Objetivo

Esta base integra o Sistema ERP com a API REST v1 do GLPI para abertura exata
e idempotente de chamados. O primeiro consumidor e o modulo Impressoras, apenas
para toner critico confirmado por percentual e alerta confirmado de
substituicao de cilindro.

O modulo generico fica em `backend/app/modules/integracoes/glpi`. O modulo
Impressoras monta os dados de negocio e nao conhece URL, headers, sessao ou
autenticacao HTTP do GLPI.

## Escopo atual

- autenticacao por `App-Token` e `user_token`;
- abertura por `POST /apirest.php/Ticket`;
- encerramento da sessao GLPI depois da tentativa;
- persistencia da tentativa em `glpi_chamados`;
- deduplicacao por evento ativo;
- registro de resposta, ticket ID e erro sanitizado;
- bloqueio antes da API quando faltam rota GLPI, codigo Protheus ou cor segura.
- envio configuravel de urgencia, requerente, usuario atribuido e grupo
  atribuido no payload do ticket.

Fechamento, solucao, estoque, Protheus, Cartuchos GLPI, dashboard, Papel e
outros tipos de alerta permanecem fora do escopo.

## Configuracao

A integracao nasce desabilitada. Configure o ambiente e habilite somente depois
de validar os IDs com a administracao do GLPI:

```text
GLPI_ENABLED=false
GLPI_BASE_URL=https://glpi.example.com
GLPI_APP_TOKEN=change-me
GLPI_USER_TOKEN=change-me
GLPI_ENTITY_ID=1
GLPI_TICKET_CATEGORY_IMPRESSORAS_INSUMO_ID=77
GLPI_LOCATION_CARIACICA_ID=
GLPI_REQUEST_TYPE_ID=1
GLPI_DEFAULT_TYPE=2
GLPI_DEFAULT_STATUS=1
GLPI_DEFAULT_IMPACT=3
GLPI_DEFAULT_PRIORITY=3
GLPI_DEFAULT_URGENCY=3
GLPI_REQUESTER_USER_ID=
GLPI_ASSIGN_USER_ID=
GLPI_ASSIGN_GROUP_ID=
GLPI_TIMEOUT_SECONDS=10
GLPI_VERIFY_SSL=true
```

Tokens reais devem existir somente no ambiente seguro. Eles nao podem aparecer
em arquivos versionados, logs, payload persistido, respostas ou relatorios.

Entidade, categoria, localizacao, tipo de origem, requerente e atribuicao
usuario/grupo sao obrigatorios para abertura exata quando a integracao estiver
habilitada. Se algum estiver ausente, o registro fica como
`bloqueado_dados_incompletos` e nenhuma requisicao e enviada.

## Contrato atual de Impressoras

### Titulo

O titulo enviado ao GLPI segue o formato:

```text
Toner abaixo de 10% - {local}
Substituir cilindro - {local}
```

### Corpo

O corpo do chamado contem somente dados operacionais necessarios:

```text
Local: {local}
Nome da maquina: {nome_maquina}
Modelo: {fabricante} {modelo}
IP: {ip}
Centro de custo: {centro_custo}
Codigo do produto: {cor codigo | cor codigo}

O(s) toner(s) {cores} da impressora {nome_maquina} esta(ao) abaixo de 10%.
Chamado aberto para acompanhamento tecnico!
```

Para cilindro, a mensagem final e:

```text
O cilindro da impressora {nome_maquina} precisa ser substituido.
Chamado aberto para acompanhamento tecnico!
```

### Regras de abertura

- Toner abre chamado somente quando o percentual atual esta abaixo de 10.
- Impressora monocromatica abre chamado para preto abaixo de 10.
- Impressora colorida abre um unico chamado com todas as cores abaixo de 10 e
  todos os codigos Protheus correspondentes.
- Toner colorido sem cor segura ou sem codigo Protheus nao abre chamado e gera
  bloqueio local claro.
- Cilindro abre chamado somente por alerta confirmado de substituicao de
  cilindro ou alias equivalente normalizado pela Rules Engine.
- Percentual de cilindro nao e gatilho nesta etapa.
- Toner baixo, papel, tampa, offline, erro momentaneo e outros alertas nao
  abrem chamado GLPI.

## Persistencia e deduplicacao

`glpi_chamados` e generica e registra origem, evento, titulo, descricao, IDs de
roteamento, ticket ID, payload efetivamente enviado, resposta sanitizada, erro,
tentativas e datas. `encerrado_em` e `normalizado_em` ficam preparados para
etapas futuras, sem automacao nesta entrega.

Hashes atuais de Impressoras:

```text
impressoras:maquina:{id}:toner_abaixo_10
impressoras:maquina:{id}:substituir_cilindro
```

Um registro `pendente` ou `aberto`, sem `encerrado_em`, impede nova abertura.
Registros com erro ou bloqueio podem ser reutilizados em tentativa posterior,
sem criar duplicatas.

Para toner colorido, o hash principal fica por maquina e evento. As cores e
codigos seguem nos metadados/payload, evitando novo chamado quando outra cor
fica critica enquanto ja existe chamado ativo da mesma impressora.

## Seguranca

- nenhuma chamada usa scraping HTML;
- tokens nunca sao registrados pelo cliente;
- respostas passam por remocao recursiva de campos sensiveis;
- erro persistido nao inclui headers ou corpo bruto;
- timeout e verificacao TLS sao configuraveis;
- nenhuma chamada externa ocorre enquanto `GLPI_ENABLED=false`.

## Validacao real controlada

Em 2026-07-09 foi executado um teste real e controlado em ambiente
local/homologacao, com credenciais fora do Git e sem habilitar a integracao por
padrao.

Chamados criados:

- toner: ticket GLPI `15252`, registro local `glpi_chamados.id=1`;
- cilindro: ticket GLPI `15253`, registro local `glpi_chamados.id=2`.

Validacoes confirmadas:

- titulo e corpo seguiram o contrato atual;
- entidade `1`, categoria `77`, localizacao `1`, origem `1`, impacto `3`,
  prioridade `3` e urgencia `3` foram aceitos pelo GLPI;
- requerente `1781`, usuario atribuido `1257` e grupo atribuido `2` foram
  aplicados;
- `payload_enviado`, `resposta_glpi`, `glpi_ticket_id` e status local foram
  persistidos em `glpi_chamados`;
- repeticoes controladas respeitaram o hash de deduplicacao e nao abriram novos
  tickets.

Observacao operacional: o payload enviou `status=1`, mas o GLPI retornou
`status=2` apos a atribuicao automatica de usuario/grupo. A decisao desta etapa
e aceitar `status=2` como comportamento esperado quando a atribuicao ocorre no
momento da abertura.

Nenhum fechamento automatico foi executado. Antes de promover esta etapa para
`main`, deve ser feita uma homologacao completa em ciclo real de coleta para
confirmar ausencia de duplicidade em alertas recorrentes.

## Fluxo Git da etapa

Branch de trabalho: `feature/integracao-glpi-chamados-impressoras`.

Fluxo aprovado: validar a branch, integrar em `develop` e manter `main`
bloqueada ate a homologacao completa do ciclo real de coleta. O motivo do
bloqueio e validar o risco operacional de chamados duplicados quando alertas
persistem por varios ciclos.

## Proximos passos

1. executar homologacao completa em ciclo real de coleta;
2. confirmar que alertas recorrentes nao abrem tickets duplicados;
3. definir normalizacao do evento e encerramento futuro;
4. somente depois avaliar fechamento, estoque ou Protheus.
