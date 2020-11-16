#!/bin/bash
echo ""
echo "instance table: (select * from instance)"
echo "--------------- START ----------------------"
sqlite3 spot.db 'select * from instance'
echo "---------------  END  ----------------------"
echo ""
echo "message table: (select * from message)"
echo "--------------- START ----------------------"
sqlite3 spot.db 'select * from message'
echo "---------------  END  ----------------------"
echo ""
