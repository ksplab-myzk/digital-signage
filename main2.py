import sys
import glob
import subprocess
import vlc
import platform
import os

from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PySide6.QtGui import QPixmap, QKeySequence, QShortcut
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtCore import QPropertyAnimation

class MediaWindow(QWidget):
    def __init__(self, playlist, app, next_callback, is_master=False):
        super().__init__()
        self.playlist = playlist
        self.index = 0
        self.app = app
        self.next_callback = next_callback
        self.is_master = is_master  # ★ 追加

        self.setStyleSheet("background-color: black;")
        self.setWindowFlags(Qt.FramelessWindowHint)

        # 表示用ラベル
        self.label = QLabel()

        self.label.setGeometry(self.rect())
        self.label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        self.overlay = QLabel(self)
        self.overlay.setStyleSheet("background-color: black;")
        self.overlay.setGeometry(self.rect())
        self.overlay.hide()

        # VLCプレイヤー
        self.vlc_instance = vlc.Instance()
        self.player = None

        self.overlay = QLabel(self)
        self.overlay.setStyleSheet("background-color: black;")
        self.overlay.setGeometry(0, 0, 1, 1)  # 後でリサイズ
        self.overlay.hide()

        self.animations = []
        self.first_show = True

        # ESCで終了
        shortcut = QShortcut(QKeySequence("Escape"), self)
        shortcut.activated.connect(app.quit)

    def stop_video(self):
        if self.player:
            self.player.stop()
            self.player.release()
            self.player = None

    def show_media(self):
        if self.index >= len(self.playlist):
            self.index = 0

        item = self.playlist[self.index]
        media_type = item["type"]

        if not self.first_show:
            if self.label.pixmap() is not None:
                self.fade_out(self.label, 500)
        else:
            self.first_show = False

        # 動画停止
        if self.player:
            self.player.stop()
            self.player = None

        # 外部アプリ停止
        if hasattr(self, "process") and self.process:
            self.process.terminate()
            self.process = None

        # ---- 画像 ----
        if media_type == "image":
            pix = QPixmap(item["path"])
            self.set_scaled_pixmap(pix)
            self.fade_in(self.label, 800)

            if self.is_master:
                QTimer.singleShot(item.get("duration", 5000), self.next_callback)

        # ---- PDF画像フォルダ ----
        elif media_type == "pdf_images":
            folder = item["folder"]

            if not os.path.exists(folder):
                print("[ERROR] Folder not found:", folder)
                if self.is_master:
                    self.next_callback()
                return

            files = sorted(os.listdir(folder))
            self.pdf_pages = [
                os.path.join(folder, f)
                for f in files
                if f.lower().endswith(".png")
            ]

            if not self.pdf_pages:
                print("[ERROR] No PNG files in:", folder)
                if self.is_master:
                    self.next_callback()
                return

            self.pdf_index = 0
            self.show_pdf_page(item)

        # ---- 動画 ----
        elif media_type == "video":
            self.overlay.setGeometry(self.rect())
            self.overlay.show()
            self.fade_out(self.overlay, 800)

            self.player = self.vlc_instance.media_player_new()
            media = self.vlc_instance.media_new(item["path"])
            self.player.set_media(media)

            if self.is_master:
                def check_end():
                    if self.player is None:
                        return
                    state = self.player.get_state()
                    if state in (vlc.State.Ended, vlc.State.Stopped):
                        self.next_callback()
                        return
                    QTimer.singleShot(200, check_end)
                QTimer.singleShot(200, check_end)

            self.showFullScreen()
            self.repaint()

            win_id = int(self.winId())
            system = platform.system()

            if system == "Windows":
                QTimer.singleShot(50, lambda: self.player.set_hwnd(win_id) or self.player.play())
            else:
                QTimer.singleShot(150, lambda: self.player.set_xwindow(win_id) or self.player.play())

        # ---- 外部アプリ ----
        elif media_type == "app":
            self.process = QProcess(self)
            self.process.start(item["path"])

            if self.is_master:
                QTimer.singleShot(item.get("duration", 5000), self.close_app_and_next)


    def fade_widget(self, widget, start, end, duration=800):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.start()

    def fade_out(self, widget, duration=800):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)

        # ★ アニメーションを保持
        self.animations.append(anim)

        def finish():
            widget.hide()
            widget.setGraphicsEffect(None)
            self.animations.remove(anim)

        anim.finished.connect(finish)

        anim.start()

        # ★ フェード終了後に hide() と effect の解除
        def finish():
            widget.hide()
            widget.setGraphicsEffect(None)
        QTimer.singleShot(duration, lambda: (widget.hide(), widget.setGraphicsEffect(None)))

    def fade_in(self, widget, duration=800):
        widget.show()
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)

        # ★ アニメーションを保持
        self.animations.append(anim)

        # 終了後に effect を外し、アニメーションを削除
        def finish():
            widget.setGraphicsEffect(None)
            self.animations.remove(anim)

        anim.finished.connect(finish)
        anim.start()

        QTimer.singleShot(duration, lambda: widget.setGraphicsEffect(None))

    def show_pdf_page(self, item):
        if self.pdf_index >= len(self.pdf_pages):
            if self.is_master:
                self.next_callback()
            return

        page_path = self.pdf_pages[self.pdf_index]
        pix = QPixmap(page_path)

        # 縦横比維持＋画面内に収める
        self.set_scaled_pixmap(pix)

        # フェードイン
        self.fade_in(self.label, 800)

        self.pdf_index += 1

        if self.is_master:
            QTimer.singleShot(item.get("duration", 5000), lambda: self.show_pdf_page(item))


    def set_scaled_pixmap(self, pix):
        # ウィンドウのサイズ
        # ラベルのサイズを基準にする
        win_w = self.label.width()
        win_h = self.label.height()

        # 画像のサイズ
        img_w = pix.width()
        img_h = pix.height()

        # 縦横比を維持して最大サイズを計算
        scale = min(win_w / img_w, win_h / img_h)

        target_w = int(img_w * scale)
        target_h = int(img_h * scale)

        scaled_pix = pix.scaled(
            target_w,
            target_h,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.label.setPixmap(scaled_pix)

    def close_app_and_next(self):
        if hasattr(self, "process") and self.process:
            self.process.terminate()
            self.process = None
        self.next_callback()

    def resizeEvent(self, event):
        self.label.setGeometry(self.rect())
        super().resizeEvent(event)

    def resizeEvent(self, event):
        self.label.setGeometry(self.rect())
        super().resizeEvent(event)

def main():
    app = QApplication(sys.argv)

    # --- プレイリスト例 ---
    playlistA = [
        {"type": "image", "path": "imagesA/imga1.jpg"},
        {"type": "video", "path": "videosA/a_movie.mp4"},
        {"type": "image", "path": "imagesA/imga2.jpg"},
        {"type": "pdf_images", "folder": "KDA2026_pages", "duration": 5000}
    ]

    playlistB = [
        {"type": "image", "path": "imagesB/imgb1.jpg"},
        {"type": "video", "path": "videosB/b_movie.mp4"},
        {"type": "image", "path": "imagesB/imgb2.jpg"},
        {"type": "image", "path": "imagesB/imgb3.jpg"},
    ]

    def next_step():
        print("next_step called")

        winA.index = (winA.index + 1) % len(winA.playlist)
        winB.index = (winB.index + 1) % len(winB.playlist)
        print ("winA:index=",winA.index)
        print ("winB:index=",winB.index)
        winA.show_media()
        winB.show_media()

    # --- ウィンドウ作成 ---
    winA = MediaWindow(playlistA, app, next_step, is_master=True)
    winB = MediaWindow(playlistB, app, next_step, is_master=False)

    screens = app.screens()
    if len(screens) < 2:
        print("2画面が必要です")
        sys.exit(1)

    # 画面A
    geoA = screens[0].geometry()
    winA.setGeometry(geoA)
    winA.showFullScreen()

    # 画面B
    geoB = screens[1].geometry()
    winB.setGeometry(geoB)
    winB.showFullScreen()

    ## --- 同期タイマー（5秒ごと） ---
    #timer = QTimer()
    #timer.timeout.connect(lambda: (winA.show_media(), winB.show_media()))
    #timer.start(5000)

    # 初回表示
    winA.show_media()
    winB.show_media()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
