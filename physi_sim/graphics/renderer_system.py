from typing import TYPE_CHECKING, Optional, List, TYPE_CHECKING, Set # Add TYPE_CHECKING, Set
from physi_sim.core.system import System
from physi_sim.core.component import (
    TransformComponent, GeometryComponent, RenderComponent, ShapeType,
    SpringComponent, ForceAccumulatorComponent, ForceDetail, IdentifierComponent,
    ConnectionComponent, ConnectionType # Use ConnectionType Enum
)
from physi_sim.core.vector import Vector2D
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPolygonF, QFont # QPointF is not directly used but good to be aware, Added QFont
from PySide6.QtCore import Qt, QPointF, QRectF # Added QPointF for polygon
import uuid # For comparing UUIDs if selected_entity_id is UUID
import math # For math.degrees for rotation

# Need ForceAnalysisDisplayMode, potentially circular import risk.
# Let's try importing and see. If it fails, define it locally or pass int/enum value.
try:
    from physi_sim.graphics.main_window import ForceAnalysisDisplayMode
except ImportError:
    # Fallback if circular import detected - define locally or expect integer
    # This is less ideal. A better structure would avoid this.
    from enum import Enum, auto
    class ForceAnalysisDisplayMode(Enum):
        OBJECT = auto()
        CENTER_OF_MASS = auto()
    print("Warning: Could not import ForceAnalysisDisplayMode from main_window, using local definition.")


if TYPE_CHECKING:
    from physi_sim.core.entity_manager import EntityManager
    from .main_window import DrawingWidget # Add this import for type hinting

class RendererSystem(System):
    def __init__(self, entity_manager: 'EntityManager'): # Removed drawing_widget from constructor
        super().__init__(entity_manager)
        # self.drawing_widget = drawing_widget # No longer needed here if rendering is self-contained

    def update(self, dt: float) -> None:
        pass # Rendering is driven by paintEvent in DrawingWidget

    def render_scene(self, painter: 'QPainter',
                     drawing_widget_ref: Optional['DrawingWidget'] = None, # Added parameter
                     selected_entity_ids: Optional[Set[uuid.UUID]] = None, # Updated for multi-select
                     selected_connection_ids: Optional[Set[uuid.UUID]] = None, # Updated for multi-select
                     spring_creation_entity_a_id: Optional[uuid.UUID] = None, # For DRAW_SPRING tool highlighting
                     spring_creation_entity_b_id: Optional[uuid.UUID] = None,  # For DRAW_SPRING tool highlighting
                     highlighted_force_entity_id: Optional[uuid.UUID] = None, # For APPLY_FORCE_AT_POINT tool highlighting
                     # --- Rod/Rope creation highlight ---
                     rod_pending_selection_id: Optional[uuid.UUID] = None,
                     rod_second_pending_selection_id: Optional[uuid.UUID] = None,
                     rope_pending_selection_id: Optional[uuid.UUID] = None,
                     rope_second_pending_selection_id: Optional[uuid.UUID] = None,
                     # --- Added for Force Analysis ---
                     force_analysis_target_entity_id: Optional[uuid.UUID] = None,
                     force_analysis_display_mode: ForceAnalysisDisplayMode = ForceAnalysisDisplayMode.OBJECT,
                     pixels_per_world_unit: float = 50.0, # Get actual value from drawing widget
                     force_scale_reference: float = 10.0, # e.g., 10 Newtons
                     force_scale_pixels: float = 50.0     # e.g., 10 N = 50 pixels
                     # --- End Added ---
                     ) -> None:
       # Attempt to get TestRenderComponent first, then fall back to RenderComponent
       # This is a temporary measure for the test component.
        # A better approach would be a more generic way to specify render properties.
        import physi_sim.core.component as components_module
        ActualRenderComponent = RenderComponent # Default
        if hasattr(components_module, 'TestRenderComponent'):
            ActualRenderComponent = getattr(components_module, 'TestRenderComponent')

        # Get all entities with necessary components for rendering
        renderable_entities = []
        # FIX: Iterate directly over the set of entities
        for entity_id in self.entity_manager.entities: # Iterate directly over the set
            # Ensure entity_id is a UUID if that's what EntityManager uses internally
            # if not isinstance(entity_id, uuid.UUID):
            #     try: # Assuming entity_id might be string, convert to UUID for consistency
            #         entity_id = uuid.UUID(entity_id)
            #     except ValueError:
            #         continue # Skip if ID is not a valid UUID string

            if not (self.entity_manager.has_component(entity_id, TransformComponent) and \
                    self.entity_manager.has_component(entity_id, GeometryComponent)):
                continue

            render_info_for_sort = self.entity_manager.get_component(entity_id, ActualRenderComponent)
            if not render_info_for_sort and ActualRenderComponent is not RenderComponent:
                render_info_for_sort = self.entity_manager.get_component(entity_id, RenderComponent)
            
            z_order = 0 # Default z_order
            if render_info_for_sort and hasattr(render_info_for_sort, 'z_order'):
                z_order = render_info_for_sort.z_order
                
            # Get creation order from EntityManager
            creation_order = self.entity_manager.entity_creation_order.get(entity_id, -1) # Default to -1 if not found

            renderable_entities.append({'id': entity_id, 'z_order': z_order, 'creation_order': creation_order})

        # Sort entities first by z_order, then by creation_order (higher creation_order rendered last/on top)
        renderable_entities.sort(key=lambda e: (e['z_order'], e['creation_order']))

        # Iterate over sorted entities
        for entity_data in renderable_entities:
            entity_id = entity_data['id'] # This should be a UUID
            transform = self.entity_manager.get_component(entity_id, TransformComponent)
            geometry = self.entity_manager.get_component(entity_id, GeometryComponent)

            # Try to get TestRenderComponent, then RenderComponent
            render_info = self.entity_manager.get_component(entity_id, ActualRenderComponent)
            if not render_info and ActualRenderComponent is not RenderComponent: # Fallback if TestRenderComponent was primary
                render_info = self.entity_manager.get_component(entity_id, RenderComponent)

            if not transform or not geometry: # render_info is optional for basic shape drawing
                continue
            
            # Updated selection check for entities
            is_selected_as_entity = selected_entity_ids is not None and entity_id in selected_entity_ids
            
            # Highlighting for entities being selected for spring creation (DRAW_SPRING tool)
            is_spring_creation_highlight_a = (entity_id == spring_creation_entity_a_id)
            is_spring_creation_highlight_b = (entity_id == spring_creation_entity_b_id)
            
            # Highlighting for entity selected for force application (APPLY_FORCE_AT_POINT tool)
            is_highlighted_for_force = (entity_id == highlighted_force_entity_id)
            # Rod/Rope pending highlight
            is_rod_pending_highlight = (entity_id == rod_pending_selection_id or entity_id == rod_second_pending_selection_id)
            is_rope_pending_highlight = (entity_id == rope_pending_selection_id or entity_id == rope_second_pending_selection_id)
            # --- Added: Check if this entity is the target for force analysis ---
            is_force_analysis_target = (entity_id == force_analysis_target_entity_id)
            # --- End Added ---

            painter.save()

            # Apply rotation
            # The actual drawing calls below will need to be adjusted
            # to draw relative to the new (0,0) which is the entity's center.
            if hasattr(transform, 'angle') and transform.angle != 0:
                # Translate to the object's center
                painter.translate(transform.position.x, transform.position.y)
                # Rotate
                painter.rotate(math.degrees(transform.angle))
                # The drawing origin is now the object's center.
                # We need to translate back by -transform.position for drawing if shapes are defined in world space,
                # OR, define shapes relative to their own center. The latter is better.
                # For now, let's assume drawing functions will adjust.
                # We will adjust the drawing calls for rect, circle, polygon to draw around (0,0) in local rotated space.


            # Visibility check (assuming 'visible' or 'is_visible' attribute)
            is_visible = True
            if hasattr(render_info, 'is_visible'):
                is_visible = render_info.is_visible
            elif hasattr(render_info, 'visible'): # Fallback for TransformComponent-like visibility
                is_visible = render_info.visible
            
            if not is_visible and hasattr(transform, 'visible') and not transform.visible: # Double check with transform if applicable
                painter.restore()
                continue
            elif not is_visible and not (hasattr(transform, 'visible') and not transform.visible): # only render_info says not visible
                 painter.restore()
                 continue


            # Setup brush and pen
            fill_c_tuple = (128, 128, 128, 128) # Default semi-transparent grey
            stroke_c_tuple = (0,0,0,255) # Default black
            stroke_w = 1.0

            if render_info:
                if hasattr(render_info, 'color'): # For TestRenderComponent or similar
                    fill_c_tuple = render_info.color
                elif hasattr(render_info, 'fill_color'): # For original RenderComponent
                    fill_c_tuple = render_info.fill_color
                
                if hasattr(render_info, 'stroke_color'):
                    stroke_c_tuple = render_info.stroke_color
                if hasattr(render_info, 'stroke_width'):
                    stroke_w = render_info.stroke_width
            elif hasattr(geometry, 'parameters') and 'color' in geometry.parameters:
                # Fallback to GeometryComponent's color if no RenderComponent
                fill_c_tuple = geometry.parameters['color']


            fill_color = QColor(*[int(c) for c in fill_c_tuple]) if fill_c_tuple else QColor(Qt.GlobalColor.gray) # Ensure int components
            
            if fill_color.alpha() == 0:
                 painter.setBrush(Qt.BrushStyle.NoBrush)
            else:
                painter.setBrush(QBrush(fill_color, Qt.BrushStyle.SolidPattern))

            pen = QPen()
            main_window = painter.device().window() # Try to get MainWindow
            pixels_per_unit = 50.0 # Default fallback
            if hasattr(main_window, 'drawing_widget') and hasattr(main_window.drawing_widget, 'pixels_per_world_unit'):
                pixels_per_unit = main_window.drawing_widget.pixels_per_world_unit
            
            effective_stroke_width_world = stroke_w / pixels_per_world_unit if pixels_per_world_unit > 0 else stroke_w

            if is_selected_as_entity:
                pen.setColor(QColor(Qt.GlobalColor.yellow)) # Yellow for selected entity
                selected_stroke_width_pixels = (stroke_w + 2.5) if stroke_w > 0 else 2.5 # Slightly thicker
                pen.setWidthF(selected_stroke_width_pixels / pixels_per_world_unit if pixels_per_world_unit > 0 else selected_stroke_width_pixels)
                pen.setStyle(Qt.PenStyle.DashLine)
            elif is_force_analysis_target: # <<< Added: Force analysis highlight takes precedence over others for now
                pen.setColor(QColor(0, 255, 0, 200)) # Bright Green, slightly transparent
                highlight_stroke_width_pixels = 3.0 # Make it noticeable
                pen.setWidthF(highlight_stroke_width_pixels / pixels_per_world_unit if pixels_per_world_unit > 0 else highlight_stroke_width_pixels)
                pen.setStyle(Qt.PenStyle.SolidLine) # Solid line for force analysis target
            elif is_spring_creation_highlight_a or is_spring_creation_highlight_b: # Highlight for DRAW_SPRING tool
                pen.setColor(QColor(Qt.GlobalColor.magenta)) # Changed to Magenta for distinct highlight
                highlight_stroke_width_pixels = 2.5 # Fixed pixel width for highlight consistency
                pen.setWidthF(highlight_stroke_width_pixels / pixels_per_unit if pixels_per_unit > 0 else highlight_stroke_width_pixels)
                pen.setStyle(Qt.PenStyle.SolidLine) # Ensure solid line style
            elif is_rod_pending_highlight: # Highlight for DRAW_ROD tool (entity A)
                pen.setColor(QColor(144, 238, 144)) # Light Green
                highlight_stroke_width_pixels = 2.5
                pen.setWidthF(highlight_stroke_width_pixels / pixels_per_unit if pixels_per_unit > 0 else highlight_stroke_width_pixels)
                pen.setStyle(Qt.PenStyle.SolidLine)
            elif is_rope_pending_highlight: # Highlight for DRAW_ROPE tool (entity A)
                pen.setColor(QColor(255, 215, 0)) # Gold (more visible yellow)
                highlight_stroke_width_pixels = 2.5
                pen.setWidthF(highlight_stroke_width_pixels / pixels_per_unit if pixels_per_unit > 0 else highlight_stroke_width_pixels)
                pen.setStyle(Qt.PenStyle.SolidLine)
            elif is_highlighted_for_force: # Highlight for APPLY_FORCE_AT_POINT tool
                pen.setColor(QColor(Qt.GlobalColor.darkCyan)) # Dark Cyan for force target highlight (to differentiate from rod/rope pending)
                highlight_stroke_width_pixels = 2.5 # Use same thickness as spring highlight
                pen.setWidthF(highlight_stroke_width_pixels / pixels_per_unit if pixels_per_unit > 0 else highlight_stroke_width_pixels)
                pen.setStyle(Qt.PenStyle.SolidLine)
            elif stroke_c_tuple and stroke_w > 0: # Normal stroke
                pen.setColor(QColor(*[int(c) for c in stroke_c_tuple]))
                pen.setWidthF(effective_stroke_width_world)
                pen.setStyle(Qt.PenStyle.SolidLine)
            else:
                pen.setStyle(Qt.PenStyle.NoPen)
            
            pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin) # For sharp corners for all stroked items
            painter.setPen(pen)
 
            if geometry.shape_type == ShapeType.RECTANGLE:
                rect_params = geometry.parameters
                width = rect_params["width"]
                height = rect_params["height"]
                # If rotated, draw centered at (0,0) in the rotated coordinate system
                if hasattr(transform, 'angle') and transform.angle != 0:
                    painter.drawRect(QRectF(-width / 2, -height / 2, width, height))
                else: # Original behavior if no rotation
                    rect_x = transform.position.x - width / 2
                    rect_y = transform.position.y - height / 2
                    painter.drawRect(QRectF(rect_x, rect_y, width, height))
            
            elif geometry.shape_type == ShapeType.CIRCLE:
                circle_params = geometry.parameters
                radius = circle_params["radius"]
                # If rotated, draw centered at (0,0) in the rotated coordinate system
                if hasattr(transform, 'angle') and transform.angle != 0:
                    painter.drawEllipse(QPointF(0, 0), radius, radius)
                else: # Original behavior if no rotation
                    center_x = transform.position.x
                    center_y = transform.position.y
                    painter.drawEllipse(QPointF(center_x, center_y), radius, radius)

            elif geometry.shape_type == ShapeType.POLYGON: # Check for POLYGON directly
                poly_params = geometry.parameters
                # Ensure 'vertices' key exists and contains a list of Vector2D
                local_vertices = poly_params.get("vertices", [])
                
                q_points = []
                if hasattr(transform, 'angle') and transform.angle != 0:
                    # If rotated, painter is already translated to entity's position and rotated.
                    # Local vertices are drawn directly as they are relative to this transformed origin.
                    for v_local in local_vertices:
                        if isinstance(v_local, Vector2D):
                            q_points.append(QPointF(v_local.x, v_local.y))
                else:
                    # No rotation, painter is not translated to entity's position yet for this drawing path.
                    # Vertices are local, so add entity's world position.
                    for v_local in local_vertices:
                        if isinstance(v_local, Vector2D):
                            world_vertex = transform.position + v_local
                            q_points.append(QPointF(world_vertex.x, world_vertex.y))
                
                if len(q_points) >= 3:
                    polygon = QPolygonF(q_points)
                    painter.drawPolygon(polygon)

            painter.restore() # Restore painter state for this entity

        # --- Render Springs ---
        # This should be done after all entities are drawn, so springs appear on top or as defined by their own z-order (if implemented)
        # The painter's transform is currently reset after each entity. 
        # For global components like springs, we need to ensure the painter is in the correct world-transformed state.
        # The DrawingWidget's paintEvent sets up the main world transform. We are inside that transform here.

        # Render independent SpringComponents
        spring_components = self.entity_manager.get_all_independent_components_of_type(SpringComponent)
        if spring_components:
            default_spring_color = QColor(80, 80, 80, 220) # Dark grey
            selected_spring_color = QColor(Qt.GlobalColor.blue) # Blue for selected spring
            default_spring_pixel_width = 1.5
            selected_spring_pixel_width = 3.0 # Thicker for selected spring

            for spring_comp in spring_components:
                entity_a_transform = self.entity_manager.get_component(spring_comp.entity_a_id, TransformComponent)
                entity_b_transform = self.entity_manager.get_component(spring_comp.entity_b_id, TransformComponent)

                if entity_a_transform and entity_b_transform:
                    # Apply entity rotation to anchors if they are local offsets
                    rotated_anchor_a = spring_comp.anchor_a.rotate(entity_a_transform.angle) # Corrected: rotate
                    rotated_anchor_b = spring_comp.anchor_b.rotate(entity_b_transform.angle) # Corrected: rotate
                    world_anchor_a = entity_a_transform.position + rotated_anchor_a
                    world_anchor_b = entity_b_transform.position + rotated_anchor_b

                    current_pen = QPen()
                    # Updated selection check for connections (springs)
                    is_spring_selected = selected_connection_ids is not None and spring_comp.id in selected_connection_ids

                    if is_spring_selected:
                        current_pen.setColor(selected_spring_color)
                        current_pen.setWidthF(selected_spring_pixel_width / pixels_per_unit if pixels_per_unit > 0 else selected_spring_pixel_width)
                        current_pen.setStyle(Qt.PenStyle.SolidLine)
                    else:
                        current_pen.setColor(default_spring_color)
                        current_pen.setWidthF(default_spring_pixel_width / pixels_per_unit if pixels_per_unit > 0 else default_spring_pixel_width)
                        current_pen.setStyle(Qt.PenStyle.SolidLine) # Or DashLine for normal springs if preferred
                    
                    current_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin) # Round joins for spring lines
                    current_pen.setCapStyle(Qt.PenCapStyle.RoundCap)   # Round caps for spring lines

                    painter.save()
                    painter.setPen(current_pen)
                    painter.drawLine(QPointF(world_anchor_a.x, world_anchor_a.y),
                                     QPointF(world_anchor_b.x, world_anchor_b.y))
                    painter.restore()
        
        # --- Render Rods and Ropes ---
        # Iterate through all independent ConnectionComponents
        all_connections = self.entity_manager.get_all_independent_components_of_type(ConnectionComponent)

        rod_pen = QPen(QColor(100, 100, 100, 200)) # Dark Gray for rods
        rod_pen_width_pixels = 2.0
        rod_pen.setWidthF(rod_pen_width_pixels / pixels_per_world_unit if pixels_per_world_unit > 0 else rod_pen_width_pixels)
        
        rope_pen = QPen(QColor(139, 69, 19, 200)) # Brown for ropes
        rope_pen_width_pixels = 2.0
        rope_pen.setWidthF(rope_pen_width_pixels / pixels_per_world_unit if pixels_per_world_unit > 0 else rope_pen_width_pixels)

        # Define base properties for selected connection pens
        selected_connection_pen_width_pixels = 3.5 # Thicker for selected connection
        selected_pen_width_world = selected_connection_pen_width_pixels / pixels_per_world_unit if pixels_per_world_unit > 0 else selected_connection_pen_width_pixels

        selected_rod_pen = QPen(QColor(Qt.GlobalColor.green)) # Green for selected ROD
        selected_rod_pen.setWidthF(selected_pen_width_world)
        selected_rod_pen.setStyle(Qt.PenStyle.SolidLine)

        selected_rope_pen = QPen(QColor(Qt.GlobalColor.yellow)) # Yellow for selected ROPE
        selected_rope_pen.setWidthF(selected_pen_width_world)
        selected_rope_pen.setStyle(Qt.PenStyle.SolidLine)

        for conn_comp in all_connections:
            if conn_comp.is_broken:
                continue
            
            # The logic below now directly uses conn_comp

            if conn_comp.connection_type == ConnectionType.ROD or conn_comp.connection_type == ConnectionType.ROPE: # Use Enum
                entity_a_id = conn_comp.source_entity_id # Use source_entity_id from ConnectionComponent
                entity_b_id = conn_comp.target_entity_id
                
                transform_a = self.entity_manager.get_component(entity_a_id, TransformComponent)
                transform_b = self.entity_manager.get_component(entity_b_id, TransformComponent)

                if not transform_a or not transform_b:
                    print(f"Warning: Missing transform for entities in connection {conn_comp.id}. Skipping render.")
                    continue

                anchor_a_local = conn_comp.connection_point_a
                anchor_b_local = conn_comp.connection_point_b
                
                # transform.angle is already in radians
                angle_a_rad = transform_a.angle
                angle_b_rad = transform_b.angle

                rotated_anchor_a = anchor_a_local.rotate(angle_a_rad)
                world_anchor_a = transform_a.position + rotated_anchor_a

                rotated_anchor_b = anchor_b_local.rotate(angle_b_rad)
                world_anchor_b = transform_b.position + rotated_anchor_b
                
                painter.save()
                
                is_selected_conn = False
                current_selected_pen = None # Pen to use if this connection is selected


                # Updated selection check for connections (rods/ropes)
                if selected_connection_ids is not None and conn_comp.id in selected_connection_ids:
                    is_selected_conn = True
                    if conn_comp.connection_type == ConnectionType.ROD: # Use Enum
                        current_selected_pen = selected_rod_pen
                    elif conn_comp.connection_type == ConnectionType.ROPE: # Use Enum
                        current_selected_pen = selected_rope_pen
                
                if is_selected_conn and current_selected_pen:
                    painter.setPen(current_selected_pen)
                elif conn_comp.connection_type == ConnectionType.ROD: # Use Enum
                    painter.setPen(rod_pen)
                elif conn_comp.connection_type == ConnectionType.ROPE: # Use Enum
                    painter.setPen(rope_pen)
                
                painter.drawLine(QPointF(world_anchor_a.x, world_anchor_a.y),
                                 QPointF(world_anchor_b.x, world_anchor_b.y))
                painter.restore()

        # --- Render Force Vectors (if applicable) ---
        if force_analysis_target_entity_id is not None:
            target_transform = self.entity_manager.get_component(force_analysis_target_entity_id, TransformComponent)
            target_accumulator = self.entity_manager.get_component(force_analysis_target_entity_id, ForceAccumulatorComponent)

            if target_transform and target_accumulator and target_accumulator.detailed_forces:
                painter.save()
                # Ensure painter is in the correct world transform state (it should be if called after entity loop)
                # Set default pen/brush for force vectors
                force_pen = QPen(QColor(255, 0, 0, 200)) # Red, slightly transparent
                force_pen_width_pixels = 1.5
                force_pen.setWidthF(force_pen_width_pixels / pixels_per_world_unit if pixels_per_world_unit > 0 else force_pen_width_pixels)
                painter.setPen(force_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush) # No fill for vectors

                # Calculate scaling factor for force vectors
                world_units_per_newton = (force_scale_pixels / force_scale_reference / pixels_per_world_unit) \
                                         if force_scale_reference > 0 and pixels_per_world_unit > 0 else 0

                for force_detail in target_accumulator.detailed_forces:
                    force_vec = force_detail.force_vector
                    force_magnitude = force_vec.magnitude()
                    if force_magnitude < 1e-6: # Skip zero forces
                        continue

                    # Determine start point based on display mode
                    if force_analysis_display_mode == ForceAnalysisDisplayMode.OBJECT:
                        # Rotate local application point by entity angle
                        rotated_local_point = force_detail.application_point_local.rotate(target_transform.angle)
                        world_start = target_transform.position + rotated_local_point
                    else: # CENTER_OF_MASS mode
                        world_start = target_transform.position

                    # Calculate scaled end point for drawing
                    if world_units_per_newton > 0:
                         vector_draw_length_world = force_magnitude * world_units_per_newton
                         # Clamp max draw length? Maybe later.
                         try:
                            direction = force_vec.normalize()
                         except ZeroDivisionError:
                            continue # Skip if force vector is zero
                         world_end_scaled = world_start + direction * vector_draw_length_world
                    else: # Handle zero scale case (draw a small marker maybe?)
                         world_end_scaled = world_start # Or draw nothing

                    # Draw the vector if start and end are different enough
                    if (world_end_scaled - world_start).magnitude_squared() > (1 / pixels_per_world_unit)**2 : # Only draw if longer than ~1 pixel
                        self._draw_force_vector(painter, world_start, world_end_scaled, force_detail.force_type_label, pixels_per_world_unit, drawing_widget_ref) # Pass drawing_widget_ref

                painter.restore()
        # --- End Render Force Vectors ---

    def _draw_force_vector(self, painter: QPainter, start_pos: Vector2D, end_pos: Vector2D, label: str, scale: float, drawing_widget_ref: Optional['DrawingWidget'] = None): # Added drawing_widget_ref
        """Helper to draw a force vector with an arrowhead and label."""
        painter.save()

        # Draw line segment
        painter.drawLine(QPointF(start_pos.x, start_pos.y), QPointF(end_pos.x, end_pos.y))

        # Draw arrowhead
        arrow_size_pixels = 7.0 # Slightly smaller arrow
        arrow_angle_deg = 25.0 # Angle of arrowhead wings

        arrow_size_world = arrow_size_pixels / scale if scale > 0 else 0.01

        if arrow_size_world > 0:
            direction_vector = end_pos - start_pos
            line_length_sq = direction_vector.magnitude_squared()

            if line_length_sq > 1e-9: # Avoid issues with zero length vector
                line_length = math.sqrt(line_length_sq)
                dx = direction_vector.x / line_length
                dy = direction_vector.y / line_length

                # Calculate points for the arrowhead lines (wings)
                angle_rad = math.radians(arrow_angle_deg)
                cos_a = math.cos(angle_rad)
                sin_a = math.sin(angle_rad)

                # Point 1 (rotated direction vector by +angle_rad)
                p1_dx = dx * cos_a - dy * sin_a
                p1_dy = dx * sin_a + dy * cos_a
                p1_x = end_pos.x - p1_dx * arrow_size_world
                p1_y = end_pos.y - p1_dy * arrow_size_world

                # Point 2 (rotated direction vector by -angle_rad)
                p2_dx = dx * cos_a + dy * sin_a
                p2_dy = -dx * sin_a + dy * cos_a
                p2_x = end_pos.x - p2_dx * arrow_size_world
                p2_y = end_pos.y - p2_dy * arrow_size_world

                # Draw the two wings of the arrowhead
                painter.drawLine(QPointF(end_pos.x, end_pos.y), QPointF(p1_x, p1_y))
                painter.drawLine(QPointF(end_pos.x, end_pos.y), QPointF(p2_x, p2_y))


        # Draw Label near the arrowhead
        # Text rendering needs careful handling of scale and rotation
        # Save painter state before scaling/rotating for text
        # painter.save() # REMOVED: Save/restore should bracket the specific state changes needed for text

        # --- Calculate Label Position ---
        # Calculate a position slightly offset from the arrow end, perpendicular to the arrow direction.
        label_offset_world_dist = 0.15 # Offset distance in world units (adjust as needed)
        label_screen_offset_pixels = 5 # Additional small pixel offset for readability

        arrow_vector = end_pos - start_pos
        if arrow_vector.magnitude_squared() > 1e-9:
            direction = arrow_vector.normalize()
            # Perpendicular direction (rotate 90 degrees counter-clockwise for offset 'above' the arrow end)
            perp_direction = Vector2D(-direction.y, direction.x)
            label_world_pos = end_pos + perp_direction * label_offset_world_dist
        else:
            # Fallback if arrow is zero length: place label slightly above start point
            label_world_pos = start_pos + Vector2D(0, label_offset_world_dist) # Offset vertically

        # Convert the calculated world position to screen coordinates (Y-down)
        label_screen_pos = drawing_widget_ref.world_to_screen(label_world_pos) \
                           if drawing_widget_ref and hasattr(drawing_widget_ref, 'world_to_screen') \
                           else QPointF(end_pos.x, end_pos.y) # Fallback to end_pos if conversion fails

        # Apply additional small screen offset for better spacing from the arrow tip
        label_screen_pos += QPointF(label_screen_offset_pixels, -label_screen_offset_pixels) # Offset right and up in screen coords


        # --- Draw Text ---
        # Draw text at the calculated world position, but scale painter temporarily
        # to achieve a fixed screen size for the font.

        painter.save() # Save state before text drawing modifications

        # Set font and color
        text_font = QFont()
        text_font.setPointSizeF(7) # Small fixed size
        painter.setFont(text_font)
        painter.setPen(QColor(0, 0, 139)) # Dark Blue

        # Temporarily adjust painter transform for text drawing
        painter.save() # Save transform state
        painter.translate(label_world_pos.x, label_world_pos.y) # Move origin to label's world position
        painter.scale(1.0 / scale, -1.0 / scale) # Undo world scale and Y-flip

        # Draw text at the new origin (0,0) with a small pixel offset
        # Note: label_screen_offset_pixels is used here for slight adjustment in the unscaled space
        painter.drawText(QPointF(label_screen_offset_pixels, label_screen_offset_pixels), label) # Offset slightly right and down

        painter.restore() # Restore transform state

        # Restore font/pen state
        painter.restore() # Matches the save before text drawing modifications

        # The final painter.restore() matches the save at the very beginning of _draw_force_vector
        # Ensure this final restore exists and is not commented out.
        # It seems it was missing or commented out based on previous errors.
        # Adding it back explicitly here if the original function structure implied it.
        # Note: The original read_file ended at line 492, so the end of the function wasn't fully visible.
        # Assuming the function ends shortly after this, we need the final restore.
        # If the apply_diff fails because this restore already exists uncommented later, we'll adjust.

        # painter.restore() # This should correspond to the save at the beginning of the function.
        # Let's assume the original function had this structure:
        # def _draw_force_vector(...):
        #    painter.save() # Initial save
        #    ... draw line ...
        #    ... draw arrowhead ...
        #    ... draw label (with its own save/restore for font/pen) ...
        #    painter.restore() # Final restore matching the initial save
        # We need to ensure this final restore is present.

        # Since the previous apply_diff might have removed or commented it,
        # let's ensure it's present at the end.
        # If the function already has a final restore, this might cause issues.
        # Let's check the code again to be sure about the structure.

        # Re-checking the structure based on common patterns:
        # The painter.save() at line 365 should have a corresponding restore at the end.
        # The painter.save() at line 410 (now removed/refactored) was for text.
        # The new painter.save() added before text settings needs a restore after text drawing.

        # Final structure attempt:
        # painter.save() # Line 365
        # ... draw line ...
        # ... draw arrowhead ...
        # painter.save() # For text settings
        # ... set font/pen ...
        # ... draw text ...
        # painter.restore() # Restore text settings
        # painter.restore() # Restore original state from line 365

        # The code block above correctly restores after text drawing.
        # We need to ensure the restore for line 365 is present.
        painter.restore() # <<< RESTORE 1 (Matches SAVE 1 at line 365)

    # End of _draw_force_vector method