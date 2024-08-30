import json
import logging
from aiod.aiod import AIoD
from airedgio.airedgio import AIRedgio
from bridge.bridge import Bridge
from datetime import datetime
import argparse

# TODO: Improve logging level throughout all the files

CONFIGS = './check_publish'

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            f"./memory/debug_{datetime.now():%Y_%m_%d_%H_%M_%S}.log"
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logging.getLogger(__name__).setLevel(logging.DEBUG)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


def init_argparse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--airedgio_endpoint',
        action='store',
        required=True,
        help='The API endpoint of the AIREDGIO portal'
    )

    parser.add_argument(
        '--aiod_url',
        action='store',
        required=True,
        help='The base URL of the AIoD API server'
    )
    parser.add_argument(
        '--keycloak_url',
        action='store',
        required=True,
        help='The URL of the authentication keycloak instance'
    )
    parser.add_argument(
        '--keycloak_realm',
        action='store',
        required=True,
        help='The keycloak realm of this bridge'
    )

    parser.add_argument(
        '--client_id',
        action='store',
        required=True,
        help='The keycloak client ID of this bridge'
    )
    parser.add_argument(
        '--client_secret',
        action='store',
        required=True,
        help='The keycloak client ID of this bridge'
    )

    return parser.parse_args()

def main() -> None:
    args = init_argparse()

    bridge_configuration_path = f'{CONFIGS}/configuration_folder'
    # memory_filepath = f'./memory/memory.json'
    memory_filepath = f'sqlite:./memory/memory.sqlite3'

    # Read the access_token if it exists
    access_token: str = ''
    try:
        with open(f'{CONFIGS}/access_token.json', 'r') as fin:
            f = json.load(fin)
            access_token = f.get('access_token', '')
    except:
        pass

    # Configure the AIoD connector
    aiod = AIoD(
        aiod_baseurl=args.aiod_url,
        keycloak_client_id=args.client_id,
        keycloak_client_secret_key=args.client_secret,
        keycloak_realm_name=args.keycloak_realm,
        keycloak_server_url=args.keycloak_url
    )
    logger.info("Configured AIoD connector")

    # Configure the bridge with the AIoD connector
    bridge = Bridge(bridge_configuration_path, aiod)
    logger.info("Configured bridge")

    logger.info("Testing AIoD login...")
    if not bridge.check_aiod_login(access_token):
        logger.error("AIoD login failed")
        exit(1)
    logger.info("Successfully logged in to AIoD")

    logger.info("Testing the platform on AIoD...")
    if not bridge.check_platform():
        logger.error("Failed to test the platform on AIoD")
        exit(1)
    logger.info("Successfully tested the platform on AIoD")

    # Configure the AI REDGIO connector
    airedgio = AIRedgio(
        api_endpoint=args.airedgio_endpoint,
        bridge=bridge,
        memory_filepath=memory_filepath
    )
    logger.info("Configured AI REDGIO")

    with open(f'{CONFIGS}/services.json', 'r') as fin:
        stored_services = json.load(fin)
    with open(f'{CONFIGS}/translations.json', 'r') as fin:
        translation_checks = json.load(fin)

    translation_checks = {
        c['platform_resource_identifier']: c for c in translation_checks}
    services = {s['_id']: {
        'original_local': s,
        'translation_check': translation_checks.get(s['_id'], dict())
    } for s in stored_services}
    # Check if the download retrieves the same items as we stored locally
    # TODO: Restore this. Skipping for now as the AIREDGIO dev instance seems to be down
    # for _id in services.keys():
    #     asset = airedgio.get_by_id(_id)
    #     if asset:
    #         services[_id]['original_remote'] = asset
    # equals = map(lambda v: v['original_remote'] ==
    #              v['original_local'], services.values())
    # if not all(equals):
    #     logger.warning("Downloaded assets do not match stored files")
    #     exit(1)

    # Check if the translation is correct by translating AI REDGIO assets and comparing the results with stored ones
    for _id in services.keys():
        services[_id]['translation'] = bridge.translate(
            services[_id]['original_local'],
            'as_a_service')['/as_a_service']

    equals = map(lambda v: v['translation_check'] ==
                 v['translation'], services.values())
    if not all(equals):
        logger.warning("Translations do not match stored files")
        exit(1)

    
    # Check if upload works correctly
    # Convert each asset
    failed = list()
    success = list()
    for asset in stored_services:
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
        if not bridge.convert_asset(asset, asset_type):
            failed.append(asset['_id'])
            continue

        success.append(asset['_id'])
        logger.debug(
            'Successfully converted asset %(asset_id)s',
            {
                'asset_id': asset['_id']
            }
        )
    if failed:
        logger.warning("Failed to upload some assets")
        for asset_id in failed:
            logger.debug(
                'Failed to upload asset %(asset_id)s',
                {
                    'asset_id': asset_id
                }
            )
        exit(1)


    logger.info("All checks passed")


if __name__ == '__main__':
    main()
