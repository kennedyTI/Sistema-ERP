# Integracao GLPI - abertura de chamados

## Objetivo

Esta base integra o Sistema ERP com a API REST v1 do GLPI para abertura exata
e idempotente de chamados. O primeiro consumidor e o modulo Impressoras, apenas
para alertas confirmados de substituicao de toner ou cilindro.

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
GLPI_REQUESTER_USER_ID=
GLPI_TIMEOUT_SECONDS=10
GLPI_VERIFY_SSL=true
```

Tokens reais devem existir somente no ambiente seguro. Eles nao podem aparecer
em arquivos versionados, logs, payload persistido, respostas ou relatorios.

Entidade, categoria, localizacao e tipo de origem sao obrigatorios para abertura
exata. Se algum estiver ausente, o registro fica como
`bloqueado_dados_incompletos` e nenhuma requisicao e enviada.

## Persistencia e deduplicacao

`glpi_chamados` e generica e registra origem, evento, titulo, descricao, IDs de
roteamento, ticket ID, payload efetivamente enviado, resposta sanitizada, erro,
tentativas e datas. `encerrado_em` e `normalizado_em` ficam preparados para
etapas futuras, sem automacao nesta entrega.

Hashes iniciais de Impressoras:

```text
impressoras:maquina:{id}:substituir_toner:{cor}
impressoras:maquina:{id}:substituir_cilindro
```

Um registro `pendente` ou `aberto`, sem `encerrado_em`, impede nova abertura.
Registros com erro ou bloqueio podem ser reutilizados em tentativa posterior,
sem criar duplicatas.

## Seguranca

- nenhuma chamada usa scraping HTML;
- tokens nunca sao registrados pelo cliente;
- respostas passam por remocao recursiva de campos sensiveis;
- erro persistido nao inclui headers ou corpo bruto;
- timeout e verificacao TLS sao configuraveis;
- nenhuma chamada externa ocorre enquanto `GLPI_ENABLED=false`.

## Proximos passos

1. validar os IDs de entidade, categoria e localizacao no ambiente GLPI;
2. executar abertura controlada em homologacao com credenciais fora do Git;
3. definir normalizacao do evento e encerramento futuro;
4. somente depois avaliar fechamento, estoque ou Protheus.
