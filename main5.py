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
import datetime
import argparse
import psutil   # pip install psutil
import gc

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
    def __init__(self, playlist, app, role, sync, logger, pixmap_cache, scaled_cache):
        super().__init__()

        self.playlist = playlist
        self.index = 0
        self.app = app
        self.role = role      # "a" or "b"
        self.sync = sync      # ★ 追加
        self.pixmap_cache = pixmap_cache
        self.scaled_cache = scaled_cache

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

        self.prev_pixmap = None      # 前回の画像
        self.prev_type = None        # 前回のメディアタイプ（image/video）
        self.animations = []         # アニメーション保持
        self.first_show = True       # 初回フラグ

        self.logo_label = QLabel(self)
        self.logo_label.setAttribute(Qt.WA_TranslucentBackground)  # ★透過PNGに必須
        self.logo_label.setStyleSheet("background: transparent;")   # ★背景透明
        self.logo_label.setScaledContents(True)  # サイズ調整したい場合
        self.logo_label.raise_()  # 最前面に出す

        self.text_label = QLabel(self)
        self.text_label.setStyleSheet("background-color: transparent;")
        self.text_label.setWordWrap(True)
        self.text_label.hide()

        # self.webview = QWebEngineView(self)
        # self.webview.setGeometry(self.rect())
        # self.webview.hide()
        self.webview = None   # ★必ず初期化しておく

        self.logger = logger   # ★ これが必要！

        self.original_geometry = self.label.geometry()

        # 黒画面(初回のみのためキャッシュ不要)
        self.black_pixmap = QPixmap(self.width(), self.height())
        self.black_pixmap.fill(Qt.black)


        # ESCで終了
        shortcut = QShortcut(QKeySequence("Escape"), self)
        shortcut.activated.connect(app.quit)

    def stop_video(self):
        if self.player:
            self.player.stop()
            self.player.release()
            self.player = None

    def show_media(self):

        self.logger.write(self.role, f"show_media() : {self.role}: 開始")

        if getattr(self, "_transition_running", False):
            self.logger.write(self.role, f"show_media() : {self.role}: _transition_running return")
            return

        if getattr(self, "_showing", False):
            self.logger.write(self.role, f"show_media() : {self.role}: _showing return")
            return

        self._showing = True

        # ★ 前の画像を完全に消す（これが重要）
        self.label.clear()
        self.label.setStyleSheet("background-color: transparent;")
        self.label.hide()

        self.text_label.hide()
        self.text_label.clear()

        # ★ WebView も一旦隠す（描画順序の乱れを防ぐ）
        if self.webview is not None:
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

            #if self.index >= len(self.playlist):
            #    self.sync.finished(self.role)   # role = "a" or "b"
                #self.index = 0

            # if self.prev_pixmap is not None:
            #    self.prev_pixmap = self.get_scaled_pixmap(self.prev_pixmap)

            # ★ まず前の Web を必ず片付ける（マスター／サブ共通）
            if hasattr(self, "webview") and self.webview is not None:
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

                if self.webview is not None:
                    self.webview.stackUnder(self.label)
                self.apply_text(item.get("text"))
                self.apply_logo(item.get("logo"))

                self.logger.write(self.role, f"[DEBUG] loading image: {item['path']}")

                path = item["path"]
                if path not in self.pixmap_cache:
                    self.pixmap_cache[path] = QPixmap(path)

                pix = self.pixmap_cache[path]

                self.logger.write(self.role,
                    f"[Image] [{self.role}] index={self.index} path={path} isNull={pix.isNull()}"
                )
                if pix.isNull():
                    self.show_error(f"画像が読み込めません: {item['path']}")
                    return

                print(f"[DEBUG] pix.isNull() = {pix.isNull()}")

                if path not in self.scaled_cache:
                    self.scaled_cache[path] = self.get_scaled_pixmap(self.pixmap_cache[path])
                scaled = self.scaled_cache[path]

                self.logger.write(self.role, f"show_media() : image を表示開始")

                # 初回
                if self.prev_pixmap is None:
                    # self.label.setPixmap(scaled)
                    self._set_label_pixmap(scaled, "show_media:199")

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
                self.logger.write(self.role, 
                    f"show_media():[PDF] show_pdf_page() Called in:[{self.role}] index={self.index} path={item['folder']} "
                )

            # ---- 動画 ----
            elif media_type == "video":

                self.apply_logo(item.get("logo"))

                # 1. 動画開始前に黒背景を作る
                # black = QPixmap(self.width(), self.height())
                # black.fill(Qt.black)

                # 2. トランジション実行（画像→黒）
                transition = self.choose_transition()
                transition.run(self.prev_pixmap, self.black_pixmap, self._after_transition_video_start)

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
            # if self.index == len(self.playlist) - 1:
            #    self.sync.finished(self.role)   # role = "a" or "b"

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

        self.logger.write(self.role, f"show_pdf_page() : PDF開始 pdf_index={self.pdf_index}")

        self.apply_logo(item.get("logo"))

        if self.pdf_index >= len(self.pdf_pages):
            self.logger.write(self.role, f"show_pdf_page() : PDF終了(最終頁) pdf_index={self.pdf_index}")
            self.pdf_index = 0
            self._transition_running = False
            self._next_item()
            return

        page_path = self.pdf_pages[self.pdf_index]

        if page_path not in self.pixmap_cache:
            self.pixmap_cache[page_path] = QPixmap(page_path)
        pix = self.pixmap_cache[page_path]

        orientation = item.get("orientation", None)

        if orientation == "portrait":
            # 縦長に強制
            if pix.width() > pix.height():
                pix = pix.transformed(QTransform().rotate(90), Qt.SmoothTransformation)

        elif orientation == "landscape":
            # 横長に強制
            if pix.height() > pix.width():
                pix = pix.transformed(QTransform().rotate(90), Qt.SmoothTransformation)

        if page_path not in self.scaled_cache:
            self.scaled_cache[page_path] = self.get_scaled_pixmap(self.pixmap_cache[page_path],orientation)
        scaled = self.scaled_cache[page_path]

        # 初回
        if self.prev_pixmap is None:
            # self.label.setPixmap(scaled)
            self._set_label_pixmap(scaled, "show_pdf_page")

            self.prev_pixmap = scaled
            QTimer.singleShot(item.get("duration", 5000), lambda: self._next_pdf_page(item))
            return

        # トランジション実行（前ページ→次ページ）
        transition = self.choose_transition()
        transition.run(self.prev_pixmap, scaled, lambda: self._after_pdf_transition(item, scaled))

        self.logger.write(self.role, f"show_pdf_page() : PDF終了 pdf_index={self.pdf_index}")

    def _next_pdf_page(self, item):
        self.pdf_index += 1
        self.show_pdf_page(item)

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

        self.logger.write(self.role,
            f"[Web BEFORE] index={self.index} "
            f"showing={getattr(self, '_showing', None)} "
            f"transition_running={getattr(self, '_transition_running', None)} "
            f"label_visible={self.label.isVisible()} "
            f"web_visible={self.webview.isVisible() if self.webview else None}"
        )

        self.apply_logo(item.get("logo"))

        self.logger.write(self.role, 
            f"[Web] [{self.role}] index={self.index} url={item['url']} "
        )
        self._transition_running = False

        url = item["url"]
        duration = item.get("duration", 10000)

        # # WebView がなければ作る
        # if not hasattr(self, "webview"):
        #     self.webview = QWebEngineView(self)

        if self.webview is not None:
            self.webview.deleteLater()

        self.webview = QWebEngineView(self)

        self.webview.setAttribute(Qt.WA_TranslucentBackground, True)
        self.webview.setStyleSheet("background: transparent;")

        self.webview.setGeometry(self.rect())
        self.webview.load(QUrl(url))

        #self.label.lower()  
        #self.label.hide()
        #self.webview.show()
        #self.webview.raise_()

        QTimer.singleShot(50, lambda: self._show_web_delayed(item))

        self.logger.write(self.role,
            f"[Web AFTER] index={self.index} "
            f"showing={getattr(self, '_showing', None)} "
            f"transition_running={getattr(self, '_transition_running', None)} "
            f"label_visible={self.label.isVisible()} "
            f"web_visible={self.webview.isVisible()}"
        )

        # ★ ロゴを WebView の上に重ねる
        if hasattr(self, "logo_label"):
            self.logo_label.raise_()

        # ★ スクロール設定を保存
        self.web_scroll_enabled = item.get("scroll", False)
        self.web_scroll_speed = item.get("scroll_speed", 1.0)

        # ★ ページ読み込み完了後にスクロール開始
        self.webview.loadFinished.connect(self._start_web_scroll)

        QTimer.singleShot(duration, self._close_web_and_next)

    def _show_web_delayed(self, item):
        self.label.lower()
        self.label.hide()
        self.webview.show()
        self.webview.raise_()

    def _start_web_scroll(self, ok):

        # self.logger.write(self.role,  f"[Web] [{self.role}] start_web_scroll " )

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

        # self.logger.write(self.role, f"[Web] [{self.role}] start_web_scroll END")

    def _close_web_and_next(self):

        self.logger.write(self.role, 
            f"[Web] [{self.role}] close_web_end_next() "
        )

        # # WebView を隠す（破棄しない）
        # if hasattr(self, "webview"):
        #     self.webview.hide()
        #     self.webview.lower()  # Z-order を下げる

        # ★ スクロール停止
        self.webview.page().runJavaScript(
            "if (window._scrollTimer) clearInterval(window._scrollTimer);"
        )

        # WebView を破棄する
        if hasattr(self, "webview") and self.webview is not None:
            self.webview.setParent(None)
            self.webview.page().deleteLater()
            self.webview.deleteLater()
            self.webview = None
            gc.collect()

        self.logger.write(self.role, 
            f"[Web] [{self.role}] close_web_end_next() END"
        )

        self._next_item()

    def _set_label_pixmap(self, pix, context=""):
        if pix is None or (hasattr(pix, "isNull") and pix.isNull()):
            print(f"[PIXMAP ERROR] {context} pixmap is None or null")
            return
        self.label.setPixmap(pix)

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

        # self.label.setPixmap(scaled_pix)
        self._set_label_pixmap(scaled_pix, "set_scaled_pixmap")

    def get_scaled_pixmap(self, pix, orientation=None):

        self.logger.write(self.role, f"get_scaled_pixmap() Start " )

        if pix is None:
            print("[DEBUG] get_scaled_pixmap: pix is None")
            return None
    
        if pix.isNull():
            print("[DEBUG] get_scaled_pixmap: pix isNull")
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
        if self.webview is not None:
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
        # self.label.setPixmap(self.prev_pixmap)
        # self._set_label_pixmap(self.prev_pixmap, "_after_transition")
        # if self.prev_pixmap is not None:
        #     self.logger.write(self.role, f"_after_transition() : role={self.role} prev_pixmap not none")
        #     self._set_label_pixmap(self.prev_pixmap, "_after_transition")

        # if self.prev_pixmap is None and hasattr(self, "_transition_new_pix"):
        #     self._set_label_pixmap(self._transition_new_pix, "_after_transition:new_pix")
        #     self.prev_pixmap = self._transition_new_pix
        if  hasattr(self, "_transition_new_pix"):
            self._set_label_pixmap(self._transition_new_pix, "_after_transition:new_pix")
            self.prev_pixmap = self._transition_new_pix

        # 次の画像へ進む
        item = self.playlist[self.index]

        self.logger.write(self.role, f"_after_transition() : role={self.role} next_item={item}")

        duration = item.get("duration", 5000)
        # duration = 10
        QTimer.singleShot(duration, self._next_item)

        self.logger.write(self.role, f"_after_transition() : role={self.role} 終了")

    def _after_transition_video_start(self):
        item = self.playlist[self.index]

        # 動画プレイヤー初期化
        self.player = self.vlc_instance.media_player_new()
        media = self.vlc_instance.media_new(item["path"])
        self.player.set_media(media)

        # ★ VLC のスケーリング設定（mac の暫定対処）
        self.player.video_set_scale(0)              # 自動スケーリング
        self.player.video_set_aspect_ratio("16:9")  # 画面比率固定
        
        win_id = int(self.winId())

        # OSごとに埋め込み方法を変える
        if platform.system() == "Windows":
            QTimer.singleShot(50, lambda: self.player.set_hwnd(win_id) or self.player.play())
        elif platform.system() == "Linux":
            QTimer.singleShot(150, lambda: self.player.set_xwindow(win_id) or self.player.play())
        else:  # macOS
            QTimer.singleShot(500, lambda: self.player.set_nsobject(win_id) or self.player.play())
            # 埋め込み後に強制リサイズ（再描画イベント発生）
            QTimer.singleShot(600, lambda: self.resize(self.width(), self.height()))

        # ★元のロジック：動画終了監視（ポーリング）
        self._check_video_end()

    def _check_video_end(self):
        if self.player is None:
            return

        # self.logger.write(self.role,
        #    f"[_check_video_end()] [{self.role}] index={self.index}  Start")

        state = self.player.get_state()

        # self.logger.write(self.role,
        #     f"[_check_video_end() BEFORE] index={self.index} state={state} "
        #     f"showing={getattr(self, '_showing', None)} "
        #     f"transition_running={getattr(self, '_transition_running', None)} "
        #     f"label_visible={self.label.isVisible()} "
        #     f"web_visible={self.webview.isVisible() if hasattr(self, 'webview') else None}"
        # )
        
        # self.logger.write(self.role,
        #    f"[_check_video_end()] [{self.role}] index={self.index}  state ={state}")

        if state in (vlc.State.Ended, vlc.State.Stopped):
            # self._transition_from_video()   # ★ここが重要
            # self._next_item()

            self.logger.write(self.role,
                f"[_check_video_end()] [{self.role}] index={self.index}  state ={state}")

            self._transition_running = False   # ★ 応急処置

            # VLC の描画先を切り離す（最重要）
            #try:
            #    self.player.set_hwnd(0)
            #except:
            #    pass

            # ★ OSごとに描画先を切り離す（最重要）
            self.detach_video_output()

            if self.player:
                self.player.stop()
                self.player = None

            # label の残留フレームを消す
            self.label.clear()
            self.label.repaint()
            self.label.hide()
            self.label.lower()

            # ★ここで index を進める（必須）
            self.index += 1
            if self.index >= len(self.playlist):
                # self.index = 0
                # ★ 応急処置：ここで finished() を呼ぶ
                self.sync.finished(self.role)
                return

            # 次のコンテンツを確認
            next_item = self.playlist[self.index]

            if next_item["type"] == "video":
                self._after_transition_video_start()

            elif next_item["type"] in ("image", "pdf"):
                self._transition_from_video()

            elif next_item["type"] == "web":
                # ★ WEB の場合はフェードを使わず直接表示
                # self.player.stop()
                # self.player = None
                self.show_web(next_item)

            return

        QTimer.singleShot(200, self._check_video_end)


    def detach_video_output(self):
        try:
            if sys.platform.startswith("win"):
                self.player.set_hwnd(0)
            elif sys.platform.startswith("linux"):
                self.player.set_xwindow(0)
            elif sys.platform.startswith("darwin"):
                self.player.set_nsobject(0)
        except Exception as e:
            print("detach_video_output error:", e)

    def _transition_from_video(self):

        # 動画停止
        if self.player:
            self.player.stop()
            self.player = None

        # 黒背景を old_pix として扱う
        # black = QPixmap(self.width(), self.height())
        # black.fill(Qt.black)

        # 次の画像を読み込む
        next_item = self.playlist[self.index]

        # 画像以外はまず「フェードなしで素直に show_media()」に逃がす
        if next_item["type"] != "image":
            print(f"[TRANSITION] next_item type={next_item['type']} → skip fade, call show_media()")
            self.show_media()
            return

        if next_item["path"] not in self.pixmap_cache:
            self.pixmap_cache[next_item["path"]] = QPixmap(next_item["path"])
        raw = self.pixmap_cache[next_item["path"]]

        if raw.isNull():
            print(f"[TRANSITION ERROR] QPixmap({next_item['path']}) is null")
            self.show_media()  # とりあえず落ちないように逃がす
            return

        if next_item["path"] not in self.scaled_cache:
            self.scaled_cache[next_item["path"]] = self.get_scaled_pixmap(self.pixmap_cache[next_item["path"]])
        next_pix = self.self.scaled_cache[next_item["path"]]

        # トランジション実行（黒→画像）
        transition = self.choose_transition()
        transition.run(self.black_pixmap, next_pix, self._after_transition)

    def _after_pdf_transition(self, item, scaled):
        self.prev_pixmap = scaled
        self.pdf_index += 1

        QTimer.singleShot(item.get("duration", 5000), lambda: self.show_pdf_page(item))

    def apply_logo(self, logo_info):

        self.logger.write(self.role,
            f"[apply_logo()] [{self.role}] index={self.index} Start")

        if not logo_info:

            self.logger.write(self.role,
                f"[apply_logo()] [{self.role}] Logo Nothing return")
            self.logo_label.hide()
            return

        # ロゴ画像読み込み
        pix = QPixmap(logo_info["path"])
        if pix.isNull():
            self.logger.write(self.role,
                f"[apply_logo()] [{self.role}] Logo pix null return")
            self.logo_label.hide()
            return

        # サイズ指定
        w, h = logo_info.get("size", [pix.width(), pix.height()])
        self.logo_label.setPixmap(pix)
        # self._set_label_pixmap(pix, "apply_logo")

        self.logo_label.resize(w, h)

        # 位置指定
        pos = logo_info.get("pos", "top-left")
        self.current_logo_pos = pos  # resizeEvent 用

        offset_x = logo_info.get("offset_x", 0)
        offset_y = logo_info.get("offset_y", 0)

        self.set_logo_position(pos, w, h, offset_x, offset_y)

        print("logo geometry:", self.logo_label.geometry())
        print("logo pos:", self.logo_label.pos())
        print("logo size:", self.logo_label.size())

        self.logo_label.raise_()
        self.logo_label.show()

        self.logger.write(self.role,
            f"[apply_logo()] [{self.role}] index={self.index} End")

    def set_logo_position(self, pos, w, h, offset_x=0, offset_y=0):

        self.logger.write(self.role, f"[set_logo_position()] [{self.role}] Start")

        margin = 20
        win_w = self.width()
        win_h = self.height()

        if pos == "top-left":
            x = margin + offset_x
            y = margin + offset_y

        elif pos == "top-right":
            x = win_w - w - margin + offset_x
            y = margin + offset_y

        elif pos == "bottom-left":
            x = margin + offset_x
            y = win_h - h - margin + offset_y

        elif pos == "bottom-right":
            x = win_w - w - margin + offset_x
            y = win_h - h - margin + offset_y

        elif pos == "center":
            x = (win_w - w)//2 + offset_x
            y = (win_h - h)//2 + offset_y

        else:
            x = margin + offset_x
            y = margin + offset_y

        self.logo_label.move(x, y)

        self.logger.write(self.role, f"[set_logo_position()] [{self.role}] End")

    def apply_text(self, text_info):

        self.logger.write(self.role,
            f"[apply_text()] [{self.role}] index={self.index} Start")

        if not text_info:
            self.text_label.hide()

            self.logger.write(self.role,
                f"[apply_text()] [{self.role}] text Nothing return")

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

        self.logger.write(self.role,
            f"[apply_text()] [{self.role}] index={self.index} End")

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

    def on_sync_command(self, cmd, playlist_folder, playlist_file):
        # if cmd == "REPEAT":
        #     self._next_item()

        self.logger.write(self.role, f"on_sync_command() : role={self.role} 開始")

        if cmd.startswith("START_PAIR_"):

            # ★ 状態フラグをリセット
            self._nexting = False
            self.transition_running = False
            self.pdf_index = 0   # PDF用のインデックスもリセット推奨

            # pair = int(cmd.split("_")[-1])
            # fname = f"playlist{self.role.upper()}{pair}.json"
            self.playlist = load_playlist(playlist_file, playlist_folder)
            self.index = 0
            self.show_media()

        self.logger.write(self.role, f"on_sync_command() : role={self.role} 終了")

    def _next_item(self):

        self.logger.write(self.role, f"_next_item() : role={self.role} 開始")
        self.logger.write(self.role, f"_next_item(): transition_running={getattr(self, '_transition_running', None)}")

        self.logger.write(self.role, 
            f"playlist length={len(self.playlist)} index={self.index} role={self.role}"
        )

        if getattr(self, "error_mode", False):
            self.logger.write(self.role, f"_next_item() : role={self.role} error_mode! return")
            return  # ★ エラー発生後は進行停止

        if getattr(self, "_transition_running", False):
            self.logger.write(self.role, f"_next_item() : role={self.role} transition_running return")
            return

        if getattr(self, "_nexting", False):
            self.logger.write(self.role, f"_next_item() : role={self.role} _nexting return")
            return
        
        self._nexting = True
        self.index += 1

        if self.index >= len(self.playlist) :
            # self.index = 0
            self.logger.write(self.role, f"_next_item() : role={self.role} last_item return")
            self.sync.finished(self.role)
            return  # ★ 最終アイテムの場合は進行停止

        self.show_media()
        self._nexting = False

        self.logger.write(self.role, f"_next_item() : role={self.role} 終了")

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

    def reset_state(self):
        # プレイリストのインデックスをリセット
        self.index = 0

        # PDF のページインデックスがある場合はリセット
        if hasattr(self, "pdf_index"):
            self.pdf_index = 0

        # 遷移中フラグをリセット
        if hasattr(self, "transition_running"):
            self.transition_running = False

        # next_item の二重呼び出し防止フラグをリセット
        if hasattr(self, "_nexting"):
            self._nexting = False

    def reset_webview(self):
        if self.webview is not None:
            self.webview.setParent(None)
            self.webview.page().deleteLater()
            self.webview.deleteLater()
            self.webview = None
            gc.collect()

def load_config():

    config = configparser.ConfigParser()
    with open("config.ini", "r", encoding="utf-8") as f:
        config.read_file(f)

    return {
        "mode": config.get("display", "mode", fallback="dual").strip().lower(),
        "fallback_to_single": config.getboolean("display", "fallback_to_single", fallback=True),

        "playlist_folder": config.get("playlist", "folder", fallback="playlists"),

        "pairs_a": config.get("playlist", "pairs_a", fallback="pairsA"),
        "pairs_b": config.get("playlist", "pairs_b", fallback="pairsB"),
        "path_a": config.get("playlist", "path_a", fallback="playlistA"),
        "path_b": config.get("playlist", "path_b", fallback="playlistB"),

        "allow_single_when_b_missing": config.getboolean(
            "playlist", "allow_single_when_b_missing", fallback=True
        ),

        "enable_time_control" : config.getboolean("system", "enable_time_control"),
        "start_time" : config.get("system", "start_time"),
        "end_time" : config.get("system", "end_time")
    }

class PairSync:

    def __init__(self, logger, playlist_folder, pairsA, pairsB, enable_time_control, start_time, end_time):
        self.current_pair = 0
        self.a_cycles = 0
        self.b_cycles = 0
        self.winA = None
        self.winB = None
        self.error_flag = False

        self.playlist_folder = playlist_folder
        self.pairsA = pairsA
        self.pairsB = pairsB
        self.logger = logger 

        self.pairsA = load_pairs(pairsA, playlist_folder)
        self.pairsB = load_pairs(pairsB, playlist_folder)

        self.enable_time_control = enable_time_control
        self.start_time = start_time
        self.end_time = end_time

    def error(self, role, message):
        self.error_flag = True
        print(f"[PairSync] ERROR from {role}: {message}")

    def register_windows(self, winA, winB):
        self.winA = winA
        self.winB = winB

    def finished(self, role):

        self.logger.write(role, f"finished() : role={role} 開始")

        # --- 時刻チェック ---
        if self.check_time_range():
            self.logger.write(role, f"finished() : 終了時間経過 End")
            sys.exit(0)

        if self.error_flag:
            return  # ★ エラー発生後はペア切り替え停止
        
        if role == "A":
            self.a_cycles += 1
            self.logger.write(role, f"finished() : a_cyles ={self.a_cycles} ")
        else:
            self.b_cycles += 1
            self.logger.write(role, f"finished() : b_cyles ={self.b_cycles} ")

        # --- シングルモード ---
        if self.mode == "single":
            if self.a_cycles >= 1:
                self.logger.write(role, "finished() : SINGLE → next_pair call")
                self.next_pair()
            self.logger.write(role, f"finished() : role={role} 終了")
            return

        # --- デュアルモード（従来の処理） ---
        # --- 同期ルール ---
        # A/B 両方が 1 周したら次のペアへ
        if self.a_cycles >= 1 and self.b_cycles >= 1:
            self.logger.write(role, f"finished() : role={role} next_pair call")
            self.next_pair()

        self.logger.write(role, f"finished() : role={role} 終了")

    # def send(self, role, cmd):
    #     if role == "A":
    #         self.winA.on_sync_command(cmd)
    #     else:
    #         self.winB.on_sync_command(cmd)

    def next_pair(self):

        self.logger.write("", f"next_pair() 開始")

        # 次のペア番号を仮に計算
        next_pair = self.current_pair + 1

        # 範囲外なら 0 に戻す（ループ）
        if next_pair >= len(self.pairsA):
            next_pair = 0
            self.winA.reset_webview()
            if self.winB:
                self.winB.reset_webview()

        # プレイリストフォルダ
        playlist_folder = self.playlist_folder

        fileA = self.pairsA[next_pair]
        fileB = self.pairsB[next_pair]

        # 次のペアのファイルパス（フォルダ基準）
        fnameA = os.path.join(playlist_folder, fileA)
        fnameB = os.path.join(playlist_folder, fileB)
        self.logger.write("", f"next_pair() NEXT playlistA={fnameA} playlistB={fnameB} ")

        # ★ ファイルが存在しなければ pair1 に戻す
        if not (os.path.exists(fnameA) and os.path.exists(fnameB)):
            self.logger.write("", f"next_pair() playlistA={fnameA} playlistB={fnameB} Not exist")
            next_pair = 0

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

        # --- シングルモード ---
        if self.mode == "single":
            self.winA.reset_state()
            self.winA.on_sync_command(f"START_PAIR_{self.current_pair}", playlist_folder, fileA)

        else:
            # -- デュアルモード
            self.winA.reset_state()
            self.winB.reset_state()

            # A/B に新しいペアを開始させる
            self.winA.on_sync_command(f"START_PAIR_{self.current_pair}", playlist_folder, fileA)
            self.winB.on_sync_command(f"START_PAIR_{self.current_pair}", playlist_folder, fileB)

        self.logger.write("", f"next_pair() 終了")

    def check_time_range(self):
        if not self.enable_time_control:
            return False

        now = datetime.datetime.now().time()
        ed = datetime.datetime.strptime(self.end_time, "%H:%M").time()

        # 終了時間を過ぎたら True を返す
        return now > ed

def load_pairs(path: str, playlist_folder: str):
    base_dir = Path(__file__).resolve().parent
    p = base_dir / playlist_folder / path

    if not p.exists():
        return []

    try:
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except:
        return []


def load_playlist(path: str, playlist_folder: str):

    # playlist_folder/path を絶対パス化
    base_dir = Path(__file__).resolve().parent
    playlist_dir = base_dir / playlist_folder
    p = playlist_dir / path

    # p = Path(path)
    if not p.exists():
        return []
    try:
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except:
        return []

def load_playlist_pair(base_a: str, base_b: str, pair_number: int, playlist_folder: str):
    # file_a = f"{base_a}{pair_number}.json"
    # file_b = f"{base_b}{pair_number}.json"

    playlistA = load_playlist(base_a, playlist_folder)
    playlistB = load_playlist(base_b, playlist_folder)

    if not playlistA:
        return None, None  # A が無いならこのペアは存在しない

    # B が無い場合は None のまま返す（fallback ロジックが後で処理）
    return playlistA, playlistB

# 多重起動チェック
LOCK_FILE = "digital_signage.lock"

def check_single_instance():
    if os.path.exists(LOCK_FILE):
        # 既存の PID を読む
        with open(LOCK_FILE, "r") as f:
            pid = int(f.read().strip())

        # PID が生きているか確認
        if psutil.pid_exists(pid):
            print("[WARN] 既に起動しています → 多重起動を終了します")
            sys.exit(0)
        else:
            # 死んでいる PID → ロックファイルを削除して再作成
            os.remove(LOCK_FILE)

    # 新しい PID を書き込む
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

def cleanup_lock_file():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

# ---------------------------------------------------------
# メイン処理
# ---------------------------------------------------------
def main():

    app = QApplication(sys.argv)

    # ロガー
    logger = DailyLogger(base_dir="logs", prefix="signage_")

    check_single_instance()

    cfg = load_config()
    mode = cfg["mode"]
    fallback_to_single = cfg["fallback_to_single"]
    allow_single_when_b_missing = cfg["allow_single_when_b_missing"]

    enable_time_control = cfg["enable_time_control"]
    start_time = cfg["start_time"]
    end_time = cfg["end_time"]

    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--time-control", action="store_true",
                        help="時間制御を無効にする")
    args = parser.parse_args()
    if args.time_control:
        enable_time_control = False

    # 起動時刻の制御
    if enable_time_control :
        now = datetime.datetime.now().time()
        st = datetime.datetime.strptime(start_time, "%H:%M").time()
        ed = datetime.datetime.strptime(end_time, "%H:%M").time()

        if not (st <= now <= ed):
            print("[INFO] 動作時間外のため終了します")
            logger.write("", "[INFO] 動作時間外のため終了します")
            sys.exit(0)

    playlist_folder = cfg["playlist_folder"]
    # base_a = cfg["path_a"].replace(".json", "")
    # base_b = cfg["path_b"].replace(".json", "")

    pairs_a = cfg["pairs_a"]
    pairs_b = cfg["pairs_b"]

    # pixmapのキャッシュ
    pixmap_cache = {}
    scaled_cache = {}

    # 同期エンジン
    sync = PairSync(logger, playlist_folder, pairs_a, pairs_b, enable_time_control, start_time, end_time)

    firstA = sync.pairsA[0]
    firstB = sync.pairsB[0]

    screens = app.screens()
    screen_count = len(screens)

    print(f"[INFO] Requested mode={mode}, screens={screen_count}")
    logger.write("", f"[INFO] Requested mode={mode}, screens={screen_count}")

    # -----------------------------------------------------
    # ペア番号 1 を読み込む
    # -----------------------------------------------------
    pair_number = 0
    playlistA, playlistB = load_playlist_pair(firstA, firstB, pair_number, playlist_folder)

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

    sync.mode = mode

    winA = None
    winB = None

    # -----------------------------------------------------
    # 1画面モード
    # -----------------------------------------------------
    if mode == "single":
        print("[INFO] Running in SINGLE display mode")

        winA = MediaWindow(playlistA, app, "A", sync, logger, pixmap_cache, scaled_cache)
        sync.register_windows(winA, None)

        geoA = screens[0].geometry()
        winA.setGeometry(geoA)
        winA.showFullScreen()

        winA.show_media()
        try:
            sys.exit(app.exec())
        finally:
            cleanup_lock_file()

    # -----------------------------------------------------
    # 2画面モード
    # -----------------------------------------------------
    else:
        print("[INFO] Running in DUAL display mode")

        winA = MediaWindow(playlistA, app, "A", sync, logger, pixmap_cache, scaled_cache)
        winB = MediaWindow(playlistB, app, "B", sync, logger, pixmap_cache, scaled_cache)

        sync.register_windows(winA, winB)

        geoA = screens[0].geometry()
        geoB = screens[1].geometry()

        winA.setGeometry(geoA)
        winA.showFullScreen()

        winB.setGeometry(geoB)
        winB.showFullScreen()

        winA.show_media()
        winB.show_media()

        try:
            sys.exit(app.exec())
        finally:
            cleanup_lock_file()

# ---------------------------------------------------------
# エントリーポイント
# ---------------------------------------------------------
if __name__ == "__main__":
    main()
