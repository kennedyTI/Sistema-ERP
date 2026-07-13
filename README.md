# Sistema ERP v2

Sistema ERP modular desenvolvido para demonstrar uma arquitetura corporativa moderna, com backend em FastAPI, administração via Django Admin, autenticação centralizada, permissões por grupos, frontend React/Vite e execução em containers Docker com proxy HTTPS.

A versão atual publicada é a **v2.4.1 — Toner de impressoras**.

Registro detalhado da release: [docs/releases/v2.4.1-toner-impressoras.md](docs/releases/v2.4.1-toner-impressoras.md).

---

## Visão geral

O Sistema ERP v2 foi estruturado como uma base evolutiva para módulos corporativos. A aplicação possui separação clara entre frontend, API, administração interna e banco de dados.

A plataforma já contém:

- autenticação com Django Auth + JWT;
- administração interna via Django Admin;
- permissões administradas por grupos;
- API FastAPI versionada em `/api/v2`;
- frontend React/Vite com rotas protegidas;
- infraestrutura Docker Compose;
- proxy reverso Nginx com HTTPS local;
- Redis e Celery para conectividade assíncrona de impressoras;
- módulo Impressoras em evolução incremental.

O módulo Impressoras é o primeiro domínio operacional do sistema. Ele já possui cadastro de máquinas, status operacional, alertas operacionais, permissões granulares, imagens de modelos, auditoria cadastral e interface responsiva.

---

## Problema resolvido

O projeto resolve a necessidade de criar uma base ERP modular, segura e evolutiva, capaz de receber novos domínios sem acoplar regras de negócio à interface ou ao banco de forma improvisada.

No módulo Impressoras, a versão atual resolve problemas como:

- cadastro centralizado de máquinas;
- separação entre status cadastral e status operacional;
- consulta operacional somente de máquinas ativas;
- coleta e exibição de alertas operacionais atuais;
- histórico de alertas e logs consultivos;
- proteção contra edição manual de status e logs operacionais;
- controle de permissões pelo Django Admin;
- edição cadastral com validação por campo;
- controle de concorrência por `atualizado_em`;
- auditoria de edição e ativação/inativação;
- interface responsiva para desktop, notebook, tablet e celular.

---

## Principais funcionalidades

### Plataforma

- Login com JWT;
- rota protegida para usuários autenticados;
- grupos e permissões gerenciados pelo Django Admin;
- Admin separado da API principal;
- proxy HTTPS local;
- build e execução via Docker Compose;
- testes automatizados de backend.

### Módulo Impressoras

- menu condicionado por permissões;
- tela Dashboard placeholder;
- tela Papel placeholder;
- cadastro de Máquinas;
- cards de resumo cadastral;
- listagem completa, sem paginação;
- máquinas ativas e inativas na tela Máquinas;
- status operacional apenas para máquinas ativas;
- conectividade automática a cada 60 segundos;
- confirmação em cascata por ICMP, TCP, SNMP e HTML/HTTP;
- histórico de mudanças confirmadas online/offline;
- alertas operacionais coletados e sincronizados em ciclo agendado;
- regras de alertas, OIDs SNMP e credenciais de coleta administradas pelo Django Admin;
- priorização por severidade e alternância de alertas equivalentes no Status;
- fallback HTML/HTTP por modelo e fallback IPP para modelos HP compatíveis;
- logs operacionais das últimas 24 horas no detalhe de Status;
- modal único de consulta e edição;
- toggle Ativo/Inativo sem reload;
- validação por campo;
- conflito de concorrência por `atualizado_em`;
- imagens de modelos por `url_imagem`;
- fallback visual `Imagem não disponível`;
- colunas configuráveis e reordenáveis;
- preferências de colunas por usuário;
- feedback visual no arraste de colunas;
- responsividade mobile.

---

## Arquitetura

O projeto utiliza uma arquitetura modular com separação entre camadas de apresentação, API, administração e persistência.

```text
Usuário
  ↓ HTTPS
sistema_erp_proxy
  ↓
frontend / api / admin
  ↓
postgres
```

### Serviços Docker

| Serviço Compose | Container | Função |
| ---------------- | --------- | ------ |
| `sistema_erp_proxy` | `sistema_erp_proxy` | Proxy reverso Nginx com HTTPS |
| `frontend` | `portal_industria_frontend` | Interface web React/Vite |
| `api` | `portal_industria_api` | API FastAPI |
| `admin` | `portal_industria_admin` | Django Admin |
| `postgres` | `portal_industria_postgres` | Banco PostgreSQL |
| `migrations` | `portal_industria_migrations` | Execução das migrations e seeds iniciais |
| `redis` | `portal_industria_redis` | Broker, cache transitório e locks de conectividade |
| `celery-worker` | `portal_industria_celery_worker` | Execução das coletas de conectividade e alertas |
| `celery-beat` | `portal_industria_celery_beat` | Agendamento dos ciclos de conectividade e alertas |

### Regras arquiteturais importantes

- O frontend não decide permissões sozinho; ele obedece às permissões retornadas pelo backend.
- O Django Admin e o banco centralizam a configuração de grupos e permissões.
- Tabelas e colunas novas do banco devem ser criadas em português.
- Código-fonte pode permanecer em inglês.
- API e textos visíveis ao usuário devem permanecer em português daqui para frente.
- Status e logs operacionais de Impressoras são somente leitura por Admin/API manual.
- Máquinas inativas aparecem em Máquinas, mas não aparecem em Status.

---

## Tecnologias utilizadas

### Backend

- Python;
- FastAPI;
- Django Admin;
- Django Auth;
- SQLAlchemy;
- Alembic;
- PostgreSQL;
- JWT;
- Pytest.
- Redis;
- Celery;
- PySNMP.

### Frontend

- React;
- Vite;
- TypeScript;
- Tailwind CSS;
- componentes UI modulares;
- Sonner para feedback visual.

### Infraestrutura

- Docker;
- Docker Compose;
- Nginx;
- HTTPS local com certificado self-signed.

---

## Estrutura do projeto

```text
sistema_erp/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   ├── migrations/
│   │   ├── modules/
│   │   │   ├── audit/
│   │   │   ├── auth/
│   │   │   ├── backoffice/
│   │   │   └── printers/
│   │   │       ├── dashboard/
│   │   │       ├── machines/
│   │   │       ├── paper/
│   │   │       └── status/
│   │   ├── shared/
│   │   └── main.py
│   ├── backoffice/
│   └── scripts/
│
├── frontend/
│   ├── public/
│   │   └── static/imgs/printers/
│   └── src/
│       ├── app/
│       ├── modules/
│       │   ├── auth/
│       │   ├── home/
│       │   └── printers/
│       │       ├── dashboard/
│       │       ├── machines/
│       │       ├── paper/
│       │       ├── shared/
│       │       └── status/
│       ├── routes/
│       └── shared/
│
├── docker/
│   └── nginx/
├── docs/
│   └── releases/
├── docker-compose.yml
├── Dockerfile
├── manage.py
└── README.md
```

---

## Como executar localmente

Copie os arquivos de exemplo antes de iniciar:

```bash
cp .env.example .env
cp .env.docker.example .env.docker
cp backend/.env.example backend/.env
```

No Windows PowerShell:

```powershell
Copy-Item .env.example .env
Copy-Item .env.docker.example .env.docker
Copy-Item backend/.env.example backend/.env
```

Revise os valores conforme o ambiente local.

Suba os serviços:

```bash
docker compose --env-file .env.docker up -d --build
```

Verifique os containers:

```bash
docker compose --env-file .env.docker ps -a
```

Acesse:

```text
https://localhost:8443/login
https://localhost:8443/inicio
https://localhost:8443/admin/
https://localhost:8443/impressoras/dashboard
https://localhost:8443/impressoras/status
https://localhost:8443/impressoras/maquinas
https://localhost:8443/impressoras/papel
```

Para parar:

```bash
docker compose --env-file .env.docker down
```

Para parar e remover volumes locais:

```bash
docker compose --env-file .env.docker down -v
```

Use `down -v` com cuidado, pois ele remove dados locais do banco.

---

## Docker

### Portas locais

| Serviço     | Porta  |
| ----------- | ------ |
| HTTP local  | `8080` |
| HTTPS local | `8443` |

O acesso HTTP redireciona para HTTPS:

```text
http://localhost:8080 → https://localhost:8443
```

As portas externas podem ser alteradas no `.env.docker`:

```env
NGINX_HTTP_PORT=8080
NGINX_HTTPS_PORT=8443
```

### Certificado HTTPS local

O proxy espera os arquivos:

```text
docker/nginx/certs/localhost.crt
docker/nginx/certs/localhost.key
```

Esses arquivos não são versionados.

Exemplo de certificado local self-signed:

```bash
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout docker/nginx/certs/localhost.key \
  -out docker/nginx/certs/localhost.crt \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

O navegador pode exibir aviso de segurança por se tratar de certificado local. Em homologação ou produção, use certificado oficial da infraestrutura.

### Comandos úteis

Criar superusuário do Django Admin:

```bash
docker compose --env-file .env.docker exec admin python manage.py createsuperuser
```

Rodar testes:

```bash
docker compose --env-file .env.docker exec api pytest -q
```

Verificar Django:

```bash
docker compose --env-file .env.docker exec admin python manage.py check
```

Compilar Python:

```bash
docker compose --env-file .env.docker exec api python -m compileall -q backend
```

Build do frontend:

```bash
docker compose --env-file .env.docker run --rm frontend npm run build
```

---

## Autenticação e permissões

O sistema utiliza Django Auth como fonte de usuários, grupos e permissões. O frontend consome as permissões retornadas por `/api/v2/auth/me` e exibe menus, rotas e botões conforme o que o backend autoriza.

### Grupos principais

| Grupo                 | Acesso esperado                                                |
| --------------------- | -------------------------------------------------------------- |
| `Equipe Técnica`      | Início, Impressoras, Dashboard, Status, Máquinas, Papel e Admin |
| `Gestor`              | Início, Impressoras, Dashboard, Status, Máquinas e Papel        |
| `Operador`            | Início, Impressoras, Dashboard e Status                        |
| `Integração Protheus` | Sem acesso ao portal visual                                    |

### Permissões do módulo Impressoras

- `impressoras.ver_dashboard`;
- `impressoras.ver_status`;
- `impressoras.ver_maquinas`;
- `impressoras.criar_maquinas`;
- `impressoras.editar_maquinas`;
- `impressoras.alternar_status_maquinas`;
- `impressoras.ver_papel`.

O comando idempotente abaixo cria e atualiza os grupos/permissões oficiais:

```bash
docker compose --env-file .env.docker exec admin python manage.py seed_admin_groups
```

### Contrato de permissões

O endpoint `/api/v2/auth/me` expõe permissões em português para o frontend:

```json
{
  "permissoes": {
    "impressoras": {
      "ver_dashboard": true,
      "ver_status": true,
      "ver_maquinas": true,
      "criar_maquinas": true,
      "editar_maquinas": true,
      "alternar_status_maquinas": true,
      "ver_papel": true
    }
  }
}
```

---

## Roadmap

### Etapas do módulo Impressoras

| Etapa | Descrição | Status |
| ----- | --------- | ------ |
| Etapa 1 | Fundação do módulo Impressoras | Concluída |
| Etapa 2 | Cadastro de Máquinas | Concluída |
| Etapa 3 | Status e Dashboard | Parcial: Status concluído; Dashboard real pendente |
| Etapa 4 | Papel, Toner e Histórico | Parcial: percentual de toner em desenvolvimento |
| Etapa 3.5.1 | Conectividade 60s com Redis/Celery e histórico confirmado | Concluída |
| Etapa 3.5.2 | Alertas e estado da máquina em 5min | Concluída |
| Etapa 3.5.3 | Percentual de toner via Printer-MIB em 60min | Em desenvolvimento |
| Etapa 3.5.4 | Papel e históricos ampliados | Não iniciada |
| Etapa 3.5.5 | Dashboard operacional | Não iniciada |

### Próximas frentes planejadas

- Dashboard real do módulo Impressoras;
- catálogo próprio de modelos de impressora;
- Papel;
- ampliação da coleta de Toner;
- histórico operacional ampliado;
- integração Protheus;
- integração bdTotvs documentada em `docs/integracoes/bdTotvs.md`;
- integração GLPI;
- coleta rica de informações em ciclos de 60 minutos;
- assistente Telegram em etapa futura.

### Branches planejadas para evolução futura

As próximas features podem seguir a nomenclatura abaixo, quando os respectivos escopos forem iniciados:

```text
develop
  feature/printers-dashboard-module
  feature/paper-monitoring-module
  feature/toner-monitoring-module
  feature/alerts-module
  feature/protheus-integration
  feature/telegram-assistant
```

Observação: as branches já entregues até a versão atual tiveram nomes incrementais diferentes, preservados no histórico Git.

---

## Releases

### Publicadas

| Release | Descrição |
| ------- | --------- |
| `v2.0.0-base` | Base modular institucional |
| `v2.1.0-modulo-impressoras-base` | Fundação do módulo Impressoras |
| `v2.2.0-printers-machines-crud` | Cadastro inicial de máquinas |
| `v2.3.0-maquinas-e-status-operacional` | Máquinas, status operacional e polimento visual |
| `v2.4.0-status-alertas-impressoras` | Status e alertas de impressoras |
| `v2.4.1-toner-impressoras` | Coleta percentual e regras operacionais de toner |

### Planejadas

| Release planejada | Escopo previsto |
| ----------------- | --------------- |
| `v2.5.0-integracao-glpi-chamados` | Integração de chamados com GLPI |
| `v2.6.0-dashboard-impressoras` | Dashboard real do módulo Impressoras |
| `v2.7.0-suprimentos` | Papel e histórico ampliado |

As tags publicadas não devem ser reescritas. Ajustes documentais posteriores à publicação podem entrar em commits normais de documentação.

---

## Screenshots

Pasta sugerida para imagens de documentação:

```text
docs/screenshots/
```

Screenshots recomendados para o portfólio:

- login;
- tela inicial;
- Máquinas;
- modal de Máquinas;
- Status operacional;
- modal de Status;
- Django Admin;
- responsividade mobile.

No momento, os screenshots ainda não estão versionados oficialmente.

---

## Status do projeto

Estado atual:

```text
Versão atual: v2.4.1-toner-impressoras
Etapa concluída: Etapa 3.5.3 — Porcentagem de toner
Próxima etapa: v2.5.0 — Integração GLPI de chamados
```

Estado de desenvolvimento da integracao GLPI:

- branch de trabalho: `feature/integracao-glpi-chamados-impressoras`;
- fluxo aprovado: validar na feature e integrar em `develop`;
- `main` permanece bloqueada ate homologacao completa do ciclo real de coleta;
- motivo do bloqueio: confirmar ausencia de chamados duplicados em alertas
  recorrentes antes de publicar a proxima release.

Validações da release v2.4.1:

- 482 testes aprovados;
- Django check sem problemas;
- frontend build aprovado;
- npm audit com 0 vulnerabilidades;
- Docker e migrations funcionando;
- Redis, Celery Worker, Celery Beat e proxy ativos;
- login/me/logout retornando HTTP 200;
- Máquinas e Status retornando HTTP 200;
- HTTPS validado;
- Status exibindo somente máquinas ativas;
- alertas atuais, histórico e logs operacionais validados;
- interface validada em desktop, notebook, tablet e celular;
- nenhum arquivo sensível rastreado.

Limitações não bloqueantes conhecidas:

- aviso antigo de chunks acima de 500 kB no build frontend;
- uso de certificado self-signed em ambiente local;
- Dashboard real ainda pendente;
- Papel e histórico ampliado ainda não iniciados; percentual de toner básico em validação.

---

## Padrão de comentários

O projeto adota comentários voltados para manutenção humana, seguindo o padrão herdado da v1.

### Blocos de seção

Python:

```python
# ---------------------------------------------------------------------
# 📌 TÍTULO DA SEÇÃO
# ---------------------------------------------------------------------
# Explique a intenção do bloco, regra de negócio ou decisão técnica.
```

TypeScript/React:

```tsx
// -----------------------------------------------------------------------------
// 📌 TÍTULO DA SEÇÃO
// -----------------------------------------------------------------------------
// Explique a intenção do bloco, regra de negócio ou decisão técnica.
```

### Diretrizes

- Comentar regras de negócio, permissões, integrações e decisões técnicas.
- Evitar comentários óbvios linha a linha.
- Preferir comentários em português.
- Manter docstrings em funções críticas do backend.
- Preservar comentários de arquivos gerados apenas quando necessário.
- Não comentar secrets, credenciais ou dados reais.

---

## Observações de segurança

- Não versionar arquivos `.env` reais.
- Não versionar certificados e chaves privadas reais.
- Não usar certificado self-signed em produção.
- Alterar senhas e secrets antes de homologação/produção.
- Utilizar certificado interno oficial para ambientes corporativos.
- Revisar permissões dos grupos antes de liberar acesso a usuários finais.
- Não versionar dados reais de impressoras, usuários ou infraestrutura.

---

## Licença

Projeto desenvolvido para fins de estudo, evolução técnica e demonstração de arquitetura de sistemas corporativos.
