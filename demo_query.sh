poll_platform() {
    PLATFORM_ID=8
    URL="http://localhost:8000/platforms/v1/${PLATFORM_ID}"
        
    while true; do
        echo -ne "\r\033[KPolling for platform with identifier ${PLATFORM_ID}: polling..."
        sleep 1

        # Send a GET request and capture both the response body and HTTP status code
        RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "${URL}" -H "accept: application/json")
        RESPONSE_BODY=$(echo "${RESPONSE}" | sed '$d')  # Get the response body

        # Get the HTTP response code
        HTTP_CODE=$(echo "${RESPONSE}" | tail -n1)

        # Check the HTTP response code
        if [ "${HTTP_CODE}" -eq 200 ]; then
            # If the platform is found, show the result
            echo -e "\r\033[KPlatform found:"
            echo "${RESPONSE_BODY}" | jq .
            break
        elif [ "${HTTP_CODE}" -eq 404 ]; then
            # If the platform is not found, read the error message from the body
            # echo "${RESPONSE_BODY}" | jq -r '.detail'
            echo -ne "\r\033[KPolling for platform with identifier ${PLATFORM_ID}: $(echo "${RESPONSE_BODY}" | jq -r '.detail')"
            sleep 1
        else
            # Handle unexpected response codes
            echo "Received unexpected status code: ${HTTP_CODE}"
            echo "Response body:"
            echo "${RESPONSE_BODY}"
            break
        fi
    done
}

poll_service_count() {
    URL="http://localhost:8000/counts/services/v1?detailed=false"
        
    echo "Polling service count... "

    while true; do

        # Send a GET request and capture both the response body and HTTP status code
        RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "${URL}" -H "accept: application/json")
        RESPONSE_BODY=$(echo "${RESPONSE}" | sed '$d')  # Get the response body

        # Get the HTTP response code
        HTTP_CODE=$(echo "${RESPONSE}" | tail -n1)

        # Check the HTTP response code
        if [ "${HTTP_CODE}" -eq 200 ]; then
            echo -ne "\r\033[KPolling service count... Service count: ${RESPONSE_BODY}"
            sleep 2
        elif [ "${HTTP_CODE}" -eq 404 ]; then
            # If the platform is not found, read the error message from the body
            echo -ne "\r\033[KPolling service count... $(echo "${RESPONSE_BODY}" | jq -r '.detail')"
            sleep 2
        else
            # Handle unexpected response codes
            echo "Received unexpected status code: ${HTTP_CODE}"
            echo "Response body:"
            echo "${RESPONSE_BODY}"
            break
        fi
    done
}

poll_platform
poll_service_count