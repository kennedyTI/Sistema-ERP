# Integracao bdTotvs - SQL Server TOTVS/Protheus

## Objetivo

A integracao bdTotvs fornece uma base generica, segura e reutilizavel para
consultas ao banco TOTVS/Protheus em SQL Server. Ela fica isolada no padrao
modular do Sistema ERP v2 em `backend/app/modules/integracoes/bdTotvs`.

## Escopo atual

- carregamento de configuracao a partir do ambiente e de `backend/.env`;
- suporte a SQL Server via ODBC configuravel;
- autenticacao por Trusted Connection ou usuario/senha;
- montagem interna da connection string;
- executor de consultas parametrizadas;
- retorno de linhas como lista de dicionarios;
- conversao de datas, horas, bytes e Decimal para formatos amigaveis a JSON;
- healthcheck com `SELECT 1 AS ok`;
- comando Django `testar_integracao_bdtotvs`;
- erros sanitizados sem connection string, host, usuario ou senha.

## Fora do escopo

Esta fase nao implementa modulo Compras, Rastreabilidade de Compras, frontend,
dashboard, tabelas de rastreabilidade, importadores SC/PC/NF, Celery,
agendamento, JSON operacional, consultas de compras ou alteracoes no modulo
Impressoras.

Tambem nao consulta tabelas Protheus como SC1, SC7, SD1, SF1, SE2, SB1, SB2 ou
NNR. A unica consulta operacional desta fase e `SELECT 1 AS ok`.

## Variaveis de ambiente

Variaveis preferenciais:

```env
TOTVS_DB_HOST=<host-do-sql-server>
TOTVS_DB_PORT=1433
TOTVS_DB_NAME=<nome-do-banco>
TOTVS_DB_USER=<usuario>
TOTVS_DB_PASSWORD=<senha>
TOTVS_DB_DRIVER=ODBC Driver 17 for SQL Server
TOTVS_DB_TRUSTED_CONNECTION=false
TOTVS_DB_TIMEOUT=30
TOTVS_DB_ENCRYPT=true
TOTVS_DB_TRUST_SERVER_CERTIFICATE=true
```

Aliases com prefixos `BDTOTVS`, `BD_TOTVS`, `PROTHEUS_DB` e `PROTHEUS_SQL`
tambem sao aceitos para compatibilidade. Valores reais devem existir somente no
ambiente seguro e nunca devem ser versionados.

## Autenticacao

Com `TOTVS_DB_TRUSTED_CONNECTION=true`, a connection string usa
`Trusted_Connection=yes` e ignora usuario/senha.

Com `TOTVS_DB_TRUSTED_CONNECTION=false`, a conexao usa usuario e senha SQL
Server. Nesse modo, `TOTVS_DB_USER` e `TOTVS_DB_PASSWORD` sao obrigatorios.

## Driver ODBC

O driver vem de `TOTVS_DB_DRIVER`, sem valor fixo no codigo. Exemplos comuns:

```text
ODBC Driver 17 for SQL Server
ODBC Driver 18 for SQL Server
SQL Server
```

No Windows, o driver precisa estar instalado no sistema operacional. Em Docker
Linux, a imagem tambem precisa ter o runtime/driver ODBC correspondente antes
de executar o healthcheck real.

## Comando de teste

```powershell
py -3.11 manage.py testar_integracao_bdtotvs
```

Saida esperada em sucesso:

```text
[bdTotvs] Configuracao carregada: host presente, database presente, driver presente.
[bdTotvs] Teste SELECT 1 executado com sucesso.
[bdTotvs] Tempo: 120ms.
```

Saida esperada em falha:

```text
[bdTotvs] Configuracao carregada: host ausente, database ausente, driver ausente.
[bdTotvs] Falha ao conectar ao bdTotvs. Codigo: configuration_error.
```

Nenhuma saida deve incluir `SERVER=`, `UID=`, `PWD=`, connection string,
usuario real, host real, IP real ou senha.

## Executor

Interface principal:

```python
from backend.app.modules.integracoes.bdTotvs import execute_query, execute_scalar

linhas = execute_query("SELECT 1 AS ok")
valor = execute_scalar("SELECT 1 AS ok")
```

Parametros posicionais:

```python
execute_query("SELECT ? AS ok", params=(1,))
```

Parametros nomeados:

```python
execute_query("SELECT :valor AS ok", params={"valor": 1})
```

Os valores dos parametros sao enviados ao driver; o executor nao concatena
valores sensiveis no SQL.

## Erros sanitizados

Excecoes publicas:

- `TotvsConfigurationError`;
- `TotvsConnectionError`;
- `TotvsQueryError`;
- `TotvsPermissionError`;
- `TotvsTimeoutError`.

Mensagens brutas do driver sao convertidas para mensagens seguras. Stack trace,
connection string, query com dados sensiveis, host, usuario e senha nao devem
aparecer em retornos, logs do comando ou relatorios.

## Healthcheck

O healthcheck executa somente:

```sql
SELECT 1 AS ok
```

Retorno em sucesso:

```python
{
    "success": True,
    "message": "Conexao com bdTotvs validada com sucesso.",
    "elapsed_ms": 123,
}
```

Retorno em erro:

```python
{
    "success": False,
    "message": "Falha ao conectar ao bdTotvs.",
    "elapsed_ms": 123,
    "error_code": "connection_error",
}
```

## Seguranca

- `backend/.env` nao deve ser versionado;
- valores reais nao devem aparecer em docs, testes, prints ou commits;
- a connection string e interna ao modulo de conexao;
- `repr(TotvsDbConfig)` mascara host, database, driver, usuario e senha;
- `SecretValue` mascara a senha em `str` e `repr`;
- testes automatizados usam mocks e nao dependem do banco real.

## Proximos passos

1. confirmar variaveis reais em ambiente seguro;
2. validar o driver ODBC instalado na maquina de execucao;
3. executar `py -3.11 manage.py testar_integracao_bdtotvs`;
4. somente depois abrir fase especifica do modulo Compras/Rastreabilidade.
