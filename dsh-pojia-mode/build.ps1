# 生成 SHA256SUMS.txt（供下载者校验），并重打包
$ErrorActionPreference = 'Stop'
$src  = $PSScriptRoot
$dist = Join-Path $src 'dist'
$zip  = Join-Path $dist 'dsh-pojia-mode.zip'

New-Item -ItemType Directory -Path $dist -Force | Out-Null
Remove-Item $zip -Force -ErrorAction SilentlyContinue

$files = @(
    'unlock-dsh-silent.vbs',
    'unlock-dsh.bat',
    'unlock-dsh.ps1',
    'README.md',
    'LICENSE',
    'assets\agent.cordis.yml.tmpl',
    'assets\preset.yml.tmpl'
)

Write-Host '[*] 编码门禁检查' -ForegroundColor Cyan

# ps1 必须带 UTF-8 BOM（PS 5.1 靠 BOM 判编码，无 BOM 会按 GBK 读 -> 假语法错）
$b = [System.IO.File]::ReadAllBytes((Join-Path $src 'unlock-dsh.ps1'))
if (-not ($b[0] -eq 239 -and $b[1] -eq 187 -and $b[2] -eq 191)) {
    throw 'unlock-dsh.ps1 缺少 UTF-8 BOM —— PowerShell 5.1 会读成 GBK 导致语法错误'
}
Write-Host '  [OK] unlock-dsh.ps1 = UTF-8 with BOM' -ForegroundColor Green

# bat 必须纯 ASCII（cmd.exe 按 OEM 代码页解析）
$bb = [System.IO.File]::ReadAllBytes((Join-Path $src 'unlock-dsh.bat'))
$n  = ($bb | Where-Object { $_ -gt 127 }).Count
if ($n -ne 0) { throw "unlock-dsh.bat 含 $n 个非 ASCII 字节 —— cmd.exe 会撕裂解析" }
Write-Host '  [OK] unlock-dsh.bat = 纯 ASCII' -ForegroundColor Green

# vbs 必须是 ANSI/GBK，绝不能是 UTF-8 BOM（脚本宿主会报「语句未结束」）
$vb = [System.IO.File]::ReadAllBytes((Join-Path $src 'unlock-dsh-silent.vbs'))
if ($vb[0] -eq 239 -and $vb[1] -eq 187 -and $vb[2] -eq 191) {
    throw 'unlock-dsh-silent.vbs 是 UTF-8 BOM —— 脚本宿主会报「语句未结束」，必须存 GBK'
}
Write-Host '  [OK] unlock-dsh-silent.vbs = ANSI/GBK' -ForegroundColor Green

# 模板必须无 BOM（DSH 的 YAML 加载器要求）
foreach ($t in @('assets\agent.cordis.yml.tmpl', 'assets\preset.yml.tmpl')) {
    $tb = [System.IO.File]::ReadAllBytes((Join-Path $src $t))
    if ($tb[0] -eq 239 -and $tb[1] -eq 187 -and $tb[2] -eq 191) {
        throw "$t 带 BOM —— DSH 的 YAML 加载器会解析失败"
    }
    Write-Host "  [OK] $t = UTF-8 无 BOM" -ForegroundColor Green
}

# --- 打包 ---
$tmp = Join-Path $env:TEMP ('dspm-pkg-' + (Get-Random))
New-Item -ItemType Directory -Path (Join-Path $tmp 'assets') -Force | Out-Null
foreach ($f in $files) { Copy-Item (Join-Path $src $f) (Join-Path $tmp $f) -Force }
Compress-Archive -Path (Join-Path $tmp '*') -DestinationPath $zip -Force
Remove-Item $tmp -Recurse -Force

# --- SHA256SUMS.txt ---
$lines = @()
foreach ($f in $files) {
    $p = Join-Path $src $f
    $h = (Get-FileHash $p -Algorithm SHA256).Hash.ToLower()
    $lines += "$h  $($f -replace '\\','/')"
}
$sumPath = Join-Path $src 'SHA256SUMS.txt'
[System.IO.File]::WriteAllLines($sumPath, $lines, (New-Object System.Text.UTF8Encoding($false)))

# --- 核对 ---
Add-Type -AssemblyName System.IO.Compression.FileSystem
$z = [System.IO.Compression.ZipFile]::OpenRead($zip)
Write-Host ''
Write-Host ('[*] ' + $zip + '  (' + (Get-Item $zip).Length + ' bytes)') -ForegroundColor Cyan
foreach ($e in $z.Entries) { Write-Host ('  ' + $e.FullName + '  (' + $e.Length + ' B)') }
$z.Dispose()
Write-Host ''
Write-Host ('[*] SHA256SUMS.txt  (' + $lines.Count + ' 行)') -ForegroundColor Cyan
$lines | ForEach-Object { Write-Host ('  ' + $_) }
Write-Host ''
Write-Host '[OK] 打包完成' -ForegroundColor Green
