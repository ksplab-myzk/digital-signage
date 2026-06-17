import sys
import glob
import subprocess
import vlc
import platform
import os
import random

from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PySide6.QtGui import QPixmap, QKeySequence, QShortcut
from PySide6.QtCore import Qt, QTimer, QProcess, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtCore import QPropertyAnimation

from transitions.fade import FadeTransition
from transitions.crossfade import CrossFadeTransition
from transitions.slide_crossfade import SlideCrossFadeTransition
from transitions.cardflip import CardFlipTransition

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

        self.transitions = [
            FadeTransition(self),
            CrossFadeTransition(self),
            SlideCrossFadeTransition(self),
            CardFlipTransition(self)
        ]

        self.prev_pixmap = None
        self.prev_type = None

        self.prev_pixmap = None      # 前回の画像
        self.prev_type = None        # 前回のメディアタイプ（image/video）
        self.animations = []         # アニメーション保持
        self.first_show = True       # 初回フラグ

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
            scaled = self.get_scaled_pixmap(pix)

            # 初回
            if self.prev_pixmap is None:
                self.label.setPixmap(scaled)
                self.prev_pixmap = scaled
                if self.is_master:
                    QTimer.singleShot(item.get("duration", 5000), self.next_callback)
                return

            # ★ ランダムトランジションを選択
            transition = self.choose_transition()

            # ★ トランジション実行
            transition.run(self.prev_pixmap, scaled, self._after_transition)

            self.prev_pixmap = scaled

            #if self.is_master:
            #    QTimer.singleShot(item.get("duration", 5000), self.next_callback)

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

            #if self.is_master:
            #    QTimer.singleShot(item.get("duration", 5000), self.close_app_and_next)

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
        # QTimer.singleShot(duration, lambda: (widget.hide(), widget.setGraphicsEffect(None)))

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

        #QTimer.singleShot(duration, lambda: widget.setGraphicsEffect(None))


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

        #if self.is_master:
        #    QTimer.singleShot(item.get("duration", 5000), lambda: self.show_pdf_page(item))

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

    def get_scaled_pixmap(self, pix):
        if pix.isNull():
            return pix

        # ウィンドウサイズに合わせてスケール
        w = self.width()
        h = self.height()

        return pix.scaled(
            w, h,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

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

    def choose_transition(self):
        return random.choice(self.transitions)

    def transition_to_video(self, next_pix):
        transition = self.choose_transition()

        def after():
            self.overlay.setOpacity(1.0)
            self.overlay.show()
            self.play_video()
            self.fade_out_overlay()

        transition.run(self.prev_pixmap, next_pix, after)

    def transition_from_video(self, next_pix):
        transition = self.choose_transition()

        def after_overlay():
            self.stop_video()
            transition.run(None, next_pix, self._after_transition)

        self.fade_in_overlay(after_overlay)

    def _after_transition(self):

        # トランジション終了後に次の画像へ進むための待ち時間をセット
        item = self.playlist[self.index]
        duration = item.get("duration", 5000)

        # トランジション終了後に次の画像へ
        if self.is_master:
            QTimer.singleShot(10, self.next_callback)


def main():
    app = QApplication(sys.argv)

    # --- プレイリスト例 ---
    playlistA = [
        {"type": "image", "path": "imagesA/imga1.jpg"},
        {"type": "image", "path": "imagesA/imga2.jpg"},
        {"type": "image", "path": "imagesA/imga3.png"},
        {"type": "image", "path": "imagesA/imga4.png"},
        {"type": "image", "path": "imagesA/imga5.png"},
        {"type": "image", "path": "imagesA/imga6.png"},
        {"type": "image", "path": "imagesA/imga7.png"},
        {"type": "image", "path": "imagesA/imga8.png"},
    ]

    playlistB = [
        {"type": "image", "path": "imagesB/imgb1.jpg"},
        {"type": "image", "path": "imagesB/imgb2.jpg"},
        {"type": "image", "path": "imagesB/imgb3.jpg"},
        {"type": "image", "path": "imagesB/imgb4.jpg"},
        {"type": "image", "path": "imagesB/imgb5.jpg"},
        {"type": "image", "path": "imagesB/imgb6.jpg"},
        {"type": "image", "path": "imagesB/imgb7.jpg"},
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
