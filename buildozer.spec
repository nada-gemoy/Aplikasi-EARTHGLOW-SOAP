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
android.minapi = 23
android.archs = arm64-v8a
android.permissions = READ_EXTERNAL_STORAGE,READ_MEDIA_IMAGES
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
