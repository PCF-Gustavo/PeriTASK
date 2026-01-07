// ContextMenuObject.cpp

#include "pch.h"
#include "framework.h"
#include "resource.h"
#include "AddContextMenu_i.h"

#include <atlbase.h>
#include <atlcom.h>
#include <shlobj.h>
#include <shellapi.h>
#include <windows.h>

#include <vector>
#include <string>

using namespace ATL;

//
// ======================================================
// 🔹 Função auxiliar: lê o caminho de instalação do Registry
// ======================================================
// Espera que o WiX crie:
// HKLM\Software\PeriTASK
//   InstallPath = "C:\Program Files\PeriTASK\"
//
bool GetInstallPath(std::wstring& outPath)
{
    HKEY hKey{};
    if (RegOpenKeyExW(
        HKEY_LOCAL_MACHINE,
        L"Software\\PeriTASK",
        0,
        KEY_READ | KEY_WOW64_64KEY,
        &hKey) != ERROR_SUCCESS)
        return false;

    wchar_t buffer[MAX_PATH]{};
    DWORD bufferSize = sizeof(buffer);

    LONG res = RegQueryValueExW(
        hKey,
        L"InstallPath",
        nullptr,
        nullptr,
        reinterpret_cast<LPBYTE>(buffer),
        &bufferSize);

    RegCloseKey(hKey);

    if (res != ERROR_SUCCESS)
        return false;

    outPath = buffer;

    // garante barra no final
    if (!outPath.empty() && outPath.back() != L'\\')
        outPath += L'\\';

    return true;
}

//
// ======================================================
// 🔹 Classe COM do Context Menu
// ======================================================
class ATL_NO_VTABLE CContextMenuObject :
    public CComObjectRootEx<CComSingleThreadModel>,
    public CComCoClass<CContextMenuObject, &CLSID_ContextMenuObject>,
    public IShellExtInit,
    public IContextMenu
{
public:
    CContextMenuObject() {}

    DECLARE_REGISTRY_RESOURCEID(IDR_ADDCONTEXTMENU)
    DECLARE_NOT_AGGREGATABLE(CContextMenuObject)

    BEGIN_COM_MAP(CContextMenuObject)
        COM_INTERFACE_ENTRY(IShellExtInit)
        COM_INTERFACE_ENTRY(IContextMenu)
    END_COM_MAP()

    DECLARE_PROTECT_FINAL_CONSTRUCT()

    HRESULT FinalConstruct() { return S_OK; }
    void FinalRelease() {}

    // ======================================================
    // IShellExtInit
    // ======================================================
    STDMETHOD(Initialize)(
        LPCITEMIDLIST,
        IDataObject* pDataObj,
        HKEY) override
    {
        selectedFiles.clear();
        if (!pDataObj)
            return S_OK;

        FORMATETC fmt = { CF_HDROP, nullptr, DVASPECT_CONTENT, -1, TYMED_HGLOBAL };
        STGMEDIUM stg{};

        if (FAILED(pDataObj->GetData(&fmt, &stg)))
            return S_OK;

        HDROP hDrop = (HDROP)GlobalLock(stg.hGlobal);
        if (hDrop)
        {
            UINT count = DragQueryFileW(hDrop, 0xFFFFFFFF, nullptr, 0);
            wchar_t path[MAX_PATH];

            for (UINT i = 0; i < count; ++i)
            {
                if (DragQueryFileW(hDrop, i, path, ARRAYSIZE(path)))
                    selectedFiles.emplace_back(path);
            }
            GlobalUnlock(stg.hGlobal);
        }

        ReleaseStgMedium(&stg);
        return S_OK;
    }

    // ======================================================
    // IContextMenu
    // ======================================================
    STDMETHOD(QueryContextMenu)(
        HMENU hMenu,
        UINT indexMenu,
        UINT idCmdFirst,
        UINT,
        UINT uFlags) override
    {
        if (uFlags & CMF_DEFAULTONLY)
            return MAKE_HRESULT(SEVERITY_SUCCESS, 0, 0);

        InsertMenuW(
            hMenu,
            indexMenu,
            MF_BYPOSITION | MF_STRING,
            idCmdFirst,
            L"PeriTASK");

        return MAKE_HRESULT(SEVERITY_SUCCESS, 0, 1);
    }

    STDMETHOD(InvokeCommand)(LPCMINVOKECOMMANDINFO pici) override
    {
        // --- Verificação do comando ---
        const auto pex =
            (pici->cbSize == sizeof(CMINVOKECOMMANDINFOEX))
            ? reinterpret_cast<const CMINVOKECOMMANDINFOEX*>(pici)
            : nullptr;

        const bool isUnicode = (pex && (pex->fMask & CMIC_MASK_UNICODE)) != 0;
        bool isVerbString = false;

        if (isUnicode)
            isVerbString = HIWORD(pex->lpVerbW) != 0;
        else
            isVerbString = HIWORD(pici->lpVerb) != 0;

        if (!isVerbString)
        {
            UINT idCmd = isUnicode ? LOWORD(pex->lpVerbW) : LOWORD(pici->lpVerb);
            if (idCmd != 0)
                return S_FALSE;
        }

        // ======================================================
        // 🔹 Descobre caminho instalado
        // ======================================================
        std::wstring installPath;
        if (!GetInstallPath(installPath))
        {
            MessageBoxW(
                pici->hwnd,
                L"PeriTASK não está instalado corretamente.",
                L"PeriTASK",
                MB_ICONERROR);
            return S_OK;
        }

        std::wstring exePath = installPath + L"UserInterface.exe";

        if (GetFileAttributesW(exePath.c_str()) == INVALID_FILE_ATTRIBUTES)
        {
            MessageBoxW(
                pici->hwnd,
                L"UserInterface.exe não encontrado.",
                L"PeriTASK",
                MB_ICONERROR);
            return S_OK;
        }

        // ======================================================
        // 🔹 Parâmetros: arquivos selecionados
        // ======================================================
        std::wstring params;
        for (const auto& f : selectedFiles)
        {
            params += L"\"";
            params += f;
            params += L"\" ";
        }

        // ======================================================
        // 🔹 Executa o WPF
        // ======================================================
        SHELLEXECUTEINFOW sei{};
        sei.cbSize = sizeof(sei);
        sei.fMask = SEE_MASK_FLAG_DDEWAIT | SEE_MASK_NOASYNC;
        sei.hwnd = pici->hwnd;
        sei.lpVerb = L"open";
        sei.lpFile = exePath.c_str();
        sei.lpParameters = params.empty() ? nullptr : params.c_str();
        sei.lpDirectory = installPath.c_str();
        sei.nShow = SW_SHOWNORMAL;

        if (!ShellExecuteExW(&sei))
        {
            DWORD err = GetLastError();
            wchar_t msg[256];
            swprintf_s(msg, L"Erro ao executar PeriTASK (%lu).", err);
            MessageBoxW(pici->hwnd, msg, L"PeriTASK", MB_ICONERROR);
        }

        return S_OK;
    }

    STDMETHOD(GetCommandString)(
        UINT_PTR idCmd,
        UINT uFlags,
        UINT*,
        LPSTR pszName,
        UINT cchMax) override
    {
        if (idCmd == 0 && (uFlags & GCS_HELPTEXTW))
        {
            const wchar_t* help = L"Executa o PeriTASK";
            wcsncpy_s(reinterpret_cast<wchar_t*>(pszName), cchMax, help, _TRUNCATE);
        }
        return S_OK;
    }

private:
    std::vector<std::wstring> selectedFiles;
};

OBJECT_ENTRY_AUTO(__uuidof(ContextMenuObject), CContextMenuObject)
