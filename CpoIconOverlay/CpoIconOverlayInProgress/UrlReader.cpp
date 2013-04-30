// UrlReaderConsole.cpp : Defines the entry point for the console application.
//
#include "UrlReader.h"
#include "stdafx.h"
#include <iostream>

UrlReader::UrlReader()
{
}

UrlReader::UrlReader(LPCTSTR inputPath, syncMap * map)
{
	// assume valid connection, check during query
	isValidConn = true;

	//add Cloud Desk folder to path
	queryForUserRoot();
	_tcscpy(currentParentFolder, userPath);

	this->fileStateSyncedMap = map;
}

//initial startup parse of user path
void UrlReader::parse()
{
	//create URL params with folder
	TCHAR urlParams[MAX_PATH + 50] = TEXT("?state=progress&folder=");
	StringCchCat(urlParams, MAX_PATH, userPath);
	performParse(urlParams);
}

void UrlReader::parseSubFolder(TCHAR * subFolder){
	TCHAR urlParams[MAX_PATH + 50] = TEXT("?state=progress&folder=");
	StringCchCat(urlParams, MAX_PATH, subFolder);
	performParse(urlParams);
	updateParentFolder(subFolder);
}

void UrlReader::performParse(TCHAR * urlParams){
	char* jsonStringToParse = getJsonStringFromServer(urlParams, false);
	if(isValidConn){
		json_settings settings;
		memset(&settings, 0, sizeof (json_settings)); 
		char error[256];
		json_value * val = json_parse_ex(&settings, jsonStringToParse, error);
		UrlReader::parseJsonValue(val);
	}
}

void longPullThread(void * params){
	struct paramStruct * threadParams = (struct paramStruct *)params;
	struct paramStruct localParam;

	_tcscpy(localParam.filePath, threadParams->filePath);
	_tcscpy(localParam.folderPath, threadParams->folderPath);
	localParam.urlReader = threadParams->urlReader;

	TCHAR urlParams[MAX_PATH + 50] = TEXT("?state=progress&transition=true&folder=");
	StringCchCat(urlParams, MAX_PATH, localParam.filePath);

	Sleep(5000);
	if(_tcscmp(localParam.filePath, _T("")) != 0){
		char * returnVal = localParam.urlReader->getJsonStringFromServer(urlParams, true);

		TCHAR findChar = '/';
		TCHAR replaceChar = '\\';

		int i = 0;
		while(localParam.filePath[i] != '\0'){
			if((int)localParam.filePath[i] == (int)findChar){
				localParam.filePath[i] = replaceChar;
			}
			i++;
		}
		//TCHAR urlParams2[MAX_PATH + 50] = TEXT("?debug=");
		//StringCchCat(urlParams2, MAX_PATH, localParam.filePath);

		//LPCVOID absPath = localParam.filePath;
		//SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST | SHCNF_FLUSHNOWAIT, NULL, NULL);
		SHChangeNotify(SHCNE_UPDATEITEM, SHCNF_PATH | SHCNF_FLUSH, localParam.filePath, NULL);
		//localParam.urlReader->getJsonStringFromServer(urlParams2, true);
		//MessageBox(NULL, threadParams->filePath, L"Prev Param", MB_OK);
		//MessageBox(NULL, localParam.filePath, L"Local", MB_OK);
		//delete threadParams;
	}
}

void UrlReader::longPull(TCHAR * filePath){
	struct paramStruct ps;
 	_tcscpy(ps.filePath, filePath);
	TCHAR * temp = getFileFolder(filePath);

	_tcscpy(ps.folderPath, temp);
	//delete temp;
	//temp = NULL;
	ps.urlReader = this;

	//begin thread with longPull
	_beginthread(longPullThread, 0, (void *)&ps);
	
	//refresh parent icon
	//updateParentFolder(temp);
}

void UrlReader::updateParentFolder(TCHAR * input){
	if(_tcscmp(input, currentParentFolder) != 0){
		//put into refresh parent function
		TCHAR parentFolder[MAX_PATH];
		_tcscpy(parentFolder, input);
		TCHAR findChar = '/';
		TCHAR replaceChar = '\\';
		int i = 0;
		while(parentFolder[i] != '\0'){
			if((int)parentFolder[i] == (int)findChar){
				parentFolder[i] = replaceChar;
			}
			i++;
		}

		_tcscpy(currentParentFolder, parentFolder);
		SHChangeNotify(SHCNE_UPDATEITEM, SHCNF_PATH | SHCNF_FLUSH, parentFolder, NULL);
	}
	
}

void UrlReader::queryForUserRoot(){
	if(isValidConn){
		TCHAR * rootFolderQuery = TEXT("/rootfolder");
		char * rootPath = getJsonStringFromServer(rootFolderQuery, false);
		if(rootPath){
			json_settings settings;
			memset(&settings, 0, sizeof (json_settings)); 
			char error[256];
			json_value * jsonRootPath = json_parse_ex(&settings, rootPath, error);
			char * path = jsonRootPath->u.object.values->value->u.string.ptr;

			MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, userPath, MAX_PATH);
		}	
	}
}

TCHAR * UrlReader::getUserRootPath(){
	return userPath;
}

bool UrlReader::getConnState(){
	return isValidConn;
}

void UrlReader::parseJsonValue(json_value *val){
		 
		 if(val == 0) {
			printf("error parsing");
		} else {
			
			if(val->type == json_object) {
				for (unsigned int i = 0; i < val->u.object.length; i++) {
					char* currName = val->u.object.values[i].name;
					json_value * folderVal = val->u.object.values[i].value;

					if(!strcmp(currName, "folder")){
						json_value * valFolderName = folderVal->u.object.values[1].value;
						
						char * folderName = valFolderName->u.string.ptr;
						mbstowcs(currDir, folderName, strlen(folderName));
						currDir[strlen(folderName)] = '\0';
					}
					parseJsonValue(val->u.object.values[i].value);
				}
			} else if (val->type == json_array) {
				for (unsigned int j = 0; j < val->u.array.length; j++) {
					int len = val->u.array.length;
					_json_value *foldersArray = val->u.array.values[j];
					
					char* currName = val->u.array.values[j]->u.string.ptr;
					if(!strcmp(val->parent->u.object.values[0].name, "files")) {
						const size_t nameSize = strlen(currName) + 1;

						wchar_t * wc = new wchar_t[nameSize];
						mbstowcs(wc, currName, nameSize);

						TCHAR filePath[MAX_PATH];
						_tcscpy(filePath, currDir);

						StringCchCat(filePath, MAX_PATH, TEXT("/"));
						StringCchCat(filePath, MAX_PATH, wc);

						size_t len = _tcslen(filePath) + 2;
						TCHAR filePathPtr [MAX_PATH];
						_tcscpy(filePathPtr, filePath);
						urlPathEncode(filePathPtr);

						fileStateSyncedMap->insert( std::pair<std::wstring, bool>(std::wstring(filePathPtr), true) );
						longPull(filePathPtr);

						delete wc;
						wc = NULL;
					}
					parseJsonValue(val->u.array.values[j]);
				}
			}
		}
	 }

char* UrlReader::getJsonStringFromServer(const wchar_t* request, bool isThread) {

	DWORD dwSize = 0;
	DWORD dwDownloaded = 0;
	LPSTR pszOutBuffer;
	BOOL  bResults = FALSE;
	HINTERNET  hSession = NULL, 
				hConnect = NULL,
				hRequest = NULL;

	// Use WinHttpOpen to obtain a session handle.
	hSession = WinHttpOpen( L"WinHTTP - OverlayInProgress",  
							WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
							WINHTTP_NO_PROXY_NAME, 
							WINHTTP_NO_PROXY_BYPASS, 0);

	//uses 127.0.0.1 instead of localhost as Win7 has problems using localhost
	if (hSession)
		WinHttpSetTimeouts( hSession, 5000, 5000, 5000, 5000);
		hConnect = WinHttpConnect( hSession, L"127.0.0.1",
										63111, 0);

	// Create an HTTP request handle.
	if (hConnect)
		hRequest = WinHttpOpenRequest( hConnect, L"GET", request,
										NULL, WINHTTP_NO_REFERER, 
										WINHTTP_DEFAULT_ACCEPT_TYPES, 
										0);

	// Send a request.
	if (hRequest)
		bResults = WinHttpSendRequest( hRequest,
										WINHTTP_NO_ADDITIONAL_HEADERS,
										0, WINHTTP_NO_REQUEST_DATA, 0, 
										0, 0);

	// End the request.
	if (bResults)
		bResults = WinHttpReceiveResponse( hRequest, NULL);

	// Keep checking for data until there is nothing left.
	if (bResults)
		do 
		{
			// Check for available data.
			dwSize = 0;
			if (!WinHttpQueryDataAvailable( hRequest, &dwSize))
				printf("Error %u in WinHttpQueryDataAvailable.\n", GetLastError());

			// Allocate space for the buffer.
			pszOutBuffer = new char[dwSize+1];
			if (!pszOutBuffer)
			{
				printf("Out of memory\n");
				dwSize=0;
			}
			else
			{
				// Read the Data.
					ZeroMemory(pszOutBuffer, dwSize+1);
				if (!WinHttpReadData( hRequest, (LPVOID)pszOutBuffer, 
										dwSize, &dwDownloaded))
					printf( "Error %u in WinHttpReadData.\n", GetLastError());
				else {
					if(dwSize == 0) {
					} else {
						if(!isThread){
							isValidConn = true; //we have data and good connection
						}
						return pszOutBuffer;
					}
				}
				// Free the memory allocated to the buffer.
				delete [] pszOutBuffer;
			}

		} while (dwSize > 0);
		
	// Report any errors.
	if (!bResults){
		printf("Error %d has occurred.\n", GetLastError());
		if(!isThread){
			isValidConn = false; //no connection
		}
	}

	// Close any open handles.
	if (hRequest) WinHttpCloseHandle(hRequest);
	if (hConnect) WinHttpCloseHandle(hConnect);
	if (hSession) WinHttpCloseHandle(hSession);
	char * non = '\0';
	return non;
}

void UrlReader::urlPathEncode(TCHAR * path){
	TCHAR findChar = '\\';
	TCHAR replaceChar = '/';

	int i = 0;
	while(path[i] != '\0'){
		if((int)path[i] == (int)findChar){
			path[i] = replaceChar;
		}
		i++;
	}
}

TCHAR * UrlReader::getFileFolder(TCHAR * path){
	//extracts folder path from a file name
	TCHAR file[MAX_PATH];
	_tcscpy(file, path);
	urlPathEncode(file);

	TCHAR findChar = '/';

	int i = 0;
	int lastOccurance = 0;
	while(file[i] != '\0'){
		if((int)file[i] == (int)findChar){
			lastOccurance = i;
		}
		i++;
	}

	file[lastOccurance] = '\0';

	TCHAR * folder = new TCHAR[lastOccurance+1];
	_tcscpy(folder, file);
	return folder;
}

UrlReader::~UrlReader(void)
{
	//TODO
}

