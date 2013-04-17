#include "StdAfx.h"

#include "FileState.h"

#define NULL_TERMINATED  -1
#define MAX_RETRIES 3
#define OTHERS_DOCS _T("Others Docs")


//constructor
FileState::FileState(LPCTSTR userPath)
{
	TCHAR path[MAX_PATH];
	_tcscpy(path, userPath);
	urlPathEncode(path);

	urlReader = UrlReader::UrlReader(path, &myFileSyncMap);
	urlReader.parse();
	time(&cacheResetTimer);
}

void FileState::isValidCache()
{
	isValidConn = urlReader.getConnState();
	if(!isValidConn){//no connection clear chace
		clearCache();
		return;
	}

	time_t currTime;
	time(&currTime);
	double diff;
	diff = difftime(currTime, cacheResetTimer);
	if(diff > 0.3){
		clearCache();
		time(&cacheResetTimer);
	}

}

bool FileState::inProgress(LPCTSTR path)
{
	isValidCache();
	//clearCache();
	
	TCHAR file[MAX_PATH];
	_tcscpy(file, path);
	urlPathEncode(file);

	//MessageBox(NULL, path, L"File Path InProgress", MB_OK);
	printf("FilePath = %s", path);
	TCHAR * tempPtr = new TCHAR[MAX_PATH];
	_tcscpy(tempPtr, file);
	bool isValidFolder = false;
	
	if(myFileSyncMap.find(file) != myFileSyncMap.end()){
		if(myFileSyncMap.find(file)->second){
			urlReader.longPull(tempPtr);
			//MessageBox(NULL, path, L"return true", MB_OK);
			return true; //file is synced
		}else{
			//MessageBox(NULL, path, L"return false", MB_OK);
			return false; //file is in map but not synced -- this currently isn't used
		}
	}else{ //file does not exist in map, perform a query and update map for this specific folder
		TCHAR * fileFolder = getFileFolder(file);
		isValidFolder = isValidCloudFolder(fileFolder);
		if(isValidFolder){
			//query new folder params
			urlReader.parseSubFolder(fileFolder);
			if(myFileSyncMap.find(file) != myFileSyncMap.end()){
				urlReader.longPull(tempPtr);
				delete fileFolder;
				fileFolder = NULL;
				//MessageBox(NULL, path, L"return true after query", MB_OK);
				//urlReader.longPull(file);
				return true;
			}
		}
		delete fileFolder;
		fileFolder = NULL;
		if(isValidFolder && isValidConn){
			//MessageBox(NULL, path, L"return false after everything", MB_OK);
			//SHChangeNotify(SHCNE_UPDATEITEM, SHCNF_PATH | SHCNF_FLUSHNOWAIT, path, NULL);
			urlReader.longPull(tempPtr);
			return true;
		}
		return false;
	}
}

void FileState::clearCache(){//clears map to reset cache
	syncMap::iterator it = myFileSyncMap.begin();
	syncMap::iterator temp;
	while(it!=myFileSyncMap.end()){
		temp = it;
		++it;
		myFileSyncMap.erase(temp);
	}
	myFileSyncMap.clear();
}

bool FileState::isValidCloudFolder(TCHAR * folder){
	TCHAR * sub = _tcsstr(folder, TEXT("Cloud Portal Office"));
	if(sub == NULL){
		return false;
	}else{
		return true;
	}
}

void FileState::urlPathEncode(TCHAR * path){
	TCHAR findChar = '\\';
	TCHAR replaceChar = '/';

	int i = 0;
	while(path[i] != '\0'){
		if((int)path[i] == (int)findChar){
			path[i] = replaceChar;
		}
		++i;
	}
}

TCHAR * FileState::getFileFolder(TCHAR * path){
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

//deconstructor
FileState::~FileState(void)
{

}
