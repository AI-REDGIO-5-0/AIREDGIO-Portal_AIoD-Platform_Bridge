from itertools import islice
import json
from logging import getLogger
import os
from typing import Iterator
from bridge.platform_converter import PlatformConverter
from memory.memory import Memory
from .queries import Queries
from datetime import datetime
from requests import Session, session, status_codes

logger = getLogger(__name__)


class AIRedgio(PlatformConverter):
    _name = 'airedgio'
    _session: Session | None = None
    _timestamp_format = '%Y-%m-%dT%H:%M:%S.%fZ'
    _api_endpoint: str
    _headers = {
        'Content-Type': 'application/json',
    }
    _memory: Memory
    translators: dict[str, dict] = {}

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
        memory_filepath: str,
        translators_folder: str,
        queries: dict = {},
    ):
        self._api_endpoint = api_endpoint

        self._memory = Memory.memory_factory(memory_filepath)

        self._queries = Queries(queries)

        if not os.path.isdir(translators_folder):
            raise FileNotFoundError(f'Folder "{translators_folder}" not found')
        for filename in os.listdir(translators_folder):
            try:
                with open(os.path.join(translators_folder, filename), 'r') as fin:
                    translator_type = os.path.splitext(filename)[0]
                    self.translators[translator_type] = json.load(fin)
                    logger.debug(
                        'Loaded translator for %(translator_type)s',
                        {
                            'translator_type': translator_type
                        }
                    )
            except Exception as e:
                logger.warning(
                    'Error while reading translator file %(translator_filename)s: %(error)s',
                    {
                        'translator_filename': filename,
                        'error': e,
                    }
                )

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

    def translate_created(self) -> list[tuple[dict, str]]:
        failed = list()
        success = list()
        logger.debug(
            'Translating all created assets from %(latest_created_date)s',
            {
                'latest_created_date': self.memory.latest_created_date
            }
        )
        # Download assets month by month
        for month in self.download_all_created_assets():
            # Convert each asset
            for asset in month:
                asset_id = asset['_id']
                # TODO: Validate AIRedgio entity
                logger.debug(
                    'Translating asset %(asset_id)s',
                    {
                        'asset_id': asset_id
                    }
                )
                asset_type = (
                    asset['_type']
                    .lower()
                    .replace(' ', '_')
                )
                asset = self.translate(asset, asset_type)
                if not asset:
                    logger.debug(
                        'Failed to translate asset %(asset_id)s of type %(asset_type)s',
                        {
                            'asset_id': asset_id,
                            'asset_type': asset_type,
                        }
                    )
                    failed.append(asset_id)
                    continue

                success.append((asset, asset_type))
                logger.debug(
                    'Successfully converted asset %(asset_id)s',
                    {
                        'asset_id': asset_id
                    }
                )

        self.memory.update_created([], failed)
        return success

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

    def translate_modified(self) -> list[tuple[dict, str]]:
        failed = list()
        success = list()
        logger.debug(
            'Translating all modified assets from %(latest_modified_date)s',
            {
                'latest_modified_date': self.memory.latest_modified_date
            }
        )
        # Download assets month by month
        for month in self.download_all_modified_assets():
            # Convert each asset
            for asset in month:
                asset_id = asset['_id']
                # TODO: Validate AIRedgio entity
                # If the modified date is the same as the created date, then it has not been modified
                if asset['_source']['properties']['created'] == asset['_source']['properties']['changed']:
                    logger.info(
                        'Asset %(asset_id)s has not been modified since creation',
                        {
                            'asset_id': asset_id
                        }
                    )
                    continue

                logger.debug(
                    'Translating asset %(asset_id)s',
                    {
                        'asset_id': asset_id
                    }
                )
                asset_type = (
                    asset['_type']
                    .lower()
                    .replace(' ', '_')
                )

                asset = self.translate(asset, asset_type)
                if not asset:
                    logger.debug(
                        'Failed to translate asset %(asset_id)s of type %(asset_type)s',
                        {
                            'asset_id': asset_id,
                            'asset_type': asset_type,
                        }
                    )
                    failed.append(asset_id)
                    continue

                success.append((asset, asset_type))
                logger.debug(
                    'Successfully converted asset %(asset_id)s',
                    {
                        'asset_id': asset_id
                    }
                )

        self.memory.update_modified([], failed)
        return success

    def translate_failed_created(self) -> list[tuple[dict, str]]:
        failed = list()
        success = list()
        logger.debug('Translating all failed assets')
        for asset_id in self.memory.failed_created:
            # TODO Check if failed ones have been deleted before we could upload them
            logger.debug(
                'Translating asset %(asset_id)s',
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
                continue

            asset_type = asset['_type'].lower().replace(' ', '_')

            asset = self.translate(asset, asset_type)
            if not asset:
                logger.debug(
                    'Failed to translate failed created asset %(asset_id)s of type %(asset_type)s',
                    {
                        'asset_id': asset_id,
                        'asset_type': asset_type,
                    }
                )
                failed.append(asset_id)
                continue

            success.append((asset, asset_type))
            logger.debug(
                'Successfully translated asset %(asset_id)s',
                {
                    'asset_id': asset_id
                }
            )

        self.memory.update_created([], failed)
        return success

    def translate_failed_modified(self) -> list[tuple[dict, str]]:
        failed = list()
        success = list()
        logger.debug('Translating all failed assets')
        for asset_id in self.memory.failed_modified:
            logger.debug(
                'Translating asset %(asset_id)s',
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
                continue

            asset_type = asset['_type'].lower().replace(' ', '_')
            asset = self.translate(asset, asset_type)
            if not asset:
                logger.debug(
                    'Failed to translate failed modified asset %(asset_id)s of type %(asset_type)s',
                    {
                        'asset_id': asset_id,
                        'asset_type': asset_type,
                    }
                )
                failed.append(asset_id)
                continue

            success.append((asset, asset_type))
            logger.debug(
                'Successfully converted asset %(asset_id)s',
                {
                    'asset_id': asset_id
                }
            )

        self.memory.update_modified([], failed)
        return success

    # def check_deletion(self) -> None:
    #     # TODO: Implement a retry-mechanism to assure each asset in the list gets tested at least once in a while
    #     removed = list()
    #     logger.debug("Checking if any asset has been deleted from AIREDGIO")
    #     for asset_id in self.memory.success_created:
    #         asset = self.get_by_id(asset_id)
    #         if asset:
    #             logger.debug(
    #                 'Asset %(asset_id)s has not been deleted',
    #                 {
    #                     'asset_id': asset_id
    #                 }
    #             )
    #             continue

    #         asset_type = asset['_type'].lower().replace(' ', '_')
    #         if self._bridge.delete_asset(asset_id, asset_type):
    #             logger.debug(
    #                 'Asset %(asset_id)s has not been removed from AIoD',
    #                 {
    #                     'asset_id': asset_id
    #                 }
    #             )
    #             removed.append(asset_id)
    #         else:
    #             logger.debug(
    #                 'Could not remove asset %(asset_id)s from AIoD',
    #                 {
    #                     'asset_id': asset_id
    #                 }
    #             )
    #     self.memory.update_removed(removed)

    def translate_all(self) -> list[tuple[dict, str]]:
        # Convert the assets that failed to upload the last time
        assets = self.translate_failed_created()
        self.memory.save()

        # Convert assets created after the last run
        assets += self.translate_created()
        self.memory.save()

        # Convert the assets that failed to upload the last time
        assets += self.translate_failed_modified()
        self.memory.save()

        # # Convert assets created after the last run
        assets += self.translate_modified()
        self.memory.save()

        # # Check if created have been deleted
        # self.check_deletion()
        # self.memory.save()

        return assets

    def update_assets_status(self, success: list[str], failed: list[str]) -> None:
        self.memory.update_created(success, failed)
        self.memory.update_modified(success, failed)

    @property
    def name(self) -> str:
        return self._name

    def can_handle(self, asset_type: str) -> bool:
        return asset_type in self.translators

    def _translate(
        self,
        instance: dict,
        created: dict,
        translator: dict = {},
        translator_type: str = '',
        index: int | None = None
    ) -> dict:
        if 'contacts' in instance.get('_source', {}):
            c = instance['_source']['contacts']
            if not isinstance(c, list):
                instance['_source']['contacts'] = [c]

        # 'translation' is the resulting AIoD JSON asset
        translation: dict[str, int | str | dict | list] = {}

        # Either use the provided translator JSON or open a translator file based on the type
        if not translator:
            if translator_type not in self.translators:
                logger.error(
                    'Translator for type %(translator_type)s not found',
                    {
                        'translator_type': translator_type,
                    }
                )
                return translation
            translator = self.translators[translator_type]

        # 'translation['.reference']' holds the keys to other assets that need to be referenced inside 'translation'
        translation['.reference'] = dict()
        for key, value in translator.items():
            match value:
                case int():
                    translation[key] = value
                case str() if not value.startswith('$'):
                    translation[key] = value
                case str() if value.startswith('$/'):
                    # The value represents a path in the AI REDGIO JSON to the wanted value
                    # TODO: instead of just path + append, allow something like {path + append} * n
                    splits = value.split('$', 2)
                    path = splits[1]
                    append = splits[2:] if len(splits) > 2 else ''
                    current_value = instance
                    # Follow the path
                    for k in islice(path.split('/'), 1, None):
                        if isinstance(current_value, dict):
                            if k in current_value:
                                current_value = current_value[k]
                            else:
                                break
                        elif isinstance(current_value, list):
                            if k.isdigit() and len(current_value) > int(k):
                                current_value = current_value[int(k)]
                            elif k == 'i' and index != None and len(current_value) > index:
                                current_value = current_value[index]
                            else:
                                break
                        else:
                            break
                    else:
                        # Only use 'current_value' if the for-loop executed till the end (meaning the path was found)
                        if isinstance(current_value, str):
                            # Can only append to str
                            translation[key] = f'{current_value}{append}'
                        else:
                            translation[key] = current_value
                case str() if value.startswith('$ref'):
                    # The value represents a different object that must be created and this 'translation' will only hold a reference identifier to it, not the object itself
                    if index != None:
                        value = f'{value}/{index}'
                    if value in created:
                        # If it's already been created, reference that one
                        translation['.reference'][key] = value
                    else:
                        # Recursively create the referenced object
                        created[value] = None
                        res = self._translate(
                            instance,
                            created,
                            translator_type=value.split('/')[1],
                            index=index
                        )
                        created[value] = res
                        translation['.reference'][key] = value
                case str() if value.startswith('$listref'):
                    # Replace the list with a list of referenced objects
                    splits = value.split('/')
                    t = splits[1]
                    current_value = instance
                    for k in islice(splits, 2, None):
                        if isinstance(current_value, dict) and k in current_value:
                            current_value = current_value[k]
                        elif isinstance(current_value, list):
                            if k.isdigit() and len(current_value) > int(k):
                                current_value = current_value[int(k)]
                            else:
                                break
                        else:
                            break
                    else:
                        translation[key] = list()

                        # For each element in the list, apply the same behaviour as with the values starting with '$ref'
                        # Pass 'i' as the index
                        for i in range(len(current_value)):
                            value = f'$ref/{splits[1]}/{i}'
                            if value in created:
                                translation['.reference'][key] = value
                            else:
                                created[value] = None
                                res = self._translate(
                                    instance,
                                    created,
                                    translator_type=t,
                                    index=i
                                )
                                created[value] = res
                                translation['.reference'][f'{key}/{i}'] = value
                case dict():
                    # Recursively translate each dictionary
                    res = self._translate(instance, created, value)
                    translation[key] = res
                    # Merge the references in the inner dict with the ones of 'translation'
                    refs = res.pop('.reference', {})
                    for k, v in refs.items():
                        translation['.reference'][f'{key}/{k}'] = v
                case list():
                    res = self._translate(
                        instance,
                        created,
                        {k: v for k, v in enumerate(value)}
                    )
                    refs = res.pop('.reference', {})
                    res = [x for sublist in res.values() if isinstance(
                        sublist, list) for x in sublist]
                    for k, v in refs.items():
                        translation['.reference'][f'{key}/{k}'] = v
                    translation[key] = list(res)

        return translation

    def translate(
        self,
        instance: dict,
        translator_type: str,
    ) -> dict:
        created = dict()
        translated = self._translate(
            instance,
            created,
            translator_type=translator_type
        )
        if not translated:
            return dict()
        created[f'/{translator_type}'] = translated
        return created

    def get_asset_id(self, asset: dict) -> str:
        return asset.get('id', '')