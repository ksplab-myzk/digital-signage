import PySide6
import vlc

print (PySide6.__version__)
instance = vlc.Instance()
print (instance.libvlc_get_version())
