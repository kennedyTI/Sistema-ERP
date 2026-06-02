# Portal industria v2 - Base Modular

Esta pasta contem a base v2 modular do Portal industria. A Etapa 1 removeu o dominio de Impressoras; esta Etapa 2 reorganizou a base limpa em modulos, sem alterar o comportamento funcional.

A v1 continua sendo a versao operacional. Nesta v2, os modulos operacionais ainda nao foram reimplementados.

## Escopo Atual

Mantido:

- login em `/login`;
- tela inicial em `/inicio`;
- autenticacao Django Auth + JWT;
- Django Admin em `/admin/`;
- grupos/permissoes oficiais;
- audit/log generico;
- layout/sidebar visual aprovado;
- Docker com `postgres`, `migrations`, `api`, `admin` e `frontend`.

Nao implementado nesta etapa:

- Dashboard;
- Impressoras;
- Papel;
- Toner;
- Alertas operacionais;
- Protheus de suprimentos;
- SNMP;
- monitoramento/worker/beat.

## Estrutura Backend

- `backend/app/core`: infraestrutura comum, configuracao, banco, Django bootstrap, JWT, responses, exceptions, logging e timezone.
- `backend/app/modules/auth`: rotas `/api/v2/auth`, schemas, services, permissoes e dependencias de autenticacao.
- `backend/app/modules/backoffice`: grupos oficiais, permissoes administrativas, politica de admin e comandos Django.
- `backend/app/modules/audit`: models SQLAlchemy, models Django somente leitura, admin, schemas e services de audit/log generico.
- `backend/app/shared`: helpers reutilizaveis sem regra de negocio.
- `backend/app/migrations`: migrations Alembic da base operacional.
- `backend/backoffice`: projeto Django Admin (`settings.py`, `urls.py`, `wsgi.py`, `asgi.py`).

## Estrutura Frontend

- `frontend/src/app`: router, providers e layout principal.
- `frontend/src/modules/auth`: pagina de login, store/provider de auth, client de API, guarda de rota e componentes do login.
- `frontend/src/modules/home`: pagina `/inicio`.
- `frontend/src/shared`: UI, componentes compartilhados, hooks e helpers.
- `frontend/src/routes`: arquivos finos do TanStack Router para `/login`, `/inicio` e redirecionamento `/`.

## Rotas Atuais

Frontend:

- `/login`
- `/inicio`

Backend:

- `POST /api/v2/auth/login`
- `GET /api/v2/auth/me`
- `POST /api/v2/auth/logout`
- `/admin/`

Compatibilidade temporaria:

- `/api/v1/auth/*` ainda monta o mesmo router para clientes antigos. A rota oficial da v2 e `/api/v2/auth/*`.

## Grupos Oficiais

- `Equipe Técnica`: acessa `/inicio`, ve Admin e pode acessar o Django Admin.
- `Gestor`: acessa `/inicio`, nao ve Admin.
- `Operador`: acessa `/inicio`, nao ve Admin.
- `Integração Protheus`: reservado para integracoes; nao acessa o portal visual.

## Docker

Subir a base:

```bash
docker compose --env-file .env.docker up -d --build
```

Verificar containers:

```bash
docker compose --env-file .env.docker ps -a
```

Rodar migrations e grupos acontece no service `migrations`:

```bash
python docker/scripts/create_schemas.py
alembic -c backend/alembic.ini upgrade head
python manage.py migrate --noinput
python manage.py seed_admin_groups
```

## Superuser

Criar manualmente:

```bash
python manage.py createsuperuser
python manage.py seed_admin_groups
```

Depois associe o usuario ao grupo `Equipe Técnica` para exibir o item Admin no portal.

## Testes

Backend:

```bash
python -m compileall -q backend
pytest -q
python manage.py check
```

Frontend:

```bash
cd frontend
npm install
npm run build
```

## Proxima Etapa

- renomear a identidade publica removendo industria;
- substituir por Industria / Sistema ERP;
- preparar o projeto para portfolio e evolucao para ERP industrial.
