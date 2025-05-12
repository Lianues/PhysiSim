from .vector import Vector2D # 确保 Vector2D 被导入
from typing import List # Add this import

# World coordinate system: Y-axis points upwards.
# Gravity acts downwards along the negative Y-axis.
GRAVITY_ACCELERATION = Vector2D(0, -9.81) # Standard gravity, Y component is negative.
# print(f"LOG_UTILS_INIT: GRAVITY_ACCELERATION set to {GRAVITY_ACCELERATION}") # Ensure this is correct at startup

EPSILON = 1e-6 # A small number for float comparisons and to prevent division by zero

def is_point_inside_polygon(point: Vector2D, polygon_vertices: List[Vector2D]) -> bool:
    """
    Checks if a point is inside a polygon using the ray casting algorithm.
    Assumes polygon_vertices are ordered (clockwise or counter-clockwise).
    Handles horizontal segments by not counting them as crossings if they are at point.y.
    """
    if not polygon_vertices or len(polygon_vertices) < 3:
        return False

    n = len(polygon_vertices)
    inside = False
    
    p1x, p1y = polygon_vertices[0].x, polygon_vertices[0].y
    for i in range(n + 1): # Iterate n+1 times to process all edges, including the one back to the start
        p2x, p2y = polygon_vertices[i % n].x, polygon_vertices[i % n].y # Use i % n to wrap around to the first vertex
        
        # Check if the point's y-coordinate is within the y-range of the current edge
        # and the ray from point (extending horizontally to the right) could potentially cross this edge.
        if (p1y <= point.y < p2y) or (p2y <= point.y < p1y):
            # Edge is not horizontal and crosses the horizontal line at point.y.
            # Calculate the x-coordinate of the intersection of the ray and the edge.
            # vt = (float)(point.y - p1y) / (p2y - p1y)
            # xinters = p1x + vt * (p2x - p1x)
            # Simplified:
            xinters = (point.y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
            if point.x < xinters: # Point is to the left of the intersection, so the ray crosses.
                inside = not inside
        # Special case for points exactly on a horizontal segment:
        # If point.y == p1y == p2y, and point.x is between min(p1x, p2x) and max(p1x, p2x),
        # the point is on the boundary. Standard ray casting might count this differently.
        # This implementation considers points on horizontal boundaries as outside
        # unless explicitly handled. The above condition (p1y <= point.y < p2y) or (p2y <= point.y < p1y)
        # implicitly handles horizontal segments by not evaluating them if point.y is exactly on them
        # because neither `point.y < p1y` (if p1y==p2y) nor `point.y < p2y` would be true.
        # For robustness with vertices, more complex logic is needed. This is a common simplified version.

        p1x, p1y = p2x, p2y # Move to the next point
        
    return inside