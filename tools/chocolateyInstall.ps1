$packageName = 'syncthing-gtk'
$installerType = 'EXE'
$url = ''
$silentArgs = '/S'
$validExitCodes = @(0)

Install-ChocolateyPackage "$packageName" "$installerType" "$silentArgs" "$url" -validExitCodes $validExitCodes
