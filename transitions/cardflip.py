import math
from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QSequentialAnimationGroup
from PySide6.QtGui import QTransform
from .base import TransitionBase

class CardFlipTransition(TransitionBase):
    def run(self, old_pix, new_pix, finished):

        self.parent.logger.write(self.parent.role,f"CardFlipTransition start")

        parent = self.parent
        label = parent.label
        
        label.setPixmap(old_pix)

        effect = QGraphicsOpacityEffect(label)
        label.setGraphicsEffect(effect)

        # 1. old をフェードアウト（カードが裏返るイメージ）
        fade_out = QPropertyAnimation(effect, b"opacity")
        fade_out.setDuration(300)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)

        # 2. new をフェードイン（カードの裏側）
        fade_in = QPropertyAnimation(effect, b"opacity")
        fade_in.setDuration(300)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)

        group = QSequentialAnimationGroup(label)

        group.addAnimation(fade_out)
        group.addAnimation(fade_in)

        def swap_pix():
            label.setPixmap(new_pix)

        fade_out.finished.connect(swap_pix)

        def on_finished():
            self.parent.logger.write(self.parent.role,f"CardFlipTransition finished")

            label.setGraphicsEffect(None)
            finished()

        group.finished.connect(on_finished)
        group.start()
