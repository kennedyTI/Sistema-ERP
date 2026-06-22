"""Execucao PowerShell para consulta e criacao de usuarios no Active Directory."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass

from backend.app.modules.automacao.novo_usuario.config import (
    NovoUsuarioAutomationSettings,
)
from backend.app.modules.automacao.novo_usuario.services.admission_email_parser import (
    AdmissionData,
)
from backend.app.modules.automacao.novo_usuario.services.login_generator import (
    get_ad_name_parts,
)


@dataclass(frozen=True)
class ADUserPayload:
    login: str
    full_name: str
    first_name: str
    last_name: str
    description: str
    title: str
    department: str
    domain: str
    ou: str
    office: str
    company: str
    groups: tuple[str, ...]


@dataclass(frozen=True)
class PowerShellResult:
    success: bool
    stdout: str
    stderr: str
    returncode: int

    @property
    def output(self) -> str:
        parts = []
        if self.stdout:
            parts.append(self.stdout.strip())
        if self.stderr:
            parts.append(self.stderr.strip())
        return "\n".join(parts).strip()


class ActiveDirectoryError(RuntimeError):
    """Falha na execucao local dos cmdlets de Active Directory."""


def build_ad_user_payload(
    admission: AdmissionData,
    login: str,
    settings: NovoUsuarioAutomationSettings,
) -> ADUserPayload:
    first_name, last_name = get_ad_name_parts(admission.nome_completo)
    return ADUserPayload(
        login=login,
        full_name=admission.nome_completo,
        first_name=first_name,
        last_name=last_name,
        description=f"{admission.cargo} - {admission.unid_org}",
        title=admission.cargo,
        department=admission.unid_org,
        domain=settings.ad_domain,
        ou=settings.ad_ou,
        office=settings.ad_office,
        company=settings.ad_company,
        groups=settings.ad_groups,
    )


class PowerShellADUserService:
    def __init__(self, settings: NovoUsuarioAutomationSettings):
        self.settings = settings
        self.executable = (
            shutil.which("powershell.exe")
            or shutil.which("powershell")
            or shutil.which("pwsh")
        )

    def _run_script(self, script: str, *, password_to_mask: str | None = None) -> PowerShellResult:
        if not self.executable:
            raise ActiveDirectoryError("PowerShell nao encontrado neste ambiente.")

        completed = subprocess.run(
            [
                self.executable,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "-",
            ],
            input=script,
            capture_output=True,
            text=True,
            timeout=self.settings.powershell_timeout_seconds,
            check=False,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if password_to_mask:
            stdout = stdout.replace(password_to_mask, "********")
            stderr = stderr.replace(password_to_mask, "********")
        return PowerShellResult(
            success=completed.returncode == 0,
            stdout=stdout,
            stderr=stderr,
            returncode=completed.returncode,
        )

    def assert_active_directory_module_available(self) -> None:
        result = self._run_script(
            """
$ErrorActionPreference = "Stop"
Import-Module ActiveDirectory -ErrorAction Stop
Write-Output "ActiveDirectory module available"
"""
        )
        if not result.success:
            raise ActiveDirectoryError(
                "Modulo ActiveDirectory nao disponivel no PowerShell local. "
                + result.output
            )

    def login_exists(self, login: str) -> bool:
        safe_login = login.replace("'", "''")
        result = self._run_script(
            f"""
$ErrorActionPreference = "Stop"
Import-Module ActiveDirectory -ErrorAction Stop
$user = Get-ADUser -Filter "SamAccountName -eq '{safe_login}'" `
    -Properties SamAccountName,UserPrincipalName,Name
if ($null -eq $user) {{
    Write-Output '{{"exists": false}}'
}} else {{
    [PSCustomObject]@{{
        exists = $true
        samAccountName = $user.SamAccountName
        userPrincipalName = $user.UserPrincipalName
        name = $user.Name
    }} | ConvertTo-Json -Compress
}}
"""
        )
        if not result.success:
            raise ActiveDirectoryError(
                f"Falha ao consultar login {login} no AD. {result.output}"
            )
        try:
            payload = json.loads(result.stdout.strip())
        except json.JSONDecodeError as exc:
            raise ActiveDirectoryError(
                f"Resposta inesperada ao consultar login {login}: {result.output}"
            ) from exc
        return bool(payload.get("exists"))

    def create_user(
        self,
        payload: ADUserPayload,
        *,
        temporary_password: str,
    ) -> PowerShellResult:
        data = {
            "login": payload.login,
            "full_name": payload.full_name,
            "first_name": payload.first_name,
            "last_name": payload.last_name,
            "description": payload.description,
            "title": payload.title,
            "department": payload.department,
            "domain": payload.domain,
            "ou": payload.ou,
            "office": payload.office,
            "company": payload.company,
            "groups": list(payload.groups),
            "temporary_password": temporary_password,
        }
        json_payload = json.dumps(data, ensure_ascii=False)
        script = f"""
$ErrorActionPreference = "Stop"
Import-Module ActiveDirectory -ErrorAction Stop
$data = @'
{json_payload}
'@ | ConvertFrom-Json
$securePassword = ConvertTo-SecureString $data.temporary_password -AsPlainText -Force
$upn = "$($data.login)@$($data.domain)"

New-ADUser `
    -Name $data.full_name `
    -GivenName $data.first_name `
    -Surname $data.last_name `
    -DisplayName $data.full_name `
    -Description $data.description `
    -Office $data.office `
    -UserPrincipalName $upn `
    -SamAccountName $data.login `
    -Title $data.title `
    -Department $data.department `
    -Company $data.company `
    -Path $data.ou `
    -Enabled:$false

Set-ADAccountPassword -Identity $data.login -NewPassword $securePassword -Reset
Set-ADUser -Identity $data.login -ChangePasswordAtLogon $true
Enable-ADAccount -Identity $data.login

foreach ($group in $data.groups) {{
    Add-ADGroupMember -Identity $group -Members $data.login
}}

[PSCustomObject]@{{
    status = "created"
    login = $data.login
    userPrincipalName = $upn
    groups = $data.groups
}} | ConvertTo-Json -Compress
"""
        result = self._run_script(script, password_to_mask=temporary_password)
        if not result.success:
            raise ActiveDirectoryError(
                f"Falha ao criar usuario {payload.login} no AD. {result.output}"
            )
        return result
