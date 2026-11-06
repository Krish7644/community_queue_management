$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& '.\.venv\Scripts\python.exe' '.\backend\manage.py' runserver 127.0.0.1:8000
