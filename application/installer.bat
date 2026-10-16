@echo off
rem INSTALLATION AUTOMATIQUE — Windows : installe Python si besoin, installe ou met a jour, cree un raccourci sur le Bureau, demarre.
rem   installer.bat          installation neuve ; si une installation existe deja ici : MISE A JOUR sans perte
rem   installer.bat --maj    mise a jour explicite
cd /d "%~dp0"
set PY=
where python >nul 2>nul && set PY=python
if "%PY%"=="" where py >nul 2>nul && set PY=py
if "%PY%"=="" (
  echo ==^> Python est introuvable : tentative d'installation automatique
  where winget >nul 2>nul && winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
  echo.
  echo Python vient d'etre installe : FERMEZ cette fenetre puis relancez installer.bat pour continuer.
  echo Si l'installation a echoue, installez Python 3 depuis https://www.python.org/downloads/ en cochant "Add Python to PATH".
  pause & exit /b 1
)
echo ==^> Installation des dependances
%PY% -m pip install -q -r backend\requirements.txt
%PY% -c "import flask, jwt" 2>nul || ( echo ERREUR : modules Python manquants. Verifiez Internet puis relancez INSTALLER.bat & pause & exit /b 1 )
set MODE=%1
if "%MODE%"=="" if exist backend\data\morgue.db ( set MODE=--maj & echo ==^> Installation existante detectee : mise a jour sans perte de donnees )
cd backend
if "%MODE%"=="--maj" ( %PY% -c "import db; db.init_db(); print('Base migree / a jour.')" ) else ( %PY% install.py %* )
if errorlevel 1 ( cd .. & pause & exit /b 1 )
cd ..
rem Raccourci sur le Bureau
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\PEGINTI Morgue.lnk'); $s.TargetPath='%~dp0demarrer.bat'; $s.WorkingDirectory='%~dp0'; $s.Save()" >nul 2>nul
echo.
echo Installation terminee. Un raccourci "PEGINTI Morgue" est sur le Bureau (double-clic pour demarrer).
if not "%MODE%"=="--maj" (
  echo Premiere connexion : identifiant admin  -  mot de passe provisoire Admin123!  ^(changement obligatoire^)
  echo Double authentification exigee : installez Google/Microsoft Authenticator, Aegis ou FreeOTP sur le telephone avant de vous connecter.
)
start "PEGINTI Morgue" "%~dp0demarrer.bat"
timeout /t 4 >nul
start http://localhost:3001
pause
