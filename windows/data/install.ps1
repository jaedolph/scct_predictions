$ErrorActionPreference = "Stop"


Write-Output "Installing SCCT Predictions..."

New-Item -Path ".\build" -ItemType "directory" -Force

Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.12.4/python-3.12.4-embed-amd64.zip -OutFile .\build\python.zip
Expand-Archive -LiteralPath .\build\python.zip -DestinationPath .\data\python\ -Force

Copy-Item .\data\python312._pth .\data\python\python312._pth

Invoke-WebRequest -Uri https://bootstrap.pypa.io/get-pip.py -OutFile .\build\get-pip.py
.\data\python\python.exe .\build\get-pip.py --no-warn-script-location

.\data\python\python.exe -m pip install .\data\scct_predictions-0.2.1-py3-none-any.whl --no-warn-script-location

Remove-Item -LiteralPath ".\build" -Force -Recurse

Write-Output "Finished installation. You can close this window now."
