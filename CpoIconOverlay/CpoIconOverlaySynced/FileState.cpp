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
	//urlReader.parse();
	time(&cacheResetTimer);
}

void FileState::isValidCache()
{
	bool isValid = urlReader.getConnState();
	if(!isValid){//no connection clear chace
		clearCache();
		return;
	}

	time_t currTime;
	time(&currTime);
	double diff;
	diff = difftime(currTime, cacheResetTimer);
	if(diff > 0.5){
		clearCache();
		time(&cacheResetTimer);
	}

}

/// <summary>
/// Determines whether the specified path is synchronized.
/// </summary>
/// <param name="path">The path for which to determine the synchronization.</param>
/// <return>
/// True is path is synchronized, False otherwise.
/// </return>
bool FileState::isSynchronized(LPCTSTR path)
{
	isValidCache();
	
	TCHAR file[MAX_PATH];
	_tcscpy(file, path);
	urlPathEncode(file);
	
	if(myFileSyncMap.find(file) != myFileSyncMap.end()){
		if(myFileSyncMap.find(file)->second){
			return true; //file is synced
		}else{
			return false; //file is in map but not synced -- this currently isn't used
		}
	}else{ //file does not exist in map, perform a query and update map for this specific folder
		TCHAR * fileFolder = getFileFolder(file);
		bool isValidFolder = isValidCloudFolder(fileFolder);
		if(isValidFolder){
			//query new folder params
			urlReader.parseSubFolder(fileFolder);
			if(myFileSyncMap.find(file) != myFileSyncMap.end()){
				delete fileFolder;
				fileFolder = NULL;
				return true;
			}
		}
		delete fileFolder;
		fileFolder = NULL;
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
	TCHAR * userPath = urlReader.getUserRootPath();
	urlPathEncode(userPath);
	TCHAR * sub = _tcsstr(folder, userPath);
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
