@echo off
rem Synchronisation de la discothèque avec ce baladeur.
rem À poser à la racine du dossier de musique du baladeur (ex. <lecteur>:\Music).
rem Le lanceur cherche la discothèque sur les lecteurs montés : un dossier de premier
rem niveau qui contient « _bot\config.toml ». Les lettres de lecteur peuvent donc varier.
rem Options transmises telles quelles : --simulation, ou « restaurer --confirmer » à la place de synchro.
chcp 65001 >nul
setlocal EnableExtensions

set "DAP=%~dp0"
set "DAP=%DAP:~0,-1%"
set "RACINE="
for %%d in (C D E F G H I J K L M N O P Q R S T U V W X Y Z) do (
  if not defined RACINE if exist "%%d:\" (
    for /d %%r in ("%%d:\*") do (
      if not defined RACINE if exist "%%r\_bot\config.toml" set "RACINE=%%r"
    )
  )
)

if not defined RACINE (
  echo Discotheque introuvable : aucun dossier contenant _bot\config.toml sur les lecteurs.
  pause
  exit /b 1
)

set "SENS=synchro"
if /i "%~1"=="restaurer" (
  set "SENS=restaurer"
  shift
)

echo Discotheque : %RACINE%
echo Baladeur    : %DAP%
echo.
"%RACINE%\_bot\.venv\Scripts\disco.exe" --config "%RACINE%\_bot\config.toml" dap %SENS% --dap "%DAP%" %1 %2 %3
echo.
pause
