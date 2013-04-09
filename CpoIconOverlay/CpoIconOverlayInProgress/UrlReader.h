#include "StdAfx.h"
#include "json.h"
#include "stdio.h"

#include <windows.h>
#include <winhttp.h>
#pragma comment(lib,"winhttp.lib")

#include <map>
#include <string>
#include <strsafe.h>

#ifndef URLREADER_H
#define URLREADER_H

typedef std::map<std::wstring, bool> syncMap;



class UrlReader
{
private:
	TCHAR * userPath;
	syncMap * fileStateSyncedMap;
	bool isValidConn;
	TCHAR currDir[MAX_PATH];

public:
	UrlReader::UrlReader();
	UrlReader::UrlReader(LPCTSTR inputPath, syncMap * map);
	void UrlReader::parse();
	void UrlReader::parseSubFolder(TCHAR * subFolder);
	void UrlReader::performParse(TCHAR * urlParams);
	void UrlReader::longPull(TCHAR * filePath);
	bool UrlReader::getConnState();
	void UrlReader::parseJsonValue(json_value *val);
	char* UrlReader::getJsonStringFromServer(const wchar_t* request, bool isThread);
	void UrlReader::urlPathEncode(TCHAR * path);
	TCHAR * UrlReader::getFileFolder(TCHAR * filePath);
	TCHAR * UrlReader::getUserRootPath();
	UrlReader::~UrlReader(void);
};
struct paramStruct {
	TCHAR filePath[MAX_PATH];
	TCHAR folderPath[MAX_PATH];
	UrlReader * urlReader;
};

#endif