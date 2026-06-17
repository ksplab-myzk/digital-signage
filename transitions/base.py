class TransitionBase:
    def __init__(self, parent):
        self.parent = parent  # MainWindow への参照

    def run(self, old_pixmap, new_pixmap, finished_callback):
        raise NotImplementedError
