$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$credentialReader = @'
import json
from pathlib import Path
import MySQLdb, MySQLdb.cursors
from dotenv import dotenv_values
c=dotenv_values('backend/.env')
d=MySQLdb.connect(host='127.0.0.1',user=c['DB_USER'],passwd=c['DB_PASSWORD'],db='community_scanner_legacy',charset='utf8mb4',cursorclass=MySQLdb.cursors.DictCursor)
roles=[('admin','admins',""),('hod','authorities'," AND account_type='HOD' AND COALESCE(profile_type,'')<>'BRAHMACHARI' AND EXISTS(SELECT 1 FROM hod_passes WHERE hod_id=authorities.id)"),('congregation','authorities'," AND account_type='CONGREGATION'"),('brahmachari','authorities'," AND profile_type='BRAHMACHARI'"),('scanner','scanners',''),('volunteer','volunteers','')]
result=[]
with d.cursor() as q:
 for role,table,extra in roles:
  q.execute('SELECT username,password FROM '+table+" WHERE status='ACTIVE'"+extra+' ORDER BY id LIMIT 1')
  row=q.fetchone()
  if row: result.append(dict(role=role,**row))
print(json.dumps(result))
d.close()
'@
$roleAccounts = ($credentialReader | & '.\.venv\Scripts\python.exe' -) | ConvertFrom-Json
$liveBase = 'https://rajputsagai.com/janmashtami_qline_scanner'
$liveOutput = Join-Path (Get-Location).Path 'backend\media\live-reference'
[IO.Directory]::CreateDirectory($liveOutput) | Out-Null
function Get-LiveSummary([string]$markup) {
    $headings = @([regex]::Matches($markup,'(?is)<(title|h[1-6])\b[^>]*>(.*?)</\1>') | ForEach-Object {[Net.WebUtility]::HtmlDecode([regex]::Replace($_.Groups[2].Value,'<[^>]+>',' ')).Trim()})
    $navigation = @()
    foreach($nav in [regex]::Matches($markup,'(?is)<nav\b[^>]*>(.*?)</nav>')) {
        foreach($link in [regex]::Matches($nav.Groups[1].Value,'(?is)<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>')) {
            $navigation += [PSCustomObject]@{Label=[Net.WebUtility]::HtmlDecode([regex]::Replace($link.Groups[2].Value,'<[^>]+>',' ')).Trim();Url=$link.Groups[1].Value.Replace($liveBase,'')}
        }
    }
    $forms = @([regex]::Matches($markup,'(?is)<form\b([^>]*)>(.*?)</form>') | ForEach-Object {
        [PSCustomObject]@{Action=[regex]::Match($_.Groups[1].Value,'action="([^"]*)"').Groups[1].Value.Replace($liveBase,'');Method=[regex]::Match($_.Groups[1].Value,'method="([^"]*)"').Groups[1].Value;Fields=@([regex]::Matches($_.Groups[2].Value,'<(?:input|select|textarea)\b[^>]*name="([^"]+)"') | ForEach-Object {$_.Groups[1].Value});Buttons=@([regex]::Matches($_.Groups[2].Value,'(?is)<button\b[^>]*>(.*?)</button>') | ForEach-Object {[Net.WebUtility]::HtmlDecode([regex]::Replace($_.Groups[1].Value,'<[^>]+>',' ')).Trim()})}
    } | Select-Object -First 8)
    [PSCustomObject]@{Headings=$headings;Navigation=$navigation;Forms=$forms;HasPassGrid=$markup.Contains('pass-card-preview');HasTable=$markup.Contains('<table');Images=[regex]::Matches($markup,'<img\b').Count}
}
$roleReport = @{}
foreach($account in $roleAccounts) {
    try {
        $loginPage=Invoke-WebRequest -Uri "$liveBase/index.php" -UseBasicParsing -SessionVariable liveSession
        $csrf=[regex]::Match($loginPage.Content,'name="csrf" value="([^"]+)"').Groups[1].Value
        $roleHomeResponse=Invoke-WebRequest -Uri "$liveBase/login" -UseBasicParsing -WebSession $liveSession -Method Post -Body @{csrf=$csrf;role='common';username=$account.username;password=$account.password}
        if($roleHomeResponse.Content.Contains('data-clear-login-fields')) { throw 'The imported account did not authenticate on the live portal.' }
        $pages=@{Home=(Get-LiveSummary $roleHomeResponse.Content)}
        $links=@([regex]::Matches($roleHomeResponse.Content,'href="([^"]+)"') | ForEach-Object {[Net.WebUtility]::HtmlDecode($_.Groups[1].Value)})
        foreach($pageType in @('profile','shared-passes')) {
            $url=$links | Where-Object {$_.StartsWith($liveBase) -and $_.Contains('/'+$pageType)} | Select-Object -First 1
            if($url) { $page=Invoke-WebRequest -Uri $url -UseBasicParsing -WebSession $liveSession; $pages[$pageType]=Get-LiveSummary $page.Content }
        }
        $image=[regex]::Matches($roleHomeResponse.Content,'<img\b[^>]*src="([^"]+)"') | ForEach-Object {[Net.WebUtility]::HtmlDecode($_.Groups[1].Value)} | Where-Object {$_.StartsWith($liveBase) -and ($_ -match '/image|/uploads/cards/')} | Select-Object -First 1
        if($image) { Invoke-WebRequest -Uri $image -UseBasicParsing -WebSession $liveSession -OutFile (Join-Path $liveOutput ($account.role+'-pass.png')) }
        $roleReport[$account.role]=[PSCustomObject]@{Available=$true;Pages=$pages;ReferenceImage=[bool]$image}
        Write-Output ($account.role+': live role inspection complete.')
    } catch { $roleReport[$account.role]=[PSCustomObject]@{Available=$false;Reason=$_.Exception.Message} }
}
foreach($asset in @('app.css','components.css')) { Invoke-WebRequest -Uri "$liveBase/assets/css/$asset" -UseBasicParsing -OutFile (Join-Path $liveOutput $asset) }
$roleReport | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $liveOutput 'role-audit.json') -Encoding utf8
$roleReport | ConvertTo-Json -Depth 9
$roleAccounts=$null
