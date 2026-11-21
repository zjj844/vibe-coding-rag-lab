@echo off
REM React prebuild (ASCII only: cmd.exe reads .cmd with the OEM codepage)
REM
REM Three flags matter:
REM   --jsx=automatic : use the React 17+ JSX runtime (react/jsx-runtime).
REM                     Without it esbuild emits React.createElement(...), but our
REM                     components never `import React` -> "React is not defined"
REM                     -> blank page. This was the actual black-screen bug.
REM   --format=iife   : classic script, so a plain <script src> works.
REM   --define ...    : the \" escapes are required. cmd.exe strips plain quotes,
REM                     which makes esbuild define an IDENTIFIER named production
REM                     instead of the STRING "production" (React stays in dev mode,
REM                     and `if (production === "production")` would throw).
cd /d "%~dp0"
node_modules\@esbuild\win32-x64\esbuild.exe src\main.jsx --bundle --format=iife --jsx=automatic --outfile=dist\app.js --loader:.jsx=jsx --define:process.env.NODE_ENV=\"production\" --minify --log-level=warning
if errorlevel 1 exit /b 1
echo [build] dist\app.js generated
