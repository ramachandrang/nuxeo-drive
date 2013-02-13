#include "./easySQLite/Sqlite3.h"

/// <summary>
/// Class FileState. Caches the SQLite database handler and a prepared statement.
/// Provides <cref>isSynchronized</cref> method to return the "synchronized" status of the input path.
/// </summary>
class FileState
{
private:
    static const char* szSql;
    static const char* szSql1;
    static const char* szSql2;
    static const char* szSql3;

    TCHAR           db_path[MAX_PATH];
    TCHAR           tchRoot[MAX_PATH];
    bool            invalidDb;
    sqlite3*        pDb;
    sqlite3_stmt*   pStmt;
    sqlite3_stmt*   pStmt1;
    sqlite3_stmt*   pStmt2;
    sqlite3_stmt*   pStmt3;

    bool isValidDb();
    void initDb();

public:
    FileState(LPCTSTR db_path);
    ~FileState(void);

    bool isSynchronized(LPCTSTR path);
    bool isOthersDocsSynchronized();
};

