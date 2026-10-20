Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Resolve the project root from this script's own location.
root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
python = fso.BuildPath(root, ".venv\Scripts\python.exe")
appDir = fso.BuildPath(root, "src")

cmd = "cmd /c cd /d """ & appDir & """ && """ & python & """ -m flask --app ""udp.app:create_app()"" run --host 127.0.0.1 --port 8765 --no-reload"
WshShell.Run cmd, 0, False
