import sys
import os
import math
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QGraphicsOpacityEffect
)
from PyQt5.QtGui import QPixmap, QTransform
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QSize

class FadeTest(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Fade Test")
        self.setGeometry(100, 100, 1280, 720)

        # 画像リスト
        self.images = [
            "images/img1.jpg",
            "images/img2.jpg",
            "images/img3.jpg"
        ]
        self.index = 0

        # ラベル
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setGeometry(self.rect())

        # ボタン
        self.btn_fade = QPushButton("Fade In/Out", self)
        self.btn_fade.clicked.connect(self.fade_transition)

        self.btn_cross = QPushButton("Crossfade", self)
        self.btn_cross.clicked.connect(self.crossfade_transition)

        self.btn_slide = QPushButton("slide_crossfade", self)
        self.btn_slide.clicked.connect(self.slide_crossfade)

        self.btn_flip = QPushButton("Cardflip", self)
        self.btn_flip.clicked.connect(self.card_flip)

        self.btn_flip3d = QPushButton("Cardflip3D", self)
        self.btn_flip3d.clicked.connect(self.card_flip_3d)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.btn_fade)
        layout.addWidget(self.btn_cross)
        layout.addWidget(self.btn_slide)
        layout.addWidget(self.btn_flip)
        layout.addWidget(self.btn_flip3d)
        self.setLayout(layout)

        # 初期画像
        self.show_image(self.images[self.index])

        self.animations = []

    def resizeEvent(self, event):
        self.label.setGeometry(self.rect())
        super().resizeEvent(event)

    # -------------------------
    # 画像表示（縦横比維持）
    # -------------------------
    def show_image(self, path):
        pix = QPixmap(path)
        if pix.isNull():
            return

        win_w = self.label.width()
        win_h = self.label.height()

        img_w = pix.width()
        img_h = pix.height()

        scale = min(win_w / img_w, win_h / img_h)
        target_w = int(img_w * scale)
        target_h = int(img_h * scale)

        scaled = pix.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.label.setPixmap(scaled)

    # -------------------------
    # フェードイン
    # -------------------------
    def fade_in(self, duration=800):
        effect = QGraphicsOpacityEffect(self.label)
        self.label.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)

        # ★ アニメーションを保持
        self.animations.append(anim)

        def finish():
            # 終了したアニメーションを削除
            self.animations.remove(anim)
            self.label.setGraphicsEffect(None)

        anim.finished.connect(finish)
        anim.start()

    # -------------------------
    # フェードアウト
    # -------------------------
    def fade_out(self, callback=None, duration=800):
        effect = QGraphicsOpacityEffect(self.label)
        self.label.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)

        # ★ アニメーションを保持
        self.animations.append(anim)

        def finish():
            self.animations.remove(anim)
            self.label.setGraphicsEffect(None)
            if callback:
                callback()

        anim.finished.connect(finish)
        anim.start()

    # -------------------------
    # フェードイン → フェードアウト
    # -------------------------
    def fade_transition(self):
        self.fade_out(self._after_fade_out)

    def _after_fade_out(self):
        self.index = (self.index + 1) % len(self.images)
        self.show_image(self.images[self.index])
        self.fade_in()

    # -------------------------
    # クロスフェード
    # -------------------------
    def crossfade_transition(self):
        # 現在の pixmap を取得（すでにスケーリング済み）
        current_pix = self.label.pixmap()

        # 古い画像を old_label にコピー
        old_label = QLabel(self)
        old_label.setGeometry(self.label.geometry())
        old_label.setAlignment(Qt.AlignCenter)
        old_label.setPixmap(current_pix)
        old_label.show()

        # 新しい画像を new_label にセット（スケーリングしてから）
        new_label = QLabel(self)
        new_label.setGeometry(self.label.geometry())
        new_label.setAlignment(Qt.AlignCenter)

        self.index = (self.index + 1) % len(self.images)
        pix = QPixmap(self.images[self.index])

        # ★ ここが重要：新しい画像も同じスケーリングを適用
        scaled = self.get_scaled_pixmap(pix)  # set_scaled_pixmap と同じ処理
        new_label.setPixmap(scaled)
        new_label.show()

        # エフェクト
        old_effect = QGraphicsOpacityEffect(old_label)
        new_effect = QGraphicsOpacityEffect(new_label)
        old_label.setGraphicsEffect(old_effect)
        new_label.setGraphicsEffect(new_effect)

        old_effect.setOpacity(1.0)
        new_effect.setOpacity(0.0)

        # アニメーション
        anim_old = QPropertyAnimation(old_effect, b"opacity")
        anim_old.setDuration(800)
        anim_old.setStartValue(1.0)
        anim_old.setEndValue(0.0)

        anim_new = QPropertyAnimation(new_effect, b"opacity")
        anim_new.setDuration(800)
        anim_new.setStartValue(0.0)
        anim_new.setEndValue(1.0)

        # アニメーション保持
        self.animations.append(anim_old)
        self.animations.append(anim_new)

        def finish():
            old_label.deleteLater()
            new_label.deleteLater()
            self.label.setPixmap(scaled)  # 最終的に本体ラベルに反映
            self.animations.remove(anim_old)
            self.animations.remove(anim_new)

        anim_new.finished.connect(finish)

        anim_old.start()
        anim_new.start()

    def get_scaled_pixmap(self, pix):
        win_w = self.label.width()
        win_h = self.label.height()

        img_w = pix.width()
        img_h = pix.height()

        scale = min(win_w / img_w, win_h / img_h)
        target_w = int(img_w * scale)
        target_h = int(img_h * scale)

        return pix.scaled(
            target_w, target_h,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

    def slide_crossfade(self):
        w = self.label.width()
        h = self.label.height()

        # --- 古い画像ラベル ---
        old_label = QLabel(self)
        old_label.setGeometry(self.label.geometry())
        old_label.setAlignment(Qt.AlignCenter)
        old_label.setPixmap(self.label.pixmap())
        old_label.show()

        # --- 新しい画像ラベル ---
        new_label = QLabel(self)
        new_label.setGeometry(self.label.geometry())
        new_label.setAlignment(Qt.AlignCenter)

        # 次の画像をスケーリングしてセット
        self.index = (self.index + 1) % len(self.images)
        pix = QPixmap(self.images[self.index])
        scaled = self.get_scaled_pixmap(pix)
        new_label.setPixmap(scaled)

        # 新しい画像は右側からスタート
        new_label.move(w, 0)
        new_label.show()

        # --- エフェクト（透明度） ---
        old_eff = QGraphicsOpacityEffect(old_label)
        new_eff = QGraphicsOpacityEffect(new_label)
        old_label.setGraphicsEffect(old_eff)
        new_label.setGraphicsEffect(new_eff)

        old_eff.setOpacity(1.0)
        new_eff.setOpacity(0.0)

        # --- アニメーション ---
        duration = 800

        # 古い画像：左へスライド
        anim_old_pos = QPropertyAnimation(old_label, b"pos")
        anim_old_pos.setDuration(duration)
        anim_old_pos.setStartValue(old_label.pos())
        anim_old_pos.setEndValue(old_label.pos() - QPoint(w, 0))

        # 古い画像：フェードアウト
        anim_old_op = QPropertyAnimation(old_eff, b"opacity")
        anim_old_op.setDuration(duration)
        anim_old_op.setStartValue(1.0)
        anim_old_op.setEndValue(0.0)

        # 新しい画像：右から中央へスライド
        anim_new_pos = QPropertyAnimation(new_label, b"pos")
        anim_new_pos.setDuration(duration)
        anim_new_pos.setStartValue(QPoint(w, 0))
        anim_new_pos.setEndValue(QPoint(0, 0))

        # 新しい画像：フェードイン
        anim_new_op = QPropertyAnimation(new_eff, b"opacity")
        anim_new_op.setDuration(duration)
        anim_new_op.setStartValue(0.0)
        anim_new_op.setEndValue(1.0)

        # --- アニメーション保持 ---
        self.animations += [anim_old_pos, anim_old_op, anim_new_pos, anim_new_op]

        def finish():
            old_label.deleteLater()
            new_label.deleteLater()
            self.label.setPixmap(scaled)
            for a in [anim_old_pos, anim_old_op, anim_new_pos, anim_new_op]:
                self.animations.remove(a)

        anim_new_op.finished.connect(finish)

        # --- 同時スタート ---
        anim_old_pos.start()
        anim_old_op.start()
        anim_new_pos.start()
        anim_new_op.start()

    def card_flip(self):
        # 現在の画像
        current_pix = self.label.pixmap()

        # 古い画像ラベル
        old_label = QLabel(self)
        old_label.setGeometry(self.label.geometry())
        old_label.setAlignment(Qt.AlignCenter)
        old_label.setPixmap(current_pix)
        old_label.show()

        # 新しい画像ラベル（最初は幅ゼロ）
        new_label = QLabel(self)
        new_label.setGeometry(self.label.geometry())
        new_label.setAlignment(Qt.AlignCenter)

        self.index = (self.index + 1) % len(self.images)
        pix = QPixmap(self.images[self.index])
        scaled = self.get_scaled_pixmap(pix)
        new_label.setPixmap(scaled)

        # 新しい画像は幅0で開始（中央に配置）
        new_label.resize(0, self.label.height())
        new_label.move(self.label.width() // 2, 0)
        new_label.show()

        duration = 400

        # --- 古い画像：幅を縮める（100% → 0%） ---
        anim_old = QPropertyAnimation(old_label, b"size")
        anim_old.setDuration(duration)
        anim_old.setStartValue(old_label.size())
        anim_old.setEndValue(QSize(0, old_label.height()))

        # --- 新しい画像：幅を広げる（0% → 100%） ---
        anim_new = QPropertyAnimation(new_label, b"size")
        anim_new.setDuration(duration)
        anim_new.setStartValue(QSize(0, new_label.height()))
        anim_new.setEndValue(QSize(self.label.width(), new_label.height()))

        # 新しい画像の位置調整（中央から広がる）
        anim_new_pos = QPropertyAnimation(new_label, b"pos")
        anim_new_pos.setDuration(duration)
        anim_new_pos.setStartValue(QPoint(self.label.width() // 2, 0))
        anim_new_pos.setEndValue(QPoint(0, 0))

        # アニメーション保持
        self.animations += [anim_old, anim_new, anim_new_pos]

        def after_old():
            old_label.hide()

        def finish():
            old_label.deleteLater()
            new_label.deleteLater()
            self.label.setPixmap(scaled)
            for a in [anim_old, anim_new, anim_new_pos]:
                self.animations.remove(a)

        anim_old.finished.connect(after_old)
        anim_new_pos.finished.connect(finish)

        # 同時スタート
        anim_old.start()
        anim_new.start()
        anim_new_pos.start()

    def card_flip_3d(self):
        # 古い画像
        old_pix = self.label.pixmap()

        old_label = QLabel(self)
        old_label.setGeometry(self.label.geometry())
        old_label.setAlignment(Qt.AlignCenter)
        old_label.setPixmap(old_pix)
        old_label.show()

        # 新しい画像
        self.index = (self.index + 1) % len(self.images)
        pix = QPixmap(self.images[self.index])
        new_pix = self.get_scaled_pixmap(pix)

        new_label = QLabel(self)
        new_label.setGeometry(self.label.geometry())
        new_label.setAlignment(Qt.AlignCenter)
        new_label.setPixmap(new_pix)
        new_label.hide()  # 最初は隠す

        duration = 600

        # -------------------------
        # 1) 古い画像を「奥に倒れ込む」ように変形
        # -------------------------
        def animate_old(step):
            # step: 0 → 1
            angle = step * 90  # 0° → 90°
            scale = max(0.01, abs(math.cos(math.radians(angle))))
            shear = math.sin(math.radians(angle)) * 0.5  # パース感

            t = QTransform()
            t.shear(shear, 0)
            t.scale(scale, 1)

            transformed = old_pix.transformed(t, Qt.SmoothTransformation)
            old_label.setPixmap(transformed)

            # 90° 付近で新しい画像に切り替え
            if step > 0.5 and not new_label.isVisible():
                new_label.show()
                old_label.hide()

        # -------------------------
        # 2) 新しい画像を「手前に起き上がる」ように変形
        # -------------------------
        def animate_new(step):
            # step: 0 → 1
            angle = (1 - step) * 90  # 90° → 0°
            scale = max(0.01, abs(math.cos(math.radians(angle))))
            shear = math.sin(math.radians(angle)) * 0.5

            t = QTransform()
            t.shear(shear, 0)
            t.scale(scale, 1)

            transformed = new_pix.transformed(t, Qt.SmoothTransformation)
            new_label.setPixmap(transformed)

            if step >= 1.0:
                self.label.setPixmap(new_pix)
                old_label.deleteLater()
                new_label.deleteLater()

        # -------------------------
        # タイマーで 3D アニメーションを実行
        # -------------------------
        steps = 30
        interval = duration // steps
        current = 0

        def tick():
            nonlocal current
            step = current / steps

            if step <= 0.5:
                animate_old(step * 2)
            else:
                animate_new((step - 0.5) * 2)

            current += 1
            if current > steps:
                timer.stop()

        timer = QTimer(self)
        timer.timeout.connect(tick)
        timer.start(interval)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = FadeTest()
    win.show()
    sys.exit(app.exec_())
