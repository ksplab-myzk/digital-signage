import sys
import glob
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut

class SlideWindow(QLabel):
    def __init__(self, image_paths, app):
        super().__init__()
        self.image_paths = image_paths
        self.index = 0
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: black;")
        
        # ESCキーで終了（ウィンドウに紐づける）
        shortcut = QShortcut(QKeySequence("Escape"), self)
        shortcut.activated.connect(app.quit)
    
    def show_image(self):
        if not self.image_paths:
            return
        path = self.image_paths[self.index]
        pix = QPixmap(path)
        self.setPixmap(pix.scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        ))
        self.index = (self.index + 1) % len(self.image_paths)

def main():
    app = QApplication(sys.argv)

    # --- 画像リスト読み込み ---
    imagesA = sorted(glob.glob("imagesA/*.jpg"))
    imagesB = sorted(glob.glob("imagesB/*.jpg"))

    # --- 2つのウィンドウ作成 ---
    winA = SlideWindow(imagesA, app)
    winB = SlideWindow(imagesB, app)

    screens = app.screens()
    if len(screens) < 2:
        print("2画面が必要です")
        sys.exit(1)

    # --- 画面Aに配置 ---
    geoA = screens[0].geometry()
    winA.setGeometry(geoA)
    winA.showFullScreen()

    # --- 画面Bに配置 ---
    geoB = screens[1].geometry()
    winB.setGeometry(geoB)
    winB.showFullScreen()

    # --- 同期タイマー（5秒ごと） ---
    timer = QTimer()
    timer.timeout.connect(lambda: (winA.show_image(), winB.show_image()))
    timer.start(5000)

    # 初回表示
    winA.show_image()
    winB.show_image()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
