// wrapper para dlldata.c

#ifdef _MERGE_PROXYSTUB // DLL de proxy mesclado simples

#define REGISTER_PROXY_DLL //DllRegisterServer, etc.

#define USE_STUBLESS_PROXY	//definido somente com switch MIDL /Oicf

#pragma comment(lib, "rpcns4.lib")
#pragma comment(lib, "rpcrt4.lib")

#define ENTRY_PREFIX	Prx

#include "dlldata.c"
#include "AddContextMenu_p.c"

#endif //_MERGE_PROXYSTUB
