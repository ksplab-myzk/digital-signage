from PySide6.QtCore import QEasingCurve, Qt, QVariantAnimation
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel

from .base import TransitionBase


class CrossFadeTransition(TransitionBase):
    duration_ms = 1800

    def run(self, old_pix, new_pix, finished):
        parent = self.parent
        parent.logger.write(parent.role, "CrossFadeTransition start")

        label = parent.label
        generation = getattr(parent, "_pair_generation", 0)
        old_pix = old_pix if old_pix is not None else parent.black_pixmap

        parent._transition_running = True
        parent._transition_new_pix = new_pix

        bounds = label.geometry()
        old_layer = self._create_layer(parent, bounds)
        new_layer = self._create_layer(parent, bounds)
        old_layer.show()
        old_layer.raise_()
        new_layer.show()
        new_layer.raise_()
        label.hide()
        parent._crossfade_labels = (old_layer, new_layer)

        old_effect = QGraphicsOpacityEffect(old_layer)
        old_layer.setGraphicsEffect(old_effect)
        new_effect = QGraphicsOpacityEffect(new_layer)
        new_layer.setGraphicsEffect(new_effect)

        max_block_size = min(48, max(8, min(old_pix.width(), old_pix.height()) // 18))
        animation = QVariantAnimation(parent)
        animation.setDuration(self.duration_ms)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.InOutCubic)
        parent._transition_group = animation

        def update_frame(value):
            if generation != getattr(parent, "_pair_generation", 0):
                return

            progress = float(value)
            old_progress = min(1.0, progress / 0.6)
            new_progress = max(0.0, (progress - 0.3) / 0.7)
            old_block_size = 1 + round((max_block_size - 1) * old_progress)
            new_block_size = 1 + round((max_block_size - 1) * (1.0 - new_progress))

            old_layer.setPixmap(self._pixelate(old_pix, old_block_size))
            new_layer.setPixmap(self._pixelate(new_pix, new_block_size))
            old_effect.setOpacity(max(0.0, 1.0 - progress / 0.72))
            new_effect.setOpacity(min(1.0, max(0.0, (progress - 0.28) / 0.72)))

        animation.valueChanged.connect(update_frame)
        update_frame(0.0)

        def on_finished():
            if generation != getattr(parent, "_pair_generation", 0):
                return

            self._cleanup_layers(parent, old_layer, new_layer)
            label.setPixmap(new_pix)
            label.show()
            label.raise_()
            if getattr(parent, "_transition_group", None) is animation:
                parent._transition_group = None
            parent.logger.write(parent.role, "CrossFadeTransition finished")
            animation.deleteLater()
            finished()

        animation.finished.connect(on_finished)
        animation.start()

    @staticmethod
    def _create_layer(parent, geometry):
        layer = QLabel(parent)
        layer.setGeometry(geometry)
        layer.setAlignment(Qt.AlignCenter)
        layer.setStyleSheet("background: transparent;")
        layer.setAttribute(Qt.WA_TransparentForMouseEvents)
        return layer

    @staticmethod
    def _pixelate(pixmap, block_size):
        if block_size <= 1 or pixmap.isNull():
            return pixmap

        reduced = pixmap.scaled(
            max(1, pixmap.width() // block_size),
            max(1, pixmap.height() // block_size),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation,
        )
        return reduced.scaled(
            pixmap.size(),
            Qt.IgnoreAspectRatio,
            Qt.FastTransformation,
        )

    @staticmethod
    def _cleanup_layers(parent, old_layer, new_layer):
        if getattr(parent, "_crossfade_labels", None) == (old_layer, new_layer):
            parent._crossfade_labels = None
        old_layer.hide()
        new_layer.hide()
        old_layer.deleteLater()
        new_layer.deleteLater()
