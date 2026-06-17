from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QSequentialAnimationGroup
from PySide6.QtGui import QTransform

from .base import TransitionBase

    # -------------------------
    # クロスフェード
    # -------------------------
class CrossFadeTransition(TransitionBase):
    def run(self, old_pix, new_pix, finished):

        self.parent.logger.write(self.parent.role, f"CrossFadeTransition start")

        parent = self.parent
        label = parent.label

        # まず old_pix を表示
        label.setPixmap(old_pix)

        effect = QGraphicsOpacityEffect(label)
        label.setGraphicsEffect(effect)

        # new_pix を裏でセットしておき、opacity でクロスさせる
        # 実際には old→new のフェードに見える
        def set_new_pix():
            label.setPixmap(new_pix)

        # フェードアウト（old → 黒）
        anim_out = QPropertyAnimation(effect, b"opacity")
        anim_out.setDuration(600)
        anim_out.setStartValue(1.0)
        anim_out.setEndValue(0.0)

        # フェードイン（黒 → new）
        anim_in = QPropertyAnimation(effect, b"opacity")
        anim_in.setDuration(600)
        anim_in.setStartValue(0.0)
        anim_in.setEndValue(1.0)

        group = QSequentialAnimationGroup(label)
        group.addAnimation(anim_out)
        group.addAnimation(anim_in)

        anim_out.finished.connect(set_new_pix)

        def on_finished():
            self.parent.logger.write(self.parent.role, f"CrossFadeTransition finished")

            label.setGraphicsEffect(None)
            label.setGeometry(parent.original_geometry)
            finished()

        group.finished.connect(on_finished)
        group.start()

