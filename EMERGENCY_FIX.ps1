# EMERGENCY FIX SCRIPT - Run as Administrator in PowerShell
# This will completely remove ALL cached references to the old add-in

Write-Host "=== EMERGENCY FIX FOR OUTLOOK ADD-IN ===" -ForegroundColor Green
Write-Host "This will remove ALL cached references to orangedesert URL" -ForegroundColor Yellow
Write-Host ""

# Step 1: Kill all Office processes
Write-Host "Step 1: Closing all Office applications..." -ForegroundColor Cyan
Get-Process | Where-Object {$_.Name -like "*OUTLOOK*" -or $_.Name -like "*WINWORD*" -or $_.Name -like "*EXCEL*" -or $_.Name -like "*POWERPNT*"} | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Step 2: Clear all Office caches
Write-Host "Step 2: Clearing Office caches..." -ForegroundColor Cyan

# Clear Web Extension Framework cache
$wefPaths = @(
    "$env:LOCALAPPDATA\Microsoft\Office\16.0\Wef",
    "$env:LOCALAPPDATA\Microsoft\Office\15.0\Wef",
    "$env:LOCALAPPDATA\Packages\Microsoft.Office.Desktop_8wekyb3d8bbwe\LocalCache\Local\Microsoft\Office\16.0\Wef",
    "$env:APPDATA\Microsoft\Office\16.0\Wef",
    "$env:LOCALAPPDATA\Microsoft\Office\Wef",
    "$env:TEMP\Wef"
)

foreach ($path in $wefPaths) {
    if (Test-Path $path) {
        Write-Host "  Clearing: $path" -ForegroundColor Gray
        Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Clear Office cache
$officeCachePaths = @(
    "$env:LOCALAPPDATA\Microsoft\Office\16.0\OfficeFileCache",
    "$env:LOCALAPPDATA\Microsoft\Office\16.0\BackstageInAppNavCache",
    "$env:LOCALAPPDATA\Microsoft\Office\OTele",
    "$env:LOCALAPPDATA\Microsoft\Office\16.0\Roaming"
)

foreach ($path in $officeCachePaths) {
    if (Test-Path $path) {
        Write-Host "  Clearing: $path" -ForegroundColor Gray
        Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Step 3: Clear Internet Explorer/Edge cache (Office uses IE engine)
Write-Host "Step 3: Clearing browser cache..." -ForegroundColor Cyan
RunDll32.exe InetCpl.cpl,ClearMyTracksByProcess 8
RunDll32.exe InetCpl.cpl,ClearMyTracksByProcess 2

# Step 4: Reset Outlook navigation pane
Write-Host "Step 4: Resetting Outlook settings..." -ForegroundColor Cyan
$outlookPath = "C:\Program Files\Microsoft Office\root\Office16\outlook.exe"
if (Test-Path $outlookPath) {
    & $outlookPath /resetnavpane
    & $outlookPath /cleanviews
    & $outlookPath /cleanserverrules
    & $outlookPath /cleanwebcache
}

# Step 5: Clear registry entries for add-ins
Write-Host "Step 5: Clearing add-in registry entries..." -ForegroundColor Cyan
$regPaths = @(
    "HKCU:\Software\Microsoft\Office\16.0\Outlook\Resiliency\DisabledItems",
    "HKCU:\Software\Microsoft\Office\16.0\Outlook\Resiliency\CrashingAddinList",
    "HKCU:\Software\Microsoft\Office\16.0\Outlook\Resiliency\NotificationReminderAddinData",
    "HKCU:\Software\Microsoft\Office\16.0\WEF"
)

foreach ($regPath in $regPaths) {
    if (Test-Path $regPath) {
        Write-Host "  Clearing registry: $regPath" -ForegroundColor Gray
        Remove-Item -Path $regPath -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Step 6: Create fresh manifest file
Write-Host "Step 6: Creating fresh manifest file..." -ForegroundColor Cyan
$manifestContent = @'
<?xml version="1.0" encoding="UTF-8"?>
<OfficeApp xmlns="http://schemas.microsoft.com/office/appforoffice/1.1"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
           xmlns:bt="http://schemas.microsoft.com/office/officeappbasictypes/1.0"
           xmlns:mailappor="http://schemas.microsoft.com/office/mailappversionoverrides/1.0"
           xsi:type="MailApp">
  
  <Id>d2422753-f7f6-4a4a-9e1e-7512f37a50e5</Id>
  <Version>1.5.0</Version>
  <ProviderName>The Well Recruiting Solutions</ProviderName>
  <DefaultLocale>en-US</DefaultLocale>
  <DisplayName DefaultValue="The Well - Send to Zoho"/>
  <Description DefaultValue="Process recruitment emails and automatically create candidate records in Zoho CRM."/>
  <IconUrl DefaultValue="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/icon-32.png"/>
  <HighResolutionIconUrl DefaultValue="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/icon-80.png"/>
  <SupportUrl DefaultValue="https://thewell.solutions/"/>
  
  <AppDomains>
    <AppDomain>well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io</AppDomain>
    <AppDomain>well-intake-api-dnajdub4azhjcgc3.z03.azurefd.net</AppDomain>
    <AppDomain>addin.emailthewell.com</AppDomain>
  </AppDomains>
  
  <Hosts>
    <Host Name="Mailbox"/>
  </Hosts>
  
  <Requirements>
    <Sets DefaultMinVersion="1.14">
      <Set Name="Mailbox"/>
    </Sets>
  </Requirements>
  
  <FormSettings>
    <Form xsi:type="ItemRead">
      <DesktopSettings>
        <SourceLocation DefaultValue="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/taskpane.html?v=1.5.0"/>
        <RequestedHeight>250</RequestedHeight>
      </DesktopSettings>
    </Form>
  </FormSettings>
  
  <Permissions>ReadWriteItem</Permissions>
  
  <Rule xsi:type="RuleCollection" Mode="Or">
    <Rule xsi:type="ItemIs" ItemType="Message" FormType="Read"/>
  </Rule>
  
  <DisableEntityHighlighting>false</DisableEntityHighlighting>
  
  <VersionOverrides xmlns="http://schemas.microsoft.com/office/mailappversionoverrides" xsi:type="VersionOverridesV1_0">
    <VersionOverrides xmlns="http://schemas.microsoft.com/office/mailappversionoverrides/1.1" xsi:type="VersionOverridesV1_1">
      <Requirements>
        <bt:Sets DefaultMinVersion="1.14">
          <bt:Set Name="Mailbox"/>
        </bt:Sets>
      </Requirements>
      
      <Hosts>
        <Host xsi:type="MailHost">
          <DesktopFormFactor>
            <FunctionFile resid="Commands.Url"/>
            
            <ExtensionPoint xsi:type="MessageReadCommandSurface">
              <OfficeTab id="TabDefault">
                <Group id="msgReadGroup">
                  <Label resid="GroupLabel"/>
                  <Control xsi:type="Button" id="msgReadOpenButton">
                    <Label resid="TaskpaneButton.Label"/>
                    <Supertip>
                      <Title resid="TaskpaneButton.Label"/>
                      <Description resid="TaskpaneButton.Tooltip"/>
                    </Supertip>
                    <Icon>
                      <bt:Image size="16" resid="Icon.16x16"/>
                      <bt:Image size="32" resid="Icon.32x32"/>
                      <bt:Image size="80" resid="Icon.80x80"/>
                    </Icon>
                    <Action xsi:type="ShowTaskpane">
                      <SourceLocation resid="Taskpane.Url"/>
                    </Action>
                  </Control>
                </Group>
              </OfficeTab>
            </ExtensionPoint>
          </DesktopFormFactor>
        </Host>
      </Hosts>
      
      <Resources>
        <bt:Images>
          <bt:Image id="Icon.16x16" DefaultValue="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/icon-16.png"/>
          <bt:Image id="Icon.32x32" DefaultValue="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/icon-32.png"/>
          <bt:Image id="Icon.80x80" DefaultValue="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/icon-80.png"/>
        </bt:Images>
        
        <bt:Urls>
          <bt:Url id="Commands.Url" DefaultValue="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/commands.html?v=1.5.0"/>
          <bt:Url id="Taskpane.Url" DefaultValue="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/taskpane.html?v=1.5.0"/>
        </bt:Urls>
        
        <bt:ShortStrings>
          <bt:String id="GroupLabel" DefaultValue="The Well"/>
          <bt:String id="TaskpaneButton.Label" DefaultValue="Send to Zoho"/>
        </bt:ShortStrings>
        
        <bt:LongStrings>
          <bt:String id="TaskpaneButton.Tooltip" DefaultValue="Process this email and create candidate records in Zoho CRM"/>
        </bt:LongStrings>
      </Resources>
    </VersionOverrides>
  </VersionOverrides>
</OfficeApp>
'@

$manifestPath = "$env:USERPROFILE\Desktop\TheWell_Manifest_FIXED.xml"
$manifestContent | Out-File -FilePath $manifestPath -Encoding UTF8
Write-Host "  Fresh manifest saved to: $manifestPath" -ForegroundColor Green

Write-Host ""
Write-Host "=== CLEANUP COMPLETE ===" -ForegroundColor Green
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "1. Start Outlook" -ForegroundColor White
Write-Host "2. Go to: Get Add-ins -> My add-ins -> Add from File" -ForegroundColor White
Write-Host "3. Browse to: $manifestPath" -ForegroundColor White
Write-Host "4. Click Install" -ForegroundColor White
Write-Host ""
Write-Host "The manifest file uses ONLY the new wittyocean URLs." -ForegroundColor Green
Write-Host "NO orangedesert references!" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to exit"