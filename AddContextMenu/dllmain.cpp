// dllmain.cpp : Implementação do DllMain.

#include "pch.h"
#include "framework.h"
#include "resource.h"
#include "AddContextMenu_i.h"
#include "dllmain.h"
#include "xdlldata.h"

CAddContextMenuModule _AtlModule;

// Ponto de Entrada DLL
extern "C" BOOL WINAPI DllMain(HINSTANCE hInstance, DWORD dwReason, LPVOID lpReserved)
{
#ifdef _MERGE_PROXYSTUB
	if (!PrxDllMain(hInstance, dwReason, lpReserved))
		return FALSE;
#endif
	hInstance;
	return _AtlModule.DllMain(dwReason, lpReserved);
}
