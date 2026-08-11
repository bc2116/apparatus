#ifndef SourceRoot
  #error SourceRoot must point at installer/windows
#endif

#ifndef OutputDir
  #error OutputDir must name the installer output directory
#endif

#ifndef Version
  #error Version must name the Apparatus package version
#endif

#define BootstrapPath AddBackslash(SourceRoot) + "bootstrap-apparatus.ps1"
#define BootstrapHash GetSHA256OfFile(BootstrapPath)

[Setup]
AppId=ApparatusBootstrap
AppName=Apparatus
AppPublisher=Apparatus contributors
AppVersion={#Version}
DefaultDirName={tmp}\Apparatus
CreateAppDir=no
CreateUninstallRegKey=no
Uninstallable=no
PrivilegesRequired=lowest
; PrivilegesRequiredOverridesAllowed keeps its blank default: no overrides.
OutputDir={#OutputDir}
OutputBaseFilename=apparatus-installer
Compression=lzma2/max
SolidCompression=yes
SetupLogging=no
DisableProgramGroupPage=yes
DisableReadyPage=yes
DisableFinishedPage=yes
DisableWelcomePage=yes
DisableStartupPrompt=yes
AllowCancelDuringInstall=no
RestartIfNeededByRun=no
CloseApplications=no
UsePreviousAppDir=no
UsePreviousGroup=no
UsePreviousLanguage=no
UsePreviousPrivileges=no
UsePreviousSetupType=no
UsePreviousTasks=no
UsePreviousUserInfo=no

[Files]
Source: "{#BootstrapPath}"; DestName: "bootstrap-apparatus.ps1"; Flags: dontcopy noencryption; Hash: "{#BootstrapHash}"

[Code]
var
  ParsedBootstrapArguments: String;
  BootstrapExitCode: Integer;
  BootstrapOutput: String;

function StartsWith(const Value, Prefix: String): Boolean;
begin
  Result := CompareText(Copy(Value, 1, Length(Prefix)), Prefix) = 0;
end;

function IsAllowedSetupArgument(const Argument: String): Boolean;
begin
  Result :=
    (CompareText(Argument, '/SP-') = 0) or
    (CompareText(Argument, '/SILENT') = 0) or
    (CompareText(Argument, '/VERYSILENT') = 0) or
    (CompareText(Argument, '/SUPPRESSMSGBOXES') = 0) or
    (CompareText(Argument, '/NOCANCEL') = 0) or
    (CompareText(Argument, '/NORESTART') = 0) or
    (CompareText(Argument, '/LOG') = 0) or
    StartsWith(Argument, '/LOG=') or
    StartsWith(Argument, '/LANG=');
end;

function InitializeSetup(): Boolean;
var
  Argument: String;
  DryRunSeen, WorkspacePathSeen: Boolean;
  I: Integer;
  WorkspacePath: String;
begin
  Result := False;
  ParsedBootstrapArguments := '';
  BootstrapExitCode := 0;
  BootstrapOutput := '';
  DryRunSeen := False;
  WorkspacePathSeen := False;

  for I := 1 to ParamCount do
  begin
    Argument := ParamStr(I);
    if CompareText(Argument, '/DRYRUN') = 0 then
    begin
      if DryRunSeen then
      begin
        SuppressibleMsgBox('The dry-run option may be supplied only once.', mbError, MB_OK, IDOK);
        Exit;
      end;
      DryRunSeen := True;
      if ParsedBootstrapArguments <> '' then
        ParsedBootstrapArguments := ParsedBootstrapArguments + ' ';
      ParsedBootstrapArguments := ParsedBootstrapArguments + '-DryRun';
    end
    else if StartsWith(Argument, '/WORKSPACEPATH=') then
    begin
      if WorkspacePathSeen then
      begin
        SuppressibleMsgBox('The workspace location may be supplied only once.', mbError, MB_OK, IDOK);
        Exit;
      end;
      WorkspacePathSeen := True;
      WorkspacePath := Copy(Argument, Length('/WORKSPACEPATH=') + 1, MaxInt);
      if WorkspacePath = '' then
      begin
        SuppressibleMsgBox('The workspace location must not be empty.', mbError, MB_OK, IDOK);
        Exit;
      end;
      if (Pos('"', WorkspacePath) <> 0) or (Pos(#10, WorkspacePath) <> 0) or
         (Pos(#13, WorkspacePath) <> 0) then
      begin
        SuppressibleMsgBox('The workspace location contains an unsupported character.', mbError, MB_OK, IDOK);
        Exit;
      end;
      if ParsedBootstrapArguments <> '' then
        ParsedBootstrapArguments := ParsedBootstrapArguments + ' ';
      ParsedBootstrapArguments := ParsedBootstrapArguments + '-Path "' + WorkspacePath + '"';
    end
    else if not IsAllowedSetupArgument(Argument) then
    begin
      SuppressibleMsgBox('Unsupported installer option: ' + Argument, mbError, MB_OK, IDOK);
      Exit;
    end;
  end;
  Result := True;
end;

procedure LogBootstrapOutput(const S: String; const Error, FirstLine: Boolean);
begin
  if FirstLine then
    Log('Bootstrap output:');
  Log(S);
  if Length(BootstrapOutput) < 8192 then
    BootstrapOutput := BootstrapOutput + S + #13#10;
end;

procedure DeleteBootstrap();
begin
  DeleteFile(ExpandConstant('{tmp}\bootstrap-apparatus.ps1'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ExtractedPath: String;
  Launched: Boolean;
  PowerShellPath, PowerShellParameters: String;
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
  begin
    ExtractTemporaryFile('bootstrap-apparatus.ps1');
    ExtractedPath := ExpandConstant('{tmp}\bootstrap-apparatus.ps1');
    if CompareText(GetSHA256OfFile(ExtractedPath), '{#BootstrapHash}') <> 0 then
      RaiseException('The embedded bootstrap script failed its integrity check.');
    Log('Embedded bootstrap SHA-256 verified.');
  end
  else if CurStep = ssPostInstall then
  begin
    ExtractedPath := ExpandConstant('{tmp}\bootstrap-apparatus.ps1');
    PowerShellPath := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
    PowerShellParameters := '-NoProfile -ExecutionPolicy Bypass -File "' +
      ExtractedPath + '" ' + ParsedBootstrapArguments;
    try
      Launched := ExecAndLogOutput(
        PowerShellPath,
        PowerShellParameters,
        ExpandConstant('{tmp}'),
        SW_SHOWNORMAL,
        ewWaitUntilTerminated,
        ResultCode,
        @LogBootstrapOutput
      );
      if not Launched then
        RaiseException('The embedded bootstrap script could not be started.');
      BootstrapExitCode := ResultCode;
      if ResultCode <> 0 then
        SuppressibleMsgBox(
          'Apparatus setup stopped:' + #13#10 + #13#10 +
          Trim(BootstrapOutput) + #13#10 + #13#10 +
          'Re-running is safe. See installer/README.md for help.',
          mbError,
          MB_OK,
          IDOK
        );
    finally
      DeleteBootstrap();
    end;
  end;
end;

function GetCustomSetupExitCode(): Integer;
begin
  Result := BootstrapExitCode;
end;
