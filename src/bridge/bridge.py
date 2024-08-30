from itertools import islice
import json
import os
from aiod.aiod import AIoD
from bridge.platform import Platform
from logging import getLogger

logger = getLogger(__name__)


class Bridge:
    _aiod: AIoD
    _configuration_folder: str
    _timestamp_format = '%Y-%m-%dT%H:%M:%S.%fZ'
    _type_to_aiod_endpoint: dict
    _platform: Platform

    def __init__(
        self,
        configuration_folder: str,
        aiod: AIoD,
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

    @property
    def platform(self) -> Platform:
        return self._platform

    def aiod_endpoint_from_type(self, redgio_name: str) -> str:
        return self._type_to_aiod_endpoint.get(redgio_name, '')

    def check_platform(self) -> bool:
        return self.platform.check_platform()

    def _translate(
        self,
        instance: dict,
        created: dict,
        translator: dict = {},
        translator_type: str = '',
        index: int | None = None
    ) -> dict:

        # Either use the provided translator JSON or open a translator file based on the type
        if not translator:
            filepath = f'{self._configuration_folder}/translators/{translator_type}.json'
            if not os.path.isfile(filepath):
                logger.warning(
                    'Translation file "%(translator_filepath)s" not found'
                )
                return dict()
            with open(filepath, 'r') as fin:
                translator = json.load(fin)

        # 'translation' is the resulting AIoD JSON asset
        translation: dict[str, int | str | dict | list] = {}
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
        asset_type = entity_key.split('/')[1]
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
                'Could not upload asset %(asset_id)s',
                {
                    'asset_id': entity['platform_resource_identifier']
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
                        for i, char in enumerate(first_id):
                            if not char.isdigit():
                                break
                        first_id = first_id[:i]
                        first_id = int(first_id)
                        logger.info(
                            'Asset %(asset_id)s already uploaded with identifier %(asset_identifier)d, trying to solve conflict...',
                            {
                                'asset_id': entity['platform_resource_identifier'],
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
                                    'asset_id': entity['platform_resource_identifier'],
                                    'asset_identifier': first_id
                                }
                            )
                else:
                    for d in reasons:
                        logger.info(
                            'Asset %(asset_id)s: %(upload_error)s',
                            {
                                'asset_id': entity['platform_resource_identifier'],
                                'upload_error': d
                            }
                        )

            except Exception as ex:
                logger.warning(
                    'Error with asset %(asset_id)s: %(error_message)s',
                    {
                        'asset_id': entity['platform_resource_identifier'],
                        'error_message': repr(ex)
                    }
                )

        return entity

    def upload(self, created: dict, entity_key: str) -> dict:
        if not '.visited' in created:
            created['.visited'] = set()
        if not '.failed' in created:
            created['.failed'] = {}
        created['.failed'][entity_key] = set()

        current_entity = created[entity_key]

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

    def convert_asset(self, asset: dict, asset_type: str) -> bool:

        # Translate a JSON asset into AIoD format
        created = self.translate(asset, translator_type=asset_type)
        if not created:
            logger.warning(
                'Failed to translate asset %(asset_id)s',
                {
                    'asset_id': asset['_id']
                }
            )
            return False

        logger.debug(
            'Successfully translated asset %(asset_id)s',
            {
                'asset_id': asset['_id']
            }
        )

        # TODO: Validate AIoD entity

        # Upload all the created AIoD assets
        uploaded = self.upload(created, f'/{asset_type}')
        if not 'identifier' in uploaded:
            logger.warning(
                'Failed to upload asset %(asset_id)s',
                {
                    'asset_id': asset['_id']
                }
            )

            # TODO: Delete from AIoD all related entities if this failed (what if other assets reference one of these related?)
            return False

        logger.info(
            'Successfully uploaded asset %(asset_id)s with id %(asset_identifier)d',
            {
                'asset_id': asset['_id'],
                'asset_identifier': uploaded['identifier']
            }
        )

        return True

    def delete_asset(self, asset_id: str, asset_type: str) -> bool:
        success, asset, reasons = self._aiod.get_asset_from_platform(
            self.platform.name, asset_type, asset_id)
        if not success:
            logger.warn(
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
            logger.warn(
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
                logger.warn('Could not login')
                return False
            if not self._aiod.is_logged_in:
                logger.warn('Could not login')
                return False
            logger.debug('Logged in to AIoD')
        return True
