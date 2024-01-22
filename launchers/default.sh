#!/bin/bash

source /environment.sh

# initialize launch file
dt-launchfile-init

# YOUR CODE BELOW THIS LINE
# ----------------------------------------------------------------------------


# NOTE: Use the variable DT_PROJECT_PATH to know the absolute path to your code
# NOTE: Use `dt-exec COMMAND` to run the main process (blocking process)

# launching app
set +e
python3 -m upgrade_helper.main "$@"
exit $?

# ----------------------------------------------------------------------------
# YOUR CODE ABOVE THIS LINE

