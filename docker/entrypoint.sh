#!/bin/sh

# TimeZone validation
if [ -z "${TZ}" ] ; 
then 
    echo "Please set TZ environment variable with -e TZ=(timezone)"
    echo ""
else
    echo ${TZ} > /etc/timezone
    echo ""
    echo "Timezone is $(cat /etc/timezone)"
fi

exec "$@"
