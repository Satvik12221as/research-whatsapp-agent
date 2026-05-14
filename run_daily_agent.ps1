$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $ProjectDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$LogFile = Join-Path $LogDir ("task-run-" + (Get-Date -Format "yyyy-MM-dd") + ".log")
$PythonCandidates = @(
    (Join-Path $ProjectDir ".venv\Scripts\python.exe"),
    "python",
    "py",
    (Join-Path $ProjectDir "myenv\Scripts\python.exe")
)

$Python = $null
foreach ($Candidate in $PythonCandidates) {
    try {
        if ($Candidate -eq "python" -or $Candidate -eq "py") {
            $Command = Get-Command $Candidate -ErrorAction Stop
            $Python = $Command.Source
        }
        elseif (Test-Path $Candidate) {
            $Python = $Candidate
        }

        if ($Python) {
            if ((Split-Path -Leaf $Python) -eq "py.exe") {
                & $Python -3 --version *> $null
            }
            else {
                & $Python --version *> $null
            }

            if ($LASTEXITCODE -eq 0) {
                if ((Split-Path -Leaf $Python) -eq "py.exe") {
                    & $Python -3 -c "import feedparser, requests" *> $null
                }
                else {
                    & $Python -c "import feedparser, requests" *> $null
                }
            }

            if ($LASTEXITCODE -eq 0) {
                break
            }

            $Python = $null
        }
    }
    catch {
        $Python = $null
    }
}

if (-not $Python) {
    throw "Python was not found. Create .venv or install Python before running the daily agent."
}

Set-Location $ProjectDir

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Starting daily agent with $Python" | Tee-Object -FilePath $LogFile -Append

if ((Split-Path -Leaf $Python) -eq "py.exe") {
    & $Python -3 daily_agent.py 2>&1 | Tee-Object -FilePath $LogFile -Append
}
else {
    & $Python daily_agent.py 2>&1 | Tee-Object -FilePath $LogFile -Append
}

$ExitCode = $LASTEXITCODE
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Daily agent exited with code $ExitCode" | Tee-Object -FilePath $LogFile -Append
exit $ExitCode


# completed