#include "StdAfx.h"
#include "FileState.h"

#define NULL_TERMINATED  -1
#define MAX_RETRIES 3
#define OTHERS_DOCS _T("Others Docs")


const char* FileState::szSql = "select lks.local_root, lks.path, lks.local_name, lks.local_state, lks.pair_state" 
                    " from last_known_states as lks"
                    " where lks.local_name=?";

const char* FileState::szSql1 = "select local_root from root_bindings";

const char* FileState::szSql2 = "select lks.local_root, lks.path" 
            " from last_known_states as lks"
            " where lks.local_root=? and lks.folderish=1";

const char* FileState::szSql3 = "select local_folder from server_bindings";


FileState::FileState(LPCTSTR path)
{
    pDb = NULL;
    invalidDb = true;
    _tcscpy(db_path, path);
    initDb();
}

bool FileState::isValidDb()
{
    return !invalidDb;
}

void FileState::initDb()
{
    if (isValidDb())
        return;

    USES_CONVERSION;
    int result;

    if (sqlite3_open_v2(T2CA(db_path), &pDb, SQLITE_OPEN_READONLY | SQLITE_OPEN_FULLMUTEX, NULL) == SQLITE_OK)
    {
        if ((result = sqlite3_prepare_v2(pDb, szSql, NULL_TERMINATED, &pStmt, NULL)) != SQLITE_OK)
        {
            printf("error preparing SQL statement: %d (%s)", result, sqlite3_errmsg(pDb));
            return;
        }

        if ((result = sqlite3_prepare_v2(pDb, szSql1, NULL_TERMINATED, &pStmt1, NULL)) != SQLITE_OK)
        {
            printf("error preparing SQL statement: %d (%s)", result, sqlite3_errmsg(pDb));
            return;
        }

        if ((result = sqlite3_prepare_v2(pDb, szSql2, NULL_TERMINATED, &pStmt2, NULL)) != SQLITE_OK)
        {
            printf("error preparing SQL statement: %d (%s)", result, sqlite3_errmsg(pDb));
            return;
        }

        if ((result = sqlite3_prepare_v2(pDb, szSql3, NULL_TERMINATED, &pStmt3, NULL)) == SQLITE_OK)
        {
            if ((result = sqlite3_step(pStmt3)) == SQLITE_ROW)
            {
                const char* local_folder = reinterpret_cast<const char *>(sqlite3_column_text(pStmt3, 0));
                _tcscpy(tchRoot, A2CT(local_folder));
            }
        }
        else
        {
            printf("error preparing SQL statement: %d (%s)", result, sqlite3_errmsg(pDb));
            return;
        }

    } else {
        if (pDb == NULL)
        {
            printf("memory error opening the SQLite database.");
            return;
        }
        else
        {
            printf("error opening database 'nxdrive.db': %s", sqlite3_errmsg(pDb)); 
            return;
        }
    }

    invalidDb = false;
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
    USES_CONVERSION;
    TCHAR base[MAX_PATH];
    TCHAR file[MAX_PATH];

    initDb();
    if (!isValidDb())
        return false;

    __try
    {
        _tcscpy(base, path);
        PTSTR fn = PathFindFileName(base);
        if (fn == base)
        {
            // no file found
            file[0] = TCHAR('\0');
        }
        else
        {
            _tcscpy(file, fn);
           PathRemoveFileSpec(base);
        }

        // check whether it is the "Others Docs" folder as this is not a proper sync root.
        TCHAR othersPath[MAX_PATH];
        PathCombine(othersPath, tchRoot, OTHERS_DOCS);
        if (_tcsicmp(path, othersPath) == 0)
        {
            // check whether any of its subfolders is NOT synchronized
            return isOthersDocsSynchronized();
        }

        sqlite3_bind_text(pStmt, 1, T2A(file), NULL_TERMINATED, SQLITE_STATIC);

        int retries = 0, result;
        while (retries < MAX_RETRIES)
        {
            while ((result = sqlite3_step(pStmt)) == SQLITE_ROW)
            {
                const char* local_root = reinterpret_cast<const char *>(sqlite3_column_text(pStmt, 0));
                const char* local_path = reinterpret_cast<const char *>(sqlite3_column_text(pStmt, 1));
                const char* local_state = reinterpret_cast<const char *>(sqlite3_column_text(pStmt, 3));
                const char* pair_state = reinterpret_cast<const char *>(sqlite3_column_text(pStmt, 4));

                if (*local_path == '/')
                    local_path += 1;
                char* pch = strchr(const_cast<char*>(local_path), '/');
                while (pch != NULL)
                {
                    *pch = '\\';
                    pch = strchr(pch, '/');
                }
                TCHAR path2[MAX_PATH] = _T("");
                PathCombine(path2, A2CT(local_root), A2CT(local_path));
                if (_tcsicmp(path, path2) != 0)
                    continue;
                if (_stricmp(local_state, "synchronized") == 0)
                    return true;
                else
                    return false;
            }
            if (result == SQLITE_BUSY)
            {
                retries++;
            }
            else if (result == SQLITE_DONE)
            {
                return false;
            }
            else 
            {
                //printf("error preparing SQL statement: %d (%s)", result, sqlite3_errmsg(pDb));
                return false;
            }
        }
        return false;
    } __finally
    {
        sqlite3_reset(pStmt);
        sqlite3_clear_bindings(pStmt);
    }
}

bool FileState::isOthersDocsSynchronized()
{
    initDb();
    if (!isValidDb())
        return false;

    // check whether it is the "Others Docs" folder as this is not a proper sync root.
    TCHAR othersPath[MAX_PATH];
    PathCombine(othersPath, tchRoot, OTHERS_DOCS);

    // check whether any of its subfolders is NOT synchronized
    int result;
    USES_CONVERSION;
    while ((result = sqlite3_step(pStmt1)) == SQLITE_ROW)
    {
        const char* local_root = reinterpret_cast<const char *>(sqlite3_column_text(pStmt1, 0));
        if (strstr(local_root, T2CA(othersPath)) != NULL)
        {
            // this is a root binding under the "Others Docs"; check if synchronized
            sqlite3_bind_text(pStmt2, 1, local_root, NULL_TERMINATED, SQLITE_STATIC);
            if ((result = sqlite3_step(pStmt2)) == SQLITE_DONE)
            {
                // one binding root is not synchronized -> Others Docs is not synchronized
                return false;
            }
        }
        sqlite3_reset(pStmt2);
        sqlite3_clear_bindings(pStmt2);
    }
    // all roots under Others Docs are synchronized
    return true;
}

FileState::~FileState(void)
{
    if (isValidDb())
    {
        sqlite3_finalize(pStmt);
        sqlite3_finalize(pStmt1);
        sqlite3_finalize(pStmt2);
    }
    sqlite3_close(pDb);
    pDb = NULL;
}
