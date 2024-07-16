from datetime import datetime
import json
import os
from typing import Iterable

from airedgio.memory import Memory


class MemoryJSON(Memory):
    _memory_filepath: str
    _memory: dict

    def __init__(self, filepath: str, timestamp_format: str = '') -> None:
        super().__init__(timestamp_format)
        if not os.path.isfile(filepath):
            memory_folder = os.path.basename(filepath)
            if not os.path.isdir(memory_folder):
                raise ValueError(
                    f'Could not find memory file at "{filepath}"')
            self._memory = dict()
        else:
            with open(filepath, 'r') as fin:
                self._memory = json.load(fin)

        self._memory_filepath = filepath

        if 'failed' not in self._memory:
            self._memory['failed'] = dict()
        if 'created' not in self._memory['failed']:
            self._memory['failed']['created'] = set()
        else:
            self._memory['failed']['created'] = set(
                self._memory['failed']['created'])
        if 'modified' not in self._memory['failed']:
            self._memory['failed']['modified'] = set()
        else:
            self._memory['failed']['modified'] = set(
                self._memory['failed']['modified'])

        if 'latest' not in self._memory:
            self._memory['latest'] = dict()
        if 'created' not in self._memory['latest']:
            self._memory['latest']['created'] = datetime(
                2023, 10, 1).strftime(self._timestamp_format)
        if 'modified' not in self._memory['latest']:
            self._memory['latest']['modified'] = datetime(
                2023, 10, 1).strftime(self._timestamp_format)

        if 'created' not in self._memory:
            self._memory['created'] = set()
        else:
            self._memory['created'] = set(self._memory['created'])

    def save(self) -> None:
        with open(self._memory_filepath, 'w') as fout:
            json.dump(
                self._memory,
                fout,
                indent=4,
                default=lambda obj: list(obj) if isinstance(obj, set) else obj
            )

    @property
    def latest_created_date(self) -> datetime:
        return datetime.strptime(
            self._memory['latest']['created'],
            self._timestamp_format
        )

    @latest_created_date.setter
    def set_latest_created_date(self, date: datetime) -> None:
        date_str = date.strftime(self._timestamp_format)
        self._memory['latest']['created'] = date_str

    @property
    def latest_modified_date(self) -> datetime:
        return datetime.strptime(
            self._memory['latest']['modified'],
            self._timestamp_format
        )

    @latest_modified_date.setter
    def set_latest_modified_date(self, date: datetime) -> None:
        date_str = date.strftime(self._timestamp_format)
        self._memory['latest']['modified'] = date_str

    @property
    def success_created(self) -> set[str]:
        return self._memory['created']

    @property
    def failed_created(self) -> set[str]:
        return self._memory['failed']['created']

    @property
    def failed_modified(self) -> set[str]:
        return self._memory['failed']['modified']

    def update_created(self, success: Iterable[str], failed: Iterable[str]) -> None:
        tmp = self.failed_created.difference(success)
        tmp.update(failed)
        self.failed_created.clear()
        self.failed_created.update(tmp)
        self.success_created.update(success)

    def update_modified(self, success: Iterable[str], failed: Iterable[str]) -> None:
        tmp = self.failed_modified.difference(success)
        tmp.update(failed)
        self.failed_modified.clear()
        self.failed_modified.update(tmp)
        self.success_created.update(success)

    def update_removed(self, removed: Iterable[str]) -> None:
        tmp = self.success_created.difference(removed)
        self.success_created.clear()
        self.success_created.update(tmp)
