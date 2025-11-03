from contextlib import asynccontextmanager
from datetime import datetime
import json
import httpx
from fastapi import FastAPI, HTTPException, Security, status
from fastapi.security import APIKeyHeader
import uvicorn
from aiod.aiod import AIoD
from airedgio.airedgio import AIRedgio
from bridge.bridge import Bridge
from config import settings
import logging

bridge: Bridge
access_token: str = ''

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
logging.getLogger("httpcore").setLevel(logging.WARNING)

api_key_header = APIKeyHeader(name=settings.authentication_header_name)


def get_api_key(api_key: str = Security(api_key_header)):
    if api_key != settings.api_key:
        logger.info('Received API key was not the correct one')
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key"
        )
    else:
        logger.debug('Received correct API key')
        return api_key


def setup() -> None:
    global bridge, access_token
    bridge_configuration_path = f'{settings.configurations_folder}/configuration_folder'
    # Read the access_token if it exists
    try:
        with open(f'{settings.configurations_folder}/access_token.json', 'r') as fin:
            f = json.load(fin)
            access_token = f.get('access_token', '')
    except:
        pass

    # Configure the AIoD connector
    aiod = AIoD(
        aiod_baseurl=settings.aiod_url,
        keycloak_client_id=settings.client_id,
        keycloak_client_secret_key=settings.client_secret,
        keycloak_realm_name=settings.keycloak_realm,
        keycloak_server_url=settings.keycloak_url
    )
    logger.info("Configured AIoD connector")

    # Configure the AI REDGIO connector
    airedgio = AIRedgio(
        api_endpoint=settings.airedgio_endpoint,
        memory_filepath=settings.airedgio_memory_filepath,
        translators_folder=settings.airedgio_translators_folder
    )
    logger.info("Configured AI REDGIO")

    # Configure the bridge with the AIoD connector
    bridge = Bridge(bridge_configuration_path, aiod, [airedgio])
    logger.info("Configured bridge")

    logger.info("Testing AIoD login...")
    if not bridge.check_aiod_login(access_token):
        logger.error("AIoD login failed")
        raise Exception("AIoD login failed")
    logger.info("Successfully logged in to AIoD")

    logger.info("Testing the platform on AIoD...")
    if not bridge.check_platform():
        logger.warning("Failed to test the platform on AIoD")
    logger.info("Successfully tested the platform on AIoD")

    bridge.convert_all()


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup()
    yield

app = FastAPI(lifespan=lifespan)


@app.get('/check', status_code=status.HTTP_200_OK)
async def check(
    _: str = Security(get_api_key),
):
    logger.debug('Received check request')


@app.post('/create/{asset_type}', status_code=status.HTTP_200_OK)
async def create(
    asset_type: str,
    asset: dict,
    _: str = Security(get_api_key),
) -> str:
    logger.debug(
        'Received asset: %(asset)s',
        {
            'asset': asset,
        }
    )
    logger.info(
        'Received asset of type: %(asset_type)s',
        {
            'asset_type': asset_type,
        }
    )

    logger.info("Checking AIoD login...")
    if not bridge.check_aiod_login(access_token):
        logger.error("AIoD login failed")
        raise Exception("AIoD login failed")
    logger.info("Successfully logged in to AIoD")

    logger.info("Checking the platform on AIoD...")
    if not bridge.check_platform():
        logger.warning("Failed to check the platform on AIoD")
        # raise HTTPException(
        #     status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        #     detail="Failed to check the platform on AIoD"
        # )
    logger.info("Successfully checked the platform on AIoD")

    aiod_identifier = bridge.convert_asset(asset, asset_type)
    if not aiod_identifier:
        logger.warning(
            'Failed to converted asset %(asset_name)s of type %(asset_type)s',
            {
                'asset_name': asset.get('name', ''),
                'asset_type': asset_type,
            }
        )
        raise HTTPException(status_code=httpx.codes.BAD_GATEWAY)
    logger.info(
        'Successfully converted asset %(asset_name)s of type %(asset_type)s (AIoD ID: %(aiod_identifier)s)',
        {
            'asset_name': asset.get('name', ''),
            'asset_type': asset_type,
            'aiod_identifier': aiod_identifier,
        }
    )
    return str(aiod_identifier)


@app.post('/convert-all', status_code=status.HTTP_200_OK)
async def convert_all(
    platform_names: list[str],
    _: str = Security(get_api_key),
):
    bridge.convert_all(platform_names)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
