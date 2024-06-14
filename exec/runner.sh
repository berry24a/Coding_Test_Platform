#!/bin/bash

while true; do
    RESPONSE=$(curl -s -X GET http://localhost:8001/new)
    ID=$(echo $RESPONSE | jq -r '.id')
    if [ "$ID" != "null" ]; then
        curl -s -X POST http://localhost:8001/execute -H "Content-Type: application/json" -d '{"id":'$ID'}'
    fi
    sleep 10
done
