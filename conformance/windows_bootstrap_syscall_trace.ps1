#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $BootstrapScript
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Stop-TraceProof([string] $Message) {
    throw "BLOCKED-STOP: $Message"
}

if ($env:OS -ne "Windows_NT") {
    Stop-TraceProof "the Windows syscall proof requires Windows."
}

$BootstrapScript = [IO.Path]::GetFullPath($BootstrapScript)
if (-not [IO.File]::Exists($BootstrapScript)) {
    Stop-TraceProof "the bootstrap script was not found."
}

$SystemRoot = [Environment]::GetEnvironmentVariable("SystemRoot", "Machine")
if ([string]::IsNullOrWhiteSpace($SystemRoot)) {
    Stop-TraceProof "the trusted Windows system root is unavailable."
}
$PowerShell = Join-Path $SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$Wpr = Join-Path $SystemRoot "System32\wpr.exe"
$Tracerpt = Join-Path $SystemRoot "System32\tracerpt.exe"
$Logman = Join-Path $SystemRoot "System32\logman.exe"
foreach ($Tool in @($PowerShell, $Wpr, $Tracerpt, $Logman)) {
    if (-not [IO.File]::Exists($Tool)) {
        Stop-TraceProof "a required built-in Windows trace tool is unavailable: $([IO.Path]::GetFileName($Tool))."
    }
}

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;

public sealed class ApparatusSuspendedProcess : IDisposable
{
    const UInt32 CREATE_SUSPENDED = 0x00000004;
    const UInt32 CREATE_UNICODE_ENVIRONMENT = 0x00000400;
    const UInt32 CREATE_NO_WINDOW = 0x08000000;
    const UInt32 JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008;
    const UInt32 JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;
    const UInt32 WAIT_OBJECT_0 = 0x00000000;
    const UInt32 WAIT_TIMEOUT = 0x00000102;
    const Int32 JobObjectExtendedLimitInformation = 9;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct STARTUPINFO
    {
        public UInt32 cb;
        public string lpReserved;
        public string lpDesktop;
        public string lpTitle;
        public UInt32 dwX;
        public UInt32 dwY;
        public UInt32 dwXSize;
        public UInt32 dwYSize;
        public UInt32 dwXCountChars;
        public UInt32 dwYCountChars;
        public UInt32 dwFillAttribute;
        public UInt32 dwFlags;
        public UInt16 wShowWindow;
        public UInt16 cbReserved2;
        public IntPtr lpReserved2;
        public IntPtr hStdInput;
        public IntPtr hStdOutput;
        public IntPtr hStdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct PROCESS_INFORMATION
    {
        public IntPtr hProcess;
        public IntPtr hThread;
        public UInt32 dwProcessId;
        public UInt32 dwThreadId;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct JOBOBJECT_BASIC_LIMIT_INFORMATION
    {
        public Int64 PerProcessUserTimeLimit;
        public Int64 PerJobUserTimeLimit;
        public UInt32 LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public UInt32 ActiveProcessLimit;
        public IntPtr Affinity;
        public UInt32 PriorityClass;
        public UInt32 SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct IO_COUNTERS
    {
        public UInt64 ReadOperationCount;
        public UInt64 WriteOperationCount;
        public UInt64 OtherOperationCount;
        public UInt64 ReadTransferCount;
        public UInt64 WriteTransferCount;
        public UInt64 OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
        public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryUsed;
        public UIntPtr PeakJobMemoryUsed;
    }

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern bool CreateProcessW(
        string applicationName,
        StringBuilder commandLine,
        IntPtr processAttributes,
        IntPtr threadAttributes,
        bool inheritHandles,
        UInt32 creationFlags,
        IntPtr environment,
        string currentDirectory,
        ref STARTUPINFO startupInfo,
        out PROCESS_INFORMATION processInformation);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern IntPtr CreateJobObjectW(IntPtr attributes, string name);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetInformationJobObject(
        IntPtr job,
        Int32 informationClass,
        IntPtr information,
        UInt32 informationLength);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern UInt32 ResumeThread(IntPtr thread);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern UInt32 WaitForSingleObject(IntPtr handle, UInt32 milliseconds);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool GetExitCodeProcess(IntPtr process, out UInt32 exitCode);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool CloseHandle(IntPtr handle);

    IntPtr process = IntPtr.Zero;
    IntPtr thread = IntPtr.Zero;
    IntPtr job = IntPtr.Zero;
    public UInt32 ProcessId { get; private set; }

    ApparatusSuspendedProcess() { }

    static void ThrowLastError(string operation)
    {
        throw new Win32Exception(Marshal.GetLastWin32Error(), operation);
    }

    static IntPtr EnvironmentBlock(IDictionary<string, string> values)
    {
        List<string> entries = new List<string>();
        foreach (KeyValuePair<string, string> pair in values)
        {
            if (pair.Key.IndexOf('\0') >= 0 || pair.Value.IndexOf('\0') >= 0)
                throw new ArgumentException("Environment values may not contain NUL.");
            entries.Add(pair.Key + "=" + pair.Value);
        }
        entries.Sort(StringComparer.OrdinalIgnoreCase);
        string block = String.Join("\0", entries.ToArray()) + "\0\0";
        return Marshal.StringToHGlobalUni(block);
    }

    public static ApparatusSuspendedProcess Start(
        string application,
        string commandLine,
        string currentDirectory,
        IDictionary<string, string> environment)
    {
        ApparatusSuspendedProcess result = new ApparatusSuspendedProcess();
        IntPtr environmentBlock = IntPtr.Zero;
        IntPtr informationBuffer = IntPtr.Zero;
        PROCESS_INFORMATION processInformation = new PROCESS_INFORMATION();
        try
        {
            result.job = CreateJobObjectW(IntPtr.Zero, null);
            if (result.job == IntPtr.Zero) ThrowLastError("CreateJobObjectW failed");

            JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits =
                new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
            limits.BasicLimitInformation.LimitFlags =
                JOB_OBJECT_LIMIT_ACTIVE_PROCESS | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            limits.BasicLimitInformation.ActiveProcessLimit = 1;
            int informationSize = Marshal.SizeOf(limits);
            informationBuffer = Marshal.AllocHGlobal(informationSize);
            Marshal.StructureToPtr(limits, informationBuffer, false);
            if (!SetInformationJobObject(
                    result.job,
                    JobObjectExtendedLimitInformation,
                    informationBuffer,
                    (UInt32)informationSize))
                ThrowLastError("SetInformationJobObject failed");

            environmentBlock = EnvironmentBlock(environment);
            STARTUPINFO startupInfo = new STARTUPINFO();
            startupInfo.cb = (UInt32)Marshal.SizeOf(startupInfo);
            if (!CreateProcessW(
                    application,
                    new StringBuilder(commandLine),
                    IntPtr.Zero,
                    IntPtr.Zero,
                    false,
                    CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW,
                    environmentBlock,
                    currentDirectory,
                    ref startupInfo,
                    out processInformation))
                ThrowLastError("CreateProcessW failed");

            result.process = processInformation.hProcess;
            result.thread = processInformation.hThread;
            result.ProcessId = processInformation.dwProcessId;
            processInformation.hProcess = IntPtr.Zero;
            processInformation.hThread = IntPtr.Zero;
            if (!AssignProcessToJobObject(result.job, result.process))
                ThrowLastError("AssignProcessToJobObject failed");
            return result;
        }
        catch
        {
            if (processInformation.hThread != IntPtr.Zero)
                CloseHandle(processInformation.hThread);
            if (processInformation.hProcess != IntPtr.Zero)
                CloseHandle(processInformation.hProcess);
            result.Dispose();
            throw;
        }
        finally
        {
            if (environmentBlock != IntPtr.Zero) Marshal.FreeHGlobal(environmentBlock);
            if (informationBuffer != IntPtr.Zero) Marshal.FreeHGlobal(informationBuffer);
        }
    }

    public void Resume()
    {
        if (ResumeThread(thread) == UInt32.MaxValue) ThrowLastError("ResumeThread failed");
    }

    public UInt32 Wait(Int32 milliseconds)
    {
        UInt32 wait = WaitForSingleObject(process, (UInt32)milliseconds);
        if (wait == WAIT_TIMEOUT) throw new TimeoutException("traced process timed out");
        if (wait != WAIT_OBJECT_0) ThrowLastError("WaitForSingleObject failed");
        UInt32 exitCode;
        if (!GetExitCodeProcess(process, out exitCode))
            ThrowLastError("GetExitCodeProcess failed");
        return exitCode;
    }

    public void Dispose()
    {
        if (thread != IntPtr.Zero) { CloseHandle(thread); thread = IntPtr.Zero; }
        if (process != IntPtr.Zero) { CloseHandle(process); process = IntPtr.Zero; }
        // KILL_ON_JOB_CLOSE contains any process that survived a failed trace.
        if (job != IntPtr.Zero) { CloseHandle(job); job = IntPtr.Zero; }
    }
}
'@

function ConvertTo-CommandLine([string[]] $Arguments) {
    $Quoted = foreach ($Argument in $Arguments) {
        if ($Argument.Contains('"')) {
            Stop-TraceProof "a trace argument contains an unsupported quote."
        }
        '"' + $Argument + '"'
    }
    return $Quoted -join " "
}

function Get-SessionSnapshot {
    $Output = @(& $Logman query -ets 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Stop-TraceProof "built-in ETW session enumeration failed."
    }
    return ($Output | ForEach-Object { ([string] $_).TrimEnd() }) -join "`n"
}

function Get-WprStatus {
    $Output = @(& $Wpr -status 2>&1)
    # WPR uses a nonzero status when no recording is active on some builds.
    return ($Output | ForEach-Object { ([string] $_).TrimEnd() }) -join "`n"
}

function Invoke-BuiltIn([string] $Tool, [string[]] $Arguments, [string] $Failure) {
    $Output = @(& $Tool @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Stop-TraceProof "$Failure Exit $LASTEXITCODE. $($Output -join ' ')"
    }
    return $Output
}

function Get-TraceEvents(
    [string] $XmlPath,
    [uint32] $ProcessId,
    [DateTime] $StartedUtc,
    [DateTime] $FinishedUtc
) {
    try {
        [xml] $Document = [IO.File]::ReadAllText($XmlPath)
    } catch {
        Stop-TraceProof "tracerpt output could not be parsed as XML."
    }
    $Matched = [Collections.Generic.List[object]]::new()
    foreach ($Event in @($Document.SelectNodes("//*[local-name()='Event']"))) {
        $System = $Event.System
        if ($null -eq $System) { continue }
        $TimestampText = [string] $System.TimeCreated.SystemTime
        $Timestamp = [DateTime]::MinValue
        if (-not [DateTime]::TryParse(
                $TimestampText,
                [Globalization.CultureInfo]::InvariantCulture,
                [Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal,
                [ref] $Timestamp)) {
            continue
        }
        if ($Timestamp -lt $StartedUtc -or $Timestamp -gt $FinishedUtc) { continue }

        $Fields = [Collections.Generic.List[string]]::new()
        $PidCandidates = [Collections.Generic.List[string]]::new()
        foreach ($Data in @($Event.EventData.Data)) {
            $Fields.Add("$([string] $Data.Name)=$([string] $Data.'#text')")
            if (([string] $Data.Name) -match '^(?i:processid|process_id|pid)$') {
                $PidCandidates.Add([string] $Data.'#text')
            }
        }
        $ExecutionPid = [string] $System.Execution.ProcessID
        if (-not [string]::IsNullOrWhiteSpace($ExecutionPid)) {
            $PidCandidates.Add($ExecutionPid)
        }
        $AllText = @(
            [string] $System.Provider.Name,
            [string] $System.Task,
            [string] $System.Opcode,
            [string] $System.EventID,
            $ExecutionPid,
            ($Fields -join " "),
            [string] $Event.OuterXml
        ) -join " "
        $PidMatches = $false
        foreach ($CandidatePid in $PidCandidates) {
            $ParsedPid = [uint32] 0
            $CandidatePid = $CandidatePid.Trim()
            if ($CandidatePid.StartsWith("0x", [StringComparison]::OrdinalIgnoreCase)) {
                $Parsed = [uint32]::TryParse(
                    $CandidatePid.Substring(2),
                    [Globalization.NumberStyles]::HexNumber,
                    [Globalization.CultureInfo]::InvariantCulture,
                    [ref] $ParsedPid
                )
            } else {
                $Parsed = [uint32]::TryParse($CandidatePid, [ref] $ParsedPid)
            }
            if ($Parsed -and $ParsedPid -eq $ProcessId) {
                $PidMatches = $true
                break
            }
        }
        if (-not $PidMatches) { continue }

        $IsFileEvent = $AllText -match '(?i)(fileio|file[_ ]?(?:name|key|object))'
        $FileWriteLike = $AllText -match '(?i)(file(?:write|delete|rename|set(?:information|info|security|ea|basic|metadata))|>(?:write|delete|rename|setinformation|setinfo|setsecurity|setea|setbasic|setmetadata)<)'
        # Kernel FileIO "Create" means open-or-create. Only creation-capable
        # dispositions are mutations; FILE_OPEN (1) remains a read-only open.
        $FileCreateLike = (
            $AllText -match '(?i)(filecreate|>create<)' -and
            $AllText -match '(?i)CreateDisposition(?:[^0-9A-F]+)(?:(?:0x)?(?:0|2|3|4|5)|Create|OpenIf|Overwrite|OverwriteIf|Supersede)(?:[^0-9A-F]|$)'
        )
        $FileMutation = $IsFileEvent -and ($FileWriteLike -or $FileCreateLike)
        $RegistryMutation = (
            $AllText -match '(?i)(registry|kernel-registry|reg(?:create|set|delete|rename))' -and
            $AllText -match '(?i)(reg(?:create|set|delete|rename|setsecurity)|>(?:create|setvalue|delete|rename|setsecurity)<)'
        )
        $Network = $AllText -match '(?i)(tcpip|udpip|network)'
        $Matched.Add([PSCustomObject] @{
            Time = $Timestamp.ToString("o")
            Text = $AllText
            File = $FileMutation
            Registry = $RegistryMutation
            Network = $Network
        })
    }
    return @($Matched)
}

$ControllerRoot = Join-Path ([IO.Path]::GetTempPath()) ("apparatus-wpr-" + [Guid]::NewGuid().ToString("N"))
$ProfilePath = Join-Path $ControllerRoot "apparatus-bootstrap.wprp"
$ProfileHome = Join-Path $ControllerRoot "profile"
$Target = Join-Path $ProfileHome "Projects\Apparatus"
$Working = Join-Path $ControllerRoot "working"
$RegistryCanary = "Software\ApparatusWprCanary-" + [Guid]::NewGuid().ToString("N")
$FileCanary = Join-Path $ControllerRoot "file-canary.txt"
$SessionBefore = $null
$WprBefore = $null
$ActiveTrace = $false
$TraceProcess = $null
$FailureMessage = $null

try {
    [IO.Directory]::CreateDirectory($ProfileHome) > $null
    [IO.Directory]::CreateDirectory($Working) > $null
    $ProfileXml = @'
<?xml version="1.0" encoding="utf-8"?>
<WindowsPerformanceRecorder Version="1.0" Author="Apparatus" Copyright="Apparatus" Company="Apparatus">
  <Profiles>
    <SystemCollector Id="ApparatusSystemCollector" Name="NT Kernel Logger">
      <BufferSize Value="1024" />
      <Buffers Value="64" />
    </SystemCollector>
    <SystemProvider Id="ApparatusSystemProvider">
      <Keywords>
        <Keyword Value="ProcessThread" Strict="true" />
        <Keyword Value="FileIO" Strict="true" />
        <Keyword Value="FileIOInit" Strict="true" />
        <Keyword Value="Registry" Strict="true" />
        <Keyword Value="NetworkTrace" Strict="true" />
      </Keywords>
    </SystemProvider>
    <Profile Id="ApparatusBootstrap.Verbose.File" Name="ApparatusBootstrap" Description="Bootstrap dry-run syscall proof" LoggingMode="File" DetailLevel="Verbose">
      <Collectors>
        <SystemCollectorId Value="ApparatusSystemCollector">
          <SystemProviderId Value="ApparatusSystemProvider" />
        </SystemCollectorId>
      </Collectors>
    </Profile>
  </Profiles>
</WindowsPerformanceRecorder>
'@
    [IO.File]::WriteAllText($ProfilePath, $ProfileXml, [Text.UTF8Encoding]::new($false))

    $SessionBefore = Get-SessionSnapshot
    $WprBefore = Get-WprStatus
    if ($WprBefore -match '(?i)recording is in progress') {
        Stop-TraceProof "a WPR recording was already active; the proof will not disturb it."
    }
    if ($WprBefore -notmatch '(?i)(not recording|recording is not in progress|no trace profiles running)') {
        Stop-TraceProof "the existing WPR state could not be classified safely."
    }

    $ColdEnvironment = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::OrdinalIgnoreCase)
    $ColdEnvironment["APPDATA"] = Join-Path $ProfileHome "AppData\Roaming"
    $ColdEnvironment["COMSPEC"] = Join-Path $SystemRoot "System32\cmd.exe"
    $ColdEnvironment["HOME"] = $ProfileHome
    $ColdEnvironment["HOMEDRIVE"] = [IO.Path]::GetPathRoot($ProfileHome).TrimEnd('\')
    $ColdEnvironment["HOMEPATH"] = $ProfileHome.Substring([IO.Path]::GetPathRoot($ProfileHome).Length - 1)
    $ColdEnvironment["LOCALAPPDATA"] = Join-Path $ProfileHome "AppData\Local"
    $ColdEnvironment["OS"] = "Windows_NT"
    $ColdEnvironment["PATH"] = @(
        (Join-Path $SystemRoot "System32"),
        $SystemRoot,
        (Join-Path $SystemRoot "System32\WindowsPowerShell\v1.0")
    ) -join ";"
    $ColdEnvironment["PATHEXT"] = ".COM;.EXE;.BAT;.CMD"
    $ColdEnvironment["SYSTEMDRIVE"] = [IO.Path]::GetPathRoot($SystemRoot).TrimEnd('\')
    $ColdEnvironment["SYSTEMROOT"] = $SystemRoot
    $ColdEnvironment["TEMP"] = $ControllerRoot
    $ColdEnvironment["TMP"] = $ControllerRoot
    $ColdEnvironment["USERPROFILE"] = $ProfileHome
    $ColdEnvironment["WINDIR"] = $SystemRoot

    function Invoke-OneTrace([string] $Name, [string[]] $Arguments) {
        $EtlPath = Join-Path $ControllerRoot ($Name + ".etl")
        $XmlPath = Join-Path $ControllerRoot ($Name + ".xml")
        $SummaryPath = Join-Path $ControllerRoot ($Name + "-summary.xml")
        $CommandLine = ConvertTo-CommandLine @($PowerShell) + " " + (ConvertTo-CommandLine $Arguments)
        $TraceProcess = [ApparatusSuspendedProcess]::Start(
            $PowerShell,
            $CommandLine,
            $Working,
            $ColdEnvironment
        )
        try {
            # No WPR recording existed at entry. Mark cleanup-owned before the
            # start call so a partially initialized provider set is cancelled.
            $script:ActiveTrace = $true
            $null = Invoke-BuiltIn $Wpr @(
                "-start", ($ProfilePath + "!ApparatusBootstrap.Verbose"),
                "-filemode", "-recordtempto", $ControllerRoot
            ) "WPR could not start the required kernel providers."
            $Started = [DateTime]::UtcNow
            $TraceProcess.Resume()
            $ExitCode = $TraceProcess.Wait(30000)
            $Finished = [DateTime]::UtcNow
            if ($ExitCode -ne 0) {
                Stop-TraceProof "$Name exited $ExitCode under the cold trace environment."
            }
            $null = Invoke-BuiltIn $Wpr @("-stop", $EtlPath) "WPR could not stop and save the kernel trace."
            $script:ActiveTrace = $false
            $null = Invoke-BuiltIn $Tracerpt @($EtlPath, "-o", $XmlPath, "-summary", $SummaryPath, "-of", "XML", "-y") "tracerpt could not decode the kernel trace."
            return @(Get-TraceEvents $XmlPath $TraceProcess.ProcessId $Started $Finished)
        } finally {
            if ($script:ActiveTrace) {
                & $Wpr -cancel 2>&1 > $null
                $script:ActiveTrace = $false
            }
            if ($null -ne $TraceProcess) {
                $TraceProcess.Dispose()
                $TraceProcess = $null
            }
        }
    }

    $DryArguments = @(
        "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", $BootstrapScript, "-DryRun", "-Path", $Target
    )
    $DryEvents = @(Invoke-OneTrace "dry-run" $DryArguments)
    $DryMutations = @($DryEvents | Where-Object { $_.File -or $_.Registry -or $_.Network })
    if ($DryMutations.Count -ne 0) {
        $Evidence = ($DryMutations | Select-Object -First 8 | ForEach-Object { $_.Text }) -join " || "
        Stop-TraceProof "the bootstrap dry-run issued a file, registry, TCP, or UDP mutation. $Evidence"
    }
    if ([IO.Directory]::Exists($Target) -or [IO.File]::Exists($Target)) {
        Stop-TraceProof "the dry-run created its workspace target."
    }

    $ColdEnvironment["APPARATUS_TRACE_FILE"] = $FileCanary
    $FileEvents = @(Invoke-OneTrace "file-canary" @(
        "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-Command", "[IO.File]::WriteAllText(`$env:APPARATUS_TRACE_FILE, 'canary')"
    ))
    if (@($FileEvents | Where-Object { $_.File }).Count -eq 0) {
        Stop-TraceProof "the FileIO/FileIOInit providers did not observe the file canary."
    }

    $ColdEnvironment["APPARATUS_TRACE_REGISTRY"] = $RegistryCanary
    $RegistryEvents = @(Invoke-OneTrace "registry-canary" @(
        "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-Command", "`$k=[Microsoft.Win32.Registry]::CurrentUser.CreateSubKey(`$env:APPARATUS_TRACE_REGISTRY); try { `$k.SetValue('Value','canary') } finally { `$k.Dispose() }"
    ))
    if (@($RegistryEvents | Where-Object { $_.Registry }).Count -eq 0) {
        Stop-TraceProof "the Registry provider did not observe the registry canary."
    }

    $NetworkEvents = @(Invoke-OneTrace "network-canary" @(
        "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-Command", "`$c=[Net.Sockets.TcpClient]::new(); try { try { `$c.Connect('127.0.0.1',9) } catch {} } finally { `$c.Dispose() }"
    ))
    if (@($NetworkEvents | Where-Object { $_.Network }).Count -eq 0) {
        Stop-TraceProof "the Network provider did not observe the TCP canary."
    }

    Write-Output "Windows dry-run syscall proof passed: no file, registry, TCP, or UDP mutation was observed."
} catch {
    $FailureMessage = $_.Exception.Message
} finally {
    if ($ActiveTrace) {
        & $Wpr -cancel 2>&1 > $null
        $ActiveTrace = $false
    }
    if ($null -ne $TraceProcess) {
        $TraceProcess.Dispose()
        $TraceProcess = $null
    }
    try {
        [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($RegistryCanary, $false)
    } catch {}
    $RemainingRegistryKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($RegistryCanary, $false)
    if ($null -ne $RemainingRegistryKey) {
        $RemainingRegistryKey.Dispose()
        $FailureMessage = "BLOCKED-STOP: the registry canary survived cleanup."
    }
    try {
        if ([IO.Directory]::Exists($ControllerRoot)) {
            [IO.Directory]::Delete($ControllerRoot, $true)
        }
    } catch {
        $FailureMessage = "BLOCKED-STOP: trace artifacts could not be removed. $($_.Exception.Message)"
    }
    if ([IO.Directory]::Exists($ControllerRoot)) {
        $FailureMessage = "BLOCKED-STOP: trace artifacts survived cleanup."
    }
    if ($null -ne $SessionBefore) {
        try {
            $SessionAfter = Get-SessionSnapshot
            $WprAfter = Get-WprStatus
            if ($SessionAfter -ne $SessionBefore -or $WprAfter -ne $WprBefore) {
                $FailureMessage = "BLOCKED-STOP: ETW/WPR sessions were not restored exactly."
            }
        } catch {
            $FailureMessage = $_.Exception.Message
        }
    }
}

if ($null -ne $FailureMessage) {
    [Console]::Error.WriteLine($FailureMessage)
    exit 1
}
