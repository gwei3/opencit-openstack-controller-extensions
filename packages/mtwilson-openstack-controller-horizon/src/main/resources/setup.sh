#!/bin/sh

# mtwilson comprehensive compute node install script
# Outline:
# 1. source the "functions.sh" file:  mtwilson-linux-util-3.0-SNAPSHOT.sh
# 2. load existing environment configuration
# 3. look for ~/mtwilson-openstack.env and source it if it's there
# 4. enforce root user installation
# 5. install prerequisites
# 6. install Mtwilson Trust Agent and Measurement Agent
# 7. Detect if virtualization is available
# 8. Install virtualization components
#    8a. install Mtwilson VRTM
#    8b. install Mtwilson Policy Agent
#    8c. install Mtwilson OpenStack compute node extensions

#####

DEFAULT_DEPLOYMENT_TYPE="vm"

# functions script (mtwilson-linux-util-3.0-SNAPSHOT.sh) is required
# we use the following functions:
# java_detect java_ready_report 
# echo_failure echo_warning
# register_startup_script
UTIL_SCRIPT_FILE=$(ls -1 mtwilson-linux-util-*.sh | head -n 1)
if [ -n "$UTIL_SCRIPT_FILE" ] && [ -f "$UTIL_SCRIPT_FILE" ]; then
  . $UTIL_SCRIPT_FILE
fi

# load installer environment file, if present
if [ -f ~/mtwilson-openstack.env ]; then
  echo "Loading environment variables from $(cd ~ && pwd)/mtwilson-openstack.env"
  . ~/mtwilson-openstack.env
  env_file_exports=$(cat ~/mtwilson-openstack.env | grep -E '^[A-Z0-9_]+\s*=' | cut -d = -f 1)
  if [ -n "$env_file_exports" ]; then eval export $env_file_exports; fi
else
  echo "No environment file"
fi

# enforce root user installation
if [ "$(whoami)" != "root" ]; then
  echo_failure "Running as $(whoami); must install as root"
  exit -1
fi

# install prerequisites
MTWILSON_OPENSTACK_YUM_PACKAGES="zip unzip"
MTWILSON_OPENSTACK_APT_PACKAGES="zip unzip"
MTWILSON_OPENSTACK_YAST_PACKAGES="zip unzip"
MTWILSON_OPENSTACK_ZYPPER_PACKAGES="zip unzip"
auto_install "Installer requirements" "MTWILSON_OPENSTACK"
if [ $? -ne 0 ]; then echo_failure "Failed to install prerequisites through package installer"; exit -1; fi

### INSTALL MTWILSON OPENSTCK CONTROLLER
echo "Installing mtwilson extensions controller..."
CONTROLLER_PACKAGE=`ls -1 mtwilson-openstack-controller-*.bin 2>/dev/null | tail -n 1`
if [ -z "$CONTROLLER_PACKAGE" ]; then
  echo_failure "Failed to find mtwilson openstack controller installer package"
  exit -1
fi
./$CONTROLLER_PACKAGE
if [ $? -ne 0 ]; then echo_failure "Failed to install mtwilson openstack controller"; exit -1; fi


### INSTALL MTWILSON OPENSTACK HORIZON
echo "Installing mtwilson openstack horizon..."
HORIZON_PACKAGE=`ls -1 mtwilson-openstack-horizon-*.bin 2>/dev/null | tail -n 1`
if [ -z "$HORIZON_PACKAGE" ]; then
  echo_failure "Failed to find mtwilson openstack horizon installer package"
  exit -1
fi
./$HORIZON_PACKAGE
if [ $? -ne 0 ]; then echo_failure "Failed to install mtwilson openstack horizon"; exit -1; fi



echo_success "Openstack Controller Horizon Combined installer installation Complete"
