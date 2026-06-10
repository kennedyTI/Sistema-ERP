# Sistema ERP v2

Sistema ERP modular desenvolvido com foco em arquitetura limpa, autenticação centralizada, administração via Django Admin, frontend moderno e execução em containers Docker com proxy HTTPS.

O projeto foi estruturado para servir como base evolutiva para módulos corporativos, como usuários, permissões, estoque, compras, manutenção, relatórios e integrações futuras.

---

## Visão geral

O Sistema ERP v2 possui uma base institucional e modular composta por:

* Frontend em React/Vite;
* Backend em FastAPI;
* Django Admin para administração interna;
* Autenticação com Django Auth + JWT;
* Permissões por grupos;
* Banco de dados PostgreSQL;
* Proxy reverso Nginx com HTTPS;
* Docker Compose para orquestração dos serviços;
* Estrutura preparada para evolução por módulos.

### Módulo Impressoras

O módulo Impressoras passa a existir como um módulo futuro dentro do Sistema ERP, sem alterar a identidade institucional do produto.

Nesta fase, a fundacao inclui:

* estrutura modular no backend e no frontend;
* paginas placeholder de Dashboard e Papel;
* cadastro inicial de Maquinas com persistencia;
* status operacional atual das impressoras;
* linha do tempo de eventos operacionais de cada impressora;
* menu condicionado por permissões;
* API CRUD de maquinas em `/api/v2/printers/machines`;
* API de status em `/api/v2/printers/status`;
* tela inicial de listagem, criacao, edicao e ativacao/inativacao de maquinas;
* tela de consulta operacional em `/impressoras/status`;
* endpoints de desenvolvimento para Dashboard e Papel.

O status desta etapa é atualizado manualmente pela API para preparar o domínio.
Monitoramento automático, SNMP, toner, alertas complexos, Celery e Redis não
fazem parte desta etapa.

### Etapa 3 - Status operacional das impressoras

A Etapa 3 separa o cadastro de máquinas da consulta operacional:

* `Máquinas` continua responsável por criar, editar, ativar e inativar cadastros;
* `Status` apresenta a foto atual do estado operacional;
* `status_impressoras` mantém um único status atual por máquina;
* `logs_impressoras` registra somente eventos do domínio Impressoras;
* novas máquinas recebem status inicial `desconhecido`, alerta `cinza`,
  orientação `Aguardando primeira verificação` e origem `sistema`;
* atualizações manuais podem registrar `mudanca_status`, `alerta_gerado`,
  `alerta_normalizado` ou `atualizacao_manual`.

A tela `/impressoras/status` funciona como Central de Operação inicial:

* cards de Total, Online, Offline, Com alerta e Substituir toner;
* tabela priorizada por alerta vermelho, amarelo, cinza e verde;
* colunas Status, Alerta, Mensagem, Local, Máquina, IP e Atualizado em;
* modal somente de consulta com cadastro, tempos, origem, resposta técnica e
  últimos logs da impressora.

O card `Substituir toner` utiliza temporariamente uma busca textual por
`substituir toner` em `mensagem_alerta`. Isso não representa monitoramento de
toner nem integração com Protheus ou GLPI.

O Dashboard real permanece planejado para uma etapa posterior, quando houver
dados operacionais suficientes.

---

## Tecnologias utilizadas

### Backend

* Python
* FastAPI
* Django Admin
* Django Auth
* SQLAlchemy / Alembic
* PostgreSQL
* JWT
* Pytest

### Frontend

* React
* Vite
* TypeScript
* Tailwind CSS
* Componentes UI modulares

### Infraestrutura

* Docker
* Docker Compose
* Nginx
* HTTPS com certificado self-signed para desenvolvimento local

---

## Estrutura de pastas

```text
sistema_erp/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── security.py
│   │   │   ├── auth_dependencies.py
│   │   │   ├── response.py
│   │   │   └── ...
│   │   │
│   │   ├── modules/
│   │   │   ├── auth/
│   │   │   │   ├── api.py
│   │   │   │   ├── schemas.py
│   │   │   │   ├── services.py
│   │   │   │   └── ...
│   │   │   │
│   │   │   ├── backoffice/
│   │   │   │   ├── groups.py
│   │   │   │   ├── permissions.py
│   │   │   │   ├── services.py
│   │   │   │   └── management/
│   │   │   │
│   │   │   ├── audit/
│   │   │   │   ├── models.py
│   │   │   │   ├── services.py
│   │   │   │   └── ...
│   │   │   │
│   │   │   └── printers/
│   │   │       ├── dashboard/
│   │   │       ├── machines/
│   │   │       ├── paper/
│   │   │       └── status/
│   │   │
│   │   ├── shared/
│   │   │   ├── constants.py
│   │   │   ├── dates.py
│   │   │   ├── validators.py
│   │   │   └── ...
│   │   │
│   │   ├── migrations/
│   │   └── main.py
│   │
│   └── backoffice/
│       ├── manage.py
│       ├── settings.py
│       ├── urls.py
│       └── wsgi.py
│
├── frontend/
│   ├── public/
│   └── src/
│       ├── app/
│       │   ├── layout/
│       │   ├── providers.tsx
│       │   └── router.tsx
│       │
│       ├── modules/
│       │   ├── auth/
│       │   │   ├── LoginPage.tsx
│       │   │   ├── RequireAuth.tsx
│       │   │   ├── authApi.ts
│       │   │   └── components/
│       │   │
│       │   ├── home/
│       │   │   └── HomePage.tsx
│       │   │
│       │   └── printers/
│       │       ├── dashboard/
│       │       ├── machines/
│       │       ├── paper/
│       │       └── status/
│       │
│       └── shared/
│           ├── components/
│           ├── hooks/
│           ├── lib/
│           └── ui/
│
├── docker/
│   └── nginx/
│       ├── nginx.conf
│       ├── conf.d/
│       │   └── sistema_erp.conf
│       └── certs/
│           ├── README.md
│           ├── localhost.crt
│           └── localhost.key
│
├── docker-compose.yml
├── .env.example
├── .env.docker.example
└── README.md
```

---

## Arquitetura dos containers

O projeto utiliza Docker Compose para executar os serviços principais.

```text
Usuário
  ↓ HTTPS
sistema_erp_proxy
  ↓
frontend / api / admin
  ↓
postgres
```

### Serviços

| Serviço                  | Função                                   |
| ------------------------ | ---------------------------------------- |
| `sistema_erp_proxy`      | Proxy reverso Nginx com HTTPS            |
| `sistema_erp_frontend`   | Interface web React/Vite                 |
| `sistema_erp_api`        | API FastAPI                              |
| `sistema_erp_admin`      | Django Admin                             |
| `sistema_erp_postgres`   | Banco PostgreSQL                         |
| `sistema_erp_migrations` | Execução das migrations e seeds iniciais |

---

## Rotas principais

### Frontend

| Rota                     | Descrição                                |
| ------------------------ | ---------------------------------------- |
| `/login`                 | Tela de autenticação                     |
| `/inicio`                | Tela inicial do sistema                  |
| `/impressoras/dashboard` | Placeholder do dashboard de impressoras |
| `/impressoras/status`    | Consulta do status operacional atual    |
| `/impressoras/maquinas`  | Cadastro inicial de maquinas            |
| `/impressoras/papel`     | Placeholder de papel                    |
| `/admin/`                | Acesso ao Django Admin via proxy         |

### Backend

| Rota                                      | Método  | Descrição                             |
| ----------------------------------------- | ------- | ------------------------------------- |
| `/api/v2/auth/login`                      | `POST`  | Autenticação do usuário               |
| `/api/v2/auth/me`                         | `GET`   | Dados do usuário autenticado          |
| `/api/v2/auth/logout`                     | `POST`  | Encerramento da sessão/token          |
| `/api/v2/printers/dashboard`              | `GET`   | Status inicial do dashboard           |
| `/api/v2/printers/machines`               | `GET`   | Lista maquinas cadastradas            |
| `/api/v2/printers/machines`               | `POST`  | Cadastra maquina                      |
| `/api/v2/printers/machines/{id}`          | `GET`   | Detalha maquina                       |
| `/api/v2/printers/machines/{id}`          | `PATCH` | Atualiza maquina                      |
| `/api/v2/printers/machines/{id}/status`   | `PATCH` | Ativa ou inativa maquina              |
| `/api/v2/printers/status`                 | `GET`   | Lista o status atual das impressoras  |
| `/api/v2/printers/status/summary`         | `GET`   | Resumo para os cards operacionais     |
| `/api/v2/printers/status/{id}`            | `GET`   | Consulta o status de uma impressora   |
| `/api/v2/printers/status/{id}`            | `PATCH` | Atualiza status manualmente           |
| `/api/v2/printers/status/{id}/logs`       | `GET`   | Lista os últimos eventos operacionais |
| `/api/v2/printers/paper`                  | `GET`   | Status inicial do submódulo Papel     |

---

## Permissões e grupos

O sistema utiliza grupos para controlar acesso ao portal e ao Django Admin.

| Grupo                 | Acesso                                                      |
| --------------------- | ----------------------------------------------------------- |
| `Equipe Técnica`      | Início, Impressoras, Dashboard, Status, Máquinas, Papel e Admin |
| `Gestor`              | Início, Impressoras, Dashboard, Status, Máquinas e Papel       |
| `Operador`            | Início, Impressoras, Dashboard e Status                        |
| `Integração Protheus` | Sem acesso ao portal visual                                 |

---

## Configuração de ambiente

Copie os arquivos de exemplo antes de iniciar o projeto:

```bash
cp .env.example .env
cp .env.docker.example .env.docker
cp backend/.env.example backend/.env
```

No Windows PowerShell, copie com:

```powershell
Copy-Item .env.example .env
Copy-Item .env.docker.example .env.docker
Copy-Item backend/.env.example backend/.env
```

Revise os valores conforme o ambiente.

---

## Portas locais

Para evitar conflito com serviços locais que possam usar as portas 80 e 443, o ambiente de desenvolvimento utiliza:

| Serviço     | Porta  |
| ----------- | ------ |
| HTTP local  | `8080` |
| HTTPS local | `8443` |

Acesso local:

```text
http://localhost:8080
https://localhost:8443/login
https://localhost:8443/inicio
https://localhost:8443/admin/
https://localhost:8443/api/v2/auth/me
https://localhost:8443/impressoras/dashboard
https://localhost:8443/impressoras/status
https://localhost:8443/impressoras/maquinas
https://localhost:8443/impressoras/papel
```

As portas externas podem ser alteradas no `.env.docker`:

```env
NGINX_HTTP_PORT=8080
NGINX_HTTPS_PORT=8443
```

O Nginx continua ouvindo nas portas internas `80` e `443`. O acesso HTTP em
`http://localhost:8080` redireciona para `https://localhost:8443`.

Em homologação ou produção, recomenda-se usar:

```env
NGINX_HTTP_PORT=80
NGINX_HTTPS_PORT=443
```

---

## Certificado HTTPS local

O proxy espera os arquivos `docker/nginx/certs/localhost.crt` e
`docker/nginx/certs/localhost.key`. Esses arquivos não são versionados.

Para desenvolvimento, eles podem ser certificados self-signed criados
localmente. Um exemplo com OpenSSL:

```bash
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout docker/nginx/certs/localhost.key \
  -out docker/nginx/certs/localhost.crt \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

Por isso, o navegador pode exibir um aviso de segurança ao acessar:

```text
https://localhost:8443
```

Esse comportamento é esperado.

Em homologação ou produção, substitua o certificado de desenvolvimento por um certificado interno oficial fornecido pela equipe de infraestrutura/TI.
Certificados reais e chaves privadas nunca devem entrar no Git.

O HTTPS termina no `sistema_erp_proxy`; a comunicação interna entre Nginx,
frontend, API e Admin permanece HTTP. Frontend, API e Admin ficam disponíveis
sob o mesmo domínio.

---

## Como rodar o projeto com Docker

Suba todos os serviços:

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
```

Para validar com `curl`, pode ser necessário usar `-k` por causa do certificado
self-signed:

```bash
curl -k https://localhost:8443/api/v2/auth/me
```

---

## Como parar o projeto

```bash
docker compose --env-file .env.docker down
```

Para parar e remover volumes locais:

```bash
docker compose --env-file .env.docker down -v
```

Use `down -v` com cuidado, pois ele remove os dados do banco local.

---

## Criar superusuário do Django Admin

Com os containers em execução:

```bash
docker compose --env-file .env.docker exec admin python manage.py createsuperuser
```

Depois acesse:

```text
https://localhost:8443/admin/
```

---

## Rodar testes do backend

Dentro do container da API:

```bash
docker compose --env-file .env.docker exec api pytest -q
```

Compile os arquivos Python:

```bash
docker compose --env-file .env.docker exec api python -m compileall -q backend
```

Verifique o Django:

```bash
docker compose --env-file .env.docker exec admin python manage.py check
```

---

## Rodar build do frontend

```bash
docker compose --env-file .env.docker run --rm frontend npm run build
```

---

## Fluxo Git recomendado

Este projeto utiliza um fluxo profissional com branches, tags e commits padronizados.

### Branches principais

| Branch      | Uso                               |
| ----------- | --------------------------------- |
| `main`      | Versão estável                    |
| `develop`   | Desenvolvimento da próxima versão |
| `feature/*` | Novas funcionalidades             |
| `release/*` | Preparação de versões             |
| `hotfix/*`  | Correções urgentes                |

### Exemplo de criação da base

```bash
git init
git add .
git commit -m "chore: initialize Sistema ERP v2 base"
git branch -M main
git tag -a v2.0.0-base -m "Sistema ERP v2 base modular institucional"
git checkout -b develop
```

### Criar nova funcionalidade

```bash
git checkout develop
git checkout -b feature/modulo-usuarios
```

Após concluir:

```bash
git add .
git commit -m "feat(users): add user module skeleton"
git checkout develop
git merge --no-ff feature/modulo-usuarios
git branch -d feature/modulo-usuarios
```

### Criar release

```bash
git checkout develop
git checkout -b release/v2.1.0
```

Após ajustes finais:

```bash
git checkout main
git merge --no-ff release/v2.1.0
git tag -a v2.1.0 -m "Release v2.1.0"
git checkout develop
git merge --no-ff release/v2.1.0
git branch -d release/v2.1.0
```

### Hotfix

```bash
git checkout main
git checkout -b hotfix/fix-login-redirect
```

Após corrigir:

```bash
git add .
git commit -m "fix(auth): correct login redirect behind proxy"
git checkout main
git merge --no-ff hotfix/fix-login-redirect
git tag -a v2.0.1 -m "Hotfix v2.0.1"
git checkout develop
git merge --no-ff hotfix/fix-login-redirect
git branch -d hotfix/fix-login-redirect
```

---

## Convenção de commits

O projeto segue o padrão Conventional Commits.

Exemplos:

```text
feat: adiciona nova funcionalidade
fix: corrige bug
docs: altera documentação
style: ajustes visuais ou formatação
refactor: refatoração sem mudar comportamento
test: adiciona ou ajusta testes
build: alterações de build, Docker ou dependências
chore: manutenção geral
ci: ajustes de pipeline
```

Exemplos aplicados ao projeto:

```text
chore: initialize Sistema ERP v2 base
build(docker): add nginx https proxy
refactor(backend): organize modular architecture
feat(auth): add django jwt login flow
docs: document local https ports
fix(proxy): adjust local https redirect port
```

---

## Versionamento

O projeto segue versionamento semântico:

```text
MAJOR.MINOR.PATCH
```

Exemplo:

```text
v2.0.0-base
v2.0.1
v2.1.0
v3.0.0
```

Critério sugerido:

| Tipo    | Quando usar                                    |
| ------- | ---------------------------------------------- |
| `PATCH` | Correções pequenas                             |
| `MINOR` | Nova funcionalidade compatível                 |
| `MAJOR` | Mudança grande de arquitetura ou comportamento |

---

## Checklist antes de cada commit importante

Antes de realizar commits relevantes, execute:

```bash
docker compose --env-file .env.docker ps -a
docker compose --env-file .env.docker exec api pytest -q
docker compose --env-file .env.docker exec api python -m compileall -q backend
docker compose --env-file .env.docker exec admin python manage.py check
docker compose --env-file .env.docker run --rm frontend npm run build
```

---

## Próximos módulos planejados

A base está preparada para receber módulos corporativos de forma incremental.

Possíveis módulos futuros:

* Usuários e perfis avançados;
* Estoque;
* Compras;
* Manutenção;
* Relatórios;
* Integrações corporativas;
* Assistente via Telegram;
* Módulos operacionais específicos por área.

---

## Observações de segurança

* Não versionar arquivos `.env` reais.
* Não versionar certificados e chaves privadas reais.
* Não usar certificado self-signed em produção.
* Alterar senhas e secrets antes de homologação/produção.
* Utilizar certificado interno oficial para ambientes corporativos.
* Revisar permissões dos grupos antes de liberar acesso a usuários finais.

---

## Licença

Projeto desenvolvido para fins de estudo, evolução técnica e demonstração de arquitetura de sistemas corporativos.
