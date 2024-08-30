from logging import getLogger
from typing import Iterator
from airedgio.memory import Memory
from bridge.bridge import Bridge
from .queries import Queries
from datetime import datetime
from requests import Session, session, status_codes

logger = getLogger(__name__)


class AIRedgio:
    _session: Session | None = None
    _timestamp_format = '%Y-%m-%dT%H:%M:%S.%fZ'
    _api_endpoint: str
    _headers = {
        'Content-Type': 'application/json',
    }
    _bridge: Bridge
    _memory: Memory

    @property
    def session(self) -> Session:
        if not self._session:
            self._session = session()
            self._session.headers.update(self._headers)
        return self._session

    @property
    def memory(self) -> Memory:
        return self._memory

    def __init__(
        self,
        api_endpoint: str,
        bridge: Bridge,
        memory_filepath: str,
        queries: dict = {}
    ):
        self._api_endpoint = api_endpoint
        self._bridge = bridge

        self._memory = Memory.memory_factory(memory_filepath)

        self._queries = Queries(queries)

    def _post_query(self, query: str) -> list[dict]:
        response = self.session.post(
            url=self._api_endpoint,
            data=query
        )
        if response.status_code != status_codes.codes.OK:
            return []

        content = response.json()
        if not ('success' in content and content['success']):
            return []

        if 'data' not in content:
            return []

        return content['data']

    def get_created(self, start_date: datetime, end_date: datetime) -> list[dict]:
        start_string = start_date.strftime(self._timestamp_format)
        end_string = end_date.strftime(self._timestamp_format)
        query_string = self._queries.created(start_string, end_string)

        return self._post_query(query_string)

    def get_changed(self, start_date: datetime, end_date: datetime) -> list[dict]:
        start_string = start_date.strftime(self._timestamp_format)
        end_string = end_date.strftime(self._timestamp_format)
        query_string = self._queries.modified(start_string, end_string)

        return self._post_query(query_string)

    def get_by_id(self, asset_id: str) -> dict:
        query_string = self._queries.by_id(asset_id)

        res = self._post_query(query_string)

        return res[0] if res else {}

    def get_all(self) -> list[dict]:
        return self._post_query('{}')

    def _next_month(self, date: datetime) -> datetime:
        year = date.year
        month = date.month + 1
        if month > 12:
            year += 1
            month %= 12
        return datetime(year=year, month=month, day=1)

    def download_all_created_assets(self) -> Iterator[list[dict]]:
        start_date = self.memory.latest_created_date
        end_date = start_date
        while start_date <= datetime.now():
            logger.debug(
                'Requesting assets created between %(start_date)s and %(end_date)s',
                {
                    'start_date': start_date,
                    'end_date': end_date
                }
            )
            start_date = end_date
            end_date = self._next_month(start_date)

            # Get all the assets created in a month
            created_month = self.get_created(start_date, end_date)

            self.memory.latest_created_date = min(end_date, datetime.now())

            yield created_month

    def convert_created(self) -> None:
        failed = list()
        success = list()
        logger.debug(
            'Converting all created assets from %(latest_created_date)s',
            {
                'latest_created_date': self.memory.latest_created_date
            }
        )
        # Download assets month by month
        for month in self.download_all_created_assets():
            # Convert each asset
            for asset in month:
                # TODO: Validate AIRedgio entity
                logger.debug(
                    'Converting asset %(asset_id)s',
                    {
                        'asset_id': asset['_id']
                    }
                )
                asset_type = (
                    asset['_source']['aitype']
                    .lower()
                    .replace(' ', '_')
                )
                if not self._bridge.convert_asset(asset, asset_type):
                    failed.append(asset['_id'])
                    continue

                success.append(asset['_id'])
                logger.debug(
                    'Successfully converted asset %(asset_id)s',
                    {
                        'asset_id': asset['_id']
                    }
                )

        self.memory.update_created(success, failed)

    def download_all_modified_assets(self) -> Iterator[list[dict]]:
        start_date = self.memory.latest_modified_date
        end_date = start_date
        while start_date <= datetime.now():
            logger.debug(
                'Requesting assets modified between %(start_date)s and %(end_date)s',
                {
                    'start_date': start_date,
                    'end_date': end_date
                }
            )
            start_date = end_date
            end_date = self._next_month(start_date)

            # Get all the assets modified in a month
            modified_month = self.get_changed(start_date, end_date)

            self.memory.latest_modified_date = min(
                end_date, datetime.now())

            yield modified_month

    def convert_modified(self) -> None:
        failed = list()
        success = list()
        logger.debug(
            'Converting all modified assets from %(latest_modified_date)s',
            {
                'latest_modified_date': self.memory.latest_modified_date
            }
        )
        # Download assets month by month
        for month in self.download_all_modified_assets():
            # Convert each asset
            for asset in month:
                # TODO: Validate AIRedgio entity
                # If the modified date is the same as the created date, then it has not been modified
                if asset['_source']['properties']['created'] == asset['_source']['properties']['changed']:
                    logger.info(
                        'Asset %(asset_id)s has not been modified since creation',
                        {
                            'asset_id': asset['_id']
                        }
                    )
                    continue

                logger.debug(
                    'Converting asset %(asset_id)s',
                    {
                        'asset_id': asset['_id']
                    }
                )
                asset_type = (
                    asset['_source']['aitype']
                    .lower()
                    .replace(' ', '_')
                )
                if not self._bridge.convert_asset(asset, asset_type):
                    failed.append(asset['_id'])
                    continue

                success.append(asset['_id'])
                logger.debug(
                    'Successfully converted asset %(asset_id)s',
                    {
                        'asset_id': asset['_id']
                    }
                )

        self.memory.update_modified(success, failed)

    def convert_failed_created(self) -> None:
        failed = list()
        success = list()
        logger.debug('Converting all failed assets')
        for asset_id in self.memory.failed_created:
            # TODO Check if failed ones have been deleted before we could upload them
            logger.debug(
                'Converting asset %(asset_id)s',
                {
                    'asset_id': asset_id
                }
            )
            asset = self.get_by_id(asset_id)
            if not asset:
                logger.debug(
                    'Failed to download asset %(asset_id)s from the AIRedgio platform',
                    {
                        'asset_id': asset_id
                    }
                )
                failed.append(asset_id)

            asset_type = asset['_source']['aitype'].lower().replace(' ', '_')
            if not self._bridge.convert_asset(asset, asset_type):
                failed.append(asset['_id'])
                continue

            success.append(asset['_id'])
            logger.debug(
                'Successfully converted asset %(asset_id)s',
                {
                    'asset_id': asset_id
                }
            )

        self.memory.update_created(success, failed)

    def convert_failed_modified(self) -> None:
        failed = list()
        success = list()
        logger.debug('Converting all failed assets')
        for asset_id in self.memory.failed_modified:
            logger.debug(
                'Converting asset %(asset_id)s',
                {
                    'asset_id': asset_id
                }
            )
            asset = self.get_by_id(asset_id)
            if not asset:
                logger.debug(
                    'Failed to download asset %(asset_id)s from the AIRedgio platform',
                    {
                        'asset_id': asset_id
                    }
                )
                failed.append(asset_id)

            asset_type = asset['_source']['aitype'].lower().replace(' ', '_')
            if not self._bridge.convert_asset(asset, asset_type):
                failed.append(asset['_id'])
                continue

            success.append(asset['_id'])
            logger.debug(
                'Successfully converted asset %(asset_id)s',
                {
                    'asset_id': asset_id
                }
            )

        self.memory.update_modified(success, failed)

    def check_deletion(self) -> None:
        # TODO: Implement a retry-mechanism to assure each asset in the list gets tested at least once in a while
        removed = list()
        logger.debug("Checking if any asset has been deleted from AIREDGIO")
        for asset_id in self.memory.success_created:
            asset = self.get_by_id(asset_id)
            if asset:
                logger.debug(
                    'Asset %(asset_id)s has not been deleted',
                    {
                        'asset_id': asset_id
                    }
                )
                continue

            asset_type = asset['_source']['aitype'].lower().replace(' ', '_')
            if self._bridge.delete_asset(asset_id, asset_type):
                logger.debug(
                    'Asset %(asset_id)s has not been removed from AIoD',
                    {
                        'asset_id': asset_id
                    }
                )
                removed.append(asset_id)
            else:
                logger.debug(
                    'Could not remove asset %(asset_id)s from AIoD',
                    {
                        'asset_id': asset_id
                    }
                )
        self.memory.update_removed(removed)

    def convert_all(self) -> None:
        if not self._bridge.check_aiod_login():
            return

        if not self._bridge.check_platform():
            return

        # Convert the assets that failed to upload the last time
        self.convert_failed_created()
        self.memory.save()

        # Convert assets created after the last run
        self.convert_created()
        self.memory.save()

        # Convert the assets that failed to upload the last time
        self.convert_failed_modified()
        self.memory.save()

        # Convert assets created after the last run
        self.convert_modified()
        self.memory.save()

        # Check if created have been deleted
        self.check_deletion()
        self.memory.save()
