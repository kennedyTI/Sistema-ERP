# Scripts auxiliares

Este diretorio contem scripts locais de apoio para desenvolvimento e homologacao. Eles nao fazem parte do fluxo principal da aplicacao.

## Seed local de maquinas de impressoras

O script `seed_printer_machines.py` importa maquinas a partir de um arquivo JSON e faz upsert por `ip_address`, evitando duplicidade.

Para cada registro, o script tambem localiza ou cria o modelo em `printers_models` usando a combinacao `manufacturer + model`. A maquina e salva em `printer_machines` vinculada ao `model_id` correspondente.

O formato oficial usa chaves em ingles, mas o script tambem aceita aliases locais em portugues como `nome`, `ip`, `fabricante`, `modelo`, `tipo`, `local`, `setor` e `centro_custo`.

Crie o arquivo local a partir do exemplo:

```powershell
Copy-Item backend/scripts/seed_printer_machines.example.json backend/scripts/seed_printer_machines.local.json
```

Edite `backend/scripts/seed_printer_machines.local.json` somente com dados locais. Nao versionar nomes reais de equipamentos, IPs reais, setores sensiveis ou centros de custo reais.

Formato esperado:

```json
[
  {
    "name": "IMPRESSORA_EXEMPLO_001",
    "ip_address": "192.168.0.10",
    "manufacturer": "HP",
    "model": "LaserJet Exemplo",
    "type": "laser",
    "color_mode": "mono",
    "sector": "Administrativo",
    "cost_center": "CC-EXEMPLO",
    "is_active": true,
    "notes": "Registro ficticio para demonstracao"
  }
]
```

Execucao no host, quando o ambiente Python estiver configurado:

```powershell
python backend/scripts/seed_printer_machines.py backend/scripts/seed_printer_machines.local.json
```

Execucao com o arquivo ficticio de exemplo:

```powershell
python backend/scripts/seed_printer_machines.py backend/scripts/seed_printer_machines.example.json
```

Execucao via container:

```powershell
docker compose --env-file .env.docker exec api python backend/scripts/seed_printer_machines.py backend/scripts/seed_printer_machines.local.json
```

Confirme que o arquivo local esta ignorado:

```powershell
git check-ignore -v backend/scripts/seed_printer_machines.local.json
git ls-files "backend/scripts/*.local.json" "backend/scripts/*.local.csv" "backend/scripts/*.local.xlsx"
```

## Seed oficial de regras de alertas

O script `seed_printer_alert_rules.py` sincroniza as regras oficiais da Rules
Engine na tabela `regras_alertas_impressoras`. Ele nao recebe arquivos locais,
nao contem dados de equipamentos e pode ser executado repetidamente sem
duplicar registros.

Execucao no host:

```powershell
python backend/scripts/seed_printer_alert_rules.py
```

Execucao via container:

```powershell
docker compose --env-file .env.docker exec api python backend/scripts/seed_printer_alert_rules.py
```

O servico `migrations` tambem executa este seed depois do Alembic.

## Seed oficial de configuracoes SNMP/OIDs

O script `seed_printer_snmp_oids.py` sincroniza os OIDs seguros iniciais na
tabela `oids_snmp_impressoras`. Ele usa somente modelo e fabricante,
nao recebe arquivos locais, nao executa coleta em equipamentos reais e nao
armazena community SNMP, IPs ou dados sensiveis.

O seed e idempotente: cria OIDs ausentes por `modelo_id + chave_metrica`,
atualiza campos controlados quando ja existem e ignora modelos que ainda nao
foram cadastrados localmente.

Execucao no host:

```powershell
python backend/scripts/seed_printer_snmp_oids.py
```

Execucao via container:

```powershell
docker compose --env-file .env.docker exec api python backend/scripts/seed_printer_snmp_oids.py
```

O servico `migrations` executa este seed depois do seed de regras de alertas.

## Seed oficial de suprimentos de impressoras

O script `seed_printer_supplies.py` sincroniza o catalogo inicial da tabela
`impressoras_suprimentos`. Os registros relacionam modelo, tipo, cor e codigo
de produto Protheus. Nao contem IP, setor, centro de custo, credencial ou dado
de equipamento fisico.

O seed e idempotente e preserva codigo nulo quando o produto ainda nao foi
identificado. Nesse caso, a integracao GLPI bloqueia a abertura e registra o
motivo, sem enviar requisicao externa.

Execucao no host:

```powershell
python backend/scripts/seed_printer_supplies.py
```

Execucao via container:

```powershell
docker compose --env-file .env.docker exec api python backend/scripts/seed_printer_supplies.py
```

O servico `migrations` executa este seed depois das migrations Alembic.
