# Automacao de Novo Usuario Windows

Modulo backend para processar e-mails de admissao e criar usuario Windows/Active
Directory por comando Django local.

## Branch de trabalho

```bash
git checkout develop
git pull origin develop
git checkout -b feature/automacao-novo-usuario-windows-local
```

Se a branch ja existir:

```bash
git checkout feature/automacao-novo-usuario-windows-local
```

Nao fazer merge direto em `develop`, `main` ou `master` antes da validacao local.

## Configuracao local

Por padrao, a automacao procura o arquivo local ja usado no backend:

```text
backend/Portal RH.url
```

Esse arquivo e local e deve permanecer ignorado pelo Git. Adicione nele as
secoes abaixo, sem remover os demais dados locais que ele ja possui:

```ini
[automacao_novo_usuario_email]
EMAIL=conta.existente@seudominio.com.br
SENHA=sua_senha_do_email

[automacao_novo_usuario_windows]
SENHA_TEMPORARIA=sua_senha_temporaria
```

Como alternativa para ambiente limpo, copie o arquivo de exemplo:

```powershell
Copy-Item backend/automacao_novo_usuario.example.ini backend/automacao_novo_usuario.local.ini
```

Edite somente o arquivo `.local.ini` com as credenciais reais:

```ini
[automacao_novo_usuario_email]
EMAIL=conta.existente@seudominio.com.br
SENHA=sua_senha_do_email

[automacao_novo_usuario_windows]
SENHA_TEMPORARIA=sua_senha_temporaria
```

Os arquivos `backend/Portal RH.url` e `backend/automacao_novo_usuario.local.ini`
sao ignorados pelo Git. Nunca versionar senha do e-mail nem senha temporaria real.

## Variaveis de ambiente

Configure no `backend/.env`:

```env
AUTOMACAO_NOVO_USUARIO_DRY_RUN=true
AUTOMACAO_NOVO_USUARIO_CREDENCIAL_PATH=Portal RH.url

AUTOMACAO_NOVO_USUARIO_EMAIL_PROVIDER=pop_smtp
AUTOMACAO_NOVO_USUARIO_POP_HOST=pop3.exemplo.local
AUTOMACAO_NOVO_USUARIO_POP_PORT=995
AUTOMACAO_NOVO_USUARIO_POP_SSL=true
AUTOMACAO_NOVO_USUARIO_SMTP_HOST=smtp.exemplo.local
AUTOMACAO_NOVO_USUARIO_SMTP_PORT=465
AUTOMACAO_NOVO_USUARIO_SMTP_SSL=true

AUTOMACAO_NOVO_USUARIO_EMAIL_LOOKBACK_MINUTES=60
AUTOMACAO_NOVO_USUARIO_POP_MAX_EMAILS=30
AUTOMACAO_NOVO_USUARIO_EMAIL_SUBJECT_PREFIX=ADMISSAO -
AUTOMACAO_NOVO_USUARIO_FAILURE_EMAIL=suporte.ti@industria.local

AUTOMACAO_NOVO_USUARIO_AD_DOMAIN=industria.local
AUTOMACAO_NOVO_USUARIO_AD_NETBIOS=INDUSTRIA
AUTOMACAO_NOVO_USUARIO_AD_OU=OU=Usuarios,OU=Corporativo,DC=industria,DC=local
AUTOMACAO_NOVO_USUARIO_AD_OFFICE=Industria ERP
AUTOMACAO_NOVO_USUARIO_AD_COMPANY=Industria
AUTOMACAO_NOVO_USUARIO_AD_GROUPS=GR-USUARIOS-PADRAO,GR-INTERNET-PADRAO
```

## Banco de dados

A tabela operacional e criada pelo Alembic:

```bash
cd backend
alembic upgrade head
```

Tabela criada:

```text
automacao_novo_usuario_windows
```

O model Django `AutomacaoNovoUsuarioWindows` e unmanaged, seguindo o padrao das
tabelas operacionais administradas pelo Alembic.

## Dry run

Com:

```env
AUTOMACAO_NOVO_USUARIO_DRY_RUN=true
```

O comando le POP3, filtra e-mails, faz parser, gera login e grava o registro,
mas nao cria usuario no AD, nao altera grupos e nao envia e-mail real.

Execute:

```bash
python manage.py processar_novo_usuario_windows
```

## Execucao real

Antes de usar `DRY_RUN=false`, valide no Windows com usuario administrativo:

```powershell
Import-Module ActiveDirectory -ErrorAction Stop
Get-Command Get-ADUser,New-ADUser,Set-ADAccountPassword,Set-ADUser,Enable-ADAccount,Add-ADGroupMember
```

Depois configure:

```env
AUTOMACAO_NOVO_USUARIO_DRY_RUN=false
```

E execute:

```bash
python manage.py processar_novo_usuario_windows
```

No modo real o comando consulta o AD, cria o usuario, aplica senha temporaria,
marca troca obrigatoria no proximo logon, adiciona os grupos fixos e responde ao
solicitante original. Em caso de falha, envia aviso para o e-mail configurado em
`AUTOMACAO_NOVO_USUARIO_FAILURE_EMAIL`.

## Seguranca

- O comando nunca imprime senha real no CMD.
- A senha temporaria real nao e salva no banco; somente a mascara e persistida.
- A senha temporaria real so entra no corpo do e-mail de sucesso quando
  `DRY_RUN=false`.
- O PowerShell recebe a senha por stdin, nao por argumento de processo.
- Arquivos reais `.local.ini`, `.env` e similares nao devem entrar no Git.
