"""Fail-closed, owner-only writes for the machine credential store."""

from __future__ import annotations

import ctypes
import os
import secrets
import stat
from ctypes import wintypes
from pathlib import Path
from typing import Any

from talamus.errors import CredentialStoreError

_OWNER_ONLY_MODE = stat.S_IRUSR | stat.S_IWUSR
_DACL_SECURITY_INFORMATION = 0x00000004
_PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000
_SECURITY_DESCRIPTOR_REVISION = 1
_TOKEN_QUERY = 0x0008
_TOKEN_USER_CLASS = 1


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("sid", ctypes.c_void_p), ("attributes", wintypes.DWORD)]


class _TokenUser(ctypes.Structure):
    _fields_ = [("user", _SidAndAttributes)]


def _windows_libraries() -> tuple[Any, Any]:
    if os.name != "nt":
        raise OSError("Windows security APIs are unavailable on this platform")
    win_dll = vars(ctypes).get("WinDLL")
    if not callable(win_dll):
        raise OSError("Windows DLL loading support is unavailable")
    advapi32 = win_dll("advapi32", use_last_error=True)
    kernel32 = win_dll("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.LPWSTR),
    ]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    advapi32.SetFileSecurityW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    advapi32.SetFileSecurityW.restype = wintypes.BOOL
    advapi32.GetFileSecurityW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetFileSecurityW.restype = wintypes.BOOL
    advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = wintypes.BOOL
    return advapi32, kernel32


def _windows_error(action: str) -> OSError:
    get_last_error = vars(ctypes).get("get_last_error")
    format_error = vars(ctypes).get("FormatError")
    if not callable(get_last_error) or not callable(format_error):
        return OSError(f"{action}: Windows error details are unavailable")
    code = int(get_last_error())
    detail = str(format_error(code))
    return OSError(code, f"{action}: {detail}")


def _current_windows_user_sid() -> str:
    advapi32, kernel32 = _windows_libraries()
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(),
        _TOKEN_QUERY,
        ctypes.byref(token),
    ):
        raise _windows_error("OpenProcessToken failed")
    try:
        needed = wintypes.DWORD()
        advapi32.GetTokenInformation(token, _TOKEN_USER_CLASS, None, 0, ctypes.byref(needed))
        if not needed.value:
            raise _windows_error("GetTokenInformation size query failed")
        buffer = ctypes.create_string_buffer(needed.value)
        if not advapi32.GetTokenInformation(
            token,
            _TOKEN_USER_CLASS,
            buffer,
            needed.value,
            ctypes.byref(needed),
        ):
            raise _windows_error("GetTokenInformation failed")
        token_user = ctypes.cast(buffer, ctypes.POINTER(_TokenUser)).contents
        sid_text = wintypes.LPWSTR()
        if not advapi32.ConvertSidToStringSidW(token_user.user.sid, ctypes.byref(sid_text)):
            raise _windows_error("ConvertSidToStringSidW failed")
        try:
            if not sid_text.value:
                raise OSError("Current Windows user SID is empty")
            return sid_text.value
        finally:
            kernel32.LocalFree(sid_text)
    finally:
        kernel32.CloseHandle(token)


def _owner_only_windows_sddl() -> str:
    return f"D:P(A;;FA;;;{_current_windows_user_sid()})"


def _canonicalize_windows_sddl(sddl: str) -> str:
    advapi32, kernel32 = _windows_libraries()
    descriptor = ctypes.c_void_p()
    if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl,
        _SECURITY_DESCRIPTOR_REVISION,
        ctypes.byref(descriptor),
        None,
    ):
        raise _windows_error("Could not build the Windows security descriptor")
    rendered = wintypes.LPWSTR()
    try:
        if not advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            descriptor,
            _SECURITY_DESCRIPTOR_REVISION,
            _DACL_SECURITY_INFORMATION,
            ctypes.byref(rendered),
            None,
        ):
            raise _windows_error("Could not canonicalize the Windows security descriptor")
        return rendered.value or ""
    finally:
        if rendered:
            kernel32.LocalFree(rendered)
        kernel32.LocalFree(descriptor)


def _canonical_windows_user_trustee(user_sid: str) -> str:
    canonical = _canonicalize_windows_sddl(f"D:P(A;;FA;;;{user_sid})")
    marker = canonical.rfind(";;;")
    if marker < 0 or not canonical.endswith(")"):
        raise OSError("Canonical Windows credential ACL has an unexpected format")
    return canonical[marker + 3 : -1]


def _set_windows_owner_only(path: Path) -> None:
    advapi32, kernel32 = _windows_libraries()
    descriptor = ctypes.c_void_p()
    sddl = _owner_only_windows_sddl()
    if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl,
        _SECURITY_DESCRIPTOR_REVISION,
        ctypes.byref(descriptor),
        None,
    ):
        raise _windows_error("Could not build the owner-only Windows ACL")
    try:
        security_information = _DACL_SECURITY_INFORMATION | _PROTECTED_DACL_SECURITY_INFORMATION
        if not advapi32.SetFileSecurityW(str(path), security_information, descriptor):
            raise _windows_error("Could not apply the owner-only Windows ACL")
    finally:
        kernel32.LocalFree(descriptor)


def _windows_dacl_sddl(path: Path) -> str:
    advapi32, kernel32 = _windows_libraries()
    needed = wintypes.DWORD()
    advapi32.GetFileSecurityW(str(path), _DACL_SECURITY_INFORMATION, None, 0, ctypes.byref(needed))
    if not needed.value:
        raise _windows_error("GetFileSecurityW size query failed")
    descriptor = ctypes.create_string_buffer(needed.value)
    if not advapi32.GetFileSecurityW(
        str(path),
        _DACL_SECURITY_INFORMATION,
        descriptor,
        needed.value,
        ctypes.byref(needed),
    ):
        raise _windows_error("GetFileSecurityW failed")
    sddl = wintypes.LPWSTR()
    if not advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW(
        descriptor,
        _SECURITY_DESCRIPTOR_REVISION,
        _DACL_SECURITY_INFORMATION,
        ctypes.byref(sddl),
        None,
    ):
        raise _windows_error("Could not inspect the Windows ACL")
    try:
        return sddl.value or ""
    finally:
        kernel32.LocalFree(sddl)


def _windows_dacl_is_owner_only_sddl(sddl: str, expected_trustee: str) -> bool:
    """Validate the effective policy while ignoring Windows ACL bookkeeping flags."""
    if not sddl.startswith("D:"):
        return False
    ace_start = sddl.find("(")
    if ace_start < 0:
        return False

    flags = sddl[2:ace_start]
    protected = False
    while flags:
        if flags.startswith("AI") or flags.startswith("AR"):
            # Windows Server may retain these auto-inheritance bookkeeping bits
            # even after the DACL has been protected. They do not grant access.
            flags = flags[2:]
        elif flags.startswith("P"):
            protected = True
            flags = flags[1:]
        else:
            return False
    if not protected:
        return False

    ace_block = sddl[ace_start:]
    if not ace_block.startswith("(") or not ace_block.endswith(")"):
        return False
    aces = ace_block[1:-1].split(")(")
    if len(aces) != 1:
        return False
    ace_type, ace_flags, rights, object_guid, inherited_guid, sid = (
        aces[0].split(";") if aces[0].count(";") == 5 else ("",) * 6
    )
    return (
        ace_type == "A"
        and not ace_flags
        and rights.casefold() in {"fa", "0x1f01ff", "0x001f01ff"}
        and not object_guid
        and not inherited_guid
        and sid == expected_trustee
    )


def credential_file_is_owner_only(path: Path) -> bool:
    """Return whether *path* has the exact credential-store permission policy."""
    if os.name == "nt":
        user_sid = _current_windows_user_sid()
        return _windows_dacl_is_owner_only_sddl(
            _windows_dacl_sddl(path),
            _canonical_windows_user_trustee(user_sid),
        )
    return stat.S_IMODE(path.stat().st_mode) == _OWNER_ONLY_MODE


def _harden_before_write(path: Path, fd: int) -> None:
    if os.name == "nt":
        _set_windows_owner_only(path)
        actual_dacl = _windows_dacl_sddl(path)
        user_sid = _current_windows_user_sid()
        expected_trustee = _canonical_windows_user_trustee(user_sid)
        if not _windows_dacl_is_owner_only_sddl(actual_dacl, expected_trustee):
            raise OSError(
                "owner-only permission verification failed: "
                f"Windows returned DACL {actual_dacl!r} for current-user SID {user_sid!r} "
                f"(canonical trustee {expected_trustee!r})"
            )
    else:
        fchmod = getattr(os, "fchmod", None)
        if fchmod is None:
            raise OSError("fchmod is unavailable on this POSIX platform")
        fchmod(fd, _OWNER_ONLY_MODE)
    if os.name != "nt" and not credential_file_is_owner_only(path):
        raise OSError("owner-only permission verification failed")


def _exclusive_temp_file(path: Path) -> tuple[int, Path]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    for _ in range(16):
        temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
        try:
            return os.open(temporary, flags, _OWNER_ONLY_MODE), temporary
        except FileExistsError:
            continue
    raise OSError("could not reserve a unique credential temporary file")


def write_owner_only_text(path: Path, contents: str) -> None:
    """Atomically write *contents* after owner-only access is proven.

    The temporary file contains no credential bytes until its POSIX mode or
    Windows protected DACL has been applied and verified. Replacing an existing
    file also replaces any overly permissive metadata without a weak write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = -1
    temporary: Path | None = None
    try:
        fd, temporary = _exclusive_temp_file(path)
        _harden_before_write(temporary, fd)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            fd = -1
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    except Exception as exc:
        if fd >= 0:
            os.close(fd)
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        if isinstance(exc, CredentialStoreError):
            raise
        raise CredentialStoreError(
            "Credential was not saved because owner-only file permissions "
            f"could not be established: {exc}"
        ) from exc
