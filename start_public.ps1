# SuiXing 公网访问启动脚本 (PowerShell)
# 使用 ngrok 创建公网隧道，让评委通过外网访问本地 Demo

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  随行 SuiXing - 公网 Demo 启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查 ngrok
$ngrok = Get-Command ngrok -ErrorAction SilentlyContinue
if (-not $ngrok) {
    Write-Host "[!] 未检测到 ngrok，正在下载..." -ForegroundColor Yellow
    Write-Host "    也可以手动下载: https://ngrok.com/download" -ForegroundColor Yellow
    Write-Host "    下载后放到项目根目录，然后重新运行本脚本" -ForegroundColor Yellow
    Write-Host ""

    # 尝试用 winget 安装
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        winget install ngrok
    } else {
        Write-Host "    请手动安装 ngrok 后重试" -ForegroundColor Red
        Write-Host "    下载地址: https://ngrok.com/download" -ForegroundColor Yellow
        pause
        exit 1
    }
}

# 2. 检查 .env
if (-not (Test-Path ".env")) {
    Write-Host "[!] 未找到 .env 文件，正在从 .env.example 创建..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "[!] 请编辑 .env 文件，填入 DeepSeek API Key" -ForegroundColor Red
    notepad .env
    pause
}

# 3. 启动 Server (后台)
Write-Host ""
Write-Host "[1/2] 启动 SuiXing Server (端口 8010)..." -ForegroundColor Green
$serverJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    python app.py 2>&1 | Out-Null
}
Write-Host "      Server 启动中... (Job ID: $($serverJob.Id))" -ForegroundColor Gray

# 等待 server 就绪
Write-Host "      等待 Server 就绪..." -ForegroundColor Gray
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8010/api/health" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $ready) {
    Write-Host "[X] Server 启动失败，请手动检查" -ForegroundColor Red
    Receive-Job -Job $serverJob
    pause
    exit 1
}
Write-Host "      Server 就绪!" -ForegroundColor Green

# 4. 启动 ngrok
Write-Host ""
Write-Host "[2/2] 启动 ngrok 公网隧道..." -ForegroundColor Green
Write-Host ""

# 尝试后台运行 ngrok
try {
    $ngrokProcess = Start-Process -FilePath "ngrok" -ArgumentList "http 8010 --log=stdout" -NoNewWindow -PassThru -RedirectStandardOutput "ngrok_output.txt"
    Start-Sleep -Seconds 3

    # 获取公网 URL
    $ngrokUrl = $null
    for ($i = 0; $i -lt 10; $i++) {
        try {
            $apiResponse = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -UseBasicParsing -TimeoutSec 2
            $ngrokUrl = $apiResponse.tunnels[0].public_url
            if ($ngrokUrl) { break }
        } catch {
            Start-Sleep -Seconds 2
        }
    }

    if ($ngrokUrl) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "  公网访问地址 (评委用):" -ForegroundColor Green
        Write-Host "  $ngrokUrl" -ForegroundColor Yellow
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "  按 Ctrl+C 停止所有服务" -ForegroundColor Gray
        Write-Host ""
    } else {
        Write-Host "[!] ngrok 已启动，请在另一个终端查看 URL:" -ForegroundColor Yellow
        Write-Host "    ngrok http 8010" -ForegroundColor Yellow
        Write-Host "    或访问 http://127.0.0.1:4040 查看隧道状态" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[!] ngrok 启动失败，请手动运行:" -ForegroundColor Yellow
    Write-Host "    ngrok http 8010" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  本地访问: http://localhost:8010" -ForegroundColor Gray
Write-Host "  API 健康检查: http://localhost:8010/api/health" -ForegroundColor Gray

# 等待用户中断
try {
    while ($true) { Start-Sleep -Seconds 1 }
} finally {
    Write-Host ""
    Write-Host "正在停止服务..." -ForegroundColor Yellow
    Stop-Job -Job $serverJob -ErrorAction SilentlyContinue
    Remove-Job -Job $serverJob -ErrorAction SilentlyContinue
    if ($ngrokProcess) { Stop-Process -Id $ngrokProcess.Id -ErrorAction SilentlyContinue }
    Write-Host "已停止" -ForegroundColor Gray
}
