from PySide6.QtCore import Qt, QPointF, QRectF, QLineF
from PySide6.QtGui import QPainter, QColor, QPen, QCursor

from physi_sim.graphics.drawing_tools.base_tool_handler import BaseToolHandler
from physi_sim.core.vector import Vector2D
from physi_sim.core.component import SpringComponent, ConnectionComponent, TransformComponent, GeometryComponent, ShapeType, ConnectionType, IdentifierComponent # Use ConnectionType Enum, Added IdentifierComponent
from physi_sim.core.entity_manager import EntityManager, EntityID # For type hinting if needed, Added EntityID
# Use a forward reference for MainWindow and DrawingWidget to avoid circular imports at runtime
# and satisfy type hinting.
from typing import TYPE_CHECKING, List, Optional, Set # Added List, Optional, Set
if TYPE_CHECKING:
    from physi_sim.graphics.main_window import MainWindow, DrawingWidget, ToolMode

import uuid # For type hinting entity IDs

class SelectToolHandler(BaseToolHandler):
    """
    处理选择工具的逻辑，包括实体选择、框选和实体拖拽。
    """

    def __init__(self):
        super().__init__()
        # DrawingWidget state that this handler will manage when active
        self.is_marqueeing: bool = False
        self.marquee_start_point: QPointF | None = None
        self.marquee_end_point: QPointF | None = None

        self.is_dragging_entity: bool = False
        self.drag_offset_from_entity_anchor: Vector2D = Vector2D(0, 0)
        self.drag_target_world_position: Vector2D | None = None
        self.current_linkage_group_members: Optional[List[EntityID]] = None # RE-ADD for new linkage logic
        self.primary_dragged_entity_id: Optional[EntityID] = None # To store the entity the user initially clicked


    def activate(self, drawing_widget: 'DrawingWidget'):
        """工具激活时调用"""
        main_window: 'MainWindow' = drawing_widget.window()
        if not hasattr(main_window, 'status_bar'): # Check if main_window is fully initialized
            return
        main_window.status_bar.showMessage("选择工具已激活。点击选择，或拖拽进行框选/移动。", 3000)
        self.is_marqueeing = False
        self.marquee_start_point = None
        self.marquee_end_point = None
        self.is_dragging_entity = False
        self.drag_offset_from_entity_anchor = Vector2D(0, 0)
        self.drag_target_world_position = None
        self.current_linkage_group_members = None # RE-ADD
        self.primary_dragged_entity_id = None
        drawing_widget.setCursor(Qt.CursorShape.ArrowCursor)


    def deactivate(self, drawing_widget: 'DrawingWidget'):
        """工具失活时调用"""
        self.is_marqueeing = False
        self.marquee_start_point = None
        self.marquee_end_point = None
        self.is_dragging_entity = False
        self.current_linkage_group_members = None # RE-ADD
        self.primary_dragged_entity_id = None
        drawing_widget.setCursor(Qt.CursorShape.ArrowCursor)
        # Clear any visual remnants if necessary, e.g., if marquee was active
        drawing_widget.update()

    def handle_mouse_press(self, event, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        entity_manager: EntityManager = main_window.entity_manager
        self.current_linkage_group_members = None # Reset at the start of any press
        self.primary_dragged_entity_id = None

        click_pos_screen = event.position()
        click_pos_world = drawing_widget._get_world_coordinates(click_pos_screen)

        clicked_on_something = False

        # --- 1. Prioritize Spring Click Detection ---
        CLICK_THRESHOLD_PIXELS_SQ = 5 * 5
        all_springs = entity_manager.get_all_independent_components_of_type(SpringComponent)
        for spring in all_springs:
            if not spring.entity_a_id or not spring.entity_b_id:
                continue
            transform_a = entity_manager.get_component(spring.entity_a_id, TransformComponent)
            transform_b = entity_manager.get_component(spring.entity_b_id, TransformComponent)
            if transform_a and transform_b:
                rotated_anchor_a = spring.anchor_a.rotate(transform_a.angle)
                rotated_anchor_b = spring.anchor_b.rotate(transform_b.angle)
                world_anchor_a = transform_a.position + rotated_anchor_a
                world_anchor_b = transform_b.position + rotated_anchor_b
                screen_anchor_a = drawing_widget.world_to_screen(world_anchor_a)
                screen_anchor_b = drawing_widget.world_to_screen(world_anchor_b)
                dist_sq = drawing_widget._point_segment_distance_sq(click_pos_screen, screen_anchor_a, screen_anchor_b)
                if dist_sq < CLICK_THRESHOLD_PIXELS_SQ:
                    main_window.set_single_selected_object("SPRING_CONNECTION", spring.id)
                    clicked_on_something = True
                    drawing_widget.update()
                    return

        # --- 2. Connection (Rod/Rope) Click Detection ---
        if not clicked_on_something:
            all_connections = entity_manager.get_all_independent_components_of_type(ConnectionComponent)
            for conn_comp in all_connections:
                if conn_comp.is_broken: continue
                if conn_comp.connection_type == ConnectionType.ROD or conn_comp.connection_type == ConnectionType.ROPE: # Use Enum
                    entity_a_id = conn_comp.source_entity_id
                    entity_b_id = conn_comp.target_entity_id
                    transform_a = entity_manager.get_component(entity_a_id, TransformComponent)
                    transform_b = entity_manager.get_component(entity_b_id, TransformComponent)
                    if transform_a and transform_b:
                        angle_a_rad = transform_a.angle
                        angle_b_rad = transform_b.angle
                        rotated_anchor_a = conn_comp.connection_point_a.rotate(angle_a_rad)
                        rotated_anchor_b = conn_comp.connection_point_b.rotate(angle_b_rad)
                        world_anchor_a = transform_a.position + rotated_anchor_a
                        world_anchor_b = transform_b.position + rotated_anchor_b
                        screen_anchor_a = drawing_widget.world_to_screen(world_anchor_a)
                        screen_anchor_b = drawing_widget.world_to_screen(world_anchor_b)
                        dist_sq = drawing_widget._point_segment_distance_sq(click_pos_screen, screen_anchor_a, screen_anchor_b)
                        if dist_sq < CLICK_THRESHOLD_PIXELS_SQ:
                            selected_type_str = "CONNECTION_ROD" if conn_comp.connection_type == ConnectionType.ROD else "CONNECTION_ROPE" # Use Enum
                            main_window.set_single_selected_object(selected_type_str, conn_comp.id)
                            clicked_on_something = True
                            drawing_widget.update()
                            return
        
        # --- 3. Entity Click Detection ---
        if not clicked_on_something:
            hit_entity_id = main_window._get_entity_at_world_pos(click_pos_world)
            if hit_entity_id:
                main_window.set_single_selected_object("ENTITY", hit_entity_id)
                clicked_on_something = True # Record that something was interacted with

                # Start dragging this newly selected (or re-selected) entity
                selected_transform = entity_manager.get_component(hit_entity_id, TransformComponent)
                if selected_transform:
                    self.is_dragging_entity = True
                    self.primary_dragged_entity_id = hit_entity_id
                    self.drag_offset_from_entity_anchor = selected_transform.position - click_pos_world
                    self.drag_target_world_position = selected_transform.position

                    # Build linkage group using BFS to find all connected entities via REVOLUTE_JOINT
                    # This will find the entire connected component of the rigid body structure.
                    if hit_entity_id: # Ensure hit_entity_id is not None
                        linkage_members_set: Set[EntityID] = set()
                        queue: List[EntityID] = [hit_entity_id]
                        visited_for_linkage: Set[EntityID] = {hit_entity_id}
                        
                        all_connections = entity_manager.get_all_independent_components_of_type(ConnectionComponent)
                        
                        head = 0
                        while head < len(queue):
                            current_entity_in_bfs = queue[head]
                            head += 1
                            linkage_members_set.add(current_entity_in_bfs)

                            for conn in all_connections:
                                if conn.connection_type == ConnectionType.REVOLUTE_JOINT and not conn.is_broken:
                                    partner_entity_id: Optional[EntityID] = None
                                    if conn.source_entity_id == current_entity_in_bfs:
                                        partner_entity_id = conn.target_entity_id
                                    elif conn.target_entity_id == current_entity_in_bfs:
                                        partner_entity_id = conn.source_entity_id
                                    
                                    if partner_entity_id and partner_entity_id not in visited_for_linkage:
                                        visited_for_linkage.add(partner_entity_id)
                                        queue.append(partner_entity_id)
                        
                        if len(linkage_members_set) > 0: # Check if any members were found (should include at least hit_entity_id)
                            self.current_linkage_group_members = list(linkage_members_set)
                            if len(self.current_linkage_group_members) > 1:
                                print(f"Editor drag: Full revolute joint linkage group: {self.current_linkage_group_members}")
                        else:
                            self.current_linkage_group_members = None
                    else:
                        self.current_linkage_group_members = None


                    drawing_widget.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                # No entity, spring, or connection was clicked - click was on empty space
                self.is_marqueeing = True
                self.marquee_start_point = click_pos_screen
                self.marquee_end_point = click_pos_screen # Initialize end point
                main_window.clear_selection() # Clear previous selection when starting marquee
                # clicked_on_something remains False
        drawing_widget.update() # Update view for selection change or marquee start


    def handle_mouse_move(self, event, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        entity_manager: EntityManager = main_window.entity_manager
        current_pos_screen = event.position()
        # It's important that current_mouse_world_pos is updated in DrawingWidget itself
        # This handler can read it if needed, but should not be solely responsible for setting it globally.
        current_pos_world = drawing_widget._get_world_coordinates(current_pos_screen)


        if self.is_marqueeing:
            self.marquee_end_point = current_pos_screen
            drawing_widget.update()
        elif self.is_dragging_entity and self.primary_dragged_entity_id:
            # Calculate the primary dragged entity's new potential position
            primary_entity_current_transform = entity_manager.get_component(self.primary_dragged_entity_id, TransformComponent)
            if not primary_entity_current_transform:
                self.is_dragging_entity = False # Should not happen if drag started
                return

            new_primary_target_pos = current_pos_world + self.drag_offset_from_entity_anchor
            delta_drag_world = new_primary_target_pos - primary_entity_current_transform.position

            if self.current_linkage_group_members and len(self.current_linkage_group_members) > 0 : # Ensure primary is in it or it's not None
                # Move all members of the linkage group by the same delta
                for member_id in self.current_linkage_group_members:
                    member_transform = entity_manager.get_component(member_id, TransformComponent)
                    if member_transform:
                        member_transform.position += delta_drag_world
                
                # Update the drag_target_world_position to reflect the primary entity's NEW position
                updated_primary_transform = entity_manager.get_component(self.primary_dragged_entity_id, TransformComponent)
                if updated_primary_transform:
                    self.drag_target_world_position = updated_primary_transform.position
                else:
                    self.drag_target_world_position = new_primary_target_pos
            else:
                # Single entity drag
                primary_entity_current_transform.position = new_primary_target_pos
                self.drag_target_world_position = new_primary_target_pos
            
            drawing_widget.update()
        # No explicit update here, relies on DrawingWidget's general update for mouse move if needed for other things like snap points.
        # However, for marquee and drag, direct updates are better.


    def handle_mouse_release(self, event, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()

        if self.is_marqueeing:
            self.is_marqueeing = False
            if self.marquee_start_point and self.marquee_end_point:
                # Convert screen marquee points to world for selection logic
                world_marquee_start_vec = drawing_widget._get_world_coordinates(self.marquee_start_point)
                world_marquee_end_vec = drawing_widget._get_world_coordinates(self.marquee_end_point)
                
                # Convert Vector2D to QPointF for QRectF constructor
                world_marquee_start_qpoint = QPointF(world_marquee_start_vec.x, world_marquee_start_vec.y)
                world_marquee_end_qpoint = QPointF(world_marquee_end_vec.x, world_marquee_end_vec.y)
                
                marquee_rect_world = QRectF(world_marquee_start_qpoint, world_marquee_end_qpoint).normalized()
                # Create marquee_rect_screen from the original screen points for line intersection checks
                marquee_rect_screen = QRectF(self.marquee_start_point, self.marquee_end_point).normalized()
                marquee_edges = [
                    QLineF(marquee_rect_screen.topLeft(), marquee_rect_screen.topRight()),
                    QLineF(marquee_rect_screen.topRight(), marquee_rect_screen.bottomRight()),
                    QLineF(marquee_rect_screen.bottomRight(), marquee_rect_screen.bottomLeft()),
                    QLineF(marquee_rect_screen.bottomLeft(), marquee_rect_screen.topLeft())
                ]

                selected_entities_in_marquee = set()
                selected_connections_in_marquee = set()

                # Entity Selection Logic (Simplified AABB check in world coordinates)
                for entity_id in main_window.entity_manager.entities:
                    transform = main_window.entity_manager.get_component(entity_id, TransformComponent)
                    geometry = main_window.entity_manager.get_component(entity_id, GeometryComponent)
                    if transform and geometry:
                        # Simple bounding box check for now
                        entity_rect_world = QRectF() # This will be AABB in world space
                        if geometry.shape_type == ShapeType.RECTANGLE:
                            params = geometry.parameters
                            # For AABB of a potentially rotated rect, we need to find min/max x/y of its corners
                            # This is more complex. For simplicity, using AABB of non-rotated shape at its position.
                            # This is what the original code did.
                            half_width = params["width"] / 2
                            half_height = params["height"] / 2
                            entity_world_pos = transform.position
                            entity_rect_world.setRect(entity_world_pos.x - half_width, entity_world_pos.y - half_height, params["width"], params["height"])
                        elif geometry.shape_type == ShapeType.CIRCLE:
                            params = geometry.parameters
                            radius = params["radius"]
                            entity_world_pos = transform.position
                            entity_rect_world.setRect(entity_world_pos.x - radius, entity_world_pos.y - radius, 2 * radius, 2 * radius)
                        
                        if marquee_rect_world.intersects(entity_rect_world) or marquee_rect_world.contains(entity_rect_world):
                            selected_entities_in_marquee.add(entity_id)

                # Connection Selection Logic (Springs, Rods, Ropes) - uses screen coordinates for intersection
                # Springs
                all_springs = main_window.entity_manager.get_all_independent_components_of_type(SpringComponent)
                for spring in all_springs:
                    if not spring.entity_a_id or not spring.entity_b_id: continue
                    transform_a = main_window.entity_manager.get_component(spring.entity_a_id, TransformComponent)
                    transform_b = main_window.entity_manager.get_component(spring.entity_b_id, TransformComponent)
                    if transform_a and transform_b:
                        rotated_anchor_a = spring.anchor_a.rotate(transform_a.angle)
                        world_anchor_a = transform_a.position + rotated_anchor_a
                        screen_anchor_a = drawing_widget.world_to_screen(world_anchor_a)
                        
                        rotated_anchor_b = spring.anchor_b.rotate(transform_b.angle)
                        world_anchor_b = transform_b.position + rotated_anchor_b
                        screen_anchor_b = drawing_widget.world_to_screen(world_anchor_b)
                        
                        connection_line = QLineF(screen_anchor_a, screen_anchor_b)
                        endpoints_in_marquee = marquee_rect_screen.contains(screen_anchor_a) and marquee_rect_screen.contains(screen_anchor_b)
                        intersects_marquee = False
                        # marquee_edges is now defined above
                        for edge in marquee_edges:
                            # intersection_type, _ = connection_line.intersects(edge) # Qt6
                            intersection_result = connection_line.intersects(edge) # Qt6 returns QLineF.IntersectionType or similar enum
                            if intersection_result == QLineF.IntersectionType.BoundedIntersection: # Check specific enum member
                                intersects_marquee = True
                                break
                        connection_bounding_rect = QRectF(screen_anchor_a, screen_anchor_b).normalized()
                        marquee_contains_connection_bbox = marquee_rect_screen.contains(connection_bounding_rect)
                        # Simplified condition from original code for brevity
                        if endpoints_in_marquee or intersects_marquee or marquee_contains_connection_bbox or marquee_rect_screen.intersects(connection_bounding_rect):
                            selected_connections_in_marquee.add(spring.id)

                # Rods and Ropes
                all_connections = main_window.entity_manager.get_all_independent_components_of_type(ConnectionComponent)
                for conn_comp in all_connections:
                    if conn_comp.is_broken: continue
                    if conn_comp.connection_type == ConnectionType.ROD or conn_comp.connection_type == ConnectionType.ROPE: # Use Enum
                        entity_a_id = conn_comp.source_entity_id
                        entity_b_id = conn_comp.target_entity_id
                        transform_a = main_window.entity_manager.get_component(entity_a_id, TransformComponent)
                        transform_b = main_window.entity_manager.get_component(entity_b_id, TransformComponent)
                        if transform_a and transform_b:
                            rotated_anchor_a = conn_comp.connection_point_a.rotate(transform_a.angle)
                            world_anchor_a = transform_a.position + rotated_anchor_a
                            screen_anchor_a = drawing_widget.world_to_screen(world_anchor_a)

                            rotated_anchor_b = conn_comp.connection_point_b.rotate(transform_b.angle)
                            world_anchor_b = transform_b.position + rotated_anchor_b
                            screen_anchor_b = drawing_widget.world_to_screen(world_anchor_b)
                            
                            connection_line = QLineF(screen_anchor_a, screen_anchor_b)
                            endpoints_in_marquee = marquee_rect_screen.contains(screen_anchor_a) and marquee_rect_screen.contains(screen_anchor_b)
                            intersects_marquee = False
                            # (Re-use marquee_edges from above)
                            for edge in marquee_edges:
                                intersection_result = connection_line.intersects(edge)
                                if intersection_result == QLineF.IntersectionType.BoundedIntersection:
                                    intersects_marquee = True
                                    break
                            connection_bounding_rect = QRectF(screen_anchor_a, screen_anchor_b).normalized()
                            marquee_contains_connection_bbox = marquee_rect_screen.contains(connection_bounding_rect)
                            
                            if endpoints_in_marquee or intersects_marquee or marquee_contains_connection_bbox or marquee_rect_screen.intersects(connection_bounding_rect):
                                selected_connections_in_marquee.add(conn_comp.id)
                
                main_window.set_marquee_selection(selected_entities_in_marquee, selected_connections_in_marquee)

            self.marquee_start_point = None
            self.marquee_end_point = None
            drawing_widget.update()

        elif self.is_dragging_entity:
            self.is_dragging_entity = False
            self.drag_target_world_position = None
            self.current_linkage_group_members = None # Clear linkage group on release
            self.primary_dragged_entity_id = None
            drawing_widget.setCursor(Qt.CursorShape.ArrowCursor)
            # The actual position of the entity should have been updated during mouse_move.
            # MainWindow's simulation_step will handle pinning if necessary.
            drawing_widget.update()
            # Property panel update is handled by MainWindow's selection change signals

    def paint_overlay(self, painter: QPainter, drawing_widget: 'DrawingWidget'):
        # This method is called by DrawingWidget.paintEvent *after* the painter has been transformed
        # to world coordinates with Y-up. So, drawing should use world coordinates.
        if self.is_marqueeing and self.marquee_start_point and self.marquee_end_point:
            # Convert screen marquee points to world for drawing with transformed painter
            world_marquee_start_vec = drawing_widget._get_world_coordinates(self.marquee_start_point)
            world_marquee_end_vec = drawing_widget._get_world_coordinates(self.marquee_end_point)
            
            world_marquee_start_qpoint = QPointF(world_marquee_start_vec.x, world_marquee_start_vec.y)
            world_marquee_end_qpoint = QPointF(world_marquee_end_vec.x, world_marquee_end_vec.y)
            
            marquee_rect_world = QRectF(world_marquee_start_qpoint, world_marquee_end_qpoint).normalized()
            
            painter.setPen(QPen(QColor(0, 100, 255, 150), 1.0 / drawing_widget.pixels_per_world_unit, Qt.PenStyle.SolidLine))
            painter.setBrush(QColor(0, 100, 255, 50)) # Light blue, very transparent fill
            painter.drawRect(marquee_rect_world)