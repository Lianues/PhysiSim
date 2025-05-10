from .vector import Vector2D # 确保 Vector2D 被导入

# Y-axis upwards is positive in world coordinates
GRAVITY_ACCELERATION = Vector2D(0, -9.81)
EPSILON = 1e-6 # A small number to prevent division by zero or for float comparisons