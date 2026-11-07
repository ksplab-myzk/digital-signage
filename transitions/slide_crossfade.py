import random

from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtCore import (
    QParallelAnimationGroup,
    QPropertyAnimation,
    QSequentialAnimationGroup,
)

from .base import TransitionBase


class SlideCrossFadeTransition(TransitionBase):
    def run(self, old_pix, new_pix, finished):
        parent = self.parent
        parent.logger.write(parent.role, "SlideCrossFadeTransition start")

        label = parent.label
        generation = getattr(parent, "_pair_generation", 0)

        parent._transition_running = True
        parent._transition_new_pix = new_pix

        if old_pix is not None:
            label.setPixmap(old_pix)
        else:
            label.setPixmap(parent.black_pixmap)

        label.show()
        label.raise_()

        effect = QGraphicsOpacityEffect(label)
        effect.setOpacity(1.0)
        label.setGraphicsEffect(effect)

        direction = random.choice(("left", "right", "up", "down"))
        end_rect = label.geometry()
        offsets = {
            "left": (-end_rect.width(), 0),
            "right": (end_rect.width(), 0),
            "up": (0, -end_rect.height()),
            "down": (0, end_rect.height()),
        }
        offset_x, offset_y = offsets[direction]
        start_rect = end_rect.translated(offset_x, offset_y)
        parent.logger.write(parent.role, f"SlideCrossFadeTransition direction={direction}")

        fade_out = QPropertyAnimation(effect, b"opacity")
        fade_out.setDuration(600)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)

        slide = QPropertyAnimation(label, b"geometry")
        slide.setDuration(600)
        slide.setStartValue(start_rect)
        slide.setEndValue(end_rect)

        fade_in = QPropertyAnimation(effect, b"opacity")
        fade_in.setDuration(600)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)

        def swap_pix():
            if generation != getattr(parent, "_pair_generation", 0):
                return
            label.setPixmap(new_pix)
            label.setGeometry(start_rect)

        seq = QSequentialAnimationGroup(label)
        seq.addAnimation(fade_out)

        sub = QParallelAnimationGroup(label)
        sub.addAnimation(slide)
        sub.addAnimation(fade_in)
        seq.addAnimation(sub)
        parent._transition_group = seq
        fade_out.finished.connect(swap_pix)

        def on_finished():
            if generation != getattr(parent, "_pair_generation", 0):
                return

            label.setGraphicsEffect(None)
            label.setGeometry(end_rect)
            label.setPixmap(new_pix)
            if getattr(parent, "_transition_group", None) is seq:
                parent._transition_group = None
            parent.logger.write(parent.role, "SlideCrossFadeTransition finished")
            finished()

        seq.finished.connect(on_finished)
        seq.start()
