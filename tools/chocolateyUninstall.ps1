$packageName = 'syncthing-gtk'
$installerType = 'EXE'
$silentArgs = '/S'
$path = "$env:ProgramFiles\SyncthingGTK"
$path86 = "${env:ProgramFiles(x86)}\SyncthingGTK"

if (Test-Path $path) {
    Uninstall-ChocolateyPackage $packageName $installerType $silentArgs "$path\uninstaller.exe"
}

if (Test-Path $path86) {
    Uninstall-ChocolateyPackage $packageName $installerType $silentArgs "$path86\uninstaller.exe"
}
