from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect
from PySide6.QtGui import QTransform
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QSequentialAnimationGroup

from .base import TransitionBase

class FadeTransition(TransitionBase):
    def run(self, old_pix, new_pix, finished):
        self.parent.logger.write(self.parent.role, f"FadeTransition start")

        parent = self.parent
        label = parent.label

        parent._transition_running = True

        # エフェクトをセット
        effect = QGraphicsOpacityEffect(label)
        label.setGraphicsEffect(effect)

        # --- フェードアウト ---
        anim1 = QPropertyAnimation(effect, b"opacity")
        anim1.setDuration(600)
        anim1.setStartValue(1.0)
        anim1.setEndValue(0.0)

        # --- フェードイン ---
        anim2 = QPropertyAnimation(effect, b"opacity")
        anim2.setDuration(600)
        anim2.setStartValue(0.0)
        anim2.setEndValue(1.0)

        # --- 2つのアニメーションを直列で実行 ---
        group = QSequentialAnimationGroup(label)  # ★ 親を label にする（重要）
        # group = QSequentialAnimationGroup()

        group.addAnimation(anim1)
        group.addAnimation(anim2)

        # フェードアウト後に画像を差し替える
        def on_fade_out_finished():
            label.setPixmap(new_pix)

        anim1.finished.connect(on_fade_out_finished)

        # 最後に1回だけ callback を呼ぶ
        def on_finished():
            self.parent.logger.write(self.parent.role, f"FadeTransition finishied")

            label.setGraphicsEffect(None)
            finished()

        group.finished.connect(on_finished)

        # ★ parent.animations に登録しない（stop() で殺されない）
        group.start()
