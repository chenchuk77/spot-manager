#!/bin/bash

while true; do
  sqlite3 spot.db 'select * from instance' >> db-trace.log
  sleep 1s
done
