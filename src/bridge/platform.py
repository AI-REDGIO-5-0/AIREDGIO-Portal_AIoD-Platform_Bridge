import json
from aiod.aiod import AIoD
import logging

logger = logging.getLogger(__name__)


class Platform:
    _name: str
    _identifier: int
    _aiod: AIoD

    def __init__(self, aiod: AIoD, platform: dict = {}, name: str = '', identifier: int = 0) -> None:
        if not (bool(platform) or bool(name)):
            raise ValueError(
                'At least one of "platform" or "name" must have a value'
            )

        if identifier < 0:
            raise ValueError(
                'The identifier has to be positive integer number'
            )

        if platform:
            if 'name' not in platform:
                raise ValueError('Platform must have a name')

            self._name = platform['name']
            if 'identifier' in platform:
                self._identifier = platform['identifier']
            else:
                self._identifier = identifier

        else:
            self._name = name
            self._identifier = identifier

        self._aiod = aiod

    @property
    def name(self) -> str:
        return self._name

    @property
    def identifier(self) -> int:
        return self._identifier

    def to_dict(self) -> dict:
        res = dict()
        res['name'] = self.name
        if self.identifier:
            res['identifier'] = self.identifier
        return res

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def check_platform(self) -> bool:
        # TODO: Check if the platform already exists with same name but different ID
        # We don't really need to know the ID, the name will suffice when uploading assets
        logger.debug("Checking the platform on AIoD...")
        if self.identifier:
            platform = self._aiod.get_platform(self.identifier)
            if platform:
                if platform['name'] == self.name:
                    return True
                else:
                    platform_id = self._aiod.update_platform(self.to_dict())
                    return platform_id != None
        logger.info(
            'Registering platform with name %(platform_name)s on AIoD',
            {
                'platform_name': self.name
            }
        )
        platform_id = self._aiod.add_platform(self.to_dict())
        if platform_id != None:
            self._identifier = platform_id
            logger.debug(
                'Added platform %(platform_name)s with identifier %(platform_identifier)d',
                {
                    'platform_name': self.name,
                    'platform_identifier': self.identifier
                }
            )
            return True
        else:
            logger.debug(
                'Could not register platform %(platform_name)s to AIoD',
                {
                    'platform_name': self.name,
                }
            )
            return False
