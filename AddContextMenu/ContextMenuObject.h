#pragma once

// 🔹 Includes mínimos para declaração COM
#include "resource.h"
#include "AddContextMenu_i.h"

#include <atlbase.h>
#include <atlcom.h>
#include <shlobj.h>     // IShellExtInit, IContextMenu

#include <vector>
#include <string>

// ======================================================
// Context Menu COM Object
// ======================================================
class ATL_NO_VTABLE CContextMenuObject :
    public ATL::CComObjectRootEx<ATL::CComSingleThreadModel>,
    public ATL::CComCoClass<CContextMenuObject, &CLSID_ContextMenuObject>,
    public IShellExtInit,
    public IContextMenu
{
public:
    CContextMenuObject();

    DECLARE_REGISTRY_RESOURCEID(IDR_ADDCONTEXTMENU)
    DECLARE_NOT_AGGREGATABLE(CContextMenuObject)

    BEGIN_COM_MAP(CContextMenuObject)
        COM_INTERFACE_ENTRY(IShellExtInit)
        COM_INTERFACE_ENTRY(IContextMenu)
    END_COM_MAP()

    DECLARE_PROTECT_FINAL_CONSTRUCT()

    HRESULT FinalConstruct();
    void FinalRelease();

    // ============================
    // IShellExtInit
    // ============================
    STDMETHOD(Initialize)(
        LPCITEMIDLIST pidlFolder,
        IDataObject* pDataObj,
        HKEY hKeyProgID) override;

    // ============================
    // IContextMenu
    // ============================
    STDMETHOD(QueryContextMenu)(
        HMENU hMenu,
        UINT indexMenu,
        UINT idCmdFirst,
        UINT idCmdLast,
        UINT uFlags) override;

    STDMETHOD(InvokeCommand)(
        LPCMINVOKECOMMANDINFO pici) override;

    STDMETHOD(GetCommandString)(
        UINT_PTR idCmd,
        UINT uFlags,
        UINT* pRes,
        LPSTR pszName,
        UINT cchMax) override;

private:
    // 🔹 Lista de arquivos selecionados
    std::vector<std::wstring> selectedFiles;
};
