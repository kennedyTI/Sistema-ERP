"""Rotas robustas do cadastro de maquinas do modulo Impressoras."""

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.modules.auth.dependencies import (
    require_printers_machines_create,
    require_printers_machines_edit,
    require_printers_machines_status_toggle,
    require_printers_machines_view,
)
from backend.app.modules.auth.schemas import PortalUser
from backend.app.modules.printers.machines.schemas import (
    DetalhesMaquina,
    MaquinaCreate,
    MaquinaRead,
    MaquinaStatusUpdate,
    MaquinaUpdate,
    RespostaMaquinas,
    ResumoMaquinas,
    ResultadoMaquina,
    ResultadoToggleMaquina,
)
from backend.app.modules.printers.machines.services import (
    MachineConflictError,
    MachineNotFoundError,
    MachineValidationError,
    PrinterModelNotFoundError,
    create_machine,
    get_machine,
    list_machines,
    machine_to_read,
    read_machine_details,
    summarize_machines,
    update_machine,
    update_machine_status,
)

router = APIRouter(prefix="/machines", tags=["Impressoras - Maquinas"])


def resposta_sucesso(dados, mensagem: str) -> dict:
    return {
        "sucesso": True,
        "mensagem": mensagem,
        "dados": dados,
        "erros": None,
    }


def resposta_erro(
    *,
    status_code: int,
    mensagem: str,
    erros: dict[str, list[str]],
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            {
                "sucesso": False,
                "mensagem": mensagem,
                "dados": None,
                "erros": erros,
            }
        ),
    )


@router.get("", response_model=RespostaMaquinas[list[MaquinaRead]])
def machines_list(
    _user: PortalUser = Depends(require_printers_machines_view),
    db: Session = Depends(get_db),
):
    machines = [machine_to_read(machine) for machine in list_machines(db)]
    return resposta_sucesso(machines, "Lista de maquinas carregada com sucesso.")


@router.get("/summary", response_model=RespostaMaquinas[ResumoMaquinas])
def machines_summary(
    _user: PortalUser = Depends(require_printers_machines_view),
    db: Session = Depends(get_db),
):
    return resposta_sucesso(
        summarize_machines(db),
        "Resumo de maquinas carregado com sucesso.",
    )


@router.post(
    "",
    response_model=RespostaMaquinas[ResultadoMaquina],
    status_code=status.HTTP_201_CREATED,
)
def machines_create(
    payload: MaquinaCreate,
    user: PortalUser = Depends(require_printers_machines_create),
    db: Session = Depends(get_db),
):
    try:
        machine = create_machine(db, payload, changed_by=user.username)
    except MachineValidationError as exc:
        return resposta_erro(
            status_code=422,
            mensagem="Nao foi possivel cadastrar a maquina.",
            erros=exc.errors,
        )
    except PrinterModelNotFoundError:
        return resposta_erro(
            status_code=422,
            mensagem="Nao foi possivel cadastrar a maquina.",
            erros={"modelo_id": ["O modelo informado nao existe."]},
        )

    return resposta_sucesso(
        ResultadoMaquina(maquina=machine_to_read(machine)),
        "Maquina cadastrada com sucesso.",
    )


@router.get(
    "/{machine_id}/details",
    response_model=RespostaMaquinas[DetalhesMaquina],
)
def machines_details(
    machine_id: int,
    user: PortalUser = Depends(require_printers_machines_view),
    db: Session = Depends(get_db),
):
    try:
        details = read_machine_details(
            db,
            machine_id,
            can_edit=user.permissoes.impressoras.editar_maquinas,
            can_toggle_status=user.permissoes.impressoras.alternar_status_maquinas,
        )
    except MachineNotFoundError:
        return resposta_erro(
            status_code=404,
            mensagem="Maquina nao encontrada.",
            erros={"id": ["Nao existe maquina com o identificador informado."]},
        )

    return resposta_sucesso(details, "Detalhes da maquina carregados com sucesso.")


@router.get("/{machine_id}", response_model=RespostaMaquinas[MaquinaRead])
def machines_detail(
    machine_id: int,
    _user: PortalUser = Depends(require_printers_machines_view),
    db: Session = Depends(get_db),
):
    try:
        machine = get_machine(db, machine_id)
    except MachineNotFoundError:
        return resposta_erro(
            status_code=404,
            mensagem="Maquina nao encontrada.",
            erros={"id": ["Nao existe maquina com o identificador informado."]},
        )

    return resposta_sucesso(
        machine_to_read(machine),
        "Maquina carregada com sucesso.",
    )


@router.patch(
    "/{machine_id}",
    response_model=RespostaMaquinas[ResultadoMaquina],
)
def machines_update(
    machine_id: int,
    payload: MaquinaUpdate,
    user: PortalUser = Depends(require_printers_machines_edit),
    db: Session = Depends(get_db),
):
    try:
        machine = update_machine(
            db,
            machine_id,
            payload,
            changed_by=user.username,
        )
    except MachineNotFoundError:
        return resposta_erro(
            status_code=404,
            mensagem="Nao foi possivel atualizar a maquina.",
            erros={"id": ["A maquina informada nao existe."]},
        )
    except PrinterModelNotFoundError:
        return resposta_erro(
            status_code=422,
            mensagem="Nao foi possivel atualizar a maquina.",
            erros={"modelo_id": ["O modelo informado nao existe."]},
        )
    except MachineValidationError as exc:
        return resposta_erro(
            status_code=422,
            mensagem="Nao foi possivel atualizar a maquina.",
            erros=exc.errors,
        )
    except MachineConflictError:
        return resposta_erro(
            status_code=409,
            mensagem=(
                "Esta maquina foi alterada por outro usuario. "
                "Atualize os dados antes de salvar."
            ),
            erros={"atualizado_em": ["Registro desatualizado."]},
        )

    return resposta_sucesso(
        ResultadoMaquina(maquina=machine_to_read(machine)),
        "Maquina atualizada com sucesso.",
    )


@router.patch(
    "/{machine_id}/status",
    response_model=RespostaMaquinas[ResultadoToggleMaquina],
)
def machines_status_update(
    machine_id: int,
    payload: MaquinaStatusUpdate,
    user: PortalUser = Depends(require_printers_machines_status_toggle),
    db: Session = Depends(get_db),
):
    try:
        result = update_machine_status(
            db,
            machine_id,
            payload,
            changed_by=user.username,
        )
    except MachineNotFoundError:
        return resposta_erro(
            status_code=404,
            mensagem="Nao foi possivel alterar o status cadastral da maquina.",
            erros={"id": ["A maquina informada nao existe."]},
        )

    message = (
        "Maquina ativada com sucesso."
        if result.maquina.ativo
        else "Maquina inativada com sucesso."
    )
    return resposta_sucesso(result, message)
