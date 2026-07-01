"""Seed idempotente das regras iniciais de alertas."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.app.modules.printers.monitoring.state.models import PrinterAlertRule


INITIAL_ALERT_RULES = (
    {
        "codigo": "error",
        "descricao": "Erro da impressora",
        "severidade": "high",
        "tipo_regra": "contains",
        "padrao": "error,print unable,fatal error,erro",
        "prioridade": 3,
        "ativo": True,
    },
    {
        "codigo": "offline",
        "descricao": "Impressora offline",
        "severidade": "high",
        "tipo_regra": "contains",
        "padrao": "offline,not responding,sem resposta",
        "prioridade": 5,
        "ativo": True,
    },
    {
        "codigo": "sem_servico",
        "descricao": "Sem serviço",
        "severidade": "high",
        "tipo_regra": "contains",
        "padrao": (
            "sem serviço,sem servico,offline,sem resposta,not responding,"
            "unreachable,fora de serviço,fora de servico"
        ),
        "prioridade": 6,
        "ativo": True,
    },
    {
        "codigo": "replace_toner",
        "descricao": "Substituir toner",
        "severidade": "high",
        "tipo_regra": "contains",
        "padrao": (
            "replace toner,substituir toner,trocar toner,subs toner,"
            "subs. toner,subs o toner,subs. o toner,subst toner,"
            "subst. toner,subst o toner,subst. o toner,substituir o toner,"
            "toner empty,sem toner,toner replace"
        ),
        "prioridade": 8,
        "ativo": True,
    },
    {
        "codigo": "replace_drum",
        "descricao": "Substituir cilindro",
        "severidade": "high",
        "tipo_regra": "contains",
        "padrao": (
            "replace drum,drum end,drum replace,substituir cilindro,"
            "substituir o cilindro,trocar cilindro,subs cilindro,"
            "subs. cilindro,subs o cilindro,subs. o cilindro,"
            "subst cilindro,subst. cilindro,subst o cilindro,"
            "subst. o cilindro,substitua cilindro,troque cilindro"
        ),
        "prioridade": 9,
        "ativo": True,
    },
    {
        "codigo": "paper_jam",
        "descricao": "Atolamento de papel",
        "severidade": "high",
        "tipo_regra": "contains",
        "padrao": "paper jam,document jam,atolamento de papel,atolamento",
        "prioridade": 10,
        "ativo": True,
    },
    {
        "codigo": "cover_open",
        "descricao": "Tampa aberta",
        "severidade": "high",
        "tipo_regra": "contains",
        "padrao": "cover open,door open,tampa aberta,porta aberta",
        "prioridade": 12,
        "ativo": True,
    },
    {
        "codigo": "no_paper",
        "descricao": "Sem papel",
        "severidade": "high",
        "tipo_regra": "contains",
        "padrao": "no paper,paper is out,paper out,sem papel,no tray,bandeja vazia",
        "prioridade": 15,
        "ativo": True,
    },
    {
        "codigo": "maintenance",
        "descricao": "Manutencao necessaria",
        "severidade": "medium",
        "tipo_regra": "contains",
        "padrao": "maintenance,service required,replace parts,manutencao",
        "prioridade": 30,
        "ativo": True,
    },
    {
        "codigo": "memory_full",
        "descricao": "Memoria cheia",
        "severidade": "medium",
        "tipo_regra": "contains",
        "padrao": "out of memory,memory full,memoria cheia",
        "prioridade": 35,
        "ativo": True,
    },
    {
        "codigo": "paper_low",
        "descricao": "Papel baixo",
        "severidade": "medium",
        "tipo_regra": "contains",
        "padrao": "paper low,papel baixo,pouco papel",
        "prioridade": 45,
        "ativo": True,
    },
    {
        "codigo": "drum_low",
        "descricao": "Cilindro perto do fim",
        "severidade": "medium",
        "tipo_regra": "contains",
        "padrao": (
            "drum needs to be replaced soon,drum needs replacement soon,"
            "drum near end,drum low,cil. proximo fim,cil proximo fim,"
            "cilindro proximo fim"
        ),
        "prioridade": 48,
        "ativo": True,
    },
    {
        "codigo": "toner_low",
        "descricao": "Toner baixo",
        "severidade": "medium",
        "tipo_regra": "contains",
        "padrao": (
            "toner baixo,toner low,toner is low,low toner,cartucho baixo,"
            "suprimento baixo,near end,quase vazio,ha pouco toner,"
            "pouco toner"
        ),
        "prioridade": 50,
        "ativo": True,
    },
    {
        "codigo": "sleep",
        "descricao": "Estado normal / dormindo",
        "severidade": "green",
        "tipo_regra": "contains",
        "padrao": "sleep,sleeping,dormindo,energy save,economia de energia",
        "prioridade": 95,
        "ativo": True,
    },
    {
        "codigo": "idle",
        "descricao": "Estado normal / em espera",
        "severidade": "green",
        "tipo_regra": "contains",
        "padrao": "idle,standby,espera,em espera",
        "prioridade": 100,
        "ativo": True,
    },
    {
        "codigo": "ok",
        "descricao": "Operacional",
        "severidade": "green",
        "tipo_regra": "contains",
        "padrao": (
            "ready,online,operational,printing,imprimindo,a imprimir,"
            "em impressao,em impressão,pronta,pronto,aquecendo,warmup,ok"
        ),
        "prioridade": 110,
        "ativo": True,
    },
    {
        "codigo": "unknown",
        "descricao": "Alerta nao reconhecido",
        "severidade": "unknown",
        "tipo_regra": "contains",
        "padrao": "",
        "prioridade": 999,
        "ativo": True,
    },
    {
        "codigo": "sem_retorno_alerta",
        "descricao": "Nenhuma mensagem de alerta foi retornada pela impressora",
        "severidade": "unknown",
        "tipo_regra": "contains",
        "padrao": "",
        "prioridade": 1000,
        "ativo": True,
    },
    {
        "codigo": "falha_coleta_alertas",
        "descricao": "Falha ao coletar alertas da impressora",
        "severidade": "high",
        "tipo_regra": "contains",
        "padrao": "",
        "prioridade": 2,
        "ativo": True,
    },
)

CONTROLLED_FIELDS = (
    "descricao",
    "severidade",
    "tipo_regra",
    "padrao",
    "prioridade",
    "ativo",
)


@dataclass(frozen=True)
class AlertRuleSeedResult:
    created: int
    updated: int
    total: int


def seed_alert_rules(db: Session) -> AlertRuleSeedResult:
    """Cria ou atualiza as regras oficiais sem gerar duplicidade."""
    codes = [item["codigo"] for item in INITIAL_ALERT_RULES]
    existing = {
        rule.codigo: rule
        for rule in db.query(PrinterAlertRule)
        .filter(PrinterAlertRule.codigo.in_(codes))
        .all()
    }
    created = 0
    updated = 0

    for item in INITIAL_ALERT_RULES:
        rule = existing.get(item["codigo"])
        if rule is None:
            rule = PrinterAlertRule(codigo=item["codigo"])
            db.add(rule)
            created += 1
        else:
            updated += 1

        for field_name in CONTROLLED_FIELDS:
            setattr(rule, field_name, item[field_name])

    db.commit()
    return AlertRuleSeedResult(
        created=created,
        updated=updated,
        total=len(INITIAL_ALERT_RULES),
    )
