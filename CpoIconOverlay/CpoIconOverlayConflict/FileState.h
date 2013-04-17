#include "UrlReader.h"
#include <stdlib.h>
#include <time.h>
#include <map>
#include <time.h>
#include <atlbase.h>
#include <atlconv.h>

/// <summary>
/// Class FileState. Caches the SQLite database handler and a prepared statement.
/// Provides <cref>isSynchronized</cref> method to return the "synchronized" status of the input path.
/// </summary>

class FileState
{
private:

	syncMap myFileSyncMap;
	time_t cacheResetTimer;

    void isValidCache();
    void initDb();

	UrlReader urlReader;

public:
    FileState(LPCTSTR path);
    ~FileState(void);

    bool isConflicted(LPCTSTR path);
	void urlPathEncode(TCHAR * path);
	TCHAR * getFileFolder(TCHAR * path);
	void clearCache();
	bool isValidCloudFolder(TCHAR * folder);
};

