import json
import os
import traceback
from aiod.aiod import AIoD
from bridge.platform import Platform
from logging import getLogger

from bridge.platform_converter import PlatformConverter

logger = getLogger(__name__)


class Bridge:
    _aiod: AIoD
    _configuration_folder: str
    _timestamp_format = '%Y-%m-%dT%H:%M:%S.%fZ'
    _type_to_aiod_endpoint: dict
    _platform: Platform
    _platform_converters: dict[str, PlatformConverter]

    def __init__(
        self,
        configuration_folder: str,
        aiod: AIoD,
        platform_converters: list[PlatformConverter] = []
    ) -> None:
        if not os.path.isdir(configuration_folder):
            raise FileNotFoundError(
                f'Folder "{configuration_folder}" not found'
            )
        self._configuration_folder = configuration_folder

        with open(f'{self._configuration_folder}/type_to_aiod_endpoint.json', 'r') as fin:
            self._type_to_aiod_endpoint = json.load(fin)

        self._aiod = aiod
        with open(f'{self._configuration_folder}/platform.json', 'r') as fin:
            platform = json.load(fin)
        self._platform = Platform(self._aiod, platform)

        self._platform_converters = {p.name: p for p in platform_converters}

    @property
    def platform(self) -> Platform:
        return self._platform

    def aiod_endpoint_from_type(self, redgio_name: str) -> str:
        return self._type_to_aiod_endpoint.get(redgio_name, '')

    def check_platform(self) -> bool:
        return self.platform.check_platform()

    def merge(self, new: dict, old: dict) -> dict:
        result = json.loads(json.dumps(new))
        for key, value in old.items():
            if key not in result:
                result[key] = value
            else:
                match value:
                    case list():
                        if isinstance(result[key], list):
                            result[key].extend(value)
                    case dict():
                        if isinstance(result[key], dict):
                            result[key] = self.merge(result[key], value)

        return result

    def post_and_put(self, entity_key: str, entity: dict) -> dict:

        # Find the AIoD endpoint matching the AI REDGIO type
        key_split = entity_key.split('/')
        asset_type = key_split[1] if len(key_split) > 1 else key_split[0]
        aiod_type = self.aiod_endpoint_from_type(asset_type)
        if not aiod_type:
            logger.warning(
                'Could not match the type %(asset_type)s with an AIoD endpoint',
                {
                    'asset_type': asset_type
                }
            )
            return entity

        # Upload to AIoD
        success, content, reasons = self._aiod.add_asset(aiod_type, entity)
        if success:
            entity['identifier'] = content['identifier']
        else:
            logger.info(
                'Could not upload asset %(asset_id)s as AIoD type %(aiod_type)s',
                {
                    'asset_id': entity['platform_resource_identifier'] if 'platform_resource_type' in entity else 'None',
                    'aiod_type': aiod_type,
                }
            )
            try:
                # Check if the reason for failure is because the asset already exists with another identifier on AIoD
                details = filter(
                    lambda d: isinstance(d, str) and d.startswith(
                        'There already exists'),
                    reasons
                )
                first_id = next(details, None)
                if first_id:
                    marker = 'identifier='
                    pos = first_id.find(marker)
                    if pos != -1:
                        first_id = first_id[pos+len(marker):]
                        i = next(
                            filter(
                                lambda c: not c[1].isdigit(),
                                enumerate(first_id)
                            ),
                            (len(first_id), 'a')
                        )[0]
                        first_id = first_id[:i]
                        first_id = int(first_id)
                        logger.info(
                            'Asset %(asset_id)s already uploaded with identifier %(asset_identifier)d, trying to solve conflict...',
                            {
                                'asset_id': entity['platform_resource_identifier'] if 'platform_resource_type' in entity else 'None',
                                'asset_identifier': first_id
                            }
                        )

                        # Retrieve the asset already on the AIoD platform
                        success, asset, _ = self._aiod.get_asset(
                            aiod_type, first_id)
                        if success:
                            # Merge the created asset with the one already on the platform and update it
                            merged = self.merge(entity, asset)
                            success, _, _ = self._aiod.update_asset(
                                aiod_type, merged)
                            if success:
                                entity['identifier'] = first_id
                        else:
                            logger.warning(
                                'Could not PUT asset %(asset_id)s with identifier %(asset_identifier)d',
                                {
                                    'asset_id': entity['platform_resource_identifier'] if 'platform_resource_type' in entity else 'None',
                                    'asset_identifier': first_id
                                }
                            )
                else:
                    for d in reasons:
                        logger.info(
                            'Asset %(asset_id)s: %(upload_error)s',
                            {
                                'asset_id': entity['platform_resource_identifier'] if 'platform_resource_type' in entity else 'None',
                                'upload_error': d
                            }
                        )

            # except Exception as ex:
            #     logger.warning(
            #         'Error with asset %(asset_id)s: %(error_message)s',
            #         {
            #             'asset_id': entity['platform_resource_identifier'] if 'platform_resource_type' in entity else 'None',
            #             'error_message': repr(ex)
            #         }
            #     )
            except Exception as ex:
                # Capture the traceback
                tb_str = traceback.format_exc()
                logger.warning(
                    'Error with asset %(asset_id)s: %(error_message)s\nTraceback: %(traceback_info)s',
                    {
                        'asset_id': entity['platform_resource_identifier'] if 'platform_resource_type' in entity else 'None',
                        'error_message': repr(ex),
                        'traceback_info': tb_str
                    }
                )
        return entity

    def upload(self, created: dict, entity_key: str) -> dict:
        if not '.visited' in created:
            created['.visited'] = set()
        if not '.failed' in created:
            created['.failed'] = {}
        created['.failed'][entity_key] = set()

        current_entity = created[entity_key if entity_key.startswith(
            '$') else f'{entity_key}']
        if entity_key in created['.visited']:
            return current_entity
        created['.visited'].add(entity_key)

        # Before uploading the current asset, solve each of its references
        if '.reference' in current_entity:
            for location, subentity_key in list(current_entity['.reference'].items()):
                if subentity_key in created['.visited']:
                    continue
                self.upload(created, subentity_key)
                if 'identifier' in created[subentity_key]:
                    new = created[subentity_key]['identifier']
                    current = current_entity
                    for step in location.split('/'):
                        match current:
                            case dict():
                                if step in current:
                                    current = current[step]
                                else:
                                    current[step] = new
                            case list():
                                step = int(step)
                                if len(current) >= step:
                                    current.append(new)
                                else:
                                    current[step] = new
                    else:
                        current_entity['.reference'].pop(location, None)
                else:
                    created['.failed'][entity_key].add(location)
                    break

        if not created['.failed'][entity_key]:
            # Only upload the current asset if all its references are resolved
            created['.failed'].pop(entity_key, None)
            self.post_and_put(entity_key, current_entity)
        return current_entity

    def convert_asset(self, asset: dict, asset_type: str) -> str:

        # Translate a JSON asset into AIoD format
        converter = next(
            filter(
                lambda x: x.can_handle(asset_type),
                self._platform_converters.values()
            ),
            None
        )
        if not converter:
            logger.warning(
                'Could not find a converter for type %(asset_type)',
                {
                    'asset_type': asset_type,
                }
            )
            return ''
        asset_id = converter.get_asset_id(asset)
        created = converter.translate(asset, translator_type=asset_type)
        if not created:
            logger.warning(
                'Failed to translate asset %(asset_id)s',
                {
                    'asset_id': asset_id
                }
            )
            return ''

        logger.debug(
            'Successfully translated asset %(asset_id)s',
            {
                'asset_id': asset_id
            }
        )

        # TODO: Validate AIoD entity

        # Upload all the created AIoD assets
        uploaded = self.upload(created, f'/{asset_type}')
        if not 'identifier' in uploaded:
            logger.warning(
                'Failed to upload asset %(asset_id)s',
                {
                    'asset_id': asset_id
                }
            )

            # TODO: Delete from AIoD all related entities if this failed (what if other assets reference one of these related?)
            return ''

        logger.info(
            'Successfully uploaded asset %(asset_id)s with id %(asset_identifier)d',
            {
                'asset_id': asset_id,
                'asset_identifier': uploaded['identifier']
            }
        )

        return uploaded['identifier']

    def delete_asset(self, asset_id: str, asset_type: str) -> bool:
        success, asset, reasons = self._aiod.get_asset_from_platform(
            self.platform.name, asset_type, asset_id)
        if not success:
            logger.warning(
                'Could not find asset %(asset_id)d by platform "%(platform_name)s on AIoD',
                {
                    'asset_id': asset_id,
                    'platform_name': self.platform.name
                }
            )
            for r in reasons:
                logger.debug(r)
            return False
        identifier = asset['identifier']
        success, _, reasons = self._aiod.delete_asset(identifier, asset_type)
        if not success:
            logger.warning(
                'Could not delete asset %(asset_id)d with identifier %(identifier) from AIoD',
                {
                    'asset_id': asset_id,
                    'identifier': identifier
                }
            )
            for r in reasons:
                logger.debug(r)

        return success

    def check_aiod_login(self, access_token: str = '') -> bool:
        if not self._aiod.is_logged_in:
            logger.debug('User not logged in to AIoD, logging in...')
            if not self._aiod.login(access_token=access_token):
                logger.warning('Could not login')
                return False
            if not self._aiod.is_logged_in:
                logger.warning('Could not login')
                return False
            logger.debug('Logged in to AIoD')
        return True

    def convert_all(self, platform_names: list[str] = []) -> None:
        platforms = list()
        if platform_names:
            platforms = [self._platform_converters[p]
                         for p in platform_names if p in self._platform_converters]
        else:
            platforms = self._platform_converters.values()

        for p in platforms:
            success = list()
            failed = list()
            assets = p.translate_all()
            for asset, type in assets:
                uploaded = self.upload(asset, type)
                if not 'identifier' in uploaded:
                    logger.warning(
                        'Failed to upload asset %(asset_id)s',
                        {
                            'asset_id': asset[f'/{type}']['platform_resource_identifier'],
                        }
                    )
                    failed.append(
                        asset[f'/{type}']['platform_resource_identifier'])
                else:
                    logger.info(
                        'Successfully uploaded asset %(asset_id)s with id %(asset_identifier)d',
                        {
                            'asset_id': asset[f'/{type}']['platform_resource_identifier'],
                            'asset_identifier': uploaded['identifier']
                        }
                    )
                    success.append(asset[f'/{type}']
                                   ['platform_resource_identifier'])
