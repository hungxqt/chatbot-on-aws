@echo off
setlocal enabledelayedexpansion

set ENV_FILE=.env
set PREFIX=/webapp-group10/backend
set REGION=us-east-1
set TYPE=SecureString
set PROFILE=workshop

for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (

    rem Skip comments and empty lines
    if not "%%A"=="" (
        set "FIRSTCHAR=%%A"
        if not "!FIRSTCHAR:~0,1!"=="#" (

            set "KEY=%%A"
            set "VALUE=%%B"

            rem Remove surrounding quotes
            set "VALUE=!VALUE:"=!"
            set "VALUE=!VALUE:'=!"

            echo Uploading !KEY! to %PREFIX%/!KEY! using profile %PROFILE% ...

            aws ssm put-parameter ^
              --name "%PREFIX%/!KEY!" ^
              --value "!VALUE!" ^
              --type "%TYPE%" ^
              --overwrite ^
              --region "%REGION%" ^
              --profile "%PROFILE%"
        )
    )
)

echo Done.
pause