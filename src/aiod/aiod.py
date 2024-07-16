from collections import namedtuple
from typing import Callable
import requests
from keycloak import KeycloakOpenID

Result = namedtuple('Result', ['success', 'value', 'reason'])


class AIoD:
    _session: requests.Session | None = None
    _headers = {
        'Content-Type': 'application/json',
    }

    _aiod_baseurl: str = ''
    _aiod_endpoint_template: str = ''
    _aiod_endpoint_platform_template: str = ''

    _keycloak_server_url: str = ''
    _keycloak_client_id: str = ''
    _keycloak_realm_name: str = ''
    _keycloak_client_secret_key: str = ''
    _keycloak_configuration: KeycloakOpenID | None = None

    def __init__(
        self,
        aiod_baseurl: str,
        keycloak_server_url: str = '',
        keycloak_client_id: str = '',
        keycloak_realm_name: str = '',
        keycloak_client_secret_key: str = ''
    ):
        self._aiod_baseurl = aiod_baseurl
        self._aiod_endpoint_template = self._aiod_baseurl + \
            '/{asset_type}/v1/{identifier}'
        self._aiod_endpoint_platform_template = self._aiod_baseurl + \
            '/platforms/{platform}/{asset_type}/v1/{platform_resource_identifier}'

        self._keycloak_server_url = keycloak_server_url
        self._keycloak_client_id = keycloak_client_id
        self._keycloak_realm_name = keycloak_realm_name
        self._keycloak_client_secret_key = keycloak_client_secret_key

    @property
    def session(self) -> requests.Session:
        if not self._session:
            self._session = requests.session()
            self._session.headers.update(self._headers)
        return self._session

    @property
    def keycloak_configuration(self) -> KeycloakOpenID:
        # TODO: Maybe a property is not the best thing, need to handle possible errors
        if not self._keycloak_configuration:
            self._keycloak_configuration = KeycloakOpenID(
                server_url=self._keycloak_server_url,
                client_id=self._keycloak_client_id,
                realm_name=self._keycloak_realm_name,
                client_secret_key=self._keycloak_client_secret_key
            )

        return self._keycloak_configuration

    @property
    def token(self) -> dict:
        return self.keycloak_configuration.token(grant_type='client_credentials')

    def login(self) -> None:
        self._headers['Authorization'] = f'Bearer {self.token["access_token"]}'
        self.session.headers.update(self._headers)

    def _format_details(self, response_content: dict) -> list[str]:
        details = []
        if response_content:
            if 'detail' in response_content:
                if isinstance(response_content['detail'], str):
                    details.append(response_content['detail'])
                elif isinstance(response_content['detail'], list):
                    for d in response_content['detail']:
                        if 'loc' in d:
                            details.append(
                                f"{'/'.join(map(str, d['loc']))} - {d['msg']}"
                            )
                        else:
                            details.append(d)
        return details

    def _handle_response(self, response: requests.Response) -> Result:
        try:
            response.raise_for_status()
            content = response.json()
            details = self._format_details(content)
            result = Result(
                response.status_code == requests.codes.ok,
                content,
                details
            )
        except requests.Timeout:
            result = Result(False, None, None)
        except requests.HTTPError as http_error:
            details = self._format_details(http_error.response.json())
            result = Result(
                False,
                None,
                details if details else list(http_error.args)
            )
        finally:
            return result

    @property
    def get_logged_user(self) -> dict:
        response = self.session.get(f'{self._aiod_baseurl}/authorization_test')
        success, user, _ = self._handle_response(response)
        return user if success else dict()

    @property
    def is_logged_in(self) -> bool:
        return bool(self.get_logged_user)

    @property
    def count(self) -> Result:
        response = self.session.get(
            self._aiod_endpoint_template.format(
                asset_type='counts',
                identifier=''
            )
        )
        return self._handle_response(response)

    def get_asset(self, asset_type: str, id: int) -> Result:
        response = self.session.get(
            self._aiod_endpoint_template.format(
                asset_type=asset_type,
                identifier=id
            )
        )
        return self._handle_response(response)

    def add_asset(self, asset_type: str, asset: dict) -> Result:
        response = self.session.post(
            self._aiod_endpoint_template.format(
                asset_type=asset_type,
                identifier=''
            ),
            json=asset
        )
        return self._handle_response(response)

    def get_asset_from_platform(
        self,
        platform_name: str,
        asset_type: str,
        platform_resource_identifier: str
    ) -> Result:
        response = self.session.get(
            self._aiod_endpoint_platform_template.format(
                platform_name=platform_name,
                asset_type=asset_type,
                platform_resource_identifier=platform_resource_identifier
            )
        )
        return self._handle_response(response)

    def update_asset(self, asset_type, asset: dict) -> Result:
        response = self.session.put(
            self._aiod_endpoint_template.format(
                asset_type=asset_type,
                identifier=asset['identifier']
            ),
            json=asset
        )
        return self._handle_response(response)

    def delete_asset(self, id: int, asset_type: str) -> Result:
        response = self.session.delete(
            self._aiod_endpoint_template.format(
                asset_type=asset_type,
                identifier=id
            )
        )
        return self._handle_response(response)

    def get_platform(self, id: int) -> dict:
        asset_type = 'platforms'
        success, result, _ = self.get_asset(asset_type, id)
        return result if success else {}

    def add_platform(self, platform: dict) -> int | None:
        asset_type = 'platforms'
        success, result, _ = self.add_asset(asset_type, platform)
        return result['identifier'] if success else None

    def update_platform(self, platform: dict) -> int | None:
        asset_type = 'platforms'
        success, result, _ = self.update_asset(asset_type, platform)
        return result if success else None

    def get_service(self, id: int) -> dict:
        asset_type = 'services'
        success, result, _ = self.get_asset(asset_type, id)
        return result if success else {}

    def add_service(self, service: dict) -> int | None:
        asset_type = 'services'
        success, result, _ = self.add_asset(asset_type, service)
        return result['identifier'] if success else None

    def update_service(self, service: dict) -> int | None:
        asset_type = 'services'
        success, result, _ = self.update_asset(asset_type, service)
        return result['identifier'] if success else None
