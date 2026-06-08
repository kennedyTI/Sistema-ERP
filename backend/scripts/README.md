# Scripts auxiliares

Este diretorio contem scripts locais de apoio para desenvolvimento e homologacao. Eles nao fazem parte do fluxo principal da aplicacao.

## Seed local de maquinas de impressoras

O script `seed_printer_machines.py` importa maquinas a partir de um arquivo JSON e faz upsert por `ip_address`, evitando duplicidade.

Crie o arquivo local a partir do exemplo:

```powershell
Copy-Item backend/scripts/seed_printer_machines.example.json backend/scripts/seed_printer_machines.local.json
```

Edite `backend/scripts/seed_printer_machines.local.json` somente com dados locais. Nao versionar nomes reais de equipamentos, IPs reais, setores sensiveis ou centros de custo reais.

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
