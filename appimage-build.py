#!/usr/bin/env python2
# Prepares directory for AppImage
import subprocess, shutil, tarfile, uuid, sys, os
from collections import namedtuple

APP="syncthing-gtk"
TARGET = "./appimage"
KEEP_BUSYBOX = True
CDN = "http://nl.alpinelinux.org/alpine/v3.10"
APK_TOOLS = "https://github.com/alpinelinux/apk-tools/releases/download/v2.10.4/apk-tools-2.10.4-x86_64-linux.tar.gz"
BUILD_ID = str(uuid.uuid4())
ALPINE_KEYS = {
	"4a6a0840": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1yHJxQgsHQREclQu4O"
		+ "he\nqxTxd1tHcNnvnQTu/UrTky8wWvgXT+jpveroeWWnzmsYlDI93eLI2ORakxb3gA2O"
		+ "\nQ0Ry4ws8vhaxLQGC74uQR5+/yYrLuTKydFzuPaS1dK19qJPXB8GMdmFOijnXX4SA\n"
		+ "jixuHLe1WW7kZVtjL7nufvpXkWBGjsfrvskdNA/5MfxAeBbqPgaq0QMEfxMAn6/R\nL5"
		+ "kNepi/Vr4S39Xvf2DzWkTLEK8pcnjNkt9/aafhWqFVW7m3HCAII6h/qlQNQKSo\nGuH3"
		+ "4Q8GsFG30izUENV9avY7hSLq7nggsvknlNBZtFUcmGoQrtx3FmyYsIC8/R+B\nywIDAQ"
		+ "AB",
	"5243ef4b": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvNijDxJ8kloskKQpJd"
		+ "x+\nmTMVFFUGDoDCbulnhZMJoKNkSuZOzBoFC94omYPtxnIcBdWBGnrm6ncbKRlR+6oy"
		+ "\nDO0W7c44uHKCFGFqBhDasdI4RCYP+fcIX/lyMh6MLbOxqS22TwSLhCVjTyJeeH7K\n"
		+ "aA7vqk+QSsF4TGbYzQDDpg7+6aAcNzg6InNePaywA6hbT0JXbxnDWsB+2/LLSF2G\nmn"
		+ "hJlJrWB1WGjkz23ONIWk85W4S0XB/ewDefd4Ly/zyIciastA7Zqnh7p3Ody6Q0\nsS2M"
		+ "Jzo7p3os1smGjUF158s6m/JbVh4DN6YIsxwl2OjDOz9R0OycfJSDaBVIGZzg\ncQIDAQ"
		+ "AB",
	"524d27bb": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAr8s1q88XpuJWLCZALd"
		+ "Kj\nlN8wg2ePB2T9aIcaxryYE/Jkmtu+ZQ5zKq6BT3y/udt5jAsMrhHTwroOjIsF9DeG"
		+ "\ne8Y3vjz+Hh4L8a7hZDaw8jy3CPag47L7nsZFwQOIo2Cl1SnzUc6/owoyjRU7ab0p\n"
		+ "iWG5HK8IfiybRbZxnEbNAfT4R53hyI6z5FhyXGS2Ld8zCoU/R4E1P0CUuXKEN4p0\n64"
		+ "dyeUoOLXEWHjgKiU1mElIQj3k/IF02W89gDj285YgwqA49deLUM7QOd53QLnx+\nxrIr"
		+ "Pv3A+eyXMFgexNwCKQU9ZdmWa00MjjHlegSGK8Y2NPnRoXhzqSP9T9i2HiXL\nVQIDAQ"
		+ "AB",
	"5261cecb": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwlzMkl7b5PBdfMzGdC"
		+ "T0\ncGloRr5xGgVmsdq5EtJvFkFAiN8Ac9MCFy/vAFmS8/7ZaGOXoCDWbYVLTLOO2qtX"
		+ "\nyHRl+7fJVh2N6qrDDFPmdgCi8NaE+3rITWXGrrQ1spJ0B6HIzTDNEjRKnD4xyg4j\n"
		+ "g01FMcJTU6E+V2JBY45CKN9dWr1JDM/nei/Pf0byBJlMp/mSSfjodykmz4Oe13xB\nCa"
		+ "1WTwgFykKYthoLGYrmo+LKIGpMoeEbY1kuUe04UiDe47l6Oggwnl+8XD1MeRWY\nsWgj"
		+ "8sF4dTcSfCMavK4zHRFFQbGp/YFJ/Ww6U9lA3Vq0wyEI6MCMQnoSMFwrbgZw\nwwIDAQ"
		+ "AB",
	"58199dcc": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA3v8/ye/V/t5xf4JiXL"
		+ "Xa\nhWFRozsnmn3hobON20GdmkrzKzO/eUqPOKTpg2GtvBhK30fu5oY5uN2ORiv2Y2ht"
		+ "\neLiZ9HVz3XP8Fm9frha60B7KNu66FO5P2o3i+E+DWTPqqPcCG6t4Znk2BypILcit\n"
		+ "wiPKTsgbBQR2qo/cO01eLLdt6oOzAaF94NH0656kvRewdo6HG4urbO46tCAizvCR\nCA"
		+ "7KGFMyad8WdKkTjxh8YLDLoOCtoZmXmQAiwfRe9pKXRH/XXGop8SYptLqyVVQ+\ntegO"
		+ "D9wRs2tOlgcLx4F/uMzHN7uoho6okBPiifRX+Pf38Vx+ozXh056tjmdZkCaV\naQIDAQ"
		+ "AB",
	"58cbb476": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoSPnuAGKtRIS5fEgYP"
		+ "XD\n8pSGvKAmIv3A08LBViDUe+YwhilSHbYXUEAcSH1KZvOo1WT1x2FNEPBEFEFU1Eyc"
		+ "\n+qGzbA03UFgBNvArurHQ5Z/GngGqE7IarSQFSoqewYRtFSfp+TL9CUNBvM0rT7vz\n"
		+ "2eMu3/wWG+CBmb92lkmyWwC1WSWFKO3x8w+Br2IFWvAZqHRt8oiG5QtYvcZL6jym\nY8"
		+ "T6sgdDlj+Y+wWaLHs9Fc+7vBuyK9C4O1ORdMPW15qVSl4Lc2Wu1QVwRiKnmA+c\nDsH/"
		+ "m7kDNRHM7TjWnuj+nrBOKAHzYquiu5iB3Qmx+0gwnrSVf27Arc3ozUmmJbLj\nzQIDAQ"
		+ "AB",
	"58e4f17d": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvBxJN9ErBgdRcPr5g4"
		+ "hV\nqyUSGZEKuvQliq2Z9SRHLh2J43+EdB6A+yzVvLnzcHVpBJ+BZ9RV30EM9guck9sh"
		+ "\nr+bryZcRHyjG2wiIEoduxF2a8KeWeQH7QlpwGhuobo1+gA8L0AGImiA6UP3LOirl\n"
		+ "I0G2+iaKZowME8/tydww4jx5vG132JCOScMjTalRsYZYJcjFbebQQolpqRaGB4iG\nWq"
		+ "hytWQGWuKiB1A22wjmIYf3t96l1Mp+FmM2URPxD1gk/BIBnX7ew+2gWppXOK9j\n1BJp"
		+ "o0/HaX5XoZ/uMqISAAtgHZAqq+g3IUPouxTphgYQRTRYpz2COw3NF43VYQrR\nbQIDAQ"
		+ "AB",
}
PythonDep = namedtuple("PythonDep", "name, version")
NativeDep = namedtuple("NativeDep", "name")

DEPS = [
	# KindOfDep(name, version)
	NativeDep("cairo"),
	NativeDep("python2"),
	NativeDep("gtk+3.0"),
	# NativeDep("gvfs"),		# TODO: This brings-in half of appimage size
	NativeDep("gdk-pixbuf"),
	NativeDep("gobject-introspection"),
	NativeDep("py2-pip"),
	NativeDep("py2-cffi"),
	NativeDep("py2-bcrypt"),
	# PythonDep("python-dateutil", "2.8.1"),
	NativeDep("py2-dateutil"),
	NativeDep("py2-gobject3"),
]


def makedirs(a):
	try:
		os.makedirs(a)
	except OSError, e:
		if e.errno == 17:		# Already exists
			return
		raise


def symlink(a, b):
	try:
		os.symlink(a, b)
	except OSError, e:
		if e.errno == 17:		# Already exists
			return
		raise


def create_dirs(path):
	makedirs(os.path.join(path, "usr/share"))
	makedirs(os.path.join(path, "usr/bin"))
	makedirs(os.path.join(path, "usr/lib"))
	makedirs(os.path.join(path, "lib"))
	symlink("usr/bin", os.path.join(path, "bin"))
	symlink("bin", os.path.join(path, "usr/sbin"))
	symlink("usr/bin", os.path.join(path, "sbin"))


def rm_if_exists(path):
	try:
		os.unlink(path)
	except OSError, e:
		if e.errno == 2:			# File not found
			return
		raise


def download(url, target_filename):
	p = subprocess.Popen(["wget", url, "--continue", "-O", target_filename])
	p.communicate()
	assert p.returncode == 0, "Download failed"


def run_bwrapped(path, tmp, args, bwrap_opts=[]):
	"""
	Takes subprocess.Popen arguments, returns subprocess.Popen instance of those
	arguments chrooted with bwrap
	"""
	bwrap_opts = list(bwrap_opts)
	if os.path.exists(os.path.join(path, "build-uuid")):
		old_build_uuid = open(os.path.join(path, "build-uuid"), "r").read()
		bwrap_opts += [
			"--symlink",
			"/appimage/elf-interpreter",
			"/tmp/%s-elf-interpreter" % (old_build_uuid, ),
		]
	
	cmd = [
		"bwrap",
		"--bind", path, "/appimage",
		"--symlink", "appimage/usr", "/usr",
		"--symlink", "appimage/lib", "/lib",
		"--symlink", "appimage/usr/bin", "/bin",
		"--symlink", "appimage/usr/bin", "/sbin",
		"--symlink", "appimage/var", "/var",
		"--symlink", "appimage/etc", "/etc",
		"--dev", "/dev",
		"--tmpfs", "/tmp",
		"--bind", "/sys", "/sys",
		"--bind", "/proc", "/proc",
		"--ro-bind", "/etc/passwd", "/etc/passwd",
		"--ro-bind", "/etc/group", "/etc/group",
		"--chdir", "/",
		"--unshare-user", "--uid", "0", "--gid", "0",
		"--share-net",
	] + bwrap_opts + [
		"--",
	] + args
	print " ".join(cmd)
	return subprocess.Popen(cmd)


def apk(path, tmp, operation, *opts):
	p = run_bwrapped(path, tmp,	[
		"/appimage/apk",
		operation,
		"--root", "/appimage",
		"--arch", "x86_64",
	] + list(opts))
	p.communicate()
	assert p.returncode == 0, "APK failed"


def get_interpreted(filename):
	p = subprocess.Popen(["readelf", "-l", filename], stdout=subprocess.PIPE)
	stdout, _ = p.communicate()
	piece = "".join([ x for x in stdout.split("\n") if "interpreter:" in x ])
	return piece.strip("[]\t ").split(":")[-1].strip(" ")


def unpack(target_path, tar_gz_filename, *opts):
	old_path = os.getcwd()
	os.chdir(target_path)
	p = subprocess.Popen(["tar", "fxz", tar_gz_filename, "--warning=none"] + list(opts))
	p.communicate()
	os.chdir(old_path)
	assert p.returncode == 0, "Extraction failed"


def prepare_apk_tools(path, tmp):
	download(APK_TOOLS, os.path.join(tmp, "/tmp/appimage-build-apk-tools-static.tar.gz"))
	unpack(path, os.path.join(tmp, "/tmp/appimage-build-apk-tools-static.tar.gz"), "--strip-components=1")
	rm_if_exists(os.path.join(path, ".PKGINFO"))
	
	makedirs(os.path.join(path, "etc/apk"))
	repofile = open(os.path.join(path, "etc/apk/repositories"), "w")
	repofile.write(CDN + "/main" + "\n")
	repofile.write(CDN + "/community" + "\n")
	repofile.close()
	
	shutil.copy("/etc/resolv.conf", os.path.join(path, "etc/resolv.conf"))
	
	makedirs(os.path.join(path, "etc/apk/keys"))
	for (id, content) in ALPINE_KEYS.items():
		keyfile_name = "etc/apk/keys/alpine-devel@lists.alpinelinux.org-%s.rsa.pub" % (id,)
		keyfile = open(os.path.join(path, keyfile_name), "w")
		keyfile.write("-----BEGIN PUBLIC KEY-----\n")
		keyfile.write(content + "\n")
		keyfile.write("-----END PUBLIC KEY-----\n")
		keyfile.close()
	
	apk(path, tmp, "add", "--update-cache", "--initdb", "--no-scripts", "busybox-static")
	p = run_bwrapped(path, tmp, ["/bin/busybox.static", "--install", "-s"])
	p.communicate()
	assert p.returncode == 0, "Busybox install install failed"
	
	# fake_install(path, "polkit", "0.116-r0")
	# fake_install(path, "linux-pam", "1.3.0-r1")


def cleanup(path):
	CLEANUP_BINARIES = [
		"gtk3-widget-factory",
		"gtk3-demo-application",
		"gtk3-demo",
	]
	if KEEP_BUSYBOX:
		if os.path.exists(os.path.join(path, "usr/bin/busybox")):
			symlink("busybox.static", os.path.join(path, "usr/bin/busybox"))
	else:
		CLEANUP_BINARIES += ["busybox", "busybox.static"]
	
	for filename in CLEANUP_BINARIES:
		full_path = os.path.join(path, "usr/bin", filename)
		if os.path.exists(full_path):
			os.unlink(full_path)


def break_paths(path):
	for filename in os.listdir(os.path.join(path, "usr/bin")):
		full_path = os.path.join(path, "usr/bin", filename)
		if os.path.islink(full_path):
			target = os.readlink(full_path)
			if target == "/bin/busybox.static" or target == "/bin/busybox":
				if KEEP_BUSYBOX:
					# Replace absolute path with relative path
					os.unlink(full_path)
					os.symlink("busybox.static", full_path)
				else:
					# Remove files linked to busybox
					os.unlink(full_path)
		elif open(full_path, "rb").read(4) == b"\x7fELF":
			# Set ELF interpreter to predictable, absolute path
			interpreter = get_interpreted(full_path)
			if interpreter == "/lib/ld-musl-x86_64.so.1" or "-elf-interpreter" in interpreter:
				p = subprocess.Popen(["patchelf",
					"--set-interpreter", "/tmp/%s-elf-interpreter" % (BUILD_ID,),
					full_path], stderr=subprocess.PIPE)
				p.communicate()
				assert p.returncode == 0, "patchelf --set-interpreter failed"
	
	# Store build-uuid so ELF interpreter path can be reconstructed later
	open(os.path.join(path, "build-uuid"), "w").write(BUILD_ID)
	symlink("lib/ld-musl-x86_64.so.1", os.path.join(path, "elf-interpreter"))


def install_native_deps(path, tmp):
	native_deps = [
		dep.name for dep in DEPS
		if isinstance(dep, NativeDep)
	]
	apk(path, tmp, "add", "--clean-protected", "--no-scripts", "-l",
			*native_deps)
	
	# Run triggers
	#
	# APK seems to use chroot to execute .post-install scripts and triggers
	# chroot fails under bwrap and for that reason, scripts are executed
	# using this method after package is installed
	def run_script(path, tmp, tar_file, name):
		tar_file.extract(name, path=os.path.join(path, "run_script"))
		p = run_bwrapped(path, tmp, ["sh", "/appimage/run_script/%s" % (name,)])
		p.communicate()
		assert p.returncode == 0 or name.endswith(".trigger"), \
				"Failed to run script '%s'" % (name, )
		shutil.rmtree(os.path.join(path, "run_script"), ignore_errors=True)
	
	t = tarfile.TarFile(os.path.join(path, "lib/apk/db/scripts.tar"), "r")
	triggers = [
		x.name for x in t.getmembers() if x.name.endswith(".trigger")
	]
	post_install = [
		x.name for x in t.getmembers()
		if x.name.startswith("%s-" % (dep.name,)) and x.name.endswith(".post-install")
	]
	for script in post_install + triggers:
		run_script(path, tmp, t, script)
	t.close()
	
	run_bwrapped(path, tmp, ["/usr/bin/gio-querymodules",
								"/usr/lib/gio/modules"]).communicate()
	run_bwrapped(path, tmp, ["/usr/bin/glib-compile-schemas",
								"/usr/share/glib-2.0/schemas"]).communicate()


def install_python_deps(path, tmp):
	py_deps = [
		"%s==%s" % (dep.name, dep.version) for dep in DEPS
		if isinstance(dep, PythonDep)
	]
	if not py_deps: return
	
	p = run_bwrapped(path, tmp, ["pip", "install"] + py_deps)
	p.communicate()
	assert p.returncode == 0, "pip install failed"


def install_python_app(path, tmp, dir_with_setup_py):
	bwrap_opts = ["--bind", dir_with_setup_py, "/py-app", "--chdir", "/py-app"]
	p = run_bwrapped(path, tmp, bwrap_opts=bwrap_opts,
			args=["python2", "setup.py", "build"])
	p.communicate()
	assert p.returncode == 0, "setup.py build failed"
	
	p = run_bwrapped(path, tmp, bwrap_opts=bwrap_opts,
			args=["python2", "setup.py", "install"])
	p.communicate()
	assert p.returncode == 0, "setup.py build failed"


if __name__ == "__main__":
	path, tmp = os.path.abspath(TARGET), "/tmp"
	create_dirs(path)
	prepare_apk_tools(path, tmp)
	install_native_deps(path, tmp)
	install_python_deps(path, tmp)
	
	# Run setup.py
	install_python_app(path, tmp, ".")
	
	# Copy AppRun script
	shutil.copy("scripts/appimage-AppRun.sh", os.path.join(path, "AppRun"))
	
	# Copy & patch desktop file
	desktop = open("%s.desktop" % (APP,), "r").read()
	# sed -i "s/Icon=.*/Icon=${APP}/g" ${BUILD_APPDIR}/${APP}.desktop
	open(os.path.join(TARGET, "%s.desktop" % (APP,)), "w").write(desktop)
	
	# Copy icon
	shutil.copy("icons/%s.png" % (APP,), os.path.join(TARGET, "%s.png" % (APP,)))
	
	# Fix path & clean-up directory
	cleanup(path)
	break_paths(path)
	
	print "\n=================="
	print "Run appimagetool -n %s to finish prepared appimage" % (TARGET,)

