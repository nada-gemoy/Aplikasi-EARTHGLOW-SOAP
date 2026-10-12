[app]

title = EarthGlow Soap Admin
package.name = earthglowsoap
package.domain = org.nadagemoy
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,webp
version = 1.0.0
requirements = python3,kivy,openpyxl,et_xmlfile
orientation = portrait
fullscreen = 0

android.api = 35
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
p4a.branch = master
p4a.commit = 957a3e5f8c270f7aa648ba185e5a68c1077a798d

[buildozer]
log_level = 2
warn_on_root = 1
