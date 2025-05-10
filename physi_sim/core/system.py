from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .entity_manager import EntityManager

class System(ABC):
    def __init__(self, entity_manager: 'EntityManager'):
        self.entity_manager = entity_manager

    @abstractmethod
    def update(self, dt: float) -> None:
        pass