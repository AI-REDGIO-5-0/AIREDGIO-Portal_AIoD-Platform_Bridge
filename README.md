# AIREDGIO-Portal_AIoD-Platform_Bridge
Bridge component to publish AI REDGIO assets on the AIoD metadata catalogue.

## General
The [bridge](./src/bridge/) will use the [aiod](./src/aiod/) module to communicate with AIoD, and expects its function to be used in a PUSH fashion: to create an asset the JSON representing such asset must be passed to the bridge, and similarly to delete an asset its identifier must be given to the bridge.  
The [airedgio](./src/airedgio/) module is responsible for the communication with the AI REDGIO portal: it retrieves assets from the AI REDGIO portal and pushes them to the bridge. 

### General steps
The [airedgio](./src/airedgio/) module is run periodically, and each time it saves the assets that failed to be converted and the last time it checked the AI REDGIO portal, so that the next time it will restart from there:
1. the module will retry to upload all the created assets that failed to upload the last time;
2. the module will retrieve from the AI REDGIO portal all the assets created after the last check, and try to upload them, taking note of those that fail;
3. the module will retry to upload all the modified assets that failed to upload the last time;
4. the bridge will retrieve from the AI REDGIO portal all the assets modified after the last check, and try to upload them, taking note of those that fail. 

### Validation
Schemas for both the AI REDGIO assets' JSON representation and the AIoD assets' JSON representation can be provided, in which case the bridge could validate the assets downloaded from AI REDGIO and their translated AIoD version (TODO). 

### Translation
The bridge will use JSON files with a special and specific syntax to translate one external JSON asset into one or more AIoD JSON asset.  
The brdige will try to map the external asset type to a "translator" file, which contains mappings from that asset's JSON keys to AIoD JSON keys.  
The translator files "describe" the desired JSON, providing for each key the desired value following this syntax:
- ```"key": "value"``` will generate, in the destination JSON, a key ```key``` with the literal value ```value```
- ```"key": { ... }```: the dictionary associated with the key ```key``` will be recursively translated
- ```"key": "$/path/to/key"```: in the generated JSON, the value associated with the key ```key``` will have the value found in the original JSON following the path denoted in ```/path/to/key```
- ```"key": "$ref/type_of_asset"``` will create a separate JSON that will need to be uploaded separately to AIoD and, once uploaded, its AIoD identifier will be used as a reference in the first generated asset. The separate JSON needs its own translator file
- ```"key": "$listref/type_of_asset/path/to/key"```: this will create a list in the generated JSON of objects as if using ```"$ref"``` on each of the elements in the list; the translator files for list elements can use ```i``` to access their index number in the list

### Configuration
Each module needs one or more configuration file to start

#### aiod
The configuration JSON for the AIoD module shall contain the following keys:
- `aiod_baseurl`: the URL of the AIoD node hosting the API endpoints;
- `keycloak_server_url`: the URL to the Keycloak instance providing IAM to the AIoD node;
- `keycloak_client_id`: the client ID to identify to Keycloak;
- `keycloak_realm_name`: the Keycloak realm to use;
- `keycloak_client_secret_key`: the client secret to gain authorization using the "client_credentials" grant type

#### bridge
This module expects a configuration folder holding multiple elements

#### airedgio
For contacting the AI REDGIO portal, only one configuration information is required: the `api_endpoint` key holds the URL hosting the AI REDGIO APIs to contact in order to retrieve the assets.  

## TODO
- [ ] Mapping files for other asset types
- [ ] Exponential backoff
- [X] Docker image
- [ ] cron job
- [X] Track deleted assets
- [ ] Generate a unique ```platform_resource_identifier``` for each craeted AIoD asset starting from the infos on the external asset
- [ ] Publish the docker image on a public registry
- [ ] Automate docker image creation using GitHub Actions