param()
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$runner=Join-Path $root 'b16_testkit.py'
if(-not (Test-Path -LiteralPath $runner) -or -not (Test-Path -LiteralPath (Join-Path $root 'TestKitIdentity.json')) -or -not (Test-Path -LiteralPath (Join-Path $root 'RunnerIdentity.json'))){Write-Host '[ERROR] Please extract full ZIP';exit 2}
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$form=New-Object System.Windows.Forms.Form
$form.Text='Bonsai Build111 Identity Fix - Matching IPA Required'
$form.ClientSize=New-Object System.Drawing.Size(580,420)
$form.StartPosition='CenterScreen'
$form.FormBorderStyle='FixedDialog'
$form.MaximizeBox=$false
$form.Font=New-Object System.Drawing.Font('Microsoft YaHei UI',10)
$title=New-Object System.Windows.Forms.Label
$title.Text='Build111 B8-B16-B8 只需输入一次 API Key'
$title.SetBounds(20,14,530,30);$form.Controls.Add($title)
$lab=New-Object System.Windows.Forms.Label
$lab.Text='API URL（可留空自动发现）'
$lab.SetBounds(20,54,520,24);$form.Controls.Add($lab)
$url=New-Object System.Windows.Forms.TextBox
$url.SetBounds(20,80,536,27);$form.Controls.Add($url)
$kl=New-Object System.Windows.Forms.Label
$kl.Text='API Key：Ctrl+V 或点击粘贴按钮'
$kl.SetBounds(20,116,530,23);$form.Controls.Add($kl)
$key=New-Object System.Windows.Forms.TextBox
$key.SetBounds(20,143,405,28);$key.UseSystemPasswordChar=$true;$form.Controls.Add($key)
$paste=New-Object System.Windows.Forms.Button
$paste.Text='粘贴';$paste.SetBounds(438,142,118,30)
$paste.Add_Click({
 try {
  $v=[System.Windows.Forms.Clipboard]::GetText().Trim()
  if($v -match '^(?i:Bearer)\s+(.+)$'){$v=$Matches[1].Trim()}
  $key.Text=$v
 }catch{[System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'粘贴失败')|Out-Null}
});$form.Controls.Add($paste)
$show=New-Object System.Windows.Forms.CheckBox
$show.Text='显示 API Key';$show.SetBounds(20,183,250,24)
$show.Add_CheckedChanged({$key.UseSystemPasswordChar=-not $show.Checked})
$form.Controls.Add($show)
$fresh=New-Object System.Windows.Forms.CheckBox
$fresh.Text='从新实验开始（保留旧报告）';$fresh.SetBounds(270,183,290,24)
$form.Controls.Add($fresh)
$priorLabel=New-Object System.Windows.Forms.Label
$priorLabel.Text='Same Build111 RESULTS only (optional; keep old R2 folder)'
$priorLabel.SetBounds(20,216,535,24);$form.Controls.Add($priorLabel)
$previous=New-Object System.Windows.Forms.TextBox
$previous.SetBounds(20,242,322,28);$form.Controls.Add($previous)
$browse=New-Object System.Windows.Forms.Button
$browse.Text='Folder';$browse.SetBounds(350,242,96,30)
$browse.Add_Click({
 $dialog=New-Object System.Windows.Forms.FolderBrowserDialog
 $dialog.Description='Select same-Build111 RESULTS only; keep Build110 R2 separately'
 if($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){$previous.Text=$dialog.SelectedPath}
 $dialog.Dispose()
});$form.Controls.Add($browse)
$zipBrowse=New-Object System.Windows.Forms.Button
$zipBrowse.Text='ZIP';$zipBrowse.SetBounds(454,242,102,30)
$zipBrowse.Add_Click({
 $dialog=New-Object System.Windows.Forms.OpenFileDialog
 $dialog.Filter='Original result ZIP (*.zip)|*.zip'
 if($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){$previous.Text=$dialog.FileName}
 $dialog.Dispose()
});$form.Controls.Add($zipBrowse)
$hint=New-Object System.Windows.Forms.Label
$hint.Text='Key 仅保留在进程内；按提示完整关闭并重启 iPad App。'
$hint.SetBounds(20,285,540,25);$form.Controls.Add($hint)
 $mode=New-Object System.Windows.Forms.ComboBox
$mode.DropDownStyle='DropDownList';$mode.Items.AddRange(@('Quick - prefill-batch (exploratory)','Full - existing certification'));$mode.SelectedIndex=0
$mode.SetBounds(20,315,536,28);$form.Controls.Add($mode)
$go=New-Object System.Windows.Forms.Button
$go.Text='开始 B8/B16/B8 测试';$go.SetBounds(305,370,158,32)
$go.Add_Click({
 if([string]::IsNullOrWhiteSpace($key.Text)){[System.Windows.Forms.MessageBox]::Show('请粘贴 API Key')|Out-Null;return}
 if($url.Text.Trim() -and $url.Text.Trim() -notmatch '^https?://[^\s]+$'){
  [System.Windows.Forms.MessageBox]::Show('API URL 格式无效')|Out-Null;return
 }
 $form.DialogResult=[System.Windows.Forms.DialogResult]::OK;$form.Close()
});$form.Controls.Add($go);$form.AcceptButton=$go
$cancel=New-Object System.Windows.Forms.Button
$cancel.Text='取消';$cancel.SetBounds(478,370,78,32)
$cancel.Add_Click({$form.DialogResult=[System.Windows.Forms.DialogResult]::Cancel;$form.Close()})
$form.Controls.Add($cancel);$form.CancelButton=$cancel
$result=$form.ShowDialog()
if($result -ne [System.Windows.Forms.DialogResult]::OK){$form.Dispose();exit 2}
$env:BONSAI_API_KEY=$key.Text.Trim()
if($url.Text.Trim()){$env:BONSAI_BASE_URL=$url.Text.Trim()}
$resumeArgs=@('--resume-latest')
if($fresh.Checked){$resumeArgs=@()}
if($previous.Text.Trim()){$resumeArgs=@('--previous-results',$previous.Text.Trim())}
$modeArgs=@('--mode','full')
if($mode.SelectedIndex -eq 0){$modeArgs=@('--mode','quick','--direction','prefill-batch');$resumeArgs=@()}
$form.Dispose()
$exe=$null;$py=@()
if(Test-Path -LiteralPath (Join-Path $root 'python\python.exe')){$exe=Join-Path $root 'python\python.exe';$py=@('-u')} elseif(Test-Path -LiteralPath (Join-Path $root 'runtime\python.exe')){$exe=Join-Path $root 'runtime\python.exe';$py=@('-u')} elseif(Get-Command 'py.exe' -ErrorAction SilentlyContinue){$exe='py.exe';$py=@('-3','-u')}
elseif(Get-Command 'python.exe' -ErrorAction SilentlyContinue){$exe='python.exe';$py=@('-u')}
if(-not $exe){Write-Host '[ERROR] Python 3 is missing';Remove-Item Env:BONSAI_API_KEY;exit 2}
Write-Host 'Bonsai Build111 B8-B16-B8 - API KEY [REDACTED]'
Write-Host '[PREFLIGHT] Local registration only: static INCOMPLETE is normal. Live startup wait follows (up to 900s, no inference or arm POST during wait).'
$rc=2
try {
 & $exe @py $runner @modeArgs '--dry-run'
 if ($LASTEXITCODE -ne 0) {
   Write-Host '[ERROR] Local runner compatibility check failed before API test.'
   $rc=2
 } else {
   & $exe @py $runner @modeArgs @resumeArgs '--output' (Join-Path $root 'RESULTS')
   $rc=$LASTEXITCODE
 }
}finally{
 Remove-Item Env:BONSAI_API_KEY -ErrorAction SilentlyContinue
 Remove-Item Env:BONSAI_BASE_URL -ErrorAction SilentlyContinue
}
exit $rc
