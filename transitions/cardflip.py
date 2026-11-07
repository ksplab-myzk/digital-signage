from PySide6.QtCore import QPropertyAnimation, QSequentialAnimationGroup, QRect

from .base import TransitionBase


class CardFlipTransition(TransitionBase):
    def run(self, old_pix, new_pix, finished):
        parent = self.parent
        parent.logger.write(parent.role, "CardFlipTransition start")

        label = parent.label
        generation = getattr(parent, "_pair_generation", 0)

        parent._transition_running = True
        parent._transition_new_pix = new_pix

        label.setGeometry(parent.rect())
        if old_pix is not None:
            label.setPixmap(old_pix)
        else:
            label.setPixmap(parent.black_pixmap)

        label.show()
        label.raise_()

        full_rect = label.geometry()
        collapsed_rect = QRect(
            full_rect.center().x(),
            full_rect.y(),
            1,
            full_rect.height(),
        )

        flip_out = QPropertyAnimation(label, b"geometry")
        flip_out.setDuration(350)
        flip_out.setStartValue(full_rect)
        flip_out.setEndValue(collapsed_rect)

        flip_in = QPropertyAnimation(label, b"geometry")
        flip_in.setDuration(350)
        flip_in.setStartValue(collapsed_rect)
        flip_in.setEndValue(full_rect)

        group = QSequentialAnimationGroup(label)
        group.addAnimation(flip_out)
        group.addAnimation(flip_in)
        parent._transition_group = group

        def swap_pix():
            if generation != getattr(parent, "_pair_generation", 0):
                return
            label.setPixmap(new_pix)

        flip_out.finished.connect(swap_pix)

        def on_finished():
            if generation != getattr(parent, "_pair_generation", 0):
                return

            label.setGeometry(full_rect)
            label.setPixmap(new_pix)
            if getattr(parent, "_transition_group", None) is group:
                parent._transition_group = None
            parent.logger.write(parent.role, "CardFlipTransition finished")
            finished()

        group.finished.connect(on_finished)
        group.start()
