/* npm.exe so Python can start npm without a .cmd file.
 * Official Node ships npm.cmd; CreateProcess does not run .cmd directly.
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

static int append_text(wchar_t *cmd, size_t cap, const wchar_t *text) {
    size_t used = wcslen(cmd);
    size_t add = wcslen(text);
    if (used + add + 1 >= cap) {
        return 0;
    }
    memcpy(cmd + used, text, (add + 1) * sizeof(wchar_t));
    return 1;
}

static int append_arg(wchar_t *cmd, size_t cap, const wchar_t *arg) {
    const wchar_t *p;
    int quote = (arg[0] == L'\0');
    size_t used;
    if (cmd[0] != L'\0' && !append_text(cmd, cap, L" ")) {
        return 0;
    }
    for (p = arg; *p; p++) {
        if (*p == L' ' || *p == L'\t' || *p == L'"') {
            quote = 1;
        }
    }
    if (!quote) {
        return append_text(cmd, cap, arg);
    }
    if (!append_text(cmd, cap, L"\"")) {
        return 0;
    }
    for (p = arg; *p; p++) {
        if (*p == L'"' && !append_text(cmd, cap, L"\\")) {
            return 0;
        }
        used = wcslen(cmd);
        if (used + 2 >= cap) {
            return 0;
        }
        cmd[used] = *p;
        cmd[used + 1] = L'\0';
    }
    return append_text(cmd, cap, L"\"");
}

int wmain(int argc, wchar_t **argv) {
    wchar_t dir[1024];
    wchar_t node[1200];
    wchar_t cli[1200];
    wchar_t *cmd;
    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    DWORD code = 1;
    int i;

    if (!exe_dir(dir, 1024)) {
        return 1;
    }
    _snwprintf(node, 1200, L"%s\\node.exe", dir);
    _snwprintf(cli, 1200, L"%s\\node_modules\\npm\\bin\\npm-cli.js", dir);
    node[1199] = L'\0';
    cli[1199] = L'\0';
    if (GetFileAttributesW(node) == INVALID_FILE_ATTRIBUTES ||
        GetFileAttributesW(cli) == INVALID_FILE_ATTRIBUTES) {
        fwprintf(stderr, L"Portable Node is missing npm.\n");
        return 1;
    }
    cmd = (wchar_t *)calloc(32768, sizeof(wchar_t));
    if (!cmd) {
        return 1;
    }
    if (!append_arg(cmd, 32768, node) || !append_arg(cmd, 32768, cli)) {
        free(cmd);
        return 1;
    }
    for (i = 1; i < argc; i++) {
        if (!append_arg(cmd, 32768, argv[i])) {
            free(cmd);
            return 1;
        }
    }
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));
    if (!CreateProcessW(node, cmd, NULL, NULL, TRUE, 0, NULL, NULL, &si, &pi)) {
        fwprintf(stderr, L"Could not start npm (error %lu).\n", GetLastError());
        free(cmd);
        return 1;
    }
    free(cmd);
    WaitForSingleObject(pi.hProcess, INFINITE);
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return (int)code;
}
