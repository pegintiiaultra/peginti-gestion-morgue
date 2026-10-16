@echo off
rem DEMARRAGE — demarrer.bat (poste seul)   |   demarrer.bat reseau (reseau d'entreprise)
cd /d "%~dp0backend"
set PY=python
where python >nul 2>nul || set PY=py
set MORGUE_HOST=127.0.0.1
if "%1"=="reseau" ( set MORGUE_HOST=0.0.0.0 & echo Reseau local : les autres appareils ouvrent http://ADRESSE-IP-DE-CE-PC:3001 & echo ^(adresse IP : commande ipconfig^) )
set MORGUE_PORT=3001
%PY% app.py
pause
