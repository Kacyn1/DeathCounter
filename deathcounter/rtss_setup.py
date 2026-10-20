"""Instalacja RivaTuner Statistics Server (winget) i uruchamianie go razem z licznikiem.

RTSS wymaga uprawnień administratora. Żeby nie pytać o nie przy każdym starcie, jednorazowo
(za zgodą użytkownika w oknie UAC) tworzymy zadanie Harmonogramu zadań z najwyższymi
uprawnieniami i bez wyzwalaczy. Licznik uruchamia je później poleceniem `schtasks /Run`.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import tempfile
import winreg
from ctypes import wintypes
from pathlib import Path
from xml.sax.saxutils import escape

from .i18n import tr

TASK_NAME = "DeathCounter - RTSS"
WINGET_ID = "Guru3D.RTSS"
DEFAULT_PATH = Path(r"C:\Program Files (x86)\RivaTuner Statistics Server\RTSS.exe")
CREATE_NO_WINDOW = 0x08000000
ERROR_CANCELLED = 1223


class RtssSetupError(Exception):
    """Nie udało się zainstalować lub uruchomić RTSS."""


def find_rtss() -> Path | None:
    for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Unwinder\RTSS", 0, winreg.KEY_READ | view) as key:
                path = Path(winreg.QueryValueEx(key, "InstallPath")[0])
        except OSError:
            continue
        if path.is_file():
            return path
    return DEFAULT_PATH if DEFAULT_PATH.is_file() else None


def is_running() -> bool:
    result = _run(["tasklist", "/FI", "IMAGENAME eq RTSS.exe", "/FO", "CSV", "/NH"])
    return '"RTSS.exe"' in result.stdout


def task_exists() -> bool:
    return _run(["schtasks", "/Query", "/TN", TASK_NAME]).returncode == 0


def run_task() -> bool:
    return _run(["schtasks", "/Run", "/TN", TASK_NAME]).returncode == 0


def install_with_winget() -> None:
    """Instaluje RTSS przez winget. Instalator sam poprosi o zgodę administratora (UAC)."""
    try:
        result = _run(
            [
                "winget", "install", "--id", WINGET_ID, "--exact", "--source", "winget",
                "--silent", "--accept-package-agreements", "--accept-source-agreements",
                "--disable-interactivity",
            ],
            timeout=900,
        )
    except FileNotFoundError as exc:
        raise RtssSetupError(
            tr("W systemie brak programu winget. Zainstaluj RTSS ręcznie ze strony guru3d.com.")
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RtssSetupError(tr("Instalacja RTSS trwała zbyt długo i została przerwana.")) from exc
    if find_rtss() is None:
        details = (result.stdout + result.stderr).strip().splitlines()[-3:]
        raise RtssSetupError(
            tr("Instalacja RTSS nie powiodła się (anulowana lub błąd winget). ") + " ".join(details)
        )


def create_start_task(rtss_path: Path) -> None:
    """Tworzy zadanie uruchamiające RTSS bez okna UAC. Wymaga jednorazowej zgody (UAC)."""
    xml_path = Path(tempfile.gettempdir()) / "deathcounter_rtss_task.xml"
    xml_path.write_text(_task_xml(rtss_path), encoding="utf-16")
    try:
        code = run_elevated("schtasks.exe", f'/Create /TN "{TASK_NAME}" /XML "{xml_path}" /F')
    finally:
        xml_path.unlink(missing_ok=True)
    if code != 0 or not task_exists():
        raise RtssSetupError(tr("Nie udało się utworzyć zadania uruchamiającego RTSS (kod {code}).", code=code))


def start_rtss(rtss_path: Path) -> None:
    """Uruchamia RTSS: przez zadanie (bez UAC), a gdy go brak – bezpośrednio (z oknem UAC)."""
    if is_running():
        return
    if task_exists() and run_task():
        return
    run_elevated(str(rtss_path), "", wait=False, show=1)


def _task_xml(rtss_path: Path) -> str:
    user = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}".lstrip("\\")
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Uruchamia RivaTuner Statistics Server dla Death Counter by MK bez pytania o uprawnienia.</Description>
  </RegistrationInfo>
  <Principals>
    <Principal id="Author">
      <UserId>{escape(user)}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(str(rtss_path))}</Command>
      <WorkingDirectory>{escape(str(rtss_path.parent))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def _run(args: list[str], timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, text=True, encoding="oem", errors="replace",
        timeout=timeout, creationflags=CREATE_NO_WINDOW,
    )


class _ShellExecuteInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


_shell32 = ctypes.WinDLL("shell32", use_last_error=True)
_shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(_ShellExecuteInfo)]
_shell32.ShellExecuteExW.restype = wintypes.BOOL
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_ole32 = ctypes.WinDLL("ole32")


def run_elevated(file: str, parameters: str, wait: bool = True, show: int = 0) -> int | None:
    """Uruchamia program z uprawnieniami administratora (okno UAC). Zwraca kod wyjścia, gdy wait=True."""
    _ole32.CoInitializeEx(None, 0x2 | 0x4)  # apartment-threaded, bez OLE1 DDE (wymóg ShellExecuteEx)
    info = _ShellExecuteInfo()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x40 | 0x100  # SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC
    info.lpVerb = "runas"
    info.lpFile = file
    info.lpParameters = parameters
    info.nShow = show
    if not _shell32.ShellExecuteExW(ctypes.byref(info)):
        error = ctypes.get_last_error()
        if error == ERROR_CANCELLED:
            raise RtssSetupError(tr("Anulowano okno uprawnień administratora (UAC)."))
        raise RtssSetupError(tr("Nie można uruchomić {name} (błąd {error}).", name=Path(file).name, error=error))
    if not info.hProcess:
        return None
    try:
        if not wait:
            return None
        _kernel32.WaitForSingleObject(info.hProcess, 0xFFFFFFFF)
        code = wintypes.DWORD()
        _kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
        return code.value
    finally:
        _kernel32.CloseHandle(info.hProcess)
