# Helper for driving LinkedIn Easy Apply via Kimi WebBridge CDP.
# Dot-source this file in each PowerShell call: . .\ldrive.ps1
$D = "http://127.0.0.1:10086/command"
$S = "linkedin-easy-apply"
function Cmd($action,$cargs,$to=60){ $b=@{action=$action;args=$cargs;session=$S}|ConvertTo-Json -Depth 8 -Compress; try{return Invoke-RestMethod -Uri $D -Method Post -Body $b -ContentType 'application/json' -TimeoutSec $to}catch{return $null} }
function Cdp($method,$params){ Cmd "cdp" @{method=$method;params=$params} 20 | Out-Null }
function Ev($code){ $r=Cmd "evaluate" @{code=$code} 30; if($r){return $r.data.value}else{return $null} }
function Nav($url){ Cmd "navigate" @{url=$url} | Out-Null; Start-Sleep -Seconds 3 }
function Click($x,$y){ Cdp "Input.dispatchMouseEvent" @{type="mouseMoved";x=$x;y=$y}; Cdp "Input.dispatchMouseEvent" @{type="mousePressed";x=$x;y=$y;button="left";buttons=1;clickCount=1}; Start-Sleep -Milliseconds 120; Cdp "Input.dispatchMouseEvent" @{type="mouseReleased";x=$x;y=$y;button="left";buttons=0;clickCount=1}; Start-Sleep -Milliseconds 400 }
function Wheel($dy){ Cdp "Input.dispatchMouseEvent" @{type="mouseWheel";x=760;y=400;deltaX=0;deltaY=$dy}; Start-Sleep -Milliseconds 800 }
function TypeStr($x,$y,$text){ Click $x $y; Start-Sleep -Milliseconds 150; foreach($c in $text.ToCharArray()){ $s=[string]$c; Cdp "Input.dispatchKeyEvent" @{type="keyDown";key=$s;text=$s}; Cdp "Input.dispatchKeyEvent" @{type="keyUp";key=$s}; Start-Sleep -Milliseconds 50 } }
function KeyEnter(){ Cdp "Input.dispatchKeyEvent" @{type="keyDown";key="Enter";code="Enter";windowsVirtualKeyCode=13}; Cdp "Input.dispatchKeyEvent" @{type="keyUp";key="Enter";code="Enter";windowsVirtualKeyCode=13} }
function SelType($x,$y,$ch){ Click $x $y; Start-Sleep -Milliseconds 350; Cdp "Input.dispatchKeyEvent" @{type="keyDown";key=$ch;text=$ch}; Cdp "Input.dispatchKeyEvent" @{type="keyUp";key=$ch}; Start-Sleep -Milliseconds 350; KeyEnter; Start-Sleep -Milliseconds 400 }
function Shot(){ $ts=Get-Random; $dir=Join-Path $PSScriptRoot "snapshots"; if(-not (Test-Path $dir)){New-Item -ItemType Directory -Force $dir | Out-Null}; $p=(Join-Path $dir "s_$ts.jpg").Replace('\','/'); if(Test-Path $p){Remove-Item $p -Force}; $ok=$false; for($i=0;$i -lt 4 -and -not $ok;$i++){ $r=Cmd "screenshot" @{format="jpeg";quality=55;path=$p} 90; if(Test-Path $p){$ok=$true} else {Start-Sleep -Milliseconds 800} }; return $p }
function OpenEasyApply(){ $code="(function(){const els=Array.from(document.querySelectorAll('button,a')).filter(x=>/Easy Apply/i.test(x.textContent||''));if(!els.length)return JSON.stringify({found:false});const b=els[0];const r=b.getBoundingClientRect();return JSON.stringify({found:true,x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)})})()"; $v=Ev $code; return $v }
