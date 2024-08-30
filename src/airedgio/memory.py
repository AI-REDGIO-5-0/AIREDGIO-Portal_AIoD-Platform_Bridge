from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable

class Memory(ABC):
    _timestamp_format = '%Y-%m-%dT%H:%M:%S.%fZ'

    def __init__(
        self,
        timestamp_format: str = ''
    ) -> None:
        if timestamp_format:
            self._timestamp_format = timestamp_format

    @abstractmethod
    def save(self) -> None:
        pass
    
    @property
    @abstractmethod
    def latest_created_date(self) -> datetime:
        pass

    @latest_created_date.setter
    @abstractmethod
    def latest_created_date(self, date: datetime) -> None:
        pass

    @property
    @abstractmethod
    def latest_modified_date(self) -> datetime:
        pass

    @latest_modified_date.setter
    @abstractmethod
    def latest_modified_date(self, date: datetime) -> None:
        pass

    @property
    @abstractmethod
    def success_created(self) -> Iterable[str]:
        pass

    @property
    @abstractmethod
    def failed_created(self) -> Iterable[str]:
        pass

    @property
    @abstractmethod
    def failed_modified(self) -> Iterable[str]:
        pass

    @abstractmethod
    def update_created(self, success: list[str], failed: list[str]) -> None:
        pass

    @abstractmethod
    def update_modified(self, success: Iterable[str], failed: Iterable[str]) -> None:
        pass

    @abstractmethod
    def update_removed(self, removed: Iterable[str]) -> None:
        pass

    @classmethod
    def memory_factory(cls, connection_string: str, *args):
        if connection_string.startswith('json:'):
            from airedgio.memory_json import MemoryJSON
            return MemoryJSON(connection_string, *args)
        elif connection_string.startswith('sqlite:'):
            from airedgio.memory_sqlite import MemorySQLite
            return MemorySQLite(connection_string, *args)
        else:
            raise ValueError('Could not infer type from connection string')