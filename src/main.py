import json
import logging
from aiod.aiod import AIoD
from airedgio.airedgio import AIRedgio
from bridge.bridge import Bridge
from datetime import datetime

# TODO: Improve logging level throughout all the files

CONFIGS = './configurations'

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


def main() -> None:
    aiod_configuration_path = f'{CONFIGS}/aiod_configuration.json'
    airedgio_configuration_path = f'{CONFIGS}/airedgio_configuration.json'
    bridge_configuration_path = f'{CONFIGS}/configuration_folder'
    # memory_filepath = f'./memory/memory.json'
    memory_filepath = f'sqlite:memory/memory.sqlite3'

    # Configure the AIoD connector
    with open(aiod_configuration_path, 'r') as fin:
        aiod_configuration = json.load(fin)
    aiod = AIoD(**aiod_configuration)

    # Configure the bridge with the AIoD connector
    bridge = Bridge(bridge_configuration_path, aiod)

    # Configure the AI REDGIO connector
    with open(airedgio_configuration_path, 'r') as fin:
        airedgio_configuration = json.load(fin)
    airedgio = AIRedgio(
        **airedgio_configuration,
        bridge=bridge,
        memory_filepath=memory_filepath
    )

    # Start converting all the assets
    airedgio.convert_all()


if __name__ == '__main__':
    main()
