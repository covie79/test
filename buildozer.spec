[app]

title = DollarStar Barcode
package.name = dollarstarbarcode
package.domain = org.dollarstar
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,db
version = 0.1
requirements = python3,kivy,pyjnius
icon.filename = %(source.dir)s/logo.png
orientation = portrait
osx.kivy_version = 2.2.0
fullscreen = 0
android.permissions = CAMERA,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.build_tools_version = 33.0.2
android.ndk = 28c
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.release_artifact = aab
android.debug_artifact = apk
android.display_cutout = never
ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master
ios.ios_deploy_url = https://github.com/phonegap/ios-deploy
ios.ios_deploy_branch = 1.12.2
ios.codesign.allowed = false
ios.viewcontroller_based_statusbar_appearance = False

[buildozer]

log_level = 2
warn_on_root = 1
