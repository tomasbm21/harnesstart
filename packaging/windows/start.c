/* Double-click entry for the Windows zip. Console subsystem so a hidden
 * key prompt can run. No Git, winget, or pre-opened terminal required.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

static int exe_dir(wchar_t *out, DWORD cap) {
    DWORD n = GetModuleFileNameW(NULL, out, cap);
    wchar_t *slash;
    if (n == 0 || n >= cap) {
        return 0;
    }
    slash = wcsrchr(out, L'\\');
    if (!slash) {
        return 0;
    }
    *slash = L'\0';
    return 1;
}

static void pause_if_console(void) {
    HANDLE in = GetStdHandle(STD_INPUT_HANDLE);
    DWORD mode = 0;
    if (!GetConsoleMode(in, &mode)) {
        return;
    }
    fputws(L"\nPress Enter to close this window.\n", stderr);
    fflush(stderr);
    getwchar();
}

static int child_exit(const wchar_t *python, wchar_t *cmdline, const wchar_t *workdir) {
    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    DWORD code = 1;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));
    if (!CreateProcessW(python, cmdline, NULL, NULL, TRUE, 0, NULL, workdir, &si, &pi)) {
        fwprintf(stderr, L"Could not start Norfront Claw (error %lu).\n", GetLastError());
        return 1;
    }
    WaitForSingleObject(pi.hProcess, INFINITE);
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return (int)code;
}

int wmain(void) {
    wchar_t root[1024];
    wchar_t python[1200];
    wchar_t product[1200];
    wchar_t node[1200];
    wchar_t pyhome[1200];
    wchar_t cmdline[1600];
    wchar_t *path;
    DWORD old_len;
    int code;

    if (!exe_dir(root, 1024)) {
        fputws(L"Could not find the folder this program is in.\n", stderr);
        pause_if_console();
        return 1;
    }
    _snwprintf(python, 1200, L"%s\\runtime\\python\\python.exe", root);
    _snwprintf(product, 1200, L"%s\\product", root);
    _snwprintf(node, 1200, L"%s\\runtime\\node", root);
    _snwprintf(pyhome, 1200, L"%s\\runtime\\python", root);
    python[1199] = L'\0';
    if (GetFileAttributesW(python) == INVALID_FILE_ATTRIBUTES) {
        fputws(L"Portable Python is missing from this folder.\n", stderr);
        pause_if_console();
        return 1;
    }

    path = (wchar_t *)malloc(32768 * sizeof(wchar_t));
    if (!path) {
        return 1;
    }
    old_len = GetEnvironmentVariableW(L"PATH", path, 32768);
    if (old_len == 0 || old_len >= 32768) {
        _snwprintf(path, 32768, L"%s;%s", pyhome, node);
    } else {
        wchar_t *old = _wcsdup(path);
        if (!old) {
            free(path);
            return 1;
        }
        _snwprintf(path, 32768, L"%s;%s;%s", pyhome, node, old);
        free(old);
    }
    path[32767] = L'\0';
    SetEnvironmentVariableW(L"PATH", path);
    free(path);
    SetEnvironmentVariableW(L"CLAW_REPO", root);
    SetEnvironmentVariableW(L"PYTHONPATH", product);
    SetEnvironmentVariableW(L"PYTHONUTF8", L"1");
    SetEnvironmentVariableW(L"PYTHONIOENCODING", L"utf-8");
    SetEnvironmentVariableW(L"PYTHONDONTWRITEBYTECODE", L"1");
    SetConsoleTitleW(L"Norfront Claw");

    _snwprintf(cmdline, 1600, L"\"%s\" -m norfront_claw.boot", python);
    cmdline[1599] = L'\0';
    code = child_exit(python, cmdline, root);
    if (code != 0) {
        pause_if_console();
    }
    return code;
}
