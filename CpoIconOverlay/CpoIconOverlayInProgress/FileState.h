#include "UrlReader.h"
#include <stdlib.h>
#include <time.h>
#include <map>
#include <time.h>
#include <atlbase.h>
#include <atlconv.h>

class FileState
{
private:

	syncMap myFileSyncMap;
	time_t cacheResetTimer;
	bool isValidConn;

    void isValidCache();
    void initDb();

	UrlReader urlReader;

public:
    FileState(LPCTSTR path);
    ~FileState(void);

    bool inProgress(LPCTSTR path);
	void urlPathEncode(TCHAR * path);
	TCHAR * getFileFolder(TCHAR * path);
	void clearCache();
	bool isValidCloudFolder(TCHAR * folder);
};

