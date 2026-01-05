// dllmain.h : Declaração da classe módulo.

class CAddContextMenuModule : public ATL::CAtlDllModuleT< CAddContextMenuModule >
{
public :
	DECLARE_LIBID(LIBID_AddContextMenuLib)
	DECLARE_REGISTRY_APPID_RESOURCEID(IDR_ADDCONTEXTMENU, "{7f317968-ef7e-4959-83cc-a70490227b48}")
};

extern class CAddContextMenuModule _AtlModule;
