from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QPolygonF, QColor # Added QColor

from physi_sim.core.component import (
    IdentifierComponent, TransformComponent, GeometryComponent,
    PhysicsBodyComponent, RenderComponent, ShapeType, ForceAccumulatorComponent # Added ForceAccumulatorComponent
)
from physi_sim.core.entity_manager import EntityManager
from physi_sim.core.vector import Vector2D
from physi_sim.graphics.drawing_tools.base_tool_handler import BaseToolHandler
# from physi_sim.graphics.main_window import Tool # Assuming Tool enum is here - REMOVED TO FIX CIRCULAR IMPORT

class PolygonToolHandler(BaseToolHandler):
    def __init__(self, entity_manager: EntityManager):
        self.entity_manager = entity_manager
        self.current_vertices_world = []  # Stores Vector2D in world coordinates
        self.is_drawing = False
        self.preview_edge_end = None # Stores Vector2D for preview line

    def activate(self, drawing_widget):
        self.drawing_widget = drawing_widget
        self.current_vertices_world = []
        self.is_drawing = False
        self.preview_edge_end = None
        # Connect key press events if needed, or handle in main_window
        # drawing_widget.setFocus() # Ensure widget can receive key events

    def deactivate(self, drawing_widget):
        self.reset_drawing_state()
        # Disconnect key press events if connected

    def reset_drawing_state(self):
        self.current_vertices_world = []
        self.is_drawing = False
        self.preview_edge_end = None
        if hasattr(self, 'drawing_widget') and self.drawing_widget:
            self.drawing_widget.update() # Redraw to clear any overlays

    def handle_mouse_press(self, event, drawing_widget):
        # Use DrawingWidget's method to get world coordinates as Vector2D
        world_pos_vec = drawing_widget._get_world_coordinates(event.pos())

        if event.button() == Qt.LeftButton:
            if not self.is_drawing:
                # First click: start drawing
                self.is_drawing = True
                self.current_vertices_world.append(world_pos_vec)
                self.preview_edge_end = world_pos_vec # Initialize preview
            else:
                # Subsequent clicks: add vertex
                # Check if clicking near the first vertex to close
                if len(self.current_vertices_world) >= 2: # Need at least 2 existing vertices to consider closing
                    first_vertex_vec = self.current_vertices_world[0]
                    # Define a small tolerance for closing the polygon
                    # get_pixel_size() equivalent: 1.0 / pixels_per_world_unit
                    pixel_size_world = 1.0 / drawing_widget.pixels_per_world_unit if drawing_widget.pixels_per_world_unit > 0 else 0.01
                    close_tolerance = pixel_size_world * 10 # 10 pixels tolerance in world units

                    # Use Vector2D's distance_to or subtract and get magnitude
                    if (world_pos_vec - first_vertex_vec).magnitude() < close_tolerance:
                        if len(self.current_vertices_world) >= 3: # Must have at least 3 vertices to form a polygon
                            # Don't add the point here, finalize_polygon will handle closing.
                            self.finalize_polygon() # Finalize directly
                        else:
                            # Not enough vertices to close, treat as a regular point by adding it
                            self.current_vertices_world.append(world_pos_vec)
                        return # Stop further processing for this click

                self.current_vertices_world.append(world_pos_vec)

            drawing_widget.update()

        elif event.button() == Qt.RightButton and self.is_drawing:
            # Right click to finalize (if more than 2 vertices)
            if len(self.current_vertices_world) >= 3:
                self.finalize_polygon()
            else:
                # Not enough vertices, cancel drawing
                self.reset_drawing_state()


    def handle_mouse_move(self, event, drawing_widget):
        if self.is_drawing and self.current_vertices_world:
            self.preview_edge_end = drawing_widget._get_world_coordinates(event.pos()) # Use Vector2D
            drawing_widget.update()

    def handle_mouse_release(self, event, drawing_widget):
        # For polygon drawing, most logic is in press.
        # Double click handling might go here or in main_window's event filter.
        pass

    def handle_mouse_double_click(self, event, drawing_widget):
        if self.is_drawing and event.button() == Qt.LeftButton:
            if len(self.current_vertices_world) >= 3:
                 # Do not add current mouse position, just finalize with existing points.
                self.finalize_polygon()
            else:
                # Not enough vertices, cancel
                self.reset_drawing_state()


    def handle_key_press(self, event, drawing_widget):
        if not self.is_drawing:
            return False

        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if len(self.current_vertices_world) >= 3:
                self.finalize_polygon()
                return True # Event handled
            else: # Not enough vertices, cancel
                self.reset_drawing_state()
                return True
        elif event.key() == Qt.Key_Escape:
            self.reset_drawing_state()
            return True # Event handled
        return False


    def paint_overlay(self, painter: QPainter, drawing_widget):
        if not self.is_drawing or not self.current_vertices_world:
            return

        painter.save()
        pen = QPen(QColor(Qt.GlobalColor.blue)) # Changed color to blue
        pixel_size_world = 1.0 / drawing_widget.pixels_per_world_unit if drawing_widget.pixels_per_world_unit > 0 else 0.01
        pen.setWidthF(pixel_size_world * 1.0) # 1.0 pixel equivalent width for main lines
        painter.setPen(pen)

        # Painter received by paint_overlay is already transformed to world coordinates.
        # All drawing operations should use world coordinates and world unit dimensions.

        # Draw existing edges
        poly_qpoints_world = [QPointF(v.x, v.y) for v in self.current_vertices_world]
        if len(poly_qpoints_world) > 1:
            poly = QPolygonF(poly_qpoints_world)
            painter.drawPolyline(poly)

        # Draw preview edge from last vertex to current mouse position
        if self.preview_edge_end and self.current_vertices_world: # preview_edge_end is Vector2D
            last_world_qpoint = QPointF(self.current_vertices_world[-1].x, self.current_vertices_world[-1].y)
            preview_world_qpoint = QPointF(self.preview_edge_end.x, self.preview_edge_end.y)
            painter.drawLine(last_world_qpoint, preview_world_qpoint)

            # Optional: Draw a preview line back to the first point
            if len(self.current_vertices_world) >= 2:
                first_world_qpoint = QPointF(self.current_vertices_world[0].x, self.current_vertices_world[0].y)
                # Make dashed line thinner
                pen_preview_close = QPen(Qt.magenta, pixel_size_world * 0.5, Qt.DashLine) # 0.5 pixel equivalent width
                painter.setPen(pen_preview_close)
                painter.drawLine(preview_world_qpoint, first_world_qpoint)
                painter.setPen(pen) # Restore original pen for vertices (or rather, the main line pen)


        # Draw vertices
        pen_vertex = QPen(Qt.red)
        # Vertex outline can also be 1 pixel equivalent
        pen_vertex.setWidthF(pixel_size_world * 0.5) # Thinner outline for vertices
        painter.setPen(pen_vertex)
        brush_vertex = Qt.red
        painter.setBrush(brush_vertex)
        # Vertex radius: 2.5 pixels equivalent
        radius_world = pixel_size_world * 2.5
        
        for world_vertex_vec in self.current_vertices_world:
            painter.drawEllipse(QPointF(world_vertex_vec.x, world_vertex_vec.y), radius_world, radius_world)

        painter.restore()

    def finalize_polygon(self):
        if not self.is_drawing or len(self.current_vertices_world) < 3:
            self.reset_drawing_state()
            return

        # current_vertices_world now stores Vector2D objects
        world_vertices_vec = list(self.current_vertices_world) # Make a copy

        # Ensure the polygon is closed if the last point isn't the first
        if world_vertices_vec[0] != world_vertices_vec[-1]:
            # Check if the last point is very close to the first. If so, snap it.
            pixel_size_world = 1.0 / self.drawing_widget.pixels_per_world_unit if self.drawing_widget.pixels_per_world_unit > 0 else 0.01
            close_tolerance_snap = pixel_size_world * 2 # 2 pixels tolerance for snapping
            if (world_vertices_vec[-1] - world_vertices_vec[0]).magnitude() < close_tolerance_snap:
                 world_vertices_vec[-1] = world_vertices_vec[0] # Snap
            else: # Otherwise, explicitly close it by adding the first point.
                 world_vertices_vec.append(world_vertices_vec[0])


        # world_vertices_vec is now a list of Vector2D, supposedly closed.
        # Remove duplicate closing point for centroid calculation and local vertex list.
        # If already closed by snapping or clicking first, the last point might be a duplicate.
        # If closed by adding first point above, it's definitely a duplicate.
        
        unique_world_vertices_for_centroid = world_vertices_vec
        if len(world_vertices_vec) > 1 and world_vertices_vec[0] == world_vertices_vec[-1]:
            unique_world_vertices_for_centroid = world_vertices_vec[:-1]


        if not unique_world_vertices_for_centroid or len(unique_world_vertices_for_centroid) < 3:
            print("PolygonTool: Not enough unique vertices for centroid calculation.")
            self.reset_drawing_state()
            return

        # 1. Calculate Centroid (Geometric Center) to be the local origin (0,0)
        # This will also be the TransformComponent's position.
        centroid_x = sum(v.x for v in unique_world_vertices_for_centroid) / len(unique_world_vertices_for_centroid)
        centroid_y = sum(v.y for v in unique_world_vertices_for_centroid) / len(unique_world_vertices_for_centroid)
        polygon_world_origin = Vector2D(centroid_x, centroid_y)

        # 2. Convert world vertices to local vertices (relative to centroid)
        # Use unique_world_vertices_for_centroid for this.
        local_vertices_vector2d = []
        for v_world in unique_world_vertices_for_centroid:
            local_vertices_vector2d.append(v_world - polygon_world_origin)

        if not local_vertices_vector2d or len(local_vertices_vector2d) < 3:
            print("PolygonTool: Not enough unique vertices to form a polygon after processing.")
            self.reset_drawing_state()
            return

        # Create entity and components
        entity = self.entity_manager.create_entity()
        self.entity_manager.add_component(entity, IdentifierComponent(name=f"Polygon_{entity}"))
        self.entity_manager.add_component(entity, TransformComponent(position=polygon_world_origin, angle=0.0)) # Changed 'rotation' to 'angle'
        self.entity_manager.add_component(entity, GeometryComponent(shape_type=ShapeType.POLYGON, parameters={'vertices': local_vertices_vector2d}))
        self.entity_manager.add_component(entity, RenderComponent()) # Use default fill_color and z_order
        self.entity_manager.add_component(entity, ForceAccumulatorComponent()) # Add ForceAccumulatorComponent
        # PhysicsBodyComponent will be added with auto-calculated inertia later
        self.entity_manager.add_component(entity, PhysicsBodyComponent(mass=1.0, restitution=0.5, static_friction_coefficient=0.3, dynamic_friction_coefficient=0.3, auto_calculate_inertia=True)) # Changed 'friction'

        # After adding all components, if physics_system is available, calculate inertia
        if hasattr(self.drawing_widget, 'window') and \
           hasattr(self.drawing_widget.window(), 'physics_system') and \
           self.drawing_widget.window().physics_system is not None:
            try:
                # The method name in PhysicsSystem was calculate_and_set_inertia
                self.drawing_widget.window().physics_system.calculate_and_set_inertia(entity)
                print(f"Successfully called calculate_and_set_inertia for entity {entity}")
            except Exception as e:
                print(f"Error calling calculate_and_set_inertia for entity {entity}: {e}")
        else:
            print(f"Warning: Could not access physics_system to calculate inertia for entity {entity}")


        print(f"Polygon Entity {entity} created with {len(local_vertices_vector2d)} local vertices. Origin: {polygon_world_origin}")
        for i, v in enumerate(local_vertices_vector2d):
            print(f"  Local Vertex {i}: {v}")

        self.reset_drawing_state()
        if hasattr(self, 'drawing_widget') and self.drawing_widget:
            self.drawing_widget.update() # Update to show the newly created polygon via RendererSystem
            main_window = self.drawing_widget.window()
            if hasattr(main_window, 'clear_selection'): # MainWindow should have clear_selection
                 main_window.clear_selection() # Call clear_selection on MainWindow
            elif hasattr(main_window, 'property_panel') and main_window.property_panel and hasattr(main_window.property_panel, 'clear_selection'):
                 # Fallback if MainWindow itself doesn't have it but panel does (less likely for selection management)
                 main_window.property_panel.clear_selection()


    def complete_drawing(self):
        """Public method to be called by external actions like a toolbar button or menu."""
        if self.is_drawing and len(self.current_vertices_world) >= 3:
            self.finalize_polygon()
        else:
            self.reset_drawing_state() # Cancel if not enough points