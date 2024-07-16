from datetime import datetime
from typing import Iterable
import sqlite3

from airedgio.memory import Memory


class MemorySQLite(Memory):
    _memory_filepath: str
    _memory: dict
    _connection: sqlite3.Connection
    _fetch_size: int

    def __init__(
        self,
        connection_string: str,
        timestamp_format: str = '',
        fetch_size: int = 1000
    ) -> None:
        if not connection_string.startswith('sqlite:'):
            raise ValueError('Connection string must begin with "sqlite:"')
        connection_string = connection_string.replace('sqlite:', '', 1)
        super().__init__(timestamp_format)
        self._connection = sqlite3.connect(connection_string)
        self._fetch_size = fetch_size

        cur = self._connection.cursor()
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS failed_to_create (
                id TEXT PRIMARY KEY
            )
            '''
        )
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS failed_to_modify (
                id TEXT PRIMARY KEY
            )
            '''
        )
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS created (
                id TEXT PRIMARY KEY
            )
            '''
        )
        # The table only allows the id PKEY to have value equal to 0 so that there is always only one row
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS latest (
                id INTEGER PRIMARY KEY CHECK (id = 0),
                latest_created_date TEXT,
                latest_modified_date TEXT
            )
            '''
        )
        # If the table is empty add default dates
        cur.execute(
            '''SELECT EXISTS (SELECT 1 FROM latest)'''
        )
        empty = cur.fetchone()[0] == 0
        if empty:
            # print('Table "latest" is empty, inserting default dates... ', end='', flush=True)
            default_date = datetime(2023, 10, 1).strftime(
                self._timestamp_format)
            cur.execute(
                '''INSERT OR REPLACE INTO latest(id, latest_created_date, latest_modified_date) VALUES(?, ?, ?)''',
                (0, default_date, default_date)
            )
            # print('Populated table "latest" with default dates.')
        self._connection.commit()

    def save(self) -> None:
        self._connection.commit()

    def _latest_date(self, date_type: str) -> datetime:
        cur = self._connection.cursor()
        latest = (
            cur
            .execute(
                f'''SELECT {date_type} from latest'''
            )
            .fetchone()
            [0]
        )
        return datetime.strptime(
            latest,
            self._timestamp_format
        )

    def _latest_date_setter(self, date_type: str, date: datetime) -> None:
        cur = self._connection.cursor()
        cur.execute(
            f'''
            UPDATE latest SET {date_type} = ? WHERE id = 0
            ''',
            (date.strftime(self._timestamp_format),)
        )

    @property
    def latest_created_date(self) -> datetime:
        return self._latest_date('latest_created_date')

    @latest_created_date.setter
    def set_latest_created_date(self, date: datetime) -> None:
        self._latest_date_setter('latest_created_date', date)

    @property
    def latest_modified_date(self) -> datetime:
        return self._latest_date('latest_modified_date')

    @latest_modified_date.setter
    def set_latest_modified_date(self, date: datetime) -> None:
        self._latest_date_setter('latest_modified_date', date)

    def _get_iterable_from_table(self, table: str) -> Iterable[str]:
        cursor = self._connection.cursor()
        cursor.execute(f'SELECT id FROM {table}')
        rows = cursor.fetchmany(self._fetch_size)
        while rows:
            for row in rows:
                yield row[0]
            rows = cursor.fetchmany(self._fetch_size)

    @property
    def success_created(self) -> Iterable[str]:
        return self._get_iterable_from_table('created')

    @property
    def failed_created(self) -> Iterable[str]:
        return self._get_iterable_from_table('failed_to_create')

    @property
    def failed_modified(self) -> Iterable[str]:
        return self._get_iterable_from_table('failed_to_modify')

    def update_created(self, success: list[str], failed: list[str]) -> None:
        cursor = self._connection.cursor()
        # cursor.executemany(
        #     "DELETE FROM failed_to_create WHERE id = ?",
        #     map(lambda asset_id: (asset_id,), success)
        # )
        cursor.execute(
            f"DELETE FROM failed_to_create WHERE id IN ({', '.join(['?'] * len(success))})",
            success
        )
        cursor.executemany(
            '''
            INSERT OR REPLACE INTO failed_to_create(id) VALUES(?)
            ''',
            map(lambda asset_id: (asset_id,), failed)
        )
        cursor.executemany(
            '''
            INSERT OR REPLACE INTO created(id) VALUES(?)
            ''',
            map(lambda asset_id: (asset_id,), success)
        )

    def update_modified(self, success: Iterable[str], failed: Iterable[str]) -> None:
        cursor = self._connection.cursor()
        cursor.executemany(
            "DELETE FROM failed_to_modify WHERE id = ?",
            map(lambda asset_id: (asset_id,), success)
        )
        cursor.executemany(
            '''
            INSERT OR REPLACE INTO failed_to_modify(id) VALUES(?)
            ''',
            map(lambda asset_id: (asset_id,), failed)
        )
        cursor.executemany(
            '''
            INSERT OR REPLACE INTO created(id) VALUES(?)
            ''',
            map(lambda asset_id: (asset_id,), success)
        )

    def update_removed(self, removed: Iterable[str]) -> None:
        cursor = self._connection.cursor()
        cursor.executemany(
            "DELETE FROM created WHERE id = ?",
            map(lambda asset_id: (asset_id,), removed)
        )
        cursor = self._connection.cursor()
        cursor.executemany(
            "DELETE FROM failed_to_create WHERE id = ?",
            map(lambda asset_id: (asset_id,), removed)
        )
        cursor = self._connection.cursor()
        cursor.executemany(
            "DELETE FROM failed_to_modify WHERE id = ?",
            map(lambda asset_id: (asset_id,), removed)
        )
