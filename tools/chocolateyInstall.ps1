$packageName = 'syncthing-gtk'
$installerType = 'EXE'
$url = ''
$checksum = ''
$checksumType = 'sha256'
$silentArgs = '/S'
$validExitCodes = @(0)

Install-ChocolateyPackage "$packageName" "$installerType" "$silentArgs" "$url" -validExitCodes $validExitCodes
