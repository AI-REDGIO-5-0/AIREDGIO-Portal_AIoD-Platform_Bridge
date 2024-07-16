#!/bin/bash
docker run -v $(pwd)/configurations:/home/appuser/configurations:ro -v $(pwd)/memory:/home/appuser/memory --network=host bridge