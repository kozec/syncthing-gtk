$packageName = 'syncthing-gtk'
$installerType = 'EXE'
$url = 'https://github.com/syncthing/syncthing-gtk/releases/download/v0.5.2/SyncthingGTK-0.5.2-win32-full-installer.exe'
$url64 = $url
$silentArgs = '/S'
$validExitCodes = @(0)

Install-ChocolateyPackage "$packageName" "$installerType" "$silentArgs" "$url" "$url64"  -validExitCodes $validExitCodes
