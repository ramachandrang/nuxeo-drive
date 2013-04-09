// CpoIconOverlayHandler.cpp : Implementation of CCpoIconOverlayHandler

#include "stdafx.h"
#include "CpoIconOverlayHandlerSynced.h"
#include "Userenv.h"
#include "Shlwapi.h"
#pragma comment(lib, "Shlwapi.lib")
#pragma comment(lib, "Userenv.lib")

//#define DB_PATH  _T(".nuxeo-drive\\nxdrive.db")
#define DB_PATH  _T("")

// {6780E873-C33D-4498-AC3B-694221A87963}
static const GUID CLSID_CpoIconOverlayHandlerSynced = 
{ 0x6780e873, 0xc33d, 0x4498, { 0xac, 0x3b, 0x69, 0x42, 0x21, 0xa8, 0x79, 0x63 } };

// CCpoIconOverlayHandlerSynced

    LPTSTR CCpoIconOverlayHandlerSynced::GetUserHomeDir()
    {
        LPTSTR lptstrHomeDirBuf = (LPTSTR)malloc(MAX_PATH * sizeof(TCHAR));
        HANDLE hToken = NULL;
        OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &hToken);
        DWORD chBufSize = MAX_PATH;
        GetUserProfileDirectory(hToken, lptstrHomeDirBuf, &chBufSize);
        return lptstrHomeDirBuf;
    }

	IFACEMETHODIMP CCpoIconOverlayHandlerSynced::GetOverlayInfo(
		LPWSTR pwszIconFile, int cchMax, int* pIndex, DWORD* pdwFlags)
	{
        USES_CONVERSION;

        LPTSTR homePath = GetUserHomeDir();
        TCHAR dbPath[MAX_PATH] = {0};
        PathCombine(dbPath, homePath, DB_PATH);
        free(homePath);

        // allow to recover after db is built
        lastKnownState = new FileState(dbPath);

		// Get the module's full path
		GetModuleFileNameW(_AtlBaseModule.GetModuleInstance(), pwszIconFile, 
			cchMax);

		// Use the first icon in the resource
		*pIndex = 0;
		*pdwFlags = ISIOI_ICONFILE | ISIOI_ICONINDEX;

		return S_OK;
	}

    IFACEMETHODIMP CCpoIconOverlayHandlerSynced::GetPriority(int* pPriority)
	{
		// Request the second highest priority 
		*pPriority = 2;

		return S_OK;
	}

    IFACEMETHODIMP CCpoIconOverlayHandlerSynced::IsMemberOf(LPCWSTR pwszPath, 
												   DWORD dwAttrib)
	{
        USES_CONVERSION;

		TCHAR path [MAX_PATH];
		_tcscpy_s(path, pwszPath);
		if (_tcslen(path)<4)
			return S_FALSE;

		if (lastKnownState->isConflicted(W2CT(pwszPath)))
				return S_OK;
			else
				return S_FALSE;
	}