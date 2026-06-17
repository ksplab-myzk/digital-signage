import sys
import glob
import vlc
import platform
import os
import random
import json
import subprocess

from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PySide6.QtGui import QPixmap, QKeySequence, QShortcut, QTransform
from PySide6.QtCore import Qt, QTimer, QProcess, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtCore import QPropertyAnimation
from PySide6.QtCore import QUrl

from transitions.fade import FadeTransition
from transitions.crossfade import CrossFadeTransition
from transitions.slide_crossfade import SlideCrossFadeTransition
from transitions.cardflip import CardFlipTransition
from PySide6.QtWebEngineWidgets import QWebEngineView

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
        self.label = QLabel(self)

        self.label.setGeometry(self.rect())
        self.label.setAlignment(Qt.AlignCenter)

        # layout = QVBoxLayout()
        # layout.addWidget(self.label)
        # self.setLayout(layout)

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

        self.logo_label = QLabel(self)
        # self.logo_label.setPixmap(QPixmap("logo.png"))
        self.logo_label.setAttribute(Qt.WA_TranslucentBackground)  # ★透過PNGに必須
        self.logo_label.setStyleSheet("background: transparent;")   # ★背景透明
        self.logo_label.setScaledContents(True)  # サイズ調整したい場合
        self.logo_label.raise_()  # 最前面に出す

        self.webview = QWebEngineView(self)
        self.webview.setGeometry(self.rect())
        self.webview.hide()

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

        if self.prev_pixmap is not None:
            self.prev_pixmap = self.get_scaled_pixmap(self.prev_pixmap)

        # ★ まず前の Web を必ず片付ける（マスター／サブ共通）
        if hasattr(self, "webview"):
            self.webview.hide()
            self.webview.lower()

        self.label.show()

        item = self.playlist[self.index]
        media_type = item["type"]

        # --- 動画停止 ---
        if self.player:
            self.player.stop()
            self.player = None

        # --- 外部アプリ停止 ---
        if hasattr(self, "process") and self.process:
            self.process.terminate()
            self.process = None

        # ---- 画像 ----
        if media_type == "image":

            self.webview.stackUnder(self.label)

            self.apply_logo(item.get("logo"))

            pix = QPixmap(item["path"])
            scaled = self.get_scaled_pixmap(pix)

            # 初回
            if self.prev_pixmap is None:
                self.label.setPixmap(scaled)
                self.prev_pixmap = scaled
                if self.is_master:
                    QTimer.singleShot(item.get("duration", 5000), self.next_callback)
                return

            # ★ ランダムトランジション
            transition = self.choose_transition()

            # ★ トランジション実行
            transition.run(self.prev_pixmap, scaled, self._after_transition)

            self.prev_pixmap = scaled

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

            self.apply_logo(item.get("logo"))

            # 1. 動画開始前に黒背景を作る
            black = QPixmap(self.width(), self.height())
            black.fill(Qt.black)

            # 2. トランジション実行（画像→黒）
            transition = self.choose_transition()
            transition.run(self.prev_pixmap, black, self._after_transition_video_start)

            # 3. 動画再生は _after_transition_video_start() で開始

        # ---- 外部アプリ ----
        elif media_type == "app":
            self.process = QProcess(self)
            self.process.start(item["path"])

        elif media_type == "web":
            self.show_web(item)
            return

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

        self.apply_logo(item.get("logo"))

        if self.pdf_index >= len(self.pdf_pages):
            if self.is_master:
                self.next_callback()
            return

        page_path = self.pdf_pages[self.pdf_index]

        pix = QPixmap(page_path)

        orientation = item.get("orientation", None)

        if orientation == "portrait":
            # 縦長に強制
            if pix.width() > pix.height():
                pix = pix.transformed(QTransform().rotate(90), Qt.SmoothTransformation)

        elif orientation == "landscape":
            # 横長に強制
            if pix.height() > pix.width():
                pix = pix.transformed(QTransform().rotate(90), Qt.SmoothTransformation)

        scaled = self.get_scaled_pixmap(pix, orientation)

        # 初回
        if self.prev_pixmap is None:
            self.label.setPixmap(scaled)
            self.prev_pixmap = scaled
            if self.is_master:
                QTimer.singleShot(item.get("duration", 5000), lambda: self._next_pdf_page(item))
            return

        # トランジション実行（前ページ→次ページ）
        transition = self.choose_transition()
        transition.run(self.prev_pixmap, scaled, lambda: self._after_pdf_transition(item, scaled))

    def show_app(self, item):
        self.apply_logo(item.get("logo"))

        cmd = item["command"]
        duration = item.get("duration", None)

        # プロセス起動
        self.app_process = subprocess.Popen(cmd, shell=True)

        if duration:
            # duration 後に終了して次へ
            QTimer.singleShot(duration, self._close_app_and_next)
        else:
            # プロセス終了を監視
            QTimer.singleShot(500, self._check_app_running)

    def _check_app_running(self):
        if self.app_process.poll() is None:
            QTimer.singleShot(500, self._check_app_running)
        else:
            if self.is_master:
                self.next_callback()

    def _close_app_and_next(self):
        try:
            self.app_process.terminate()  # 正常終了を試みる
            QTimer.singleShot(500, self._kill_if_alive)
        except:
            pass

    def _kill_if_alive(self):
        if self.app_process.poll() is None:
            self.app_process.kill()  # 強制終了

        if self.is_master:
            self.next_callback()

    def show_web(self, item):
        self.apply_logo(item.get("logo"))

        url = item["url"]
        duration = item.get("duration", 10000)

        # WebView がなければ作る
        if not hasattr(self, "webview"):
            self.webview = QWebEngineView(self)
            self.webview.setAttribute(Qt.WA_TranslucentBackground, True)
            self.webview.setStyleSheet("background: transparent;")

        self.webview.setGeometry(self.rect())
        self.webview.load(QUrl(url))

        self.label.hide()
        self.webview.show()
        self.webview.raise_()

        if self.is_master:
            QTimer.singleShot(duration, self._close_web_and_next)

    def _close_web_and_next(self):
        # WebView を隠す（破棄しない）
        if hasattr(self, "webview"):
            self.webview.hide()
            self.webview.lower()  # Z-order を下げる

        # スクロール停止
        if hasattr(self, "scroll_timer"):
            self.scroll_timer.stop()

        if self.is_master:
            self.next_callback()

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

    def get_scaled_pixmap(self, pix, orientation=None):
        if pix.isNull():
            return pix

        # ウィンドウサイズに合わせてスケール
        w = self.width()
        h = self.height()

        print ("height=",pix.height())
        print ("witdh=",pix.width())

        # ★ PDF の場合は orientation を優先
        if orientation == "portrait":
            return pix.scaledToHeight(h, Qt.SmoothTransformation)

        if orientation == "landscape":
            return pix.scaledToWidth(w, Qt.SmoothTransformation)

    # ★ 通常画像は従来通り    
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
        self.overlay.setGeometry(self.rect())

        # ★ WebView もフルスクリーンに追従
        self.webview.setGeometry(self.rect())

        # ロゴ位置を再適用
        if self.logo_label.isVisible() and hasattr(self, "current_logo_pos"):
            w = self.logo_label.width()
            h = self.logo_label.height()
            self.set_logo_position(self.current_logo_pos, w, h)

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
            QTimer.singleShot(duration, self.next_callback)

    def _after_transition_video_start(self):
        item = self.playlist[self.index]

        # 動画プレイヤー初期化
        self.player = self.vlc_instance.media_player_new()
        media = self.vlc_instance.media_new(item["path"])
        self.player.set_media(media)

        # 再生開始
        win_id = int(self.winId())
        if platform.system() == "Windows":
            QTimer.singleShot(50, lambda: self.player.set_hwnd(win_id) or self.player.play())
        else:
            QTimer.singleShot(150, lambda: self.player.set_xwindow(win_id) or self.player.play())

        # 動画終了監視
        if self.is_master:
            self._check_video_end()

    def _check_video_end(self):
        if self.player is None:
            return

        state = self.player.get_state()
        if state in (vlc.State.Ended, vlc.State.Stopped):
            self._transition_from_video()
            return

        QTimer.singleShot(200, self._check_video_end)

    def _transition_from_video(self):
        # 動画停止
        self.player.stop()
        self.player = None

        # 黒背景を old_pix として扱う
        black = QPixmap(self.width(), self.height())
        black.fill(Qt.black)

        # 次の画像を読み込む
        next_item = self.playlist[self.index]
        next_pix = self.get_scaled_pixmap(QPixmap(next_item["path"]))

        # トランジション実行（黒→画像）
        transition = self.choose_transition()
        transition.run(black, next_pix, self._after_transition)

    def _after_pdf_transition(self, item, scaled):
        self.prev_pixmap = scaled
        self.pdf_index += 1

        if self.is_master:
            QTimer.singleShot(item.get("duration", 5000), lambda: self.show_pdf_page(item))

    def apply_logo(self, logo_info):
        if not logo_info:
            self.logo_label.hide()
            return

        # ロゴ画像読み込み
        pix = QPixmap(logo_info["path"])
        if pix.isNull():
            self.logo_label.hide()
            return

        # サイズ指定
        w, h = logo_info.get("size", [pix.width(), pix.height()])
        self.logo_label.setPixmap(pix)
        self.logo_label.resize(w, h)

        # 位置指定
        pos = logo_info.get("pos", "top-left")
        self.current_logo_pos = pos  # resizeEvent 用

        self.set_logo_position(pos, w, h)
        self.logo_label.show()

    def set_logo_position(self, pos, w, h):
        margin = 20
        win_w = self.width()
        win_h = self.height()

        if pos == "top-left":
            x, y = margin, margin
        elif pos == "top-right":
            x, y = win_w - w - margin, margin
        elif pos == "bottom-left":
            x, y = margin, win_h - h - margin
        elif pos == "bottom-right":
            x, y = win_w - w - margin, win_h - h - margin
        elif pos == "center":
            x, y = (win_w - w)//2, (win_h - h)//2
        else:
            x, y = margin, margin

        self.logo_label.move(x, y)

def load_playlist(path="playlist.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    app = QApplication(sys.argv)

    # --- プレイリスト例 ---
    playlistA = load_playlist("playlistA.json")

    playlistB = load_playlist("playlistB.json")

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
