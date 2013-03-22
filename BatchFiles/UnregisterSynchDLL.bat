@echo off
regsvr32 /u /s %1\bin\CpoIconOverlaySynced.dll
regsvr32 /u /s %1\bin\CpoIconOverlayInProgress.dll
regsvr32 /u /s %1\bin\CpoIconOverlayConflicted.dll
EXIT

