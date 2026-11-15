Option Explicit

Dim fso, scriptDir, projectDir, lockPath
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
projectDir = fso.GetParentFolderName(scriptDir)
lockPath = fso.BuildPath(projectDir, "digital_signage.lock")

If fso.FileExists(lockPath) Then
    fso.DeleteFile lockPath, True
End If
