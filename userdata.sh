

userdata_script="""#!/bin/bash
  # DONT EXECUTE !
  #
  # This script will be executed only once on instance first launch
  # do here:
  #
  # 1. local config changes
  # 2. local services startup (may not be necessary)
  # 3. change DNS A records using route53 (mat be done externally also), if local need aws credentials
  # 4. change prompt (lms/root)
  #
  LOG=/home/lms/user-data.output
  echo "$(date) - starting"         >> ${LOG}
  echo "executing userdata.sh"      >> ${LOG}
  echo "sourcing credentials"       >> ${LOG}
  source /home/lms/sqs-config
  python3 publish-metadata.py
  echo "$(date) - done."            >> ${LOG}
  reboot
"""
