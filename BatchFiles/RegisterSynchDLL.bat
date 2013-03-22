@echo off
regsvr32 /s %1\bin\CpoIconOverlaySynced.dll
regsvr32 /s %1\bin\CpoIconOverlayInProgress.dll
regsvr32 /s %1\bin\CpoIconOverlayConflicted.dll

