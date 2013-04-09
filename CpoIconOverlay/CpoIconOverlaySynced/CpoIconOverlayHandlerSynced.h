// CpoIconOverlayHandler.h : Declaration of the CCpoIconOverlayHandler

#pragma once
#include "resource.h"       // main symbols
#include "FileState.h"

// {6780E873-C33D-4498-AC3B-694221A87964}
extern const GUID CLSID_CpoIconOverlayHandlerSynced;


#if defined(_WIN32_WCE) && !defined(_CE_DCOM) && !defined(_CE_ALLOW_SINGLE_THREADED_OBJECTS_IN_MTA)
#error "Single-threaded COM objects are not properly supported on Windows CE platform, such as the Windows Mobile platforms that do not include full DCOM support. Define _CE_ALLOW_SINGLE_THREADED_OBJECTS_IN_MTA to force ATL to support creating single-thread COM object's and allow use of it's single-threaded COM object implementations. The threading model in your rgs file was set to 'Free' as that is the only threading model supported in non DCOM Windows CE platforms."
#endif

using namespace ATL;


// CCpoIconOverlayHandlerSynced

class ATL_NO_VTABLE CCpoIconOverlayHandlerSynced :
	public CComObjectRootEx<CComSingleThreadModel>,
	public CComCoClass<CCpoIconOverlayHandlerSynced, &CLSID_CpoIconOverlayHandlerSynced>,
    public IShellIconOverlayIdentifier
{
private:
    FileState *lastKnownState;

public:
	CCpoIconOverlayHandlerSynced()
	{
	}

DECLARE_REGISTRY_RESOURCEID(IDR_CPOICONOVERLAYHANDLER)

DECLARE_NOT_AGGREGATABLE(CCpoIconOverlayHandlerSynced)
    
BEGIN_COM_MAP(CCpoIconOverlayHandlerSynced)
    COM_INTERFACE_ENTRY(IShellIconOverlayIdentifier)
END_COM_MAP()

	// IShellIconOverlayIdentifier
	IFACEMETHODIMP GetOverlayInfo(LPWSTR, int, int*, DWORD*);
	IFACEMETHODIMP GetPriority(int*);
	IFACEMETHODIMP IsMemberOf(LPCWSTR, DWORD);

	DECLARE_PROTECT_FINAL_CONSTRUCT()

	HRESULT FinalConstruct()
	{
		return S_OK;
	}

	void FinalRelease()
	{
	}

private:
    LPTSTR GetUserHomeDir();
	int filter(unsigned int code, struct _EXCEPTION_POINTERS *ep);
};

OBJECT_ENTRY_AUTO(CLSID_CpoIconOverlayHandlerSynced, CCpoIconOverlayHandlerSynced)
