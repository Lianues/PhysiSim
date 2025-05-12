from physi_sim.core.vector import Vector2D

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from physi_sim.graphics.main_window import MainWindow # Avoid circular import

class ViewControlHandler:
    def __init__(self, main_window: 'MainWindow'):
        self.main_window = main_window
        self.drawing_widget = main_window.drawing_widget

    def reset_view(self):
        """Resets the drawing widget's view offset and scale to default."""
        if self.drawing_widget:
            self.drawing_widget.view_offset = Vector2D(0, 0)
            self.drawing_widget.pixels_per_world_unit = self.drawing_widget.DEFAULT_PIXELS_PER_WORLD_UNIT
            self.drawing_widget.update()
            # Optional: print("View reset to default.")
            if hasattr(self.main_window, 'status_bar'):
                self.main_window.status_bar.showMessage("视图已重置。", 2000)