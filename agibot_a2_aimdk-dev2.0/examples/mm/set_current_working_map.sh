#!/bin/bash

curl -X POST 'http://192.168.100.110:50807/rpc/aimdk.protocol.MappingService/SetCurrentWorkingMap' \
  -H 'Content-Type: application/json' \
  -d '{
   "header": {
      "timestamp": {
        "seconds": "0",
        "nanos": 0,
        "ms_since_epoch": "1744598548952"
      }
    },
    "command":"MappingCommand_SET_CURRENT_WORKING_MAP",
    "map_id": 123456,
}'