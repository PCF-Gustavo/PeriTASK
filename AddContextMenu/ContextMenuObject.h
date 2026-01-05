
#pragma once

// Inclua só o necessário no header.
// O PCH deve ser incluído NO CPP (ex.: ContextMenuObject.cpp).
#include "resource.h"
#include "AddContextMenu_i.h"

#include <atlbase.h>
#include <atlcom.h>
#include <shlobj.h>     // IShellExtInit, IContextMenu
#include <shellapi.h>
#include <vector>
#include <string>

// Se _ATL_NO_AUTOMATIC_NAMESPACE estiver definido no seu framework.h,
// qualifique os tipos com ATL:: para evitar erros.
class ATL_NO_VTABLE CContextMenuObject :
    public ATL::CComObjectRootEx<ATL::CComSingleThreadModel>,
    public ATL::CComCoClass<CContextMenuObject, &CLSID_ContextMenuObject>,
    public IShellExtInit,
    public IContextMenu
{
public:
    CContextMenuObject() {}

    // Se você já tem o .rgs referenciado por IDR_ADDCONTEXTMENU (101), use:
    DECLARE_REGISTRY_RESOURCEID(IDR_ADDCONTEXTMENU)
    // Se preferir registrar só via módulo principal/.rgs externo, troque por DECLARE_NO_REGISTRY()

    DECLARE_NOT_AGGREGATABLE(CContextMenuObject)

    BEGIN_COM_MAP(CContextMenuObject)
        COM_INTERFACE_ENTRY(IShellExtInit)
        COM_INTERFACE_ENTRY(IContextMenu)
    END_COM_MAP()

    DECLARE_PROTECT_FINAL_CONSTRUCT()

    HRESULT FinalConstruct() { return S_OK; }
    void FinalRelease() {}

    // --- IShellExtInit ---
public:
    STDMETHOD(Initialize)(LPCITEMIDLIST pidlFolder, IDataObject* pDataObj, HKEY hKeyProgID) override
    {
        m_selectedFiles.clear();
        if (!pDataObj) return S_OK;

        // Extrai lista de arquivos selecionados (CF_HDROP)
        FORMATETC fmt = { CF_HDROP, nullptr, DVASPECT_CONTENT, -1, TYMED_HGLOBAL };
        STGMEDIUM stg = {};
        if (FAILED(pDataObj->GetData(&fmt, &stg))) return S_OK;

        HDROP hDrop = (HDROP)GlobalLock(stg.hGlobal);
        if (hDrop)
        {
            UINT count = DragQueryFile(hDrop, 0xFFFFFFFF, nullptr, 0);
            wchar_t path[MAX_PATH];
            for (UINT i = 0; i < count; ++i)
            {
                if (DragQueryFile(hDrop, i, path, ARRAYSIZE(path)))
                    m_selectedFiles.emplace_back(path);
            }
            GlobalUnlock(stg.hGlobal);
        }
        ReleaseStgMedium(&stg);
        return S_OK;
    }

    // --- IContextMenu ---
public:
    STDMETHOD(QueryContextMenu)(HMENU hMenu, UINT indexMenu, UINT idCmdFirst,
        UINT idCmdLast, UINT uFlags) override
    {
        if (uFlags & CMF_DEFAULTONLY)
            return MAKE_HRESULT(SEVERITY_SUCCESS, 0, 0);

        InsertMenu(hMenu, indexMenu, MF_BYPOSITION | MF_STRING, idCmdFirst, L"PeriTASK");
        return MAKE_HRESULT(SEVERITY_SUCCESS, 0, 1); // adicionamos 1 comando
    }

    STDMETHOD(InvokeCommand)(LPCMINVOKECOMMANDINFO pici) override
    {
        if (HIWORD(pici->lpVerb) == 0)
        {
            UINT id = LOWORD(pici->lpVerb);
            if (id == 0)
            {
                // “Não faz nada”
                // MessageBox(pici->hwnd, L"Comando TESTE acionado.", L"AddContextMenu", MB_OK);
                return S_OK;
            }
        }
        return E_FAIL;
    }

    STDMETHOD(GetCommandString)(UINT_PTR idCmd, UINT uFlags, UINT* /*pRes*/,
        LPSTR pszName, UINT cchMax) override
    {
        if (idCmd == 0 && (uFlags & GCS_HELPTEXTW))
        {
            const wchar_t* help = L"Executa ação de teste (não faz nada).";
            wcsncpy_s((wchar_t*)pszName, cchMax, help, _TRUNCATE);
        }
        else if (idCmd == 0 && (uFlags & GCS_HELPTEXTA))
        {
            const char* help = "Executa ação de teste (não faz nada).";
            strncpy_s(pszName, cchMax, help, _TRUNCATE);
        }
        return S_OK;
    }

private:
    std::vector<std::wstring> m_selectedFiles;
};

OBJECT_ENTRY_AUTO(__uuidof(ContextMenuObject), CContextMenuObject)
