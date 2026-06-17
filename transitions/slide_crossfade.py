from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect, QLabel
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QSequentialAnimationGroup, QParallelAnimationGroup, QEasingCurve
from PySide6.QtGui import QTransform

from .base import TransitionBase

class SlideCrossFadeTransition(TransitionBase):
    def run(self, old_pix, new_pix, finished):

        self.parent.logger.write(self.parent.role,f"SlideCrossFadeTransition start")

        parent = self.parent
        label = parent.label

        w = label.width()
        h = label.height()

        # old_pix を表示
        label.setPixmap(old_pix)

        # エフェクト
        effect = QGraphicsOpacityEffect(label)
        label.setGraphicsEffect(effect)

        # フェードアウト（old）
        fade_out = QPropertyAnimation(effect, b"opacity")
        fade_out.setDuration(600)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)

        # スライドイン（new）
        geom = parent.original_geometry
        start_rect = geom.translated(w, 0)
        end_rect = geom

        slide = QPropertyAnimation(label, b"geometry")
        slide.setDuration(600)
        slide.setStartValue(start_rect)
        slide.setEndValue(end_rect)

        # フェードイン（new）
        fade_in = QPropertyAnimation(effect, b"opacity")
        fade_in.setDuration(600)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)

        # 2段階構成
        seq = QSequentialAnimationGroup(label)

        # 1段目：old をフェードアウト
        seq.addAnimation(fade_out)

        # old → new 差し替え
        def swap_pix():
            label.setPixmap(new_pix)
            label.setGeometry(start_rect)  # ★ ここが重要（初期位置に戻す）

        fade_out.finished.connect(swap_pix)

        # 2段目：slide + fade_in を並列で
        sub = QParallelAnimationGroup(label)
        sub.addAnimation(slide)
        sub.addAnimation(fade_in)

        seq.addAnimation(sub)

        def on_finished():
            self.parent.logger.write(self.parent.role,f"SlideCrossFadeTransition finishied")

            label.setGraphicsEffect(None)
            label.setGeometry(parent.original_geometry)

            finished()

        seq.finished.connect(on_finished)
        seq.start()
