from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QApplication, QFileDialog,
    QInputDialog, QMessageBox, QMenu, QSplitter, QDockWidget, QToolBar,
    QLabel, QStatusBar, QDialog, QDialogButtonBox, QFormLayout, QDoubleSpinBox # Added QDialog, QDialogButtonBox, QFormLayout, QDoubleSpinBox
)
from PySide6.QtGui import QPainter, QColor, QAction, QKeySequence, QMouseEvent, QActionGroup, QPen, QKeyEvent, QWheelEvent, QContextMenuEvent, QGuiApplication # Import QMouseEvent, QActionGroup, QPen, QKeyEvent and QWheelEvent, QContextMenuEvent
from PySide6.QtCore import Qt, QTimer, Slot, Signal, QPointF, QRectF, QLineF, QEvent # Added QPointF, QRectF, QLineF, QEvent
from enum import Enum, auto # Added for ToolMode

class ForceAnalysisDisplayMode(Enum):
    OBJECT = auto()
    CENTER_OF_MASS = auto()

from physi_sim.core.component import (
    ScriptExecutionComponent, TransformComponent, GeometryComponent, ShapeType, Component,
    RenderComponent, IdentifierComponent, SpringComponent, ForceAccumulatorComponent,
    PhysicsBodyComponent, ConnectionComponent, ConnectionType # Added ConnectionComponent and ConnectionType
)
from physi_sim.core.entity_manager import EntityManager
from physi_sim.scene.scene_manager import SceneManager
from physi_sim.scene.scene_serializer import SceneSerializer # Import SceneSerializer
from physi_sim.core.vector import Vector2D # 导入 Vector2D
from physi_sim.physics.spring_system import SpringSystem # 导入 SpringSystem
# RopeSystem import will be added if not present, or confirmed if present
from physi_sim.physics.rope_system import RopeSystem
from physi_sim.graphics.property_panel import PropertyPanel # 导入 PropertyPanel
from typing import Optional, Any, Tuple, Union, Dict, Set, TYPE_CHECKING # Added Union, Dict, Set, TYPE_CHECKING
import os # For path manipulation in window title
import uuid # Added for UUID generation and comparison
import math # Added for scale bar calculations
import json # Added for JSONDecodeError

# Tool Handlers
from physi_sim.graphics.drawing_tools.base_tool_handler import BaseToolHandler
from physi_sim.graphics.drawing_tools.select_tool_handler import SelectToolHandler
from physi_sim.graphics.drawing_tools.rectangle_tool_handler import RectangleToolHandler
from physi_sim.graphics.drawing_tools.circle_tool_handler import CircleToolHandler
from physi_sim.graphics.drawing_tools.spring_tool_handler import SpringToolHandler
from physi_sim.graphics.drawing_tools.rod_tool_handler import RodToolHandler
from physi_sim.graphics.drawing_tools.rope_tool_handler import RopeToolHandler
from physi_sim.graphics.drawing_tools.apply_force_tool_handler import ApplyForceToolHandler
from physi_sim.graphics.drawing_tools.pan_view_tool_handler import PanViewToolHandler
from physi_sim.graphics.drawing_tools.force_analysis_tool_handler import ForceAnalysisToolHandler

# Import PolygonToolHandler
from physi_sim.graphics.drawing_tools.polygon_tool_handler import PolygonToolHandler

# UI Handlers
from physi_sim.graphics.ui_handlers.scene_file_handler import SceneFileHandler
from physi_sim.graphics.ui_handlers.simulation_control_handler import SimulationControlHandler
from physi_sim.graphics.ui_handlers.view_control_handler import ViewControlHandler


class ToolMode(Enum):
    SELECT = auto()
    DRAW_RECTANGLE = auto()
    DRAW_SPRING = auto() # Added for spring drawing
    DRAW_CIRCLE = auto() # 新增：圆形绘制工具
    DRAW_ROD = auto()      # 新增：轻杆绘制工具
    DRAW_ROPE = auto()     # 新增：轻绳绘制工具
    APPLY_FORCE_AT_POINT = auto() # 新增：施加力工具
    FORCE_ANALYSIS = auto() # 新增：受力分析工具
    PAN_VIEW = auto() # 新增：平移视图工具
    POLYGON_DRAW = auto() # 新增：多边形绘制工具

class ToolAttachmentMode(Enum):
    CENTER_OF_MASS = auto()
    FREE_POSITION = auto()

# 一个简单的自定义QWidget用于绘图
class DrawingWidget(QWidget):
    # 将 selected_entity_changed 信号移到 MainWindow，因为选择逻辑在 MainWindow 中处理更合适
    # selected_entity_changed = Signal(object) # str (entity_id) or None

    def __init__(self, parent=None, entity_manager: Optional[EntityManager] = None):
        super().__init__(parent)
        self.setMinimumSize(800, 600)
        self.entity_manager = entity_manager # Store entity_manager if provided
        self.renderer_system = None # This will be set by MainWindow

        # View transform parameters
        self._widget_center_x: float = self.width() / 2
        self._widget_center_y: float = self.height() / 2
        self.DEFAULT_PIXELS_PER_WORLD_UNIT: float = 75.0
        self.pixels_per_world_unit: float = self.DEFAULT_PIXELS_PER_WORLD_UNIT
        self.view_offset: Vector2D = Vector2D(0, 0)

        # Keyboard pan speed
        self.PAN_SPEED_PIXELS: float = 20.0
        
        # Zooming parameters
        self.ZOOM_FACTOR_STEP: float = 1.1
        self._MIN_SCALE_EPSILON = 1e-9

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        # Snap mode state for connection tools (shared across relevant tools)
        self.is_snap_active: bool = True
        self.current_mouse_world_pos: Optional[Vector2D] = None
        
        # Highlighted entity for force application tool (still managed here for rendering access)
        self.highlighted_force_entity_id: Optional[uuid.UUID] = None


        # Tool Handlers
        # Ensure entity_manager is available if needed by handlers here
        # If self.entity_manager is None here, handlers needing it must be initialized later or passed EM.
        em_for_handlers = self.entity_manager
        if not em_for_handlers and parent and hasattr(parent, 'entity_manager'): # Fallback if MainWindow is parent
            em_for_handlers = parent.entity_manager

        self.tool_handlers: Dict[ToolMode, BaseToolHandler] = {
            ToolMode.SELECT: SelectToolHandler(),
            ToolMode.DRAW_RECTANGLE: RectangleToolHandler(),
            ToolMode.DRAW_CIRCLE: CircleToolHandler(),
            ToolMode.DRAW_SPRING: SpringToolHandler(), # Reverted: Does not take entity_manager
            ToolMode.DRAW_ROD: RodToolHandler(),       # Reverted: Does not take entity_manager
            ToolMode.DRAW_ROPE: RopeToolHandler(),     # Reverted: Does not take entity_manager
            ToolMode.APPLY_FORCE_AT_POINT: ApplyForceToolHandler(), # Reverted: Does not take entity_manager
            ToolMode.PAN_VIEW: PanViewToolHandler(),
            ToolMode.FORCE_ANALYSIS: ForceAnalysisToolHandler(),
            ToolMode.POLYGON_DRAW: PolygonToolHandler(em_for_handlers) # PolygonToolHandler expects entity_manager
        }
        # Note: ENTITY_DRAG is part of SELECT tool's logic
        
        # Old state attributes to be removed or managed by handlers:
        # self._drawing_start_pos, self._is_drawing, self._preview_rect (RectangleToolHandler)
        # self.is_drawing_circle, self.circle_center_world, self.circle_radius_world (CircleToolHandler)
        # self.force_apply_phase, self.force_target_entity_id, self.force_application_point_world (ApplyForceToolHandler)
        # self.is_panning, self.last_pan_pos (PanViewToolHandler)
        # self.is_dragging_entity, self.drag_offset_from_entity_anchor, self.drag_target_world_position (SelectToolHandler)
        # self.is_marqueeing, self.marquee_start_point, self.marquee_end_point (SelectToolHandler)

    def resizeEvent(self, event: QMouseEvent): # QResizeEvent
        """Update widget center when widget is resized."""
        self._widget_center_x = self.width() / 2
        self._widget_center_y = self.height() / 2
        super().resizeEvent(event)
        self.update()

    def _get_world_coordinates(self, screen_pos: QPointF) -> Vector2D:
        """Converts screen QPointF coordinates to world Vector2D coordinates."""
        # screen_x = (world_x - view_offset.x) * scale_x + widget_center_x
        # screen_y = (world_y - view_offset.y) * scale_y + widget_center_y  (where scale_y is negative)
        
        world_x = (screen_pos.x() - self._widget_center_x) / self.pixels_per_world_unit + self.view_offset.x
        # Invert Y calculation for Y-up world coordinates
        world_y = (screen_pos.y() - self._widget_center_y) / (-self.pixels_per_world_unit) + self.view_offset.y
        return Vector2D(world_x, world_y)

    def world_to_screen(self, world_pos: Vector2D) -> QPointF:
        """Converts world Vector2D coordinates (Y-up) to screen QPointF coordinates (Y-down)."""
        screen_x = (world_pos.x - self.view_offset.x) * self.pixels_per_world_unit + self._widget_center_x
        # Invert Y calculation for Y-up world coordinates
        screen_y = (world_pos.y - self.view_offset.y) * (-self.pixels_per_world_unit) + self._widget_center_y
        return QPointF(screen_x, screen_y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing) # Enable Antialiasing
        painter.fillRect(self.rect(), QColor(Qt.GlobalColor.white))
        
        main_window = self.window() # Assuming it's MainWindow

        # --- 1. Apply View Transform ---
        # The view transform makes the world coordinate `self.view_offset` appear at `self._widget_center_x, self._widget_center_y`.
        # All subsequent drawing operations using this painter are in world units,
        # with the world origin (0,0) correctly positioned relative to the view_offset.
        painter.save()
        painter.translate(self._widget_center_x, self._widget_center_y)
        # Scale Y negatively to make world Y-axis point upwards
        painter.scale(self.pixels_per_world_unit, -self.pixels_per_world_unit)
        painter.translate(-self.view_offset.x, -self.view_offset.y) # Pan: translate by negative of view center in world units

        # --- 2. Draw Coordinate Axes with Arrows (Y-axis now points up in world) ---
        axis_pen = QPen(QColor(200, 200, 200), 1.0 / self.pixels_per_world_unit, Qt.PenStyle.SolidLine)
        arrow_pen = QPen(QColor(150, 150, 150), 1.5 / self.pixels_per_world_unit, Qt.PenStyle.SolidLine) # Slightly darker/thicker arrows
        
        # Calculate visible world boundaries
        world_min_coord = self._get_world_coordinates(QPointF(0, 0))
        world_max_coord = self._get_world_coordinates(QPointF(self.width(), self.height()))
        world_min_x, world_min_y = world_min_coord.x, world_min_coord.y
        world_max_x, world_max_y = world_max_coord.x, world_max_coord.y

        # Draw axis lines to the edge of the visible area
        painter.setPen(axis_pen)
        painter.drawLine(QPointF(world_min_x, 0), QPointF(world_max_x, 0)) # X-axis line
        # Y-axis line still goes from min world Y to max world Y
        painter.drawLine(QPointF(0, world_min_y), QPointF(0, world_max_y))

        # Draw arrowheads
        arrow_size_pixels = 8.0
        arrow_size_world = arrow_size_pixels / self.pixels_per_world_unit
        
        painter.setPen(arrow_pen)
        # X-axis arrow at (world_max_x, 0)
        painter.drawLine(QPointF(world_max_x - arrow_size_world, arrow_size_world / 2), QPointF(world_max_x, 0))
        painter.drawLine(QPointF(world_max_x - arrow_size_world, -arrow_size_world / 2), QPointF(world_max_x, 0))
        # Y-axis arrow at (0, world_min_coord.y) - Points UP (positive world Y is up)
        # world_min_coord.y is the Y world coordinate at the top-left of the screen (closest to screen y=0 along the y-axis in world space)
        # Arrow lines should point *down* (in world coordinates) from the tip (world_min_coord.y)
        painter.drawLine(QPointF(arrow_size_world / 2, world_min_coord.y - arrow_size_world), QPointF(0, world_min_coord.y))
        painter.drawLine(QPointF(-arrow_size_world / 2, world_min_coord.y - arrow_size_world), QPointF(0, world_min_coord.y))

        # Draw "(0,0)" label near the origin (within transformed painter)
        painter.save()
        painter.setPen(QColor(Qt.GlobalColor.darkGray))
        painter.scale(1.0 / self.pixels_per_world_unit, 1.0 / self.pixels_per_world_unit)
        font_metrics_origin = painter.fontMetrics()
        origin_label = "(0,0)"
        label_offset_pixels = 5
        label_offset_world = label_offset_pixels / self.pixels_per_world_unit
        # Adjust Y offset for Y-up rendering (place label slightly above origin)
        painter.drawText(QPointF(label_offset_world, label_offset_world), origin_label)
        painter.restore() # Restore from text scaling

        # --- 3. Render Scene Objects (RendererSystem uses world coordinates, painter is set up with Y-up) ---
        if isinstance(main_window, MainWindow) and self.renderer_system:
            # Pass selected entity IDs and connection IDs for highlighting
            selected_entity_ids = main_window.selected_entity_ids
            selected_connection_ids = main_window.selected_connection_ids
            
            # Pass selected spring entities for DRAW_SPRING tool highlighting (if any)
            # These are different from the general selected_object_id for SPRING_CONNECTION
            spring_draw_entity_a = main_window.spring_first_entity_id if hasattr(main_window, 'spring_first_entity_id') else None
            spring_draw_entity_b = main_window.spring_second_entity_id if hasattr(main_window, 'spring_second_entity_id') else None
            
            self.renderer_system.render_scene(
                painter,
                drawing_widget_ref=self, # Pass self (DrawingWidget instance)
                selected_entity_ids=selected_entity_ids,
                selected_connection_ids=selected_connection_ids,
                spring_creation_entity_a_id=spring_draw_entity_a, # For DRAW_SPRING tool
                spring_creation_entity_b_id=spring_draw_entity_b,  # For DRAW_SPRING tool
                highlighted_force_entity_id=self.highlighted_force_entity_id if main_window.current_tool_mode == ToolMode.APPLY_FORCE_AT_POINT else None,
                force_analysis_target_entity_id=main_window.force_analysis_target_entity_id if main_window.current_tool_mode == ToolMode.FORCE_ANALYSIS else None,
                # --- Rod/Rope creation highlight ---
                rod_pending_selection_id=main_window.rod_pending_selection_id if main_window.current_tool_mode == ToolMode.DRAW_ROD else None,
                rod_second_pending_selection_id=main_window.rod_second_pending_selection_id if main_window.current_tool_mode == ToolMode.DRAW_ROD and main_window.rod_creation_phase == 2 else None,
                rope_pending_selection_id=main_window.rope_pending_selection_id if main_window.current_tool_mode == ToolMode.DRAW_ROPE else None,
                rope_second_pending_selection_id=main_window.rope_second_pending_selection_id if main_window.current_tool_mode == ToolMode.DRAW_ROPE and main_window.rope_creation_phase == 2 else None,
                # --- Pass scale info ---
                force_analysis_display_mode=main_window.force_analysis_display_mode,
                pixels_per_world_unit=self.pixels_per_world_unit,
                force_scale_reference=main_window.force_scale_reference_newtons,
                force_scale_pixels=main_window.force_scale_bar_pixels
            )

        # --- 4. Tool Specific Overlay Drawing ---
        if isinstance(main_window, MainWindow):
            current_tool_handler = self.tool_handlers.get(main_window.current_tool_mode)
            if current_tool_handler:
                current_tool_handler.paint_overlay(painter, self)

        # --- Old preview logic (now handled by tool handlers) ---
        # if isinstance(main_window, MainWindow) and \
        #    main_window.current_tool_mode == ToolMode.DRAW_RECTANGLE and \
        #    self._is_drawing and self._preview_rect: ...
        #
        # elif isinstance(main_window, MainWindow) and \
        #      main_window.current_tool_mode == ToolMode.DRAW_CIRCLE and \
        #      self.is_drawing_circle and self.circle_center_world: ...
        #
        # if self.is_marqueeing and self.marquee_start_point and self.marquee_end_point: ...


        # --- Snap Points (still drawn by DrawingWidget as it's a shared visual feedback) ---
        if isinstance(main_window, MainWindow):
            connection_tools = [ToolMode.DRAW_SPRING, ToolMode.DRAW_ROD, ToolMode.DRAW_ROPE]
            is_connection_tool_active = main_window.current_tool_mode in connection_tools

            # Debug print for the conditions
            # print(f"PaintEvent DBG: is_conn_tool_active={is_connection_tool_active}, self.is_snap_active={self.is_snap_active}, self.current_mouse_world_pos={self.current_mouse_world_pos is not None}")

            if is_connection_tool_active and self.is_snap_active and self.current_mouse_world_pos:
                # print(f"PaintEvent: Checking snap points. Mouse world: {self.current_mouse_world_pos}, Snap Active: {self.is_snap_active}")
                entity_under_mouse_id = main_window._get_entity_at_world_pos(self.current_mouse_world_pos)
                
                if entity_under_mouse_id:
                    # print(f"PaintEvent: Entity under mouse for snap points: {str(entity_under_mouse_id)[:8]}")
                    entity_geom = main_window.entity_manager.get_component(entity_under_mouse_id, GeometryComponent)
                    entity_transform = main_window.entity_manager.get_component(entity_under_mouse_id, TransformComponent)

                    if entity_geom and entity_transform:
                        local_snap_points = entity_geom.get_local_snap_points()
                        
                        snap_point_pen = QPen(QColor(255, 0, 255, 200)) # Magenta
                        snap_point_pen.setWidthF(1.5 / self.pixels_per_world_unit)
                        painter.setPen(snap_point_pen)
                        painter.setBrush(QColor(255, 0, 255, 150))

                        snap_radius_pixels = 3.0
                        snap_radius_world = snap_radius_pixels / self.pixels_per_world_unit

                        for local_point in local_snap_points:
                            world_snap_point = entity_transform.position + local_point.rotate(entity_transform.angle)
                            painter.drawEllipse(QPointF(world_snap_point.x, world_snap_point.y),
                                                snap_radius_world, snap_radius_world)
                # else:
                    # print(f"PaintEvent: No entity under mouse for snap points.")


        painter.restore() # Restore from main view transform (translate and scale)

        # --- Draw X and Y labels near arrows (in screen coordinates) ---
        label_offset_screen = 8 # Offset in screen pixels from arrow tip
        painter.setPen(QColor(Qt.GlobalColor.darkGray)) # Use same color as origin label
        font_metrics_labels = painter.fontMetrics()

        # X Label
        x_arrow_tip_screen = self.world_to_screen(Vector2D(world_max_x, 0))
        x_label = "X"
        x_label_width = font_metrics_labels.horizontalAdvance(x_label)
        # Position X label so its right edge is 2 pixels to the left of the arrow's right edge (tip)
        # Adjust Y position so the label's top aligns with the arrow's visual top edge (approx. arrow_center_y - 4px)
        x_label_pos = QPointF(x_arrow_tip_screen.x() - x_label_width - 2.0,
                              x_arrow_tip_screen.y() + font_metrics_labels.ascent() + 4.0) # Y pos: top of label aligns with arrow's top edge
        painter.drawText(x_label_pos, x_label)

        # Y Label (Y-axis arrow now points up screen)
        # Y Label: Tip is at the Y-axis intersection with the screen's top edge (world_min_coord.y)
        y_arrow_tip_screen = self.world_to_screen(Vector2D(0, world_min_coord.y))
        y_label = "Y"
        y_label_width = font_metrics_labels.horizontalAdvance(y_label)
        # Position Y label so its top edge aligns with the arrow's top edge (tip)
        # The baseline Y will be arrow_tip_y + ascent
        y_label_pos = QPointF(y_arrow_tip_screen.x() + label_offset_screen,
                              y_arrow_tip_screen.y() + font_metrics_labels.ascent())
        painter.drawText(y_label_pos, y_label)
        # --- End X/Y Labels ---


        # --- 5. Draw Adaptive Scale Bar (in screen coordinates, after restoring main transform) ---
        margin = 15  # Margin from bottom-left corner in pixels
        target_scale_bar_pixel_length = 100 # Aim for a scale bar around 100 pixels wide

        # Calculate an approximate world length for the target pixel length
        approx_world_length = target_scale_bar_pixel_length / self.pixels_per_world_unit

        # Calculate a "nice" world length (1, 2, or 5 times a power of 10)
        # that is close to the approximate length.
        if approx_world_length <= 0: # Avoid issues with log10(0) or negative
             scale_bar_world_length = 1e-6 # Use a small default if scale is extreme
        else:
            power_of_10 = 10.0 ** math.floor(math.log10(approx_world_length))
            relative_length = approx_world_length / power_of_10 # Should be between 1 and 10

            if relative_length < 1.5:
                scale_bar_world_length = 1.0 * power_of_10
            elif relative_length < 3.5:
                scale_bar_world_length = 2.0 * power_of_10
            elif relative_length < 7.5:
                scale_bar_world_length = 5.0 * power_of_10
            else:
                scale_bar_world_length = 10.0 * power_of_10 # or 1.0 * power_of_10 * 10

        # Actual pixel length for the chosen world length
        actual_scale_bar_pixel_length = int(scale_bar_world_length * self.pixels_per_world_unit)

        # Ensure the bar is at least a few pixels wide
        min_bar_pixels = 5
        if actual_scale_bar_pixel_length < min_bar_pixels:
             # If the calculated "nice" length results in too small a bar,
             # maybe force the bar to be min_bar_pixels and adjust world length accordingly?
             # Or just let it be potentially very small/invisible at extreme zooms.
             # Let's recalculate world length based on min pixels for visibility.
             actual_scale_bar_pixel_length = min_bar_pixels
             scale_bar_world_length = actual_scale_bar_pixel_length / self.pixels_per_world_unit


        bar_start_x = margin
        bar_y_screen = self.height() - margin
        bar_end_x = bar_start_x + actual_scale_bar_pixel_length
        
        painter.setPen(QColor(Qt.GlobalColor.black))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # Draw the scale bar lines
        painter.drawLine(bar_start_x, bar_y_screen, bar_end_x, bar_y_screen)
        painter.drawLine(bar_start_x, bar_y_screen - 3, bar_start_x, bar_y_screen + 3)
        painter.drawLine(bar_end_x, bar_y_screen - 3, bar_end_x, bar_y_screen + 3)
        
        # Format the label, using scientific notation for very small or large numbers
        use_scientific = scale_bar_world_length < 0.01 or scale_bar_world_length >= 10000
        
        if use_scientific:
            label_text_scale = f"{scale_bar_world_length:.1e} m"
        else:
            # Use reasonable precision for normal numbers
            if scale_bar_world_length >= 1:
                 # Show fewer decimals for larger numbers
                 precision = 2 if scale_bar_world_length < 10 else 1 if scale_bar_world_length < 100 else 0
                 label_text_scale = f"{scale_bar_world_length:.{precision}f} m"
            else:
                 # Find significant digits for small numbers (e.g., 0.05, 0.012)
                 precision = -int(math.floor(math.log10(scale_bar_world_length))) + 1
                 label_text_scale = f"{scale_bar_world_length:.{precision}f} m"

        font_metrics_scale = painter.fontMetrics()
        text_width_scale = font_metrics_scale.horizontalAdvance(label_text_scale)
        
        text_x_screen = bar_start_x + (actual_scale_bar_pixel_length - text_width_scale) / 2
        text_y_screen = bar_y_screen - 5 #pixels above the bar
        painter.drawText(int(text_x_screen), int(text_y_screen), label_text_scale)
        # --- End Draw Length Scale Bar ---

        # --- Draw Force Scale Bar (Top Right) ---
        # Drawn in screen coordinates, after restoring main transform
        painter.save() # Save state before drawing force scale

        force_margin_x = 15 # Margin from right edge
        force_margin_y = 15 # Margin from top edge
        force_bar_pixel_length = main_window.force_scale_bar_pixels if hasattr(main_window, 'force_scale_bar_pixels') else 50.0
        force_ref_n = main_window.force_scale_reference_newtons if hasattr(main_window, 'force_scale_reference_newtons') else 10.0

        force_bar_end_x = self.width() - force_margin_x
        force_bar_start_x = force_bar_end_x - force_bar_pixel_length
        force_bar_y_screen = force_margin_y + 10 # Position it below the top margin slightly

        painter.setPen(QColor(Qt.GlobalColor.red)) # Use red for force scale
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Draw the force scale bar lines
        painter.drawLine(int(force_bar_start_x), int(force_bar_y_screen), int(force_bar_end_x), int(force_bar_y_screen))
        painter.drawLine(int(force_bar_start_x), int(force_bar_y_screen) - 3, int(force_bar_start_x), int(force_bar_y_screen) + 3)
        painter.drawLine(int(force_bar_end_x), int(force_bar_y_screen) - 3, int(force_bar_end_x), int(force_bar_y_screen) + 3)

        # Format the label
        label_text_force = f"{force_ref_n:.1f} N"
        font_metrics_force = painter.fontMetrics()
        text_width_force = font_metrics_force.horizontalAdvance(label_text_force)
        text_height_force = font_metrics_force.ascent()

        text_x_force = force_bar_start_x + (force_bar_pixel_length - text_width_force) / 2
        text_y_force = force_bar_y_screen + text_height_force + 2 # Position label below the bar

        painter.drawText(int(text_x_force), int(text_y_force), label_text_force)

        painter.restore() # Restore state after drawing force scale
        # --- End Draw Force Scale Bar ---


    def _point_segment_distance_sq(self, p: QPointF, a: QPointF, b: QPointF) -> float:
        """Calculates the squared distance from point p to line segment ab."""
        # Vector ab
        ab_x = b.x() - a.x()
        ab_y = b.y() - a.y()

        # Vector ap
        ap_x = p.x() - a.x()
        ap_y = p.y() - a.y()

        # Length squared of ab
        len_sq_ab = ab_x * ab_x + ab_y * ab_y
        if len_sq_ab == 0: # a and b are the same point
            return ap_x * ap_x + ap_y * ap_y # Distance squared from p to a

        # Projection of ap onto ab, t = dot(ap, ab) / |ab|^2
        t = (ap_x * ab_x + ap_y * ab_y) / len_sq_ab

        if t < 0: # Closest point is a
            return ap_x * ap_x + ap_y * ap_y # Distance squared from p to a
        elif t > 1: # Closest point is b
            # Vector bp
            bp_x = p.x() - b.x()
            bp_y = p.y() - b.y()
            return bp_x * bp_x + bp_y * bp_y # Distance squared from p to b
        else: # Closest point is on the segment
            proj_x = a.x() + t * ab_x
            proj_y = a.y() + t * ab_y
            # Distance squared from p to projection
            dx = p.x() - proj_x
            dy = p.y() - proj_y
            return dx * dx + dy * dy

    def _point_to_segment_distance_sq_world(self, p_world: Vector2D, a_world: Vector2D, b_world: Vector2D) -> float:
        """Calculates the squared distance from world point p_world to world line segment a_world-b_world."""
        # This method calculates distance in screen space for click detection.
        p_screen = self.world_to_screen(p_world)
        a_screen = self.world_to_screen(a_world)
        b_screen = self.world_to_screen(b_world)

        # Vector ab
        ab_x = b_screen.x() - a_screen.x()
        ab_y = b_screen.y() - a_screen.y()

        # Vector ap
        ap_x = p_screen.x() - a_screen.x()
        ap_y = p_screen.y() - a_screen.y()

        len_sq_ab = ab_x * ab_x + ab_y * ab_y
        if len_sq_ab == 0:  # a and b are the same point
            return ap_x * ap_x + ap_y * ap_y

        # Projection of ap onto ab, t = dot(ap, ab) / |ab|^2
        t = (ap_x * ab_x + ap_y * ab_y) / len_sq_ab

        if t < 0:  # Closest point is a
            return ap_x * ap_x + ap_y * ap_y
        elif t > 1:  # Closest point is b
            bp_x = p_screen.x() - b_screen.x()
            bp_y = p_screen.y() - b_screen.y()
            return bp_x * bp_x + bp_y * bp_y
        else:  # Closest point is on the segment
            proj_x = a_screen.x() + t * ab_x
            proj_y = a_screen.y() + t * ab_y
            dx = p_screen.x() - proj_x
            dy = p_screen.y() - proj_y
            return dx * dx + dy * dy
 
    def mousePressEvent(self, event: QMouseEvent):
        self.setFocus()
        main_window: MainWindow = self.window()
        if not isinstance(main_window, MainWindow):
            return

        current_tool_handler = self.tool_handlers.get(main_window.current_tool_mode)
        if current_tool_handler:
            current_tool_handler.handle_mouse_press(event, self)
        else:
            # Fallback or default behavior if no handler (should not happen ideally)
            super().mousePressEvent(event)


    def mouseMoveEvent(self, event: QMouseEvent):
        main_window: MainWindow = self.window()
        if not isinstance(main_window, MainWindow):
            return
        
        # Always update the current mouse world position
        self.current_mouse_world_pos = self._get_world_coordinates(event.position())

        current_tool_handler = self.tool_handlers.get(main_window.current_tool_mode)
        if current_tool_handler:
            current_tool_handler.handle_mouse_move(event, self)
        else:
            super().mouseMoveEvent(event)
        
        # General update for things like snap points that are not tool-specific overlays
        self.update()

    def leaveEvent(self, event: QEvent): # QEvent, not QMouseEvent
        """Called when the mouse cursor leaves the widget."""
        # print("DrawingWidget leaveEvent: Mouse left widget.")
        self.current_mouse_world_pos = None
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        main_window: MainWindow = self.window()
        if not isinstance(main_window, MainWindow):
            return

        current_tool_handler = self.tool_handlers.get(main_window.current_tool_mode)
        if current_tool_handler:
            current_tool_handler.handle_mouse_release(event, self)
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        main_window: MainWindow = self.window()
        if not isinstance(main_window, MainWindow):
            super().mouseDoubleClickEvent(event)
            return

        current_tool_handler = self.tool_handlers.get(main_window.current_tool_mode)
        if current_tool_handler and hasattr(current_tool_handler, 'handle_mouse_double_click'):
            current_tool_handler.handle_mouse_double_click(event, self)
        else:
            super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent): # QContextMenuEvent
        main_window: MainWindow = self.window()
        if not isinstance(main_window, MainWindow):
            super().contextMenuEvent(event)
            return

        world_pos = self._get_world_coordinates(event.pos())
        
        # Check if the click is on a selected entity or connection
        entity_id_under_mouse = main_window._get_entity_at_world_pos(world_pos)
        connection_id_under_mouse = main_window._get_connection_at_world_pos(world_pos) # Requires implementation

        item_to_operate_on_id = None
        item_type = None # "ENTITY" or "CONNECTION"

        if entity_id_under_mouse and entity_id_under_mouse in main_window.selected_entity_ids:
            item_to_operate_on_id = entity_id_under_mouse
            item_type = "ENTITY"
        elif connection_id_under_mouse and connection_id_under_mouse in main_window.selected_connection_ids:
            item_to_operate_on_id = connection_id_under_mouse
            item_type = "CONNECTION"

        if item_to_operate_on_id:
            menu = QMenu(self)
            
            delete_action = QAction("删除", self)
            delete_action.triggered.connect(main_window._handle_delete_selected_objects)
            menu.addAction(delete_action)

            if item_type == "ENTITY":
                # Optionally, add "Properties" action if it's an entity
                properties_action = QAction("属性", self)
                # Assuming _handle_selection_change_for_property_panel can be triggered or adapted
                # to show properties for a specific entity if it's not already selected.
                # For simplicity, we'll assume if it's right-clicked and selected, its props might already be shown
                # or this action could force it.
                # This part might need more complex logic to ensure the property panel updates correctly
                # if the right-clicked entity wasn't the *only* selected one.
                # For now, let's make it re-assert selection for the property panel,
                # and then explicitly show and position the panel.
                properties_action.triggered.connect(
                    lambda checked=False, entity_id=item_to_operate_on_id:
                        main_window._handle_show_properties_for_entity(entity_id)
                )
                menu.addAction(properties_action)
            
            menu.exec(event.globalPos())
        else:
            # Standard context menu or no menu if click is not on a selected item
            # For now, just pass to super if no relevant item is clicked.
            # Later, a general canvas context menu could be added here.
            super().contextMenuEvent(event)


    def keyPressEvent(self, event: QKeyEvent):
        print("DrawingWidget keyPressEvent triggered") # DEBUG
        main_window = self.window()
        if not isinstance(main_window, MainWindow):
            super().keyPressEvent(event)
            return

        # Give current tool handler a chance to process the key press first
        current_tool_handler = self.tool_handlers.get(main_window.current_tool_mode)
        if current_tool_handler and hasattr(current_tool_handler, 'handle_key_press'):
            if current_tool_handler.handle_key_press(event, self):
                event.accept() # Assume handler accepted it
                return # Event handled by tool

        key = event.key()
        pan_modified = False
        pan_step_world = self.PAN_SPEED_PIXELS / self.pixels_per_world_unit

        if key == Qt.Key.Key_W:
            self.view_offset.y += pan_step_world
            pan_modified = True
        elif key == Qt.Key.Key_S:
            self.view_offset.y -= pan_step_world
            pan_modified = True
        elif key == Qt.Key.Key_A:
            self.view_offset.x -= pan_step_world
            pan_modified = True
        elif key == Qt.Key.Key_D:
            self.view_offset.x += pan_step_world
            pan_modified = True
        
        if pan_modified:
            self.update()
            event.accept()
            # Do not return yet, allow Shift check to proceed

        # --- Shift Key Handling for Snap Mode ---
        is_connection_tool_active = False
        connection_tools = [ToolMode.DRAW_SPRING, ToolMode.DRAW_ROD, ToolMode.DRAW_ROPE]
        if main_window.current_tool_mode in connection_tools:
            is_connection_tool_active = True

        if is_connection_tool_active:
            # Use event.modifiers() for the state *during* this specific key press event
            event_modifiers = event.modifiers()
            shift_pressed_for_this_event = bool(event_modifiers & Qt.KeyboardModifier.ShiftModifier)

            # desired_snap_state should be False if Shift is pressed for this event
            desired_snap_state = not shift_pressed_for_this_event
            
            if self.is_snap_active != desired_snap_state:
                # print(f"KeyPress: Event Shift Mod: {shift_pressed_for_this_event}. Old is_snap_active: {self.is_snap_active}. Setting is_snap_active = {desired_snap_state}")
                self.is_snap_active = desired_snap_state
                self.update()
            
            # If the key itself was Shift, accept the event.
            if key == Qt.Key.Key_Shift:
                event.accept()
        
        if not event.isAccepted():
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """Handles mouse wheel events for zooming."""
        screen_pos_before_zoom = event.position() # QPointF, mouse cursor position in widget coordinates
        world_pos_before_zoom = self._get_world_coordinates(screen_pos_before_zoom)
        
        old_scale = self.pixels_per_world_unit
        
        # Determine zoom direction
        delta_degrees = event.angleDelta().y() / 8  # Standard delta is 120 degrees for one step
        num_steps = delta_degrees / 15 # Convert degrees to number of standard scroll steps

        if num_steps > 0: # Zoom in
            new_scale = old_scale * (self.ZOOM_FACTOR_STEP ** num_steps)
        elif num_steps < 0: # Zoom out
            new_scale = old_scale / (self.ZOOM_FACTOR_STEP ** abs(num_steps))
        else:
            return # No change

        # Ensure scale doesn't become zero or negative
        self.pixels_per_world_unit = max(self._MIN_SCALE_EPSILON, new_scale)

        if abs(self.pixels_per_world_unit - old_scale) < 1e-9 : # Use a smaller epsilon for float comparison
            return

        # To keep the point under the mouse stationary in world coordinates,
        # we need to adjust the view_offset.
        # screen_x = (world_x - view_offset.x) * scale + widget_center_x
        # view_offset.x = world_x - (screen_x - widget_center_x) / scale
        
        # Calculate new view_offset to keep world_pos_before_zoom at screen_pos_before_zoom
        # Calculate new view_offset to keep world_pos_before_zoom at screen_pos_before_zoom
        # view_offset.x = world_x - (screen_x - center_x) / scale_x
        # view_offset.y = world_y - (screen_y - center_y) / scale_y  (where scale_y is negative)
        # view_offset.y = world_y + (screen_y - center_y) / abs(scale_y)
        self.view_offset.x = world_pos_before_zoom.x - (screen_pos_before_zoom.x() - self._widget_center_x) / self.pixels_per_world_unit
        self.view_offset.y = world_pos_before_zoom.y + (screen_pos_before_zoom.y() - self._widget_center_y) / self.pixels_per_world_unit # Sign change for Y-up

        self.update()
        event.accept()

    def keyReleaseEvent(self, event: QKeyEvent):
        print("DrawingWidget keyReleaseEvent triggered") # DEBUG
        main_window = self.window()
        if not isinstance(main_window, MainWindow):
            super().keyReleaseEvent(event)
            return

        key = event.key()
        
        # --- Shift Key Handling for Snap Mode (on release) ---
        # This logic specifically handles the release of the Shift key.
        if key == Qt.Key.Key_Shift and not event.isAutoRepeat():
            is_connection_tool_active = False
            connection_tools = [ToolMode.DRAW_SPRING, ToolMode.DRAW_ROD, ToolMode.DRAW_ROPE]
            if main_window.current_tool_mode in connection_tools:
                is_connection_tool_active = True
            
            if is_connection_tool_active:
                # When the Shift key itself is released, we want to activate snap mode.
                if not self.is_snap_active: # If snap was False (meaning Shift was making it False)
                    # print(f"KeyRelease: Shift KEY released. Old is_snap_active: {self.is_snap_active}. Setting is_snap_active = True")
                    self.is_snap_active = True
                    self.update()
                    event.accept()
            # If snap state is already correct (e.g. another shift key still held, or snap was already true), no change.

        if not event.isAccepted():
            super().keyReleaseEvent(event)


# Physics Settings Dialog
class PhysicsSettingsDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("物理参数设置")
        
        self.constraint_solver = None
        if self.main_window and hasattr(self.main_window, 'physics_system') and \
           self.main_window.physics_system and hasattr(self.main_window.physics_system, 'constraint_solver') and \
           self.main_window.physics_system.constraint_solver:
            self.constraint_solver = self.main_window.physics_system.constraint_solver

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.alpha_spinbox = QDoubleSpinBox()
        self.beta_spinbox = QDoubleSpinBox()

        if self.constraint_solver:
            self.alpha_spinbox.setDecimals(2)
            self.alpha_spinbox.setRange(0.0, 10000.0)
            self.alpha_spinbox.setSingleStep(0.5)
            self.alpha_spinbox.setValue(getattr(self.constraint_solver, 'baumgarte_alpha', 5.0))
            form_layout.addRow("Baumgarte Alpha:", self.alpha_spinbox)

            self.beta_spinbox.setDecimals(2)
            self.beta_spinbox.setRange(0.0, 10000.0)
            self.beta_spinbox.setSingleStep(0.5)
            self.beta_spinbox.setValue(getattr(self.constraint_solver, 'baumgarte_beta', 0.5))
            form_layout.addRow("Baumgarte Beta:", self.beta_spinbox)
        else:
            error_label = QLabel("约束求解器不可用。")
            form_layout.addRow(error_label)
            self.alpha_spinbox.setEnabled(False)
            self.beta_spinbox.setEnabled(False)
            
        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept(self):
        if self.constraint_solver:
            if hasattr(self.constraint_solver, 'baumgarte_alpha'):
                self.constraint_solver.baumgarte_alpha = self.alpha_spinbox.value()
            if hasattr(self.constraint_solver, 'baumgarte_beta'):
                self.constraint_solver.baumgarte_beta = self.beta_spinbox.value()
            print(f"Physics settings updated: Alpha={self.constraint_solver.baumgarte_alpha}, Beta={self.constraint_solver.baumgarte_beta}")
        super().accept()


class MainWindow(QMainWindow):
    # Emits: selected_entity_ids: Set[uuid.UUID], selected_connection_ids: Set[uuid.UUID]
    selection_changed = Signal(set, set)

    def __init__(self, entity_manager: EntityManager): # Add entity_manager parameter
        super().__init__()
        self.setWindowTitle("PhysiSim") # Initial title, will be updated
        self.entity_manager = entity_manager # Use passed entity_manager
        self.scene_manager = SceneManager(self.entity_manager) # Use passed entity_manager
        self._initial_scene_state_json: Optional[str] = None
        self.renderer_system = None
        self.physics_system = None
        self.collision_system = None
        self.constraint_solver = None
        self.spring_system = SpringSystem(self.entity_manager) # Ensure initialized
        self.rope_system = RopeSystem(self.entity_manager) # Ensure initialized
        # self.rod_system = RodSystem(self.entity_manager) # Initialize RodSystem # Removed
        self.script_engine = None
        self.current_simulation_time = 0.0
        self.is_simulation_running = False
        self.dt = 0.004
        
        # Selection attributes for multi-select
        self._selected_entity_ids: Set[uuid.UUID] = set()
        self._selected_connection_ids: Set[uuid.UUID] = set() # For springs, rods, ropes

        self.current_tool_mode: ToolMode = ToolMode.SELECT # Default tool mode
        # self.spring_attachment_mode: ToolAttachmentMode = ToolAttachmentMode.CENTER_OF_MASS # Removed
        # self.rod_attachment_mode: ToolAttachmentMode = ToolAttachmentMode.CENTER_OF_MASS # Removed
        # self.rope_attachment_mode: ToolAttachmentMode = ToolAttachmentMode.CENTER_OF_MASS # Removed
        self.force_application_mode: ToolAttachmentMode = ToolAttachmentMode.CENTER_OF_MASS # Keep for force tool

        # Force Analysis State
        self.force_analysis_target_entity_id: Optional[uuid.UUID] = None
        self.force_analysis_display_mode: ForceAnalysisDisplayMode = ForceAnalysisDisplayMode.OBJECT
        # Force Scale Configuration
        self.force_scale_reference_newtons: float = 10.0 # N
        self.force_scale_bar_pixels: float = 50.0      # pixels for reference N
        
        # Spring creation state
        self.spring_creation_phase: int = 0 # 0: None selected, 1: First entity selected, 2: Second selected (ready for dialog)
        self.spring_first_entity_id: Optional[uuid.UUID] = None
        self.spring_second_entity_id: Optional[uuid.UUID] = None
        self.spring_first_entity_click_pos_world: Optional[Vector2D] = None # For FREE_POSITION mode
        self.spring_second_entity_click_pos_world: Optional[Vector2D] = None # For FREE_POSITION mode

        # Rod creation state
        self.rod_creation_phase: int = 0
        self.rod_first_entity_id: Optional[uuid.UUID] = None
        self.rod_second_entity_id: Optional[uuid.UUID] = None
        self.rod_first_entity_click_pos_world: Optional[Vector2D] = None
        self.rod_second_entity_click_pos_world: Optional[Vector2D] = None

        # Rope creation state
        self.rope_creation_phase: int = 0
        self.rope_first_entity_id: Optional[uuid.UUID] = None
        self.rope_second_entity_id: Optional[uuid.UUID] = None
        self.rope_first_entity_click_pos_world: Optional[Vector2D] = None
        self.rope_second_entity_click_pos_world: Optional[Vector2D] = None
        self.rod_pending_selection_id: Optional[uuid.UUID] = None # For highlighting entity A during rod draw
        self.rope_pending_selection_id: Optional[uuid.UUID] = None # For highlighting entity A during rope draw
        self.rod_second_pending_selection_id: Optional[uuid.UUID] = None # For highlighting entity B during rod draw
        self.rope_second_pending_selection_id: Optional[uuid.UUID] = None # For highlighting entity B during rope draw

        # Snap threshold for connection points (in screen pixels squared for distance comparison)
        self.SNAP_THRESHOLD_PIXELS_SQ: float = 50.0 * 50.0 # Increased further from 30.0 * 30.0

        # --- UI Elements ---
        self.drawing_widget = DrawingWidget(self, self.entity_manager) # Pass entity_manager
        self.property_panel = PropertyPanel(self.entity_manager, self)
        self.drawing_tool_group = QActionGroup(self) # Will be populated in _create_toolbar

        # --- UI Handlers ---
        self.scene_file_handler = SceneFileHandler(self)
        self.simulation_control_handler = SimulationControlHandler(self)
        self.view_control_handler = ViewControlHandler(self)

        # --- Layout ---
        # 恢复使用 QDockWidget
        self.properties_dock = QDockWidget("属性", self)
        self.properties_dock.setWidget(self.property_panel)
        # 允许停靠在左右侧
        self.properties_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        # 添加 Dock Widget 到右侧
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)
        
        # 设置 Dock Widget 的特性，确保有关闭按钮 (默认就有)
        # QDockWidget::DockWidgetClosable 是默认特性
        # self.properties_dock.setFeatures(self.properties_dock.features() | QDockWidget.DockWidgetClosable) # 确保可关闭

        # 设置 Dock Widget 的最小宽度
        self.properties_dock.setMinimumWidth(300)
        
        # 设置中心部件
        self.setCentralWidget(self.drawing_widget)
        # 确保中心部件有最小宽度
        self.drawing_widget.setMinimumWidth(400)

        # 设置初始 Dock 大小，让布局知道它的存在
        self.resizeDocks([self.properties_dock], [350], Qt.Orientation.Horizontal)
        # 在初始布局计算完成后再隐藏它
        QTimer.singleShot(0, self.properties_dock.hide)


        self._create_menus()
        self._create_toolbar() # Create toolbar
        self._create_status_bar() # Create status bar for time display
        self.preferred_property_panel_width = 350 # 保留期望宽度
        self._update_window_title() # Set initial window title

        # --- Global Styles ---
        self.setStyleSheet("""
            QToolButton {
                border: 1px solid transparent; /* Start with a transparent border */
                border-radius: 0px; /* Ensure square corners */
                padding: 4px; /* Adjusted padding */
                padding-right: 18px; /* Ensure enough space for menu indicator */
                background-color: #f0f0f0; /* Default light gray background */
                text-align: center; /* Center the text */
            }
            QToolButton:hover {
                background-color: #e0e0e0; /* Slightly darker on hover */
                border: 1px solid #c0c0c0; /* Border on hover */
            }
            QToolButton:pressed {
                background-color: #d0d0d0; /* Darker when pressed */
                border: 1px solid #a0a0a0;
            }
            QToolButton:checked {
                color: black; /* Black text when checked */
                background-color: lightblue; /* Light blue background when checked */
                border: 1px solid #80a0c0; /* Border for checked state */
            }
            QToolButton:checked:hover {
                background-color: #aaddff; /* Slightly different hover for checked state */
            }
            QToolButton[popupMode="1"], QToolButton[popupMode="2"] {
                /* The padding-right on QToolButton should cover this. */
                /* If specific adjustments are needed, they can be added here. */
            }

            QPushButton {
                border: 1px solid #d0d0d0; /* Default border */
                border-radius: 0px; /* Ensure square corners */
                padding: 5px 10px; /* More typical padding for push buttons */
                background-color: #f0f0f0;
                text-align: center; /* Center the text */
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border: 1px solid #c0c0c0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
                border: 1px solid #a0a0a0;
            }
            QPushButton:checked { /* If any QPushButton can be checkable */
                color: black;
                background-color: lightblue;
                border: 1px solid #80a0c0;
            }
            QPushButton:checked:hover {
                background-color: #aaddff;
            }
        """)

        # 模拟循环的定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.simulation_step)
        self.timer.start(16) # 大约60 FPS

        # --- Signal Connections ---
        self.selection_changed.connect(self._handle_selection_change_for_property_panel)
        self.property_panel.property_changed.connect(self._handle_property_change)
        self.property_panel.spring_anchor_changed.connect(self._trigger_scene_redraw_on_anchor_change) # New connection

    def _trigger_scene_redraw_on_anchor_change(self, spring_id: uuid.UUID):
        """Called when a spring's anchor property is changed, triggers a redraw."""
        print(f"弹簧锚点已更改 (ID: {spring_id})，请求重绘。")
        self.drawing_widget.update()

    def _get_entity_world_bbox(self, entity_id: uuid.UUID) -> Optional[QRectF]:
        """Calculates the world-coordinate bounding box of an entity."""
        transform = self.entity_manager.get_component(entity_id, TransformComponent)
        geometry = self.entity_manager.get_component(entity_id, GeometryComponent)

        if not transform or not geometry:
            return None

        if geometry.shape_type == ShapeType.RECTANGLE:
            width = geometry.parameters.get("width", 0)
            height = geometry.parameters.get("height", 0)
            # For a rotated rectangle, the AABB is more complex.
            # We need to transform all 4 local corners to world space and then find min/max.
            local_corners = [
                Vector2D(-width / 2, -height / 2), Vector2D(width / 2, -height / 2),
                Vector2D(width / 2, height / 2), Vector2D(-width / 2, height / 2)
            ]
            world_corners = [transform.position + lc.rotate(transform.angle) for lc in local_corners]
            
            min_x = min(wc.x for wc in world_corners)
            max_x = max(wc.x for wc in world_corners)
            min_y = min(wc.y for wc in world_corners)
            max_y = max(wc.y for wc in world_corners)
            return QRectF(QPointF(min_x, min_y), QPointF(max_x, max_y))

        elif geometry.shape_type == ShapeType.CIRCLE:
            radius = geometry.parameters.get("radius", 0)
            center = transform.position
            return QRectF(center.x - radius, center.y - radius, 2 * radius, 2 * radius)
        
        elif geometry.shape_type == ShapeType.POLYGON:
            local_vertices = geometry.parameters.get("vertices", [])
            if not local_vertices: return None
            world_vertices = [transform.position + lv.rotate(transform.angle) for lv in local_vertices]
            if not world_vertices: return None
            
            min_x = min(wv.x for wv in world_vertices)
            max_x = max(wv.x for wv in world_vertices)
            min_y = min(wv.y for wv in world_vertices)
            max_y = max(wv.y for wv in world_vertices)
            return QRectF(QPointF(min_x, min_y), QPointF(max_x, max_y))
            
        return None

    def _handle_selection_change_for_property_panel(self, entity_ids: Set[uuid.UUID], connection_ids: Set[uuid.UUID]):
        """Handles selection changes and updates the property panel's content.
        Does NOT automatically show or position the panel anymore."""
        self.property_panel.update_properties(entity_ids, connection_ids)
        print(f"属性面板内容已更新。实体: {len(entity_ids)}, 连接: {len(connection_ids)}")

        if not entity_ids and not connection_ids: # Nothing selected
            # If the panel is visible and now nothing is selected, hide it.
            # This assumes the panel should only be visible if there's a selection
            # that its content is reflecting.
            if self.properties_dock.isVisible():
                 self.properties_dock.hide()
            print(f"无选择，属性面板已更新 (如果可见则隐藏)。")
    
    def _show_and_position_property_panel(self):
        """Shows the property panel, sets it to floating, and positions it."""
        if not self.properties_dock:
            return

        self.properties_dock.setFloating(True)
        
        main_window_geom = self.geometry()
        panel_width = self.preferred_property_panel_width
        panel_height = main_window_geom.height()

        screen = QGuiApplication.screenAt(self.mapToGlobal(self.rect().center()))
        if not screen: # Fallback to primary screen
            screen = QGuiApplication.primaryScreen()
        
        available_screen_geom = screen.availableGeometry()

        # Default: position to the right of the main window, flush with the edge
        target_x = main_window_geom.right()
        target_y = main_window_geom.top()
        
        # Check if there's enough space on the right of the main window on the screen
        # (main_window.right() + panel_width) would be the right edge of the panel if placed externally.
        # Compare with the screen's right edge.
        if main_window_geom.right() + panel_width > available_screen_geom.right():
            # Not enough space on the right, position it inside DrawingWidget, on its right edge
            drawing_widget_global_top_left = self.drawing_widget.mapToGlobal(QPointF(0, 0))
            # Place it flush with the drawing_widget's right inner edge
            target_x = drawing_widget_global_top_left.x() + self.drawing_widget.width() - panel_width
            target_y = drawing_widget_global_top_left.y()
            panel_height = self.drawing_widget.height() # Match drawing widget height

        self.properties_dock.show()
        # Use QTimer.singleShot to ensure geometry is set after the dock is shown and floating.
        QTimer.singleShot(0, lambda: self.properties_dock.setGeometry(int(target_x), int(target_y), int(panel_width), int(panel_height)))
        self.properties_dock.raise_()

    def _handle_show_properties_for_entity(self, entity_id: uuid.UUID):
        """Handles the 'Properties' action from the context menu."""
        self.set_single_selected_object("ENTITY", entity_id)
        # set_single_selected_object will emit selection_changed,
        # which calls _handle_selection_change_for_property_panel to update content.
        # Now, explicitly show and position.
        self._show_and_position_property_panel()

    def _capture_and_store_initial_state(self):
        """
        Captures the current scene state as JSON (without simulation time) and stores it
        as the initial state for the current session. Also resets current_simulation_time to 0.
        """
        try:
            serializer = SceneSerializer()
            # Ensure include_time is False for initial state capture
            self._initial_scene_state_json = serializer.serialize_scene_to_json_string(
                self.entity_manager,
                include_time=False
            )
            print("已捕获并存储初始场景状态 (无时间戳)。")
        except Exception as e:
            self._initial_scene_state_json = None
            QMessageBox.critical(self, "状态存储错误", f"无法捕获初始场景状态: {e}")
        
        # Always reset time when capturing a new initial state
        self.current_simulation_time = 0.0
        self.is_simulation_running = False # Usually good to pause when setting a new start point
        self._update_time_display()
        if hasattr(self, 'pause_resume_action'): # Update button text if it exists
             self.pause_resume_action.setText("继续")


    @property
    def selected_entity_ids(self) -> Set[uuid.UUID]:
        return self._selected_entity_ids

    @property
    def selected_connection_ids(self) -> Set[uuid.UUID]:
        return self._selected_connection_ids

    def is_entity_selected(self, entity_id: uuid.UUID) -> bool:
        return entity_id in self._selected_entity_ids

    def clear_selection(self):
        """Clears all current selections."""
        changed = False
        if self._selected_entity_ids:
            self._selected_entity_ids.clear()
            changed = True
        if self._selected_connection_ids:
            self._selected_connection_ids.clear()
            changed = True
        
        if changed:
            print("选择已清除。")
            self.selection_changed.emit(self._selected_entity_ids, self._selected_connection_ids)
            self.drawing_widget.update()

    def set_single_selected_object(self, obj_type: Optional[str], obj_id: Optional[uuid.UUID]):
        """Sets a single object as selected, clearing previous selections."""
        self._selected_entity_ids.clear()
        self._selected_connection_ids.clear()
        
        if obj_id is not None and obj_type is not None:
            if obj_type == "ENTITY":
                self._selected_entity_ids.add(obj_id)
            elif obj_type.startswith("CONNECTION_") or obj_type == "SPRING_CONNECTION":
                self._selected_connection_ids.add(obj_id)
            else:
                print(f"警告: 未知对象类型 '{obj_type}' 无法添加到选择中。")
        
        print(f"单一选择已设置: 实体={self._selected_entity_ids}, 连接={self._selected_connection_ids}")
        self.selection_changed.emit(self._selected_entity_ids, self._selected_connection_ids)
        self.drawing_widget.update()

    def set_marquee_selection(self, entity_ids: Set[uuid.UUID], connection_ids: Set[uuid.UUID]):
        """Sets the selection based on a marquee operation, replacing previous selection."""
        self._selected_entity_ids = entity_ids.copy() # Ensure we have a copy
        self._selected_connection_ids = connection_ids.copy() # Ensure we have a copy
        
        print(f"框选结果: {len(entity_ids)} 个实体, {len(connection_ids)} 个连接。")
        self.selection_changed.emit(self._selected_entity_ids, self._selected_connection_ids)
        self.drawing_widget.update()

    def _select_by_type(self, item_type: Union[ShapeType, str]):
        """通用函数，用于按类型选择实体或连接。"""
        self.clear_selection()
        newly_selected_entities = set()
        newly_selected_connections = set()

        if isinstance(item_type, ShapeType): # Selecting Entities by Geometry
            for entity_id in self.entity_manager.entities: # Iterate over the set of entity IDs
                geom_comp = self.entity_manager.get_component(entity_id, GeometryComponent)
                if geom_comp and geom_comp.shape_type == item_type:
                    newly_selected_entities.add(entity_id)
        elif isinstance(item_type, str): # Kept for "SPRING" for now, but should ideally be ConnectionType.SPRING
            if item_type == "SPRING": # This specific string check is for SpringComponent
                all_springs = self.entity_manager.get_all_independent_components_of_type(SpringComponent)
                for spring in all_springs:
                    newly_selected_connections.add(spring.id)
            # For ROD and ROPE, we should receive ConnectionType enum members
            # This part of the logic might need adjustment if item_type is always a string from menu.
            # For now, assuming the calling context for ROD/ROPE will pass the enum.
            # If it passes strings "ROD" or "ROPE", this block won't match ConnectionType.ROD/ROPE.
        elif isinstance(item_type, ConnectionType): # Selecting Connections by ConnectionType Enum
            all_connections = self.entity_manager.get_all_independent_components_of_type(ConnectionComponent)
            for conn in all_connections:
                if conn.connection_type == item_type: # Direct enum comparison
                    newly_selected_connections.add(conn.id)
        
        self._selected_entity_ids.update(newly_selected_entities)
        self._selected_connection_ids.update(newly_selected_connections)

        if newly_selected_entities or newly_selected_connections:
            print(f"按类型选择: {item_type} - {len(newly_selected_entities)} 个实体, {len(newly_selected_connections)} 个连接")
            self.selection_changed.emit(self._selected_entity_ids, self._selected_connection_ids)
            self.drawing_widget.update()
        else:
            self.status_bar.showMessage(f"场景中没有找到类型为 '{item_type}' 的对象。", 2000)

    def _update_window_title(self):
        if self.scene_manager.current_scene_filepath:
            filename = os.path.basename(self.scene_manager.current_scene_filepath)
            self.setWindowTitle(f"PhysiSim - {filename}")
        else:
            self.setWindowTitle("PhysiSim - 未命名场景")

    def _create_menus(self):
        menubar = self.menuBar()
        
        # --- File Menu ---
        file_menu = menubar.addMenu("文件(&F)")

        # New Scene
        new_action = QAction("新建场景(&N)", self)
        new_action.setShortcut(QKeySequence.StandardKey.New) # Use standard key
        new_action.triggered.connect(self.scene_file_handler.new_scene) # Connect to handler
        file_menu.addAction(new_action)

        # Open Scene (Connects to the modified _handle_open_scene)
        open_action = QAction("打开场景或快照(&O)...", self) # Renamed for clarity
        open_action.setShortcut(QKeySequence.StandardKey.Open) # Use standard key
        open_action.triggered.connect(self.scene_file_handler.handle_open_scene) # Connect to handler
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()

        # Save Simulation Snapshot As...
        save_snapshot_action = QAction("保存模拟快照为(&P)...", self) # P for Snapshot
        save_snapshot_action.triggered.connect(self.scene_file_handler.handle_save_snapshot_as) # Connect to handler
        file_menu.addAction(save_snapshot_action)

        # Save Initial Setup As...
        save_initial_setup_action = QAction("保存初始设置为(&I)...", self) # I for Initial
        save_initial_setup_action.triggered.connect(self.scene_file_handler.handle_save_initial_setup_as) # Connect to handler
        file_menu.addAction(save_initial_setup_action)
        
        # Save Current as New Start Point As...
        save_current_as_start_point_action = QAction("将当前存为新起点并另存为(&T)...", self) # T for sTart point
        save_current_as_start_point_action.triggered.connect(self.scene_file_handler.handle_save_current_as_start_point_as) # Connect to handler
        file_menu.addAction(save_current_as_start_point_action)

        file_menu.addSeparator()

        # --- 预设相关操作 ---
        save_preset_action = QAction("将选中实体另存为预设(&V)...", self)
        save_preset_action.triggered.connect(self._save_selected_entity_as_preset)
        file_menu.addAction(save_preset_action)
        
        file_menu.addSeparator()
        
        # Exit
        exit_action = QAction("退出(&X)", self)
        # exit_action.setShortcut("Ctrl+Q") # Common on macOS/Linux
        exit_action.setShortcut("Alt+F4") # More common on Windows for main exit
        exit_action.triggered.connect(self._exit_app)
        file_menu.addAction(exit_action)

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑(&E)")
        self.create_from_preset_menu = QMenu("从预设创建(&P)", self)
        self.create_from_preset_menu.aboutToShow.connect(lambda: self._populate_create_from_preset_menu(self.create_from_preset_menu))
        edit_menu.addMenu(self.create_from_preset_menu)

        edit_menu.addSeparator()

        select_submenu = edit_menu.addMenu("选择(&S)")
        
        # Placeholder for Delete action in Edit menu (optional)
        # delete_selected_action = QAction("删除选中项", self)
        # delete_selected_action.setShortcut(QKeySequence.StandardKey.Delete)
        # delete_selected_action.triggered.connect(self._handle_delete_selected_objects)
        # edit_menu.addAction(delete_selected_action)
        # edit_menu.addSeparator()


        select_all_rects_action = QAction("选择所有矩形", self)
        select_all_rects_action.triggered.connect(lambda: self._select_by_type(ShapeType.RECTANGLE))
        select_submenu.addAction(select_all_rects_action)

        select_all_circles_action = QAction("选择所有圆形", self)
        select_all_circles_action.triggered.connect(lambda: self._select_by_type(ShapeType.CIRCLE))
        select_submenu.addAction(select_all_circles_action)
        
        select_submenu.addSeparator()

        select_all_springs_action = QAction("选择所有弹簧", self)
        select_all_springs_action.triggered.connect(lambda: self._select_by_type("SPRING")) # Using string for connection types
        select_submenu.addAction(select_all_springs_action)

        select_all_rods_action = QAction("选择所有轻杆", self)
        select_all_rods_action.triggered.connect(lambda: self._select_by_type(ConnectionType.ROD)) # Use Enum
        select_submenu.addAction(select_all_rods_action)

        select_all_ropes_action = QAction("选择所有轻绳", self)
        select_all_ropes_action.triggered.connect(lambda: self._select_by_type(ConnectionType.ROPE)) # Use Enum
        select_submenu.addAction(select_all_ropes_action)
        
        select_submenu.addSeparator()
        
        deselect_all_action = QAction("取消全选", self)
        deselect_all_action.setShortcut(QKeySequence("Ctrl+D")) # Common deselect shortcut
        deselect_all_action.triggered.connect(self.clear_selection)
        select_submenu.addAction(deselect_all_action)


        # --- View Menu ---
        view_menu = menubar.addMenu("视图(&V)")
        reset_view_action = QAction("标准视图(&R)", self)
        reset_view_action.setShortcut("Ctrl+0") # Common shortcut for reset zoom/view
        reset_view_action.triggered.connect(self.view_control_handler.reset_view) # Connect to handler
        view_menu.addAction(reset_view_action)

        # --- Simulation Menu (New) ---
        simulation_menu = menubar.addMenu("模拟(&M)") # M for Model or Motion

        jump_to_time_action = QAction("跳转到时间(&J)...", self)
        jump_to_time_action.triggered.connect(self.simulation_control_handler.jump_to_time) # Connect to handler
        simulation_menu.addAction(jump_to_time_action)

        simulation_menu.addSeparator() # Separator before the new action

        set_current_as_initial_action = QAction("设置当前状态为初始(&T)", self)
        set_current_as_initial_action.triggered.connect(self.simulation_control_handler.set_current_as_initial_state) # Connect to handler
        simulation_menu.addAction(set_current_as_initial_action)

        simulation_menu.addSeparator() # Separator before gravity toggle

        self.toggle_gravity_action = QAction("启用重力(&G)", self)
        self.toggle_gravity_action.setCheckable(True)
        self.toggle_gravity_action.setChecked(True) # Default to True, matching PhysicsSystem
        self.toggle_gravity_action.triggered.connect(
            lambda checked: self.simulation_control_handler.toggle_gravity(checked) # Connect to handler
        )
        simulation_menu.addAction(self.toggle_gravity_action)

        simulation_menu.addSeparator()

        physics_settings_action = QAction("物理参数设置(&P)...", self)
        physics_settings_action.triggered.connect(self._open_physics_settings_dialog)
        simulation_menu.addAction(physics_settings_action)


    def _open_physics_settings_dialog(self):
        if not self.physics_system or not self.physics_system.constraint_solver:
            QMessageBox.warning(self, "错误", "物理系统或约束求解器尚未初始化。")
            return
        
        dialog = PhysicsSettingsDialog(self) # Pass main_window (self)
        dialog.exec() # exec_() for older Qt, exec() for PySide6

    def _create_toolbar(self):
        toolbar = QToolBar("Tools")
        self.addToolBar(toolbar)

        # self.drawing_tool_group was initialized in __init__
        self.drawing_tool_group.setExclusive(True)

        select_action = QAction("选择", self)
        select_action.setCheckable(True)
        select_action.setChecked(True) # Default tool
        select_action.triggered.connect(lambda: self._set_tool_mode(ToolMode.SELECT))
        toolbar.addAction(select_action)
        self.drawing_tool_group.addAction(select_action)

        # Pan View Tool Button
        pan_view_action = QAction("平移视图", self)
        pan_view_action.setCheckable(True)
        # TODO: Set an icon for pan_view_action e.g. pan_view_action.setIcon(QIcon("path/to/pan_icon.png"))
        pan_view_action.triggered.connect(lambda: self._set_tool_mode(ToolMode.PAN_VIEW))
        toolbar.addAction(pan_view_action)
        self.drawing_tool_group.addAction(pan_view_action)

        toolbar.addSeparator() # Separator after select/pan

        draw_rect_action = QAction("绘制矩形", self)
        draw_rect_action.setCheckable(True)
        draw_rect_action.triggered.connect(lambda: self._set_tool_mode(ToolMode.DRAW_RECTANGLE))
        toolbar.addAction(draw_rect_action)
        self.drawing_tool_group.addAction(draw_rect_action)

        draw_circle_action = QAction("绘制圆形", self) # 新增：绘制圆形按钮
        draw_circle_action.setCheckable(True)
        draw_circle_action.triggered.connect(lambda: self._set_tool_mode(ToolMode.DRAW_CIRCLE))
        toolbar.addAction(draw_circle_action)
        self.drawing_tool_group.addAction(draw_circle_action)

        draw_polygon_action = QAction("绘制多边形", self)
        draw_polygon_action.setCheckable(True)
        # TODO: Set an icon for draw_polygon_action
        draw_polygon_action.triggered.connect(lambda: self._set_tool_mode(ToolMode.POLYGON_DRAW))
        toolbar.addAction(draw_polygon_action)
        self.drawing_tool_group.addAction(draw_polygon_action)

        draw_spring_action = QAction("绘制弹簧", self)
        draw_spring_action.setCheckable(True)
        draw_spring_action.triggered.connect(lambda: self._set_tool_mode(ToolMode.DRAW_SPRING))
        # Removed spring_mode_menu and related actions
        toolbar.addAction(draw_spring_action)
        self.drawing_tool_group.addAction(draw_spring_action)

        # --- Draw Rod Tool ---
        draw_rod_action = QAction("绘制轻杆", self)
        draw_rod_action.setCheckable(True)
        draw_rod_action.triggered.connect(lambda: self._set_tool_mode(ToolMode.DRAW_ROD))
        # Removed rod_mode_menu and related actions
        toolbar.addAction(draw_rod_action)
        self.drawing_tool_group.addAction(draw_rod_action)

        # --- Draw Rope Tool ---
        draw_rope_action = QAction("绘制轻绳", self)
        draw_rope_action.setCheckable(True)
        draw_rope_action.triggered.connect(lambda: self._set_tool_mode(ToolMode.DRAW_ROPE))
        # Removed rope_mode_menu and related actions
        toolbar.addAction(draw_rope_action)
        self.drawing_tool_group.addAction(draw_rope_action)

        toolbar.addSeparator() # Separator after drawing tools

        apply_force_action = QAction("施加力", self) # 新增：施加力按钮
        apply_force_action.setCheckable(True)
        apply_force_action.triggered.connect(lambda: self._set_tool_mode(ToolMode.APPLY_FORCE_AT_POINT))

        force_mode_menu = QMenu(self)
        force_mode_group = QActionGroup(self)
        force_mode_group.setExclusive(True)

        center_force_action = QAction("质心模式", self)
        center_force_action.setCheckable(True)
        center_force_action.setChecked(self.force_application_mode == ToolAttachmentMode.CENTER_OF_MASS)
        center_force_action.triggered.connect(lambda: self._set_force_application_mode(ToolAttachmentMode.CENTER_OF_MASS))
        force_mode_menu.addAction(center_force_action)
        force_mode_group.addAction(center_force_action)

        free_force_action = QAction("自由定位模式", self)
        free_force_action.setCheckable(True)
        free_force_action.setChecked(self.force_application_mode == ToolAttachmentMode.FREE_POSITION)
        free_force_action.triggered.connect(lambda: self._set_force_application_mode(ToolAttachmentMode.FREE_POSITION))
        force_mode_menu.addAction(free_force_action)
        force_mode_group.addAction(free_force_action)

        apply_force_action.setMenu(force_mode_menu)
        toolbar.addAction(apply_force_action)
        self.drawing_tool_group.addAction(apply_force_action)

        # --- Force Analysis Tool ---
        self.force_analysis_action = QAction("受力分析", self) # Store as attribute for menu updates
        self.force_analysis_action.setCheckable(True)
        self.force_analysis_action.triggered.connect(lambda: self._set_tool_mode(ToolMode.FORCE_ANALYSIS))

        force_analysis_menu = QMenu(self)
        self.force_analysis_display_mode_group = QActionGroup(self)
        self.force_analysis_display_mode_group.setExclusive(True)

        self.object_mode_action_ref = QAction("对象模式", self) # Store ref
        self.object_mode_action_ref.setCheckable(True)
        self.object_mode_action_ref.setChecked(self.force_analysis_display_mode == ForceAnalysisDisplayMode.OBJECT)
        self.object_mode_action_ref.triggered.connect(lambda: self._set_force_analysis_display_mode(ForceAnalysisDisplayMode.OBJECT))
        force_analysis_menu.addAction(self.object_mode_action_ref)
        self.force_analysis_display_mode_group.addAction(self.object_mode_action_ref)

        self.com_mode_action_ref = QAction("质心模式", self) # Store ref
        self.com_mode_action_ref.setCheckable(True)
        self.com_mode_action_ref.setChecked(self.force_analysis_display_mode == ForceAnalysisDisplayMode.CENTER_OF_MASS)
        self.com_mode_action_ref.triggered.connect(lambda: self._set_force_analysis_display_mode(ForceAnalysisDisplayMode.CENTER_OF_MASS))
        force_analysis_menu.addAction(self.com_mode_action_ref)
        self.force_analysis_display_mode_group.addAction(self.com_mode_action_ref)

        self.force_analysis_action.setMenu(force_analysis_menu)
        toolbar.addAction(self.force_analysis_action)
        self.drawing_tool_group.addAction(self.force_analysis_action)
        # --- End Force Analysis Tool ---

        toolbar.addSeparator() # Separator before simulation controls

        # Pause/Resume Button
        # Initial state is Paused (is_simulation_running = False), so button should say "继续"
        self.pause_resume_action = QAction("继续", self)
        self.pause_resume_action.triggered.connect(self.simulation_control_handler.toggle_pause_resume) # Connect to handler
        toolbar.addAction(self.pause_resume_action)

    def _set_tool_mode(self, mode: ToolMode):
        if self.current_tool_mode == mode: # No change if clicking the active tool again
            return

        old_mode = self.current_tool_mode
        self.current_tool_mode = mode
        print(f"Tool mode set from {old_mode.name} to: {self.current_tool_mode.name}")

        if self.drawing_widget: # Ensure drawing_widget is initialized
            # Deactivate old tool handler
            old_tool_handler = self.drawing_widget.tool_handlers.get(old_mode)
            if old_tool_handler:
                old_tool_handler.deactivate(self.drawing_widget)

            # Activate new tool handler
            new_tool_handler = self.drawing_widget.tool_handlers.get(mode)
            if new_tool_handler:
                new_tool_handler.activate(self.drawing_widget)
            
            self.drawing_widget.current_mouse_world_pos = None # Reset mouse pos for snap logic
            # self.drawing_widget.update() # activate/deactivate should handle updates if needed

        # Clearing general selection when switching to non-select/pan tools:
        if mode not in [ToolMode.SELECT, ToolMode.PAN_VIEW]:
             self.clear_selection()
        
        # Ensure drawing_widget is updated after tool switch and potential selection clear
        if self.drawing_widget:
            self.drawing_widget.update()


    def _set_force_application_mode(self, mode: ToolAttachmentMode):
        self.force_application_mode = mode
        print(f"Force application mode set to: {mode.name}")
        self.status_bar.showMessage(f"施力工具模式: {mode.name}", 2000)
        # Similar to above, QActionGroup should handle the visual check state.

    def _exit_app(self):
        # TODO: Add check for unsaved changes before exiting
        QApplication.instance().quit()

    def _save_selected_entity_as_preset(self):
        # This method involves UI (QInputDialog) and scene_manager logic.
        # It could be part of a hypothetical "PresetHandler" or stay in MainWindow
        # if it's considered a core MainWindow action. For now, keep here.
        if not self._selected_entity_ids: # Check if the set is empty
            QMessageBox.warning(self, "保存预设失败", "没有选中的实体。请先在场景中选择一个实体。")
            return
        
        # Assuming we save the first selected entity if multiple are selected.
        # Or, disable if more than one entity is selected.
        if len(self._selected_entity_ids) > 1:
            QMessageBox.warning(self, "保存预设失败", "请只选择一个实体以保存为预设。")
            return
            
        selected_entity_id_to_save = list(self._selected_entity_ids)[0]

        preset_name, ok = QInputDialog.getText(self, "保存预设", "请输入预设名称:")
        if ok and preset_name:
            try:
                self.scene_manager.save_entity_as_preset(selected_entity_id_to_save, preset_name)
                QMessageBox.information(self, "保存成功", f"实体已保存为预设 '{preset_name}'.")
                if hasattr(self, 'create_from_preset_menu'):
                    self._populate_create_from_preset_menu(self.create_from_preset_menu)
            except Exception as e:
                QMessageBox.critical(self, "保存预设失败", f"无法保存预设: {e}")
        elif ok and not preset_name:
            QMessageBox.warning(self, "无效名称", "预设名称不能为空。")

    def _populate_create_from_preset_menu(self, menu):
        # This is UI specific and tied to MainWindow's menu. Keep here.
        menu.clear()
        try:
            presets = self.scene_manager.get_available_presets()
            if not presets:
                action = QAction("无可用预设", self)
                action.setEnabled(False)
                menu.addAction(action)
            else:
                for preset_name in presets:
                    action = QAction(preset_name, self)
                    action.triggered.connect(lambda checked=False, name=preset_name: self._load_preset_to_scene(name))
                    menu.addAction(action)
        except Exception as e:
            QMessageBox.critical(self, "加载预设列表失败", f"无法获取可用预设列表: {e}")
            action = QAction(f"错误: {e}", self)
            action.setEnabled(False)
            menu.addAction(action)


    def _load_preset_to_scene(self, preset_name):
        # This involves UI and scene_manager. Keep here for now.
        x_str, ok_x = QInputDialog.getText(self, "加载预设 - 位置", f"为预设 '{preset_name}' 输入X坐标:", text="0.0")
        if not ok_x: return

        y_str, ok_y = QInputDialog.getText(self, "加载预设 - 位置", f"为预设 '{preset_name}' 输入Y坐标:", text="0.0")
        if not ok_y: return

        try:
            pos_x = float(x_str)
            pos_y = float(y_str)
            target_position = Vector2D(pos_x, pos_y)
            
            new_entity_id = self.scene_manager.load_preset_to_scene(preset_name, target_position)
            if new_entity_id is not None:
                QMessageBox.information(self, "加载成功", f"预设 '{preset_name}' 已加载到场景中。")
                self.drawing_widget.update()
            else:
                QMessageBox.warning(self, "加载预设", f"预设 '{preset_name}' 加载失败或未返回实体ID。")
        except ValueError:
            QMessageBox.critical(self, "输入错误", "无效的坐标值。")
        except Exception as e:
            QMessageBox.critical(self, "加载预设失败", f"无法加载预设 '{preset_name}': {e}")

    def _get_entity_at_world_pos(self, world_pos: Vector2D) -> Optional[uuid.UUID]:
        """Helper to find an entity at a given world position."""
        # This logic is similar to the selection logic in DrawingWidget.mousePressEvent
        # print(f"DEBUG _get_entity_at_world_pos: Checking for entity at {world_pos}. Total entities: {len(self.entity_manager.entities)}")
        for entity_id_candidate in self.entity_manager.entities:
            ident = self.entity_manager.get_component(entity_id_candidate, IdentifierComponent)
            # print(f"  Checking entity: {str(ident.id)[:8] if ident else str(entity_id_candidate)[:8]}")
            transform = self.entity_manager.get_component(entity_id_candidate, TransformComponent)
            geometry = self.entity_manager.get_component(entity_id_candidate, GeometryComponent)
            if transform and geometry:
                # print(f"    Entity {str(entity_id_candidate)[:8]} has Transform and Geometry.")
                if geometry.shape_type == ShapeType.RECTANGLE:
                    rect_params = geometry.parameters
                    half_width = rect_params["width"] / 2.0
                    half_height = rect_params["height"] / 2.0
                    
                    # Transform click point to rectangle's local coordinate system
                    # 1. Vector from rectangle center to click point (world coordinates)
                    vec_to_click_world = world_pos - transform.position
                    
                    # 2. Rotate this vector by the negative of the rectangle's angle
                    # transform.angle is in radians
                    click_local_x = vec_to_click_world.x * math.cos(-transform.angle) - vec_to_click_world.y * math.sin(-transform.angle)
                    click_local_y = vec_to_click_world.x * math.sin(-transform.angle) + vec_to_click_world.y * math.cos(-transform.angle)
                    
                    # 3. Check if the local click point is within the rectangle's half-dimensions
                    if -half_width <= click_local_x <= half_width and \
                       -half_height <= click_local_y <= half_height:
                        # print(f"    HIT on RECTANGLE: {str(entity_id_candidate)[:8]}")
                        return entity_id_candidate
                elif geometry.shape_type == ShapeType.CIRCLE:
                    circle_params = geometry.parameters
                    radius = circle_params["radius"]
                    center = transform.position
                    # This check MUST be inside the CIRCLE block
                    if (world_pos.x - center.x)**2 + (world_pos.y - center.y)**2 <= radius**2:
                        # print(f"    HIT on CIRCLE: {str(entity_id_candidate)[:8]}")
                        return entity_id_candidate
        # print(f"  No entity found at {world_pos}")
        return None

    # handle_rod_draw_click and _prompt_for_rod_parameters moved to RodToolHandler
    # handle_rope_draw_click and _prompt_for_rope_parameters moved to RopeToolHandler
    # handle_spring_draw_click and _prompt_for_spring_parameters moved to SpringToolHandler
    def _get_local_point_for_entity(self, entity_id: uuid.UUID, world_pos: Vector2D) -> Optional[Vector2D]:
        """
        Converts a world coordinate point to the local coordinate system of an entity.
        Returns None if the entity or its transform component cannot be found.
        """
        transform = self.entity_manager.get_component(entity_id, TransformComponent)
        if not transform:
            print(f"错误: 无法找到实体 {entity_id} 的 TransformComponent。")
            return None

        # LOG: Input to _get_local_point_for_entity
        print(f"DEBUG_GET_LOCAL: EntityID={str(entity_id)[:8]}, WorldClick={world_pos}")
        print(f"  Entity Transform: Pos={transform.position}, AngleRad={transform.angle:.4f} (approx {math.degrees(transform.angle):.2f} deg)")

        # 1. Calculate the vector from the entity's center (world) to the point (world)
        offset_world = world_pos - transform.position
        
        # 2. Rotate this vector by the negative of the entity's angle to align with the entity's local axes
        # TransformComponent.angle is already in radians
        entity_angle_rad = transform.angle
        
        # Using Vector2D.rotate for clarity and consistency
        local_offset = offset_world.rotate(-entity_angle_rad)

        # LOG: Output of _get_local_point_for_entity
        print(f"  OffsetWorld={offset_world}, EntityAngleForInverseRotation={-entity_angle_rad:.4f}")
        print(f"  Calculated LocalOffset={local_offset}")
        return local_offset

    def _determine_anchor_point(self, entity_id: uuid.UUID, world_click_pos: Vector2D, is_snap_active: bool) -> Vector2D:
        """
        Determines the final anchor point in world coordinates based on snap mode.
        If snap is active, it tries to snap to the closest snap point of the entity.
        Otherwise, or if no snap point is close enough, it uses the world_click_pos.
        This method returns the chosen anchor point in WORLD coordinates.
        The conversion to local coordinates for the component happens later.
        """
        entity_transform = self.entity_manager.get_component(entity_id, TransformComponent)
        entity_geom = self.entity_manager.get_component(entity_id, GeometryComponent)

        if not entity_transform or not entity_geom:
            # Should not happen if entity_id is valid and has these components
            return world_click_pos 

        if is_snap_active:
            local_snap_points = entity_geom.get_local_snap_points()
            if not local_snap_points:
                return world_click_pos # No snap points defined

            closest_world_snap_point = None
            min_dist_sq = float('inf')
            print(f"Determining anchor for entity {entity_id}, click_world: {world_click_pos}, snap_active: {is_snap_active}")
            print(f"  Snap threshold sq: {self.SNAP_THRESHOLD_PIXELS_SQ}")

            for i, local_sp in enumerate(local_snap_points):
                world_sp = entity_transform.position + local_sp.rotate(entity_transform.angle)
                
                screen_click_pos = self.drawing_widget.world_to_screen(world_click_pos)
                screen_sp_vis = self.drawing_widget.world_to_screen(world_sp) # For visualization/debug
                
                dist_sq = (screen_click_pos.x() - screen_sp_vis.x())**2 + (screen_click_pos.y() - screen_sp_vis.y())**2
                print(f"  Snap point {i}: local={local_sp}, world={world_sp}, screen={screen_sp_vis}, dist_sq_pixels={dist_sq:.2f}")
                
                if dist_sq < min_dist_sq:
                    min_dist_sq = dist_sq
                    closest_world_snap_point = world_sp
            
            print(f"  Closest snap point: {closest_world_snap_point}, min_dist_sq_pixels: {min_dist_sq:.2f}")
            if closest_world_snap_point and min_dist_sq < self.SNAP_THRESHOLD_PIXELS_SQ:
                print(f"  Snapped to point: {closest_world_snap_point}")
                return closest_world_snap_point # Return the world coordinates of the snapped point
            else:
                # No snap point close enough, or no snap points
                print(f"No snap, using click pos: {world_click_pos} (min_dist_sq_pixels: {min_dist_sq:.2f})")
                return world_click_pos
        else:
            # Snap is not active, use the precise click position
            print(f"Snap inactive, using click pos: {world_click_pos}")
            return world_click_pos

    def _jump_to_time(self):
        target_time_str, ok = QInputDialog.getText(self, "跳转到时间", "请输入目标模拟时间 (秒):", text=f"{self.current_simulation_time:.2f}")
        if not ok or not target_time_str:
            return

        try:
            target_time = float(target_time_str)
            if target_time < 0:
                QMessageBox.warning(self, "无效时间", "目标时间不能为负数。")
                return
        except ValueError:
            QMessageBox.warning(self, "无效输入", "请输入一个有效的时间数值。")
            return

        # 1. Pause simulation
        was_running = self.is_simulation_running
        if self.is_simulation_running:
            self._toggle_pause_resume() # This will set is_simulation_running to False and update button

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor) # Indicate busy

        # 2. Restore Initial State and Reset Time
        if self._initial_scene_state_json is None:
            QMessageBox.critical(self, "无法跳转", "没有可用的初始场景状态。请先新建或打开一个场景，或设置当前状态为初始。")
            QApplication.restoreOverrideCursor()
            if was_running: # Restore previous running state if reset failed early
                 self._toggle_pause_resume()
            return

        target_time_str, ok = QInputDialog.getText(self, "跳转到时间", "请输入目标模拟时间 (秒):", text=f"{self.current_simulation_time:.2f}")
        if not ok or not target_time_str:
            return

        try:
            target_time = float(target_time_str)
            if target_time < 0:
                QMessageBox.warning(self, "无效时间", "目标时间不能为负数。")
                return
        except ValueError:
            QMessageBox.warning(self, "无效输入", "请输入一个有效的时间数值。") # This was missing in the previous diff's search block
            return # This was missing in the previous diff's search block

        # The problematic try block was here, it should be part of the main flow of _jump_to_time
        # and not nested under the except ValueError of the QInputDialog.
        # The following block is the corrected structure for restoring state.
        try:
            # Deserialize_from_string should handle clearing the entity manager.
            # If not, self.entity_manager.clear_all() would be needed here.
            # Assuming SceneSerializer.deserialize_from_string clears existing entities first.
            SceneSerializer.deserialize_from_string(self.entity_manager, self._initial_scene_state_json)
            self.current_simulation_time = 0.0
            self.clear_selection() # Clear selection after restoring state
            self._update_time_display() # Update time display after reset
            print("Restored initial scene state for jump.")
        except Exception as e:
            QMessageBox.critical(self, "状态恢复错误", f"无法恢复初始场景状态: {e}")
            QApplication.restoreOverrideCursor()
            if was_running: # Restore previous running state if reset failed
                 self._toggle_pause_resume()
            return

        # 3. Fast Forward to Target Time
        if target_time > self.dt / 2: # Only simulate if target_time is significantly greater than 0
            print(f"Fast-forwarding from t=0 to target: {target_time:.2f}s")
            steps_to_simulate = int(target_time / self.dt)
            # Ensure current_simulation_time is 0 before starting the loop
            # self.current_simulation_time = 0.0 # Already set during reset

            for i in range(steps_to_simulate):
                if i % 100 == 0: # Provide some feedback for long jumps
                    QApplication.processEvents() # Keep UI responsive
                    print(f"  Fast-forward progress: Simulating up to {((i+1)*self.dt):.2f}s / {target_time:.2f}s (step {i+1}/{steps_to_simulate})")
                
                # _perform_simulation_step_core increments self.current_simulation_time internally by self.dt
                self._perform_simulation_step_core(render=False)
            
            # After the loop, self.current_simulation_time will be approximately steps_to_simulate * self.dt.
            # Set it precisely to target_time to avoid small floating point discrepancies.
            self.current_simulation_time = target_time
        else:
            # Target time is effectively 0 or very close, state is already at t=0 after reset.
            self.current_simulation_time = target_time # Ensure it's exactly target_time (e.g. 0.0)
            print(f"Jump to time {target_time:.2f}s (already at initial state or close to it).")

        # 4. Perform one final simulation step WITH rendering to show the final state.
        # This step should NOT advance time further if we want to be exactly at target_time.
        # So, we update display, then render.
        # If _perform_simulation_step_core is called with render=True, it will advance time.
        # Instead, we'll manually update the display and request a repaint.
        
        self._update_time_display() # Show the precise target time
        self.drawing_widget.update() # Render the scene at target_time

        # 5. Update UI and restore simulation state
        QApplication.restoreOverrideCursor()
        QMessageBox.information(self, "跳转完成", f"已跳转到模拟时间: {self.current_simulation_time:.2f}s")

        if was_running: # If it was running before jump, resume it
            self._toggle_pause_resume() # This will set is_simulation_running to True and update button
        # else: keep it paused, button already says "继续" (or was updated by _toggle_pause_resume if it was called)

    def _handle_set_current_as_initial(self):
        """Sets the current simulation state as the new initial state (t=0)."""
        # Pause simulation if running, to ensure a stable state is captured
        was_running = self.is_simulation_running
        if self.is_simulation_running:
            self._toggle_pause_resume()

        # Capture the current state and reset time
        self._capture_and_store_initial_state() # This method already prints a confirmation and resets time

        # Show a user-friendly message box
        QMessageBox.information(self, "设置初始状态", "当前场景状态已设为新的时间起点 (t=0)。\n跳转到时间将从此状态开始。")

        # Optionally resume simulation if it was running before
        # if was_running:
        #     self._toggle_pause_resume()
        # Let's keep it paused after this operation for clarity.

        self.drawing_widget.update() # Refresh view to reflect t=0 if needed

    def _toggle_gravity_ui(self, checked: bool):
        """Handles the UI action for toggling gravity."""
        if self.physics_system:
            self.physics_system.toggle_gravity(checked)
            status_message = "重力已启用。" if checked else "重力已禁用。"
            self.status_bar.showMessage(status_message, 2000) # Show for 2 seconds
            print(status_message)
            # No direct visual change from gravity toggle itself, but physics behavior will change.
            # self.drawing_widget.update() # Not strictly necessary unless gravity affects visual indicators
        else:
            QMessageBox.warning(self, "错误", "物理系统尚未初始化，无法切换重力。")
            # Revert the checkbox state if the system isn't ready
            if hasattr(self, 'toggle_gravity_action'):
                self.toggle_gravity_action.setChecked(not checked) # Revert UI

    def _perform_simulation_step_core(self, render: bool = True):
        """
        Performs the core logic of a simulation step.
        Can be called with render=False for fast-forwarding.
        """
        # --- Physics Update ---
        # Force accumulators should NOT be cleared before this section,
        # so that forces from tools (like ApplyForce) are included.
        # 1. Apply all force-generating systems (including gravity)
        if self.physics_system and self.physics_system.gravity_enabled and self.entity_manager:
            for entity_id_grav in self.entity_manager.get_entities_with_components(PhysicsBodyComponent, ForceAccumulatorComponent):
                phys_body_grav = self.entity_manager.get_component(entity_id_grav, PhysicsBodyComponent)
                force_acc_grav = self.entity_manager.get_component(entity_id_grav, ForceAccumulatorComponent)
                if phys_body_grav and force_acc_grav and not phys_body_grav.is_fixed and phys_body_grav.mass > 0:
                    gravity_force = self.physics_system.gravity * phys_body_grav.mass
                    force_acc_grav.add_force(gravity_force)
                    force_acc_grav.record_force_detail(
                        force_vector=gravity_force,
                        application_point_local=Vector2D(0,0),
                        force_type_label="Gravity"
                    )
        
        if self.spring_system:
            self.spring_system.update(self.dt) # Spring system adds forces
        # if self.rod_system: # Removed
        #     self.rod_system.update(self.dt) # Rod system adds forces # Removed

        if self.collision_system:
            self.collision_system.update(self.dt) # Collision system might add forces (e.g., contact forces) or resolve penetrations

        # 2. Perform initial physics integration (prediction step)
        # This updates positions and velocities based on all accumulated forces so far.
        # It also sets physics_body.previous_acceleration based on the current net_force.
        if self.physics_system:
            self.physics_system.update(self.dt)

        # 3. Store predicted state for PBD
        # These are the positions/angles *after* force integration but *before* PBD constraint solving.
        positions_after_physics_integration: Dict[uuid.UUID, Vector2D] = {}
        angles_after_physics_integration: Dict[uuid.UUID, float] = {}
        if self.entity_manager:
            for entity_id in self.entity_manager.get_entities_with_components(TransformComponent, PhysicsBodyComponent):
                transform = self.entity_manager.get_component(entity_id, TransformComponent)
                phys_body = self.entity_manager.get_component(entity_id, PhysicsBodyComponent)
                if transform and phys_body and not phys_body.is_fixed: # PBD only affects non-fixed bodies
                    positions_after_physics_integration[entity_id] = Vector2D(transform.position.x, transform.position.y)
                    angles_after_physics_integration[entity_id] = transform.angle

        # 4. Constraint Solving (PBD for Rods)
        # This will correct positions and then update velocities based on the difference
        # between corrected positions and `positions_after_physics_integration`.
        # ConstraintSolver temporarily disabled as Rod/Rope logic moved to active force systems.
        # if self.constraint_solver:
        #     # Pass the "predicted" state (after physics integration) as the "start" state for PBD velocity calculation.
        #     self.constraint_solver.update(self.dt, positions_after_physics_integration, angles_after_physics_integration)
        
        # Note: PhysicsSystem.update() is NOT called again after PBD.
        # PBD's velocity update is considered final for this step for entities it modified.
        # previous_acceleration was set correctly by PhysicsSystem in step 2 and NOT reset by PBD solver.

        # --- Scripting Update ---
        if self.script_engine and self.entity_manager:
            entities_with_scripts = self.entity_manager.get_entities_with_components(ScriptExecutionComponent)
            for entity_id in entities_with_scripts:
                script_comp = self.entity_manager.get_component(entity_id, ScriptExecutionComponent)
                if script_comp and script_comp.on_update:
                    context = self.script_engine.build_script_context(
                        entity_id=entity_id,
                        extra_context={'time': self.current_simulation_time, 'dt': self.dt}
                    )
                    try:
                        self.script_engine.execute_script(script_comp.on_update, context)
                    except Exception:
                        pass
        
        # --- Override dragged entity position (only if rendering, or always?)
        # This logic is handled in the main simulation_step after this core step.

        # --- Rendering Request (if applicable) ---
        # This should happen BEFORE clearing forces for the NEXT step.
        if render:
            self.drawing_widget.update()
            self._update_time_display()

        # --- Clear Forces for the NEXT simulation step ---
        # This is done AFTER all systems have used the forces for the current step
        # and after rendering (so forces can be visualized if needed).
        
        # --- Clear Forces for the NEXT simulation step (MOVED BACK TO START OF simulation_step()) ---
        # This should be done at the end of the current simulation step,
        # after all forces have been used by the physics integrator and constraints.
        # if self.entity_manager:
        #     entities_with_force_accumulators = self.entity_manager.get_entities_with_components(ForceAccumulatorComponent)
        #     for entity_id_fc in entities_with_force_accumulators:
        #         force_acc = self.entity_manager.get_component(entity_id_fc, ForceAccumulatorComponent)
        #         if force_acc:
        #             force_acc.clear_all()
        
        # --- Update Time ---
        # Time is updated *after* the step's calculations are based on the time *at the start* of the step,
        # and after forces from this step have been used and then cleared.
        self.current_simulation_time += self.dt

    def _toggle_pause_resume(self):
        self.is_simulation_running = not self.is_simulation_running
        if self.is_simulation_running:
            self.pause_resume_action.setText("暂停")
            # self.timer.start() # Not needed if timer is always running and step checks state
        else:
            self.pause_resume_action.setText("继续")
            # self.timer.stop() # Or let timer run and check state in simulation_step
        self._update_time_display() # Update time display even when paused/resumed

    def _update_time_display(self):
        if hasattr(self, 'time_label'):
            self.time_label.setText(f"时间: {self.current_simulation_time:.2f} s")

    def _create_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.time_label = QLabel(f"时间: {self.current_simulation_time:.2f} s")
        self.status_bar.addPermanentWidget(self.time_label)

    def simulation_step(self):
        if not self.is_simulation_running:
            # Still update display even if paused, so time label is accurate if jump occurred
            self._update_time_display()
            return

        # --- Clear Forces for the NEXT simulation step ---
        # This should be done at the beginning of a new simulation step,
        # before any new forces are calculated and accumulated.
        if self.entity_manager:
            entities_with_force_accumulators = self.entity_manager.get_entities_with_components(ForceAccumulatorComponent)
            for entity_id_fc in entities_with_force_accumulators:
                force_acc = self.entity_manager.get_component(entity_id_fc, ForceAccumulatorComponent)
                if force_acc:
                    try:
                        setattr(force_acc, 'logging_entity_id', str(entity_id_fc)[:8]) # Store partial ID for log
                        force_acc.clear_all()
                    finally:
                        if hasattr(force_acc, 'logging_entity_id'): # Clean up attribute
                            delattr(force_acc, 'logging_entity_id')
        
        # DEBUG: Print velocities at the START of the simulation_step, AFTER force clearing
        # but BEFORE _perform_simulation_step_core
        if self.entity_manager:
            # Let's pick one or two relevant entity IDs if known, or log for all non-fixed
            # For now, log for any entity that has a PhysicsBodyComponent and is not fixed
            # This might be a lot of logs if there are many entities.
            # Consider focusing on the entities involved in the problematic constraints.
            # For example, entity '691db3d6' from previous rope logs or '1e5e5e42' from rod logs.
            # If you know the entity IDs, you can add a specific check here.
            # Example: target_debug_ids = {uuid.UUID("your-entity-id-1"), uuid.UUID("your-entity-id-2")}
            
            # Logging for all non-fixed physics bodies to see their state at step start
            for eid_debug in self.entity_manager.get_entities_with_components(PhysicsBodyComponent):
                pb_debug = self.entity_manager.get_component(eid_debug, PhysicsBodyComponent)
                if pb_debug and not pb_debug.is_fixed:
                    print(f"[DEBUG_MAIN_SIM_STEP_START] Entity {str(eid_debug)[:8]} - Velocity at start of step: {pb_debug.velocity}, PrevAccel: {pb_debug.previous_acceleration}")

        # Perform the actual simulation physics, scripting, etc.
        # The core step now increments time and can optionally render/update display.
        # For the regular timer tick, we want the core logic, then drag override, then final render.
        
        initial_time_for_step = self.current_simulation_time # For context passing if needed
        
        # Perform core simulation step (physics, scripts). This will increment self.current_simulation_time.
        # Note: self.rope_system.update() is called within _perform_simulation_step_core
        # We will comment it out there if needed, or here if _perform_simulation_step_core is too broad.
        # Let's check _perform_simulation_step_core first.

        # In _perform_simulation_step_core:
        # if self.rope_system: # Add rope system update
        #    self.rope_system.update(self.dt)
        # This is the correct place to disable it if ConstraintSolver is handling ropes.

        self._perform_simulation_step_core(render=False) # render=False to avoid double rendering/display updates

        # --- Override dragged entity position before final rendering ---
        # Access drag state from the active SelectToolHandler
        current_tool_handler = self.drawing_widget.tool_handlers.get(self.current_tool_mode)
        if self.current_tool_mode == ToolMode.SELECT and \
           isinstance(current_tool_handler, SelectToolHandler) and \
           current_tool_handler.is_dragging_entity and \
           self.selected_entity_ids and \
           current_tool_handler.drag_target_world_position is not None:
            
            # If multiple entities are selected, this naive drag will move only one (the one drag started on)
            # or needs adjustment to move all selected entities.
            # For now, assuming drag_offset_from_entity_anchor was set based on one of the selected entities.
            # This part might need refinement if dragging multiple entities simultaneously is desired.
            # Let's assume if multiple are selected, only the one that initiated the drag (if we stored it) or the first one moves.
            if len(self.selected_entity_ids) == 1: # Only apply drag if one entity is selected for simplicity
                 entity_id_to_pin = list(self.selected_entity_ids)[0]
                 transform_to_pin = self.entity_manager.get_component(entity_id_to_pin, TransformComponent)
                 if transform_to_pin:
                     transform_to_pin.position = current_tool_handler.drag_target_world_position
        
        # --- Final Rendering and UI Update for this step ---
        self.drawing_widget.update() # Request repaint of the scene
        self._update_time_display()  # Ensure time display shows the new self.current_simulation_time

    def _get_connection_at_world_pos(self, world_pos: Vector2D) -> Optional[uuid.UUID]:
        """
        Identifies a connection (Spring, Rod, Rope) at a given world position.
        Returns the ID of the connection if found, otherwise None.
        Uses a screen-space click threshold.
        """
        CLICK_THRESHOLD_PIXELS_SQ = 10.0 * 10.0  # Squared pixel distance for selection threshold

        # Check SpringComponents
        all_springs = self.entity_manager.get_all_independent_components_of_type(SpringComponent)
        for spring in all_springs:
            entity_a_transform = self.entity_manager.get_component(spring.entity_a_id, TransformComponent)
            entity_b_transform = self.entity_manager.get_component(spring.entity_b_id, TransformComponent)

            if entity_a_transform and entity_b_transform:
                rotated_anchor_a = spring.anchor_a.rotate(entity_a_transform.angle)
                world_anchor_a = entity_a_transform.position + rotated_anchor_a
                rotated_anchor_b = spring.anchor_b.rotate(entity_b_transform.angle)
                world_anchor_b = entity_b_transform.position + rotated_anchor_b

                # Use the DrawingWidget's method for distance calculation
                dist_sq = self.drawing_widget._point_to_segment_distance_sq_world(world_pos, world_anchor_a, world_anchor_b)
                if dist_sq < CLICK_THRESHOLD_PIXELS_SQ:
                    return spring.id

        # Check ConnectionComponents (Rods, Ropes)
        all_connections = self.entity_manager.get_all_independent_components_of_type(ConnectionComponent)
        for conn in all_connections:
            if conn.is_broken:
                continue

            transform_a = self.entity_manager.get_component(conn.source_entity_id, TransformComponent)
            transform_b = self.entity_manager.get_component(conn.target_entity_id, TransformComponent)

            if transform_a and transform_b:
                rotated_anchor_a = conn.connection_point_a.rotate(transform_a.angle)
                world_anchor_a = transform_a.position + rotated_anchor_a
                rotated_anchor_b = conn.connection_point_b.rotate(transform_b.angle)
                world_anchor_b = transform_b.position + rotated_anchor_b
                
                dist_sq = self.drawing_widget._point_to_segment_distance_sq_world(world_pos, world_anchor_a, world_anchor_b)
                if dist_sq < CLICK_THRESHOLD_PIXELS_SQ:
                    return conn.id
        return None

    def _handle_delete_selected_objects(self):
        """Handles the deletion of currently selected entities and connections."""
        if not self.selected_entity_ids and not self.selected_connection_ids:
            return # Nothing to delete

        # --- 1. Collect all connections to be removed due to entity deletion ---
        connections_to_remove_indirectly = set()
        
        # Identify connections linked to entities being deleted
        if self.selected_entity_ids:
            all_spring_components = self.entity_manager.get_all_independent_components_of_type(SpringComponent)
            for spring in all_spring_components:
                if spring.entity_a_id in self.selected_entity_ids or \
                   spring.entity_b_id in self.selected_entity_ids:
                    connections_to_remove_indirectly.add((spring.id, SpringComponent))

            all_connection_components = self.entity_manager.get_all_independent_components_of_type(ConnectionComponent)
            for conn_comp in all_connection_components:
                if conn_comp.source_entity_id in self.selected_entity_ids or \
                   conn_comp.target_entity_id in self.selected_entity_ids:
                    connections_to_remove_indirectly.add((conn_comp.id, ConnectionComponent))
        
        # --- 2. Delete selected entities ---
        # Make a copy for iteration as the set might change if destroy_entity has side effects handled elsewhere
        entity_ids_to_delete = list(self.selected_entity_ids)
        for entity_id in entity_ids_to_delete:
            self.entity_manager.destroy_entity(entity_id)
            print(f"实体已删除: {entity_id}")

        # --- 3. Delete selected connections (directly selected) ---
        # Make a copy for iteration
        connection_ids_to_delete_directly = list(self.selected_connection_ids)
        for conn_id in connection_ids_to_delete_directly:
            # Need to determine the type of connection to pass to remove_independent_component_by_id
            # This requires checking if it's a SpringComponent or ConnectionComponent ID.
            # A bit inefficient, but necessary if IDs are just UUIDs without type info here.
            # Option 1: Try removing as Spring, then as Connection.
            # Option 2: Store type with ID in selected_connection_ids (e.g., as a tuple).
            # For now, let's try removing from both types if found.
            
            # Try removing as SpringComponent
            if self.entity_manager.remove_independent_component_by_id(conn_id, SpringComponent):
                print(f"选中的弹簧连接已删除: {conn_id}")
                continue # Found and removed, go to next ID
            
            # Try removing as ConnectionComponent (Rod/Rope)
            if self.entity_manager.remove_independent_component_by_id(conn_id, ConnectionComponent):
                print(f"选中的连接 (杆/绳) 已删除: {conn_id}")
        
        # --- 4. Delete indirectly selected connections (due to entity deletion) ---
        for conn_id, conn_type in connections_to_remove_indirectly:
            # Check if it wasn't already deleted as part of selected_connection_ids
            # (e.g., a spring was selected AND its entity was selected)
            if conn_id not in connection_ids_to_delete_directly:
                if self.entity_manager.remove_independent_component_by_id(conn_id, conn_type):
                    print(f"关联的 {conn_type.__name__} 已删除: {conn_id}")


        # --- 5. Clear selection and update UI ---
        self.clear_selection() # This will emit selection_changed, which PropertyPanel listens to.
        # self.property_panel.clear_display() # This call is redundant as clear_selection() will trigger update_properties.
        self.drawing_widget.update() # Ensure scene redraws

        print("删除操作完成。")


    # _prompt_for_force_vector and apply_external_force_at_point are now in ApplyForceToolHandler
    def _set_force_analysis_display_mode(self, mode: ForceAnalysisDisplayMode):
        if self.force_analysis_display_mode != mode:
            self.force_analysis_display_mode = mode
            print(f"Force analysis display mode set to: {mode.name}")

            # Update the check state of the menu actions (assuming refs are stored)
            if hasattr(self, 'object_mode_action_ref') and hasattr(self, 'com_mode_action_ref'):
                self.object_mode_action_ref.setChecked(mode == ForceAnalysisDisplayMode.OBJECT)
                self.com_mode_action_ref.setChecked(mode == ForceAnalysisDisplayMode.CENTER_OF_MASS)
            
            self.status_bar.showMessage(f"受力显示模式: {mode.name}", 3000)
            if self.force_analysis_target_entity_id: # Only redraw if an entity is selected for analysis
                self.drawing_widget.update()


    @Slot(object, str, str, Any) # object_id (UUID), component_type_name (str), attribute_name (str), new_value (Any)
    def _handle_property_change(self, object_id: Optional[uuid.UUID], component_type_name: str, attribute_name: str, new_value: Any):
        """
        处理来自 PropertyPanel 的属性更改信号。
        object_id 可以是实体ID或弹簧ID。
        """
        if object_id is None:
            return

        # 检查是否是 SpringComponent
        if component_type_name == SpringComponent.__name__:
            spring_component = self.entity_manager.get_independent_component_by_id(object_id, SpringComponent)
            if spring_component:
                if hasattr(spring_component, attribute_name):
                    try:
                        setattr(spring_component, attribute_name, new_value)
                        print(f"弹簧属性已更新: SpringID={object_id}.{attribute_name} = {new_value}")
                        # 锚点更改由 PropertyPanel.spring_anchor_changed 信号处理以触发重绘
                        # 其他弹簧属性 (rest_length, stiffness_k, damping_c) 的更改通常不需要立即重绘，
                        # 它们主要影响物理计算。如果需要，可以在这里添加 self.drawing_widget.update()。
                        # 对于此任务，只有锚点明确要求重绘。
                    except Exception as e:
                        print(f"错误: 更新弹簧属性时出错 {attribute_name} for SpringID {object_id}: {e}")
                else:
                    print(f"错误: 弹簧组件 (ID: {object_id}) 没有属性 '{attribute_name}'")
            else:
                print(f"错误: 找不到ID为 '{object_id}' 的弹簧组件")
            return # SpringComponent 处理完毕

        # 如果不是 SpringComponent，则按实体组件处理
        entity_uuid = object_id # 在这种情况下，object_id 是 entity_id

        component_class = None
        import physi_sim.core.component as components_module
        if hasattr(components_module, component_type_name):
            component_class = getattr(components_module, component_type_name)
        
        if not component_class or not issubclass(component_class, Component):
            print(f"错误: 未知的实体组件类型 '{component_type_name}'")
            return
 
        component = self.entity_manager.get_component(entity_uuid, component_class)
        if component:
            if hasattr(component, attribute_name):
                # Special handling for mass change to recompute moment of inertia
                if isinstance(component, PhysicsBodyComponent) and attribute_name == 'mass':
                    try:
                        new_mass = float(new_value)
                        # Update mass first
                        setattr(component, attribute_name, new_mass)
                        print(f"实体属性已更新: EntityID={entity_uuid}.PhysicsBodyComponent.mass = {new_mass}")

                        # --- Recompute Moment of Inertia ---
                        geometry_comp = self.entity_manager.get_component(entity_uuid, GeometryComponent)
                        physics_body_comp = component # Alias for clarity

                        if geometry_comp:
                            new_inertia = float('inf') # Default for mass <= 0 or unknown shape
                            if new_mass > 0:
                                if geometry_comp.shape_type == ShapeType.RECTANGLE:
                                    width = geometry_comp.parameters.get('width', 0)
                                    height = geometry_comp.parameters.get('height', 0)
                                    inertia = (1.0 / 12.0) * new_mass * (width**2 + height**2)
                                    new_inertia = max(inertia, 1e-6) # Ensure positive
                                elif geometry_comp.shape_type == ShapeType.CIRCLE:
                                    radius = geometry_comp.parameters.get('radius', 0)
                                    inertia = 0.5 * new_mass * radius**2
                                    new_inertia = max(inertia, 1e-6) # Ensure positive
                                else:
                                     print(f"警告: 无法为实体 {entity_uuid} 的未知形状 {geometry_comp.shape_type} 计算惯量，将使用默认值 inf。")
                                     new_inertia = float('inf') # Use inf for unknown shapes if mass > 0

                            old_inertia = physics_body_comp.moment_of_inertia
                            physics_body_comp.moment_of_inertia = new_inertia
                            print(f"  因质量更改，重新计算惯量: {old_inertia:.4f} -> {new_inertia:.4f}")
                        else:
                            print(f"警告: 实体 {entity_uuid} 缺少 GeometryComponent，无法重新计算惯量。")
                        # --- End Recompute ---

                        self.drawing_widget.update() # 触发重绘
                    except ValueError:
                        print(f"错误: 无效的质量值 '{new_value}' for entity {entity_uuid}")
                        QMessageBox.warning(self, "属性更新失败", f"无效的质量值: {new_value}。请输入数字。")
                    except Exception as e:
                        print(f"错误: 更新实体质量或惯量时出错 for entity {entity_uuid}: {e}")
                        QMessageBox.critical(self, "属性更新失败", f"更新质量或惯量时发生内部错误: {e}")
                else: # Handle other attributes normally
                    try:
                        # Attempt to convert value based on component type hint if possible? (More robust)
                        # For now, assume PropertyPanel provides a reasonable type.
                        setattr(component, attribute_name, new_value)
                        print(f"实体属性已更新: EntityID={entity_uuid}.{component_type_name}.{attribute_name} = {new_value}")
                        self.drawing_widget.update() # 触发重绘以反映实体组件更改
                    except Exception as e:
                        print(f"错误: 更新实体属性时出错 {attribute_name} for {component_type_name} on entity {entity_uuid}: {e}")
                        QMessageBox.critical(self, "属性更新失败", f"更新属性 '{attribute_name}' 时发生内部错误: {e}")
            else:
                print(f"错误: 实体组件 '{component_type_name}' on entity {entity_uuid} 没有属性 '{attribute_name}'")
        else:
            print(f"错误: 找不到实体 '{entity_uuid}' 的组件 '{component_type_name}'")

    def keyPressEvent(self, event: QKeyEvent):
        """Handles key press events for the main window, e.g., Delete key."""
        key = event.key()
        modifiers = event.modifiers()

        # Handle Delete Key for deleting selected objects
        if key == Qt.Key.Key_Delete:
            if self.current_tool_mode == ToolMode.SELECT and \
               (self.selected_entity_ids or self.selected_connection_ids):
                print("Delete key pressed with selection in SELECT mode. Handling deletion.")
                self._handle_delete_selected_objects()
                event.accept()
                return # Delete handled

        # --- Shift Key (Snap Toggle for Connection Tools) ---
        # This logic is now primarily in DrawingWidget.keyPressEvent / keyReleaseEvent
        # MainWindow might need to be aware if global state related to snap is held here,
        # but current implementation has snap_active in DrawingWidget.

        # Allow DrawingWidget to handle its own key events first (like WASD pan)
        # or tool-specific key events.
        # We need to be careful not to consume events that DrawingWidget's handlers expect.
        # The DrawingWidget's keyPressEvent is called if it has focus.
        # If MainWindow gets the event first, we can forward it or handle global shortcuts here.
        
        # For now, let DrawingWidget handle its specific keys.
        # If Delete was not handled above, pass to super.
        if not event.isAccepted():
            # print(f"MainWindow keyPressEvent: Key {key} not accepted yet, passing to super.")
            super().keyPressEvent(event)
            # If super() doesn't accept it, and DrawingWidget has focus, it might get it.
            # If DrawingWidget does not have focus, this event might be lost for it.
            # Consider explicitly passing to drawing_widget if needed and if it's a child.
            # self.drawing_widget.keyPressEvent(event) # This might lead to double processing.

if __name__ == '__main__': # 用于直接测试运行此文件
    import sys
    app = QApplication(sys.argv)
    # For testing, create a mock EntityManager or a real one
    em = EntityManager()
    
    # Create a sample entity for testing property panel
    # Ensure all component types used here are discoverable by components_module
    # For example, by ensuring they are defined in physi_sim.core.component or imported there.

    # It's better to define TestRenderComponent in a place where it's naturally imported,
    # or ensure physi_sim.core.component imports it if it's in a separate file.
    # For this test, we'll define it and try to make it available.
    import physi_sim.core.component as components_module
    import dataclasses

    if not hasattr(components_module, 'TestRenderComponent'):
        @dataclasses.dataclass
        class TestRenderComponent(Component):
            color: tuple = (255,0,0,255) # RGBA
            is_visible: bool = True
            some_float: float = 1.23
            description: str = "Test Description"
        # This makes TestRenderComponent available via components_module.TestRenderComponent
        setattr(components_module, 'TestRenderComponent', TestRenderComponent)
    else:
        TestRenderComponent = getattr(components_module, 'TestRenderComponent')


    test_entity_id = em.create_entity("test_rect_1")
    em.add_component(test_entity_id, TransformComponent(position=Vector2D(50,50), rotation=10.0, scale=Vector2D(1.0, 1.0)))
    # GeometryComponent's color parameter might conflict if RenderComponent also has color.
    # For property panel testing, ensure distinct or well-handled attributes.
    # The `parameters` dict in GeometryComponent is not directly editable by the current PropertyPanel design
    # as it doesn't iterate through dict fields. PropertyPanel primarily works with dataclass fields.
    em.add_component(test_entity_id, GeometryComponent(shape_type=ShapeType.RECTANGLE, parameters={"width":30, "height":40}))
    em.add_component(test_entity_id, TestRenderComponent(color=(100,150,200,255), is_visible=True, some_float=3.14, description="First Rectangle"))

    test_entity_id_2 = em.create_entity("test_circle_1")
    em.add_component(test_entity_id_2, TransformComponent(position=Vector2D(150,100), rotation=0.0, scale=Vector2D(1.2, 1.2)))
    em.add_component(test_entity_id_2, GeometryComponent(shape_type=ShapeType.CIRCLE, parameters={"radius":25}))
    em.add_component(test_entity_id_2, TestRenderComponent(color=(50,200,50,200), is_visible=False, some_float=0.5, description="A Circle"))


    window = MainWindow(em) # Pass the entity manager
    
    # Setup a basic renderer
    from physi_sim.graphics.renderer_system import RendererSystem
    # Ensure RendererSystem can handle TestRenderComponent or a generic way to get color/visibility
    # For now, we assume RendererSystem might look for common component names or specific ones.
    # If TestRenderComponent is used for rendering properties, RendererSystem needs to know about it.
    if window.renderer_system is None:
        # Pass a mapping of component types that the renderer should use for visual properties
        # This is a more robust way than hardcoding in the renderer.
        # For simplicity, we'll assume RendererSystem is flexible or we adapt it.
        window.renderer_system = RendererSystem(window.entity_manager)
    window.drawing_widget.renderer_system = window.renderer_system

    # Initialize SpringSystem for testing if needed
    # Systems are now initialized in MainWindow.__init__
    # if window.spring_system is None:
    #     window.spring_system = SpringSystem(window.entity_manager)
    # if window.rope_system is None: # Initialize RopeSystem for testing
    #     window.rope_system = RopeSystem(window.entity_manager)
    # if not hasattr(window, 'rod_system') or window.rod_system is None: # Initialize RodSystem for testing
    #     window.rod_system = RodSystem(window.entity_manager)
    
    # 设置一个初始大小，这个大小应该能容纳绘图区和预留的属性面板空间
    initial_width = 800 + 350 # drawing_min_width + preferred_prop_width (approx)
    initial_height = 700
    window.resize(initial_width, initial_height)
    # window.setFixedWidth(initial_width) # 仍然可以尝试固定宽度

    window.show()
    
    # 之前的初始化已通过 QTimer.singleShot 隐藏 dock
    # 无需在此处再做操作

    sys.exit(app.exec())