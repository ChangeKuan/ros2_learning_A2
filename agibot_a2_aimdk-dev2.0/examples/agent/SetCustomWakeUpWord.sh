#!/bin/bash

curl --location --request POST \
  'http://127.0.0.1:59301/rpc/aimdk.protocol/AgentControlService/SetCustomWakeUpWord' \
  --header 'Content-Type: application/json' \
  --data-raw '{
    "keywords": [
      "你好你好"
    ]
  }'
