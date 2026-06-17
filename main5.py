import sys
import glob
import vlc
import platform
import os
import random
import json
import subprocess
import re
import configparser
from pathlib import Path


from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PySide6.QtGui import QPixmap, QKeySequence, QShortcut, QTransform, QFont
from PySide6.QtCore import Qt, QTimer, QProcess, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtCore import QPropertyAnimation
from PySide6.QtCore import QUrl

from transitions.fade import FadeTransition
from transitions.crossfade import CrossFadeTransition
from transitions.slide_crossfade import SlideCrossFadeTransition
from transitions.cardflip import CardFlipTransition
from PySide6.QtWebEngineWidgets import QWebEngineView

from logger import DailyLogger

class MediaWindow(QWidget):
    def __init__(self, playlist, app, role, sync, logger):
        super().__init__()

        self.playlist = playlist
        self.index = 0
        self.app = app
        self.role = role      # "a" or "b"
        self.sync = sync      # ★ 追加

        self.setStyleSheet("background-color: black;")
        self.setWindowFlags(Qt.FramelessWindowHint)

        # 表示用ラベル
        self.label = QLabel(self)

        self.label.setGeometry(self.rect())
        self.label.setAlignment(Qt.AlignCenter)

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

        self.text_label = QLabel(self)
        self.text_label.setStyleSheet("background-color: transparent;")
        self.text_label.setWordWrap(True)
        self.text_label.hide()

        self.webview = QWebEngineView(self)
        self.webview.setGeometry(self.rect())
        self.webview.hide()

        self.logger = logger   # ★ これが必要！

        self.original_geometry = self.label.geometry()

        # ESCで終了
        shortcut = QShortcut(QKeySequence("Escape"), self)
        shortcut.activated.connect(app.quit)

    def stop_video(self):
        if self.player:
            self.player.stop()
            self.player.release()
            self.player = None

    def show_media(self):

        if getattr(self, "_transition_running", False):
            return

        if getattr(self, "_showing", False):
            return
        self._showing = True

        # ★ 前の画像を完全に消す（これが重要）
        self.label.clear()
        self.label.setStyleSheet("background-color: transparent;")
        self.label.hide()

        self.text_label.hide()
        self.text_label.clear()

        # ★ WebView も一旦隠す（描画順序の乱れを防ぐ）
        self.webview.hide()

        # ★ すべてのタイマーを停止（これが重要）
        try:
            self.timer.stop()
        except:
            pass
        try:
            self.transition_timer.stop()
        except:
            pass

        try:

            self._transition_done = False

            if self.index >= len(self.playlist):
                self.index = 0

            # if self.prev_pixmap is not None:
            #    self.prev_pixmap = self.get_scaled_pixmap(self.prev_pixmap)

            # ★ まず前の Web を必ず片付ける（マスター／サブ共通）
            if hasattr(self, "webview"):
                self.webview.hide()
                self.webview.lower()

            self.label.show()

            item = self.playlist[self.index]
            media_type = item["type"]

            self.logger.write(self.role, 
                              f"show_media() : {self.role}: {item['type']} を表示開始 index={self.index}")

            # --- 動画停止 ---
            if self.player:
                self.player.stop()
                self.player = None

            # --- 外部アプリ停止 ---
            if hasattr(self, "process") and self.process:
                self.process.terminate()
                self.process = None

            # ★ 前回のアニメーションを全部止める
            # for anim in self.animations:
            #    anim.stop()
            # self.animations.clear()

            # ---- 画像 ----
            if media_type == "image":

                self.webview.stackUnder(self.label)
                self.apply_logo(item.get("logo"))
                self.apply_text(item.get("text"))

                pix = QPixmap(item["path"])
                self.logger.write(self.role,
                    f"[Image] [{self.role}] index={self.index} path={item['path']} isNull={pix.isNull()}"
                )
                if pix.isNull():
                    self.show_error(f"画像が読み込めません: {item['path']}")
                    return

                scaled = self.get_scaled_pixmap(pix)

                self.logger.write(self.role, f"show_media() : image を表示開始")

                # 初回
                if self.prev_pixmap is None:
                    self.label.setPixmap(scaled)
                    self.prev_pixmap = scaled
                    QTimer.singleShot(item.get("duration", 5000), self._next_item)
                    return

                # ★ ランダムトランジション
                transition = self.choose_transition()
                self._transition_running = True

                # ★ トランジション実行
                transition.run(self.prev_pixmap, scaled, self._after_transition)

                self.prev_pixmap = scaled

            # ---- PDF画像フォルダ ----
            elif media_type == "pdf_images":
                folder = item["folder"]

                self.logger.write(self.role, 
                    f"show_media():[PDF] [{self.role}] index={self.index} path={item['folder']} "
                )

                if not os.path.exists(folder):
                    print("[ERROR] Folder not found:", folder)
                    self.logger.write(self.role, 
                        f"show_media():[ERROR] Folder not found:[{self.role}] index={self.index} path={item['folder']} "
                    )
                    QTimer.singleShot(10, self._next_item)
                    return

                files = sorted(os.listdir(folder))
                self.pdf_pages = [
                    os.path.join(folder, f)
                    for f in files
                    if f.lower().endswith(".png")
                ]

                if not self.pdf_pages:
                    print("[ERROR] No PNG files in:", folder)
                    self.logger.write(self.role, 
                        f"show_media():[ERROR] No PNG files in:[{self.role}] index={self.index} path={item['folder']} "
                    )
                    QTimer.singleShot(10, self._next_item)
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
                duration = item.get("duration", None)
                if duration:
                    QTimer.singleShot(duration, self._next_item)
                else:
                    QTimer.singleShot(500, self._check_app_running)

            elif media_type == "web":
                self.show_web(item)
                return

            # ★ プレイリスト1周終了を検知
            if self.index == len(self.playlist) - 1:
                self.sync.finished(self.role)   # role = "a" or "b"

        finally:
            self._showing = False

    def fade_out(self, widget, duration=800):

        self.logger.write(self.role,  f"fade_out() : fade_out(開始)")

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

        self.logger.write(self.role, f"show_in() : fade_in(開始)")

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

        self.logger.write(self.role, f"show_pdf_page() : PDF開始")

        self.apply_logo(item.get("logo"))

        if self.pdf_index >= len(self.pdf_pages):
            self._next_item()
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
            self.next_item()

    def _close_app_and_next(self):
        try:
            self.app_process.terminate()  # 正常終了を試みる
            QTimer.singleShot(500, self._kill_if_alive)
        except:
            pass

    def _kill_if_alive(self):
        if self.app_process.poll() is None:
            self.app_process.kill()  # 強制終了
            self.next_item()

    def show_web(self, item):
        self.apply_logo(item.get("logo"))

        self.logger.write(self.role, 
            f"[Web] [{self.role}] index={self.index} url={item['url']} "
        )

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

        # ★ ロゴを WebView の上に重ねる
        if hasattr(self, "logo_label"):
            self.logo_label.raise_()

        # ★ スクロール設定を保存
        self.web_scroll_enabled = item.get("scroll", False)
        self.web_scroll_speed = item.get("scroll_speed", 1.0)

        # ★ ページ読み込み完了後にスクロール開始
        self.webview.loadFinished.connect(self._start_web_scroll)

        QTimer.singleShot(duration, self._close_web_and_next)


    def _start_web_scroll(self, ok):
        if not ok:
            return

        if not self.web_scroll_enabled:
            return

        speed = self.web_scroll_speed

        js = f"""
            var scrollY = 0;
            var speed = {speed};
            if (window._scrollTimer) {{
                clearInterval(window._scrollTimer);
            }}
            window._scrollTimer = setInterval(function() {{
                scrollY += speed;
                window.scrollTo(0, scrollY);
            }}, 30);
        """

        self.webview.page().runJavaScript(js)

    def _close_web_and_next(self):
        # WebView を隠す（破棄しない）
        if hasattr(self, "webview"):
            self.webview.hide()
            self.webview.lower()  # Z-order を下げる

        # ★ スクロール停止
        self.webview.page().runJavaScript(
            "if (window._scrollTimer) clearInterval(window._scrollTimer);"
        )

        self._next_item()

    def _convert_vimeo_url(self, url: str) -> str:
        # すでに埋め込みURLならそのまま
        if "player.vimeo.com/video" in url:
            return url

        # 通常URLから動画IDを抽出
        # 例: https://vimeo.com/123456789
        match = re.search(r"vimeo\.com/(\d+)", url)
        if not match:
            return url  # Vimeoでなければそのまま

        video_id = match.group(1)

        # 埋め込みURLを生成
        embed_url = (
            f"https://player.vimeo.com/video/{video_id}"
            "?autoplay=1&muted=1&loop=1&title=0&byline=0&portrait=0"
        )
        return embed_url

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

        self.logger.write(self.role, 
            f"get_scaled_pixmap() [{self.role}] height={pix.height()} width={pix.width()} "
        )

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
        self.next_item()

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
        return FadeTransition(self)
        # return random.choice(self.transitions)

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

        self.logger.write(self.role, f"_after_transition() : role={self.role} 開始")

        if self._transition_done:
            return
        self._transition_done = True
        self._transition_running = False

        # ★ ラベルの状態を完全リセット（これが絶対必要）
        self.label.setGraphicsEffect(None)
        self.label.setGeometry(0, 0, self.width(), self.height())
        # self.label.setOpacity(1.0)  # ← QLabel には opacity が無いので effect 経由なら不要
        self.label.setGraphicsEffect(None)

        # ★ pixmap を再セット（opacity=0 のままの事故を防ぐ）
        self.label.setPixmap(self.prev_pixmap)

        # 次の画像へ進む
        item = self.playlist[self.index]
        duration = item.get("duration", 5000)
        QTimer.singleShot(duration, self._next_item)

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
        self._check_video_end()

    def _check_video_end(self):
        if self.player is None:
            return

        state = self.player.get_state()
        if state in (vlc.State.Ended, vlc.State.Stopped):
            self._next_item()
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


    def apply_text(self, text_info):
        if not text_info:
            self.text_label.hide()
            return

        value = text_info.get("value", "")
        font_size = text_info.get("font_size", 48)
        color = text_info.get("color", "#FFFFFF")
        font_name = text_info.get("font", "Noto Sans JP")
        bg = text_info.get("bg_color", "transparent")

        offset_x = text_info.get("offset_x", 0)
        offset_y = text_info.get("offset_y", 0)

        # テキスト設定
        self.text_label.setText(value)
        self.text_label.setFont(QFont(font_name, font_size))
        self.text_label.setStyleSheet(
            f"color: {color}; background-color: {bg};"
        )

        # 画面幅の80%
        max_width = int(self.width() * 0.8)

        # --- Step1: wrapなしで幅を測る ---
        self.text_label.setWordWrap(False)
        self.text_label.adjustSize()
        natural_width = self.text_label.width()

        # --- Step2: 幅が80%を超えたらwrapをONにする ---
        if natural_width > max_width:
            self.text_label.setFixedWidth(max_width)
            self.text_label.setWordWrap(True)
            self.text_label.adjustSize()
        else:
            # wrap不要 → 自然な幅のまま
            self.text_label.setFixedWidth(natural_width)

        # --- 位置決め ---
        if "x" in text_info and "y" in text_info:
            self.text_label.move(text_info["x"], text_info["y"])
        else:
            self._apply_text_position(
                text_info.get("pos", "top-left"),
                offset_x,
                offset_y
            )

        self.text_label.raise_()
        self.text_label.show()

    def _apply_text_position(self, pos, offset_x=0, offset_y=0):
        w = self.width()
        h = self.height()
        tw = self.text_label.width()
        th = self.text_label.height()

        margin = 20

        if pos == "top-left":
            x = margin + offset_x
            y = margin + offset_y

        elif pos == "top-right":
            x = w - tw - margin + offset_x
            y = margin + offset_y

        elif pos == "bottom-left":
            x = margin + offset_x
            y = h - th - margin + offset_y

        elif pos == "bottom-right":
            x = w - tw - margin + offset_x
            y = h - th - margin + offset_y

        elif pos == "center":
            x = (w - tw) // 2 + offset_x
            y = (h - th) // 2 + offset_y

        self.text_label.move(int(x), int(y))

    def on_sync_command(self, cmd):
        # if cmd == "REPEAT":
        #     self._next_item()

        if cmd.startswith("START_PAIR_"):
            pair = int(cmd.split("_")[-1])
            fname = f"playlist{self.role.upper()}{pair}.json"
            self.playlist = load_playlist(fname)
            self.index = 0
            self.show_media()

    def _next_item(self):

        self.logger.write(self.role, f"_next_item() : role={self.role} 開始")
        self.logger.write(self.role, 
            f"playlist length={len(self.playlist)} index={self.index} role={self.role}"
        )

        if getattr(self, "error_mode", False):
            return  # ★ エラー発生後は進行停止

        if getattr(self, "_transition_running", False):
            return

        if getattr(self, "_nexting", False):
            return
        self._nexting = True

        self.index += 1
        if self.index >= len(self.playlist):
            self.index = 0

        self.show_media()
        self._nexting = False

    def show_error(self, message):
        html = f"""
        <html>
        <body style="background:black; color:white; text-align:center; font-size:40px;">
            <h1 style="margin-top:20%;">コンテンツが見つかりません</h1>
            <p style="font-size:28px;">{message}</p>
        </body>
        </html>
        """

        self.webview.setHtml(html)
        self.webview.show()
        self.webview.raise_()
        self.label.hide()

        # ★ エラーモードに入る（以降の進行を止める）
        self.error_mode = True

        # PairSync にも通知
        self.sync.error(self.role, message)

        self.logger.write(self.role, f"[{self.role}] ERROR: {message}")

def load_config():
    config = configparser.ConfigParser()
    with open("config.ini", "r", encoding="utf-8") as f:
        config.read_file(f)

    return {
        "mode": config.get("display", "mode", fallback="dual").strip().lower(),
        "fallback_to_single": config.getboolean("display", "fallback_to_single", fallback=True),
        "path_a": config.get("playlist", "path_a", fallback="playlistA"),
        "path_b": config.get("playlist", "path_b", fallback="playlistB"),
        "allow_single_when_b_missing": config.getboolean(
            "playlist", "allow_single_when_b_missing", fallback=True
        ),
    }

class PairSync:
    def __init__(self):
        self.current_pair = 1
        self.a_cycles = 0
        self.b_cycles = 0
        self.winA = None
        self.winB = None
        self.error_flag = False

    def error(self, role, message):
        self.error_flag = True
        print(f"[PairSync] ERROR from {role}: {message}")

    def register_windows(self, winA, winB):
        self.winA = winA
        self.winB = winB

    def finished(self, role):

        if self.error_flag:
            return  # ★ エラー発生後はペア切り替え停止
        
        if role == "a":
            self.a_cycles += 1
        else:
            self.b_cycles += 1

        # --- 同期ルール ---
        # A/B 両方が 1 周したら次のペアへ
        if self.a_cycles >= 1 and self.b_cycles >= 1:
            self.next_pair()

        # 1) どちらかがまだ1回も終わっていない → 同じペアを続行
        # if self.a_cycles == 0 or self.b_cycles == 0:
        #     self.send(role, "REPEAT")
        #     return

        # # 2) a が FINISHED した時点で b が1回以上終わっている → 次のペアへ
        # if role == "a" and self.b_cycles >= 1:
        #     self.next_pair()
        #     return

        # # 3) b が FINISHED したが a がまだ終わっていない → b をループ
        # if role == "b" and self.a_cycles == 0:
        #     self.send("b", "REPEAT")
        #     return

        # # 4) a がループ中に b も終わった → b をループ
        # if role == "b" and self.a_cycles >= 1:
        #     self.send("b", "REPEAT")
        #     return

    def send(self, role, cmd):
        if role == "a":
            self.winA.on_sync_command(cmd)
        else:
            self.winB.on_sync_command(cmd)

    def next_pair(self):
        # 次のペア番号を仮に計算
        next_pair = self.current_pair + 1

        # 次のペアのファイル名
        fnameA = f"playlistA{next_pair}.json"
        fnameB = f"playlistB{next_pair}.json"

        # ★ ファイルが存在しなければ pair1 に戻す
        if not (os.path.exists(fnameA) and os.path.exists(fnameB)):
            next_pair = 1

        # ★ ここが重要：同じペアに戻るときは START_PAIR を送らない
        if next_pair == self.current_pair:
            # カウンタだけリセットして同じペアを続行
            self.a_cycles = 0
            self.b_cycles = 0
            return

        # ペア番号を更新
        self.current_pair = next_pair

        # カウンタリセット
        self.a_cycles = 0
        self.b_cycles = 0

        # A/B に新しいペアを開始させる
        self.winA.on_sync_command(f"START_PAIR_{self.current_pair}")
        self.winB.on_sync_command(f"START_PAIR_{self.current_pair}")

def load_playlist(path=str):
    p = Path(path)
    if not p.exists():
        return []
    try:
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except:
        return []

def load_playlist_pair(base_a: str, base_b: str, pair_number: int):
    file_a = f"{base_a}{pair_number}.json"
    file_b = f"{base_b}{pair_number}.json"

    playlistA = load_playlist(file_a)
    playlistB = load_playlist(file_b)

    if not playlistA:
        return None, None  # A が無いならこのペアは存在しない

    # B が無い場合は None のまま返す（fallback ロジックが後で処理）
    return playlistA, playlistB


# ---------------------------------------------------------
# メイン処理
# ---------------------------------------------------------
def main():
    app = QApplication(sys.argv)

    # ロガー
    logger = DailyLogger(base_dir="logs", prefix="signage_")

    # 同期エンジン
    sync = PairSync()

    cfg = load_config()
    mode = cfg["mode"]
    fallback_to_single = cfg["fallback_to_single"]
    allow_single_when_b_missing = cfg["allow_single_when_b_missing"]

    base_a = cfg["path_a"].replace(".json", "")
    base_b = cfg["path_b"].replace(".json", "")

    screens = app.screens()
    screen_count = len(screens)

    print(f"[INFO] Requested mode={mode}, screens={screen_count}")

    # -----------------------------------------------------
    # ペア番号 1 を読み込む
    # -----------------------------------------------------
    pair_number = 1
    playlistA, playlistB = load_playlist_pair(base_a, base_b, pair_number)

    if not playlistA:
        print("[ERROR] playlistA1.json が見つかりません。")
        sys.exit(1)

    # -----------------------------------------------------
    # fallback ロジック
    # -----------------------------------------------------
    if mode == "dual" and screen_count < 2 and fallback_to_single:
        print("[WARN] dual モードだがディスプレイが1枚 → single に自動切替")
        mode = "single"

    if mode == "dual" and not playlistB and allow_single_when_b_missing:
        print("[WARN] playlistB1.json が無い → single に自動切替")
        mode = "single"

    # -----------------------------------------------------
    # next_step（ペア番号の自動進行）
    # -----------------------------------------------------
    winA = None
    winB = None

    def next_step():
        nonlocal winA, winB, mode, pair_number, playlistA, playlistB

        # 次のアイテムへ
        winA.index = (winA.index + 1) % len(winA.playlist)
        winA.show_media()

        if mode == "dual":
            winB.index = (winB.index + 1) % len(winB.playlist)
            winB.show_media()

        # ペアの最後まで再生したら次のペアへ
        if winA.index == 0:  # A のループ完了でペア切替
            pair_number += 1

            # 次のペアを読み込む
            nextA, nextB = load_playlist_pair(base_a, base_b, pair_number)

            if not nextA:
                # ペアが無い → 1 に戻る
                pair_number = 1
                nextA, nextB = load_playlist_pair(base_a, base_b, pair_number)

            playlistA = nextA
            winA.playlist = playlistA
            winA.index = 0

            if mode == "dual":
                if nextB:
                    playlistB = nextB
                    winB.playlist = playlistB
                    winB.index = 0
                else:
                    print("[WARN] B の次ペアが無い → A のみ再生に切替")
                    mode = "single"

    # -----------------------------------------------------
    # 1画面モード
    # -----------------------------------------------------
    if mode == "single":
        print("[INFO] Running in SINGLE display mode")

        winA = MediaWindow(playlistA, app, "A", sync, logger)

        geoA = screens[0].geometry()
        winA.setGeometry(geoA)
        winA.showFullScreen()

        winA.show_media()
        sys.exit(app.exec())

    # -----------------------------------------------------
    # 2画面モード
    # -----------------------------------------------------
    else:
        print("[INFO] Running in DUAL display mode")

        winA = MediaWindow(playlistA, app, "A", sync, logger)
        winB = MediaWindow(playlistB, app, "B", sync, logger)

        geoA = screens[0].geometry()
        geoB = screens[1].geometry()

        winA.setGeometry(geoA)
        winA.showFullScreen()

        winB.setGeometry(geoB)
        winB.showFullScreen()

        winA.show_media()
        winB.show_media()

        sys.exit(app.exec())


# ---------------------------------------------------------
# エントリーポイント
# ---------------------------------------------------------
if __name__ == "__main__":
    main()
