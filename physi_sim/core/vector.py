import math
from typing import Union

class Vector2D:
    """
    A two-dimensional vector with common vector operations.
    """
    def __init__(self, x: float, y: float):
        self.x: float = x
        self.y: float = y

    def __add__(self, other: 'Vector2D') -> 'Vector2D':
        if not isinstance(other, Vector2D):
            return NotImplemented
        return Vector2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: 'Vector2D') -> 'Vector2D':
        if not isinstance(other, Vector2D):
            return NotImplemented
        return Vector2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: Union[int, float]) -> 'Vector2D':
        if not isinstance(scalar, (int, float)):
            return NotImplemented
        return Vector2D(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: Union[int, float]) -> 'Vector2D':
        return self.__mul__(scalar)

    def __truediv__(self, scalar: Union[int, float]) -> 'Vector2D':
        if not isinstance(scalar, (int, float)):
            return NotImplemented
        if scalar == 0:
            raise ValueError("Cannot divide by zero.")
        return Vector2D(self.x / scalar, self.y / scalar)

    def __neg__(self) -> 'Vector2D':
        """Returns a new vector with negated components."""
        return Vector2D(-self.x, -self.y)

    def dot(self, other: 'Vector2D') -> float:
        """Calculates the dot product with another Vector2D."""
        if not isinstance(other, Vector2D):
            raise TypeError("Can only calculate dot product with another Vector2D.")
        return self.x * other.x + self.y * other.y

    def cross(self, other: 'Vector2D') -> float:
        """Calculates the 2D cross product (which is a scalar).
        The 2D cross product of A(x, y) and B(x', y') is A.x * B.y' - A.y * B.x'.
        """
        if not isinstance(other, Vector2D):
            raise TypeError("Can only calculate cross product with another Vector2D.")
        return self.x * other.y - self.y * other.x

    def magnitude(self) -> float:
        """Returns the magnitude (length) of the vector."""
        return math.sqrt(self.x**2 + self.y**2)

    def length(self) -> float:
        """Alias for magnitude(). Returns the length of the vector."""
        return self.magnitude()

    def magnitude_squared(self) -> float:
        """Returns the squared magnitude of the vector."""
        return self.x**2 + self.y**2

    def normalize(self) -> 'Vector2D':
        """Returns a new normalized (unit) vector."""
        mag = self.magnitude()
        if mag == 0:
            return Vector2D(0, 0) # Or raise an error, depending on desired behavior
        return Vector2D(self.x / mag, self.y / mag)

    def normalize_ip(self) -> 'Vector2D':
        """Normalizes the vector in-place and returns self."""
        mag = self.magnitude()
        if mag == 0:
            # Or raise an error
            self.x = 0
            self.y = 0
        else:
            self.x /= mag
            self.y /= mag
        return self

    def rotate(self, angle_rad: float) -> 'Vector2D':
        """Returns a new vector rotated by the given angle in radians."""
        cos_angle = math.cos(angle_rad)
        sin_angle = math.sin(angle_rad)
        new_x = self.x * cos_angle - self.y * sin_angle
        new_y = self.x * sin_angle + self.y * cos_angle
        return Vector2D(new_x, new_y)

    def perpendicular(self) -> 'Vector2D':
        """Returns a new vector that is perpendicular to this one (rotated 90 degrees counter-clockwise)."""
        return Vector2D(-self.y, self.x)

    def to_dict(self) -> dict[str, float]:
        """Serializes the vector to a dictionary."""
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> 'Vector2D':
        """Deserializes a vector from a dictionary."""
        if not isinstance(data, dict) or 'x' not in data or 'y' not in data:
            # Consider raising a more specific error or logging
            raise ValueError("Invalid data format for Vector2D.from_dict. Expected dict with 'x' and 'y'.")
        return cls(float(data['x']), float(data['y']))

    def __str__(self) -> str:
        return f"Vector2D({self.x}, {self.y})"

    def __repr__(self) -> str:
        return f"Vector2D(x={self.x}, y={self.y})"