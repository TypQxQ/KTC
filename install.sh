#!/bin/bash

#
# The responsibility of this script is to setup the Python extensions
# and configure the update processes.

# Set this to terminate on error.
set -e

# Get the root path of the repo, aka, where this script is executing
KTAMV_REPO_DIR=$(realpath $(dirname "$0"))

# This is where Klipper is installed
KLIPPER_HOME="${HOME}/klipper"

# This is where the extension are downloaded to, a subdirectory of the repo.
EXTENSION_PATH="${KTAMV_REPO_DIR}/extension"

# This is where Moonraker is installed
MOONRAKER_HOME="${HOME}/moonraker"

# This is where Klipper config files are stored
KLIPPER_CONFIG_HOME="${HOME}/printer_data/config"

# This is where Klipper Python enviroment is stored
KLIPPER_ENV="${HOME}/klippy-env"

# This is where Klipper logs are stored
KLIPPER_LOGS_HOME="${HOME}/printer_data/logs"

# This is where Klipper config files were stored before the 0.10.0 release
OLD_KLIPPER_CONFIG_HOME="${HOME}/klipper_config"

# Path to the systemd directory
SYSTEMDDIR="/etc/systemd/system"

# Path to the moonraker asvc file where services are defined
MOONRAKER_ASVC=~/printer_data/moonraker.asvc

#
# Console Write Helpers
#
c_default=$(echo -en "\e[39m")
c_green=$(echo -en "\e[92m")
c_yellow=$(echo -en "\e[93m")
c_magenta=$(echo -en "\e[35m")
c_red=$(echo -en "\e[91m")
c_cyan=$(echo -en "\e[96m")

log_header()
{
    echo -e "${c_magenta}$1${c_default}"
}

log_important()
{
    echo -e "${c_yellow}$1${c_default}"
}

log_error()
{
    log_blank
    echo -e "${c_red}$1${c_default}"
    log_blank
}

log_info()
{
    echo -e "${c_green}$1${c_default}"
}

log_blank()
{
    echo ""
}

# 
# Logic to check if Klipper is installed
# 
check_klipper() {
    # Check if Klipper is installed
    log_header "Checking if Klipper is installed..."
    if [ "$(sudo systemctl list-units --full -all -t service --no-legend | grep -F "klipper.service")" ]; then
        log_important "${INFO}Klipper service found"
    else
        log_error "${ERROR}Klipper service not found! Please install Klipper first"
        exit -1
    fi
}

# 
# Logic to verify the home directories
# 
verify_home_dirs() {
    log_header "Verifying home directories..."
    log_blank
    if [ ! -d "${KLIPPER_HOME}" ]; then
        log_error "Klipper home directory (${KLIPPER_HOME}) not found. Use '-k <dir>' option to override"
        exit -1
    fi
    if [ ! -d "${KLIPPER_CONFIG_HOME}" ]; then
        if [ ! -d "${OLD_KLIPPER_CONFIG_HOME}" ]; then
            log_error "Klipper config directory (${KLIPPER_CONFIG_HOME} or ${OLD_KLIPPER_CONFIG_HOME}) not found. Use '-c <dir>' option to override"
            exit -1
        fi
        KLIPPER_CONFIG_HOME="${OLD_KLIPPER_CONFIG_HOME}"
    fi
    log_info "Klipper config directory (${KLIPPER_CONFIG_HOME}) found"

    if [ ! -d "${MOONRAKER_HOME}" ]; then
        log_error "Moonraker home directory (${MOONRAKER_HOME}) not found. Use '-m <dir>' option to override"
        exit -1
    fi    
}

restart_klipper()
{
    log_header "Restarting Klipper..."
    sudo systemctl restart klipper
}

restart_moonraker()
{
    log_header "Restarting Moonraker..."
    sudo systemctl restart moonraker
}

verify_ready()
{
    if [ "$EUID" -eq 0 ]; then
        log_error "This script must not run as root"
        exit -1
    fi
}

# 
# Logic to link the extension to Klipper
# 
link_extension()
{
    log_header "Linking extension files to Klipper..."
    log_blank

    for file in `cd ${EXTENSION_PATH}/ ; ls *.py`; do
        ln -sf "${EXTENSION_PATH}/${file}" "${KLIPPER_HOME}/klippy/extras/${file}"
    done
}

# 
# Logic to install the update manager to Moonraker
# 
install_update_manager() {
    log_header "Adding update manager to moonraker.conf"
    dest=${KLIPPER_CONFIG_HOME}/moonraker.conf
    if test -f $dest; then
        # Backup the original printer.cfg file
        next_dest="$(nextfilename "$dest")"
        log_info "Copying original moonraker.conf file to ${next_dest}"
        cp ${dest} ${next_dest}
        already_included=$(grep -c '\[update_manager ktc\]' ${dest} || true)
        if [ "${already_included}" -eq 0 ]; then
            echo "" >> "${dest}"    # Add a blank line
            echo "" >> "${dest}"    # Add a blank line
            echo -e "[update_manager ktc]]" >> "${dest}"    # Add the section header
            echo -e "type: git_repo" >> "${dest}"
            echo -e "path: ~/ktc" >> "${dest}"
            echo -e "origin: https://github.com/TypQxQ/ktc.git" >> "${dest}"
            echo -e "primary_branch: main" >> "${dest}"
            echo -e "install_script: install.sh" >> "${dest}"
            echo -e "managed_services: klipper" >> "${dest}"
        else
            log_error "[update_manager ktc] already exists in moonraker.conf - skipping installing it there"
        fi

    else
        log_error "moonraker.conf not found!"
    fi
}

# 
# Logic to install the configuration to Klipper
# 
install_klipper_config() {
    log_header "Adding configuration to printer.cfg"

    # Add configuration to printer.cfg if it doesn't exist
    dest=${KLIPPER_CONFIG_HOME}/printer.cfg
    if test -f $dest; then
        # Backup the original printer.cfg file
        next_dest="$(nextfilename "$dest")"
        log_info "Copying original printer.cfg file to ${next_dest}"
        cp ${dest} ${next_dest}

        # Add the configuration to printer.cfg
        # This example assumes that that both the server and the webcam stream are running on the same machine as Klipper
        already_included=$(grep -c '\[ktamv\]' ${dest} || true)
        if [ "${already_included}" -eq 0 ]; then
            echo "" >> "${dest}"    # Add a blank line
            echo "" >> "${dest}"    # Add a blank line
            echo -e "[ktamv]" >> "${dest}"    # Add the section header
            echo -e "nozzle_cam_url: http://localhost/webcam/snapshot?max_delay=0" >> "${dest}"   # Add the address of the webcam stream that will be accessed by the server
            echo -e "server_url: http://localhost:${PORT}" >> "${dest}"    # Add the address of the kTAMV server that will be accessed Klipper
            echo -e "move_speed: 1800" >> "${dest}"   # Add the speed at which the toolhead moves when aligning
            echo -e "send_frame_to_cloud: ${SEND_IMAGES}" >> "${dest}"   # If true, the images of the nozzle will be sent to the developer
            echo -e "detection_tolerance: 0" >> "${dest}"   # number of pixels to have as tolerance when detecting the nozzle.

            log_info "Added kTAMV configuration to printer.cfg"
            log_important "Please check the configuration in printer.cfg and adjust it as needed"
        else
            log_error "[ktamv] already exists in printer.cfg - skipping adding it there"
        fi
    else
        log_error "File printer.cfg file not found! Cannot add kTAMV configuration. Do it manually."
    fi

    # Add the inclusion of macros.cfg to printer.cfg if it doesn't exist
    already_included=$(grep -c '\[include ktamv_macros.cfg\]' ${dest} || true)
    if [ "${already_included}" -eq 0 ]; then
        echo "" >> "${dest}"    # Add a blank line
        echo -e "[include ktamv-macros.cfg]" >> "${dest}"    # Add the section header
    else
        log_error "[include ktamv-macros.cfg] already exists in printer.cfg - skipping adding it there"
    fi
    
    if [ ! -f "${KLIPPER_CONFIG_HOME}/ktamv-macros.cfg" ]; then
        log_info "Copying ktamv-macros.cfg to ${KLIPPER_CONFIG_HOME}"
        cp ${KTAMV_REPO_DIR}/ktamv-macros.cfg ${KLIPPER_CONFIG_HOME}
    else
        log_error "[include ktamv-macros.cfg] already exists in printer.cfg - skipping adding it there"
    fi
    # Restart Klipper
    restart_klipper

}

# 
# Logic to install kTAMV as a systemd service
# 
install_sysd(){
    log_header "Installing system start script so the server can start from Moonrker..."

    # Comand to launch the server to be used in the service file
    LAUNCH_CMD="${KTAMV_ENV}/bin/python ${KTAMV_REPO_DIR}/server/ktamv_server.py --port ${PORT}"

    # Create systemd service file
    SERVICE_FILE="${SYSTEMDDIR}/kTAMV_server.service"

    # If the service file already exists, don't overwrite
    [ -f $SERVICE_FILE ] && return
    sudo /bin/sh -c "cat > ${SERVICE_FILE}" << EOF
#Systemd service file for kTAMV_server
[Unit]
Description=Server component for kTAMV. A tool alignment tool for Klipper using machine vision.
After=network-online.target moonraker.service

[Install]
WantedBy=multi-user.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$KTAMV_REPO_DIR/server
ExecStart=$LAUNCH_CMD
Restart=always
RestartSec=10
EOF
    # Use systemctl to enable the klipper systemd service script
        sudo systemctl enable kTAMV_server.service
        sudo systemctl daemon-reload

        # Start the server
        start_server

        # Add kTAMV to the service list of Moonraker
        add_to_asvc

        # Restart Moonraker
        restart_moonraker
}

add_to_asvc()
{
    log_header "Trying to add kTAMV_server to service list"
    if [ -f $MOONRAKER_ASVC ]; then
        log_info "moonraker.asvc was found"
        if ! grep -q kTAMV_server $MOONRAKER_ASVC; then
            log_info "moonraker.asvc does not contain 'kTAMV_server'! Adding it..."
            echo "" >> $MOONRAKER_ASVC    # Add a blank line
            echo -e "kTAMV_server" >> $MOONRAKER_ASVC
        fi
    else
        log_error "moonraker.asvc not found! Add 'kTAMV_server' to the service list manually"
    fi
}

start_server()
{
    log_header "Launching kTAMV Server..."
    sudo systemctl restart kTAMV_server
}


# 
# Logic to ask a question and get a yes or no answer while displaying a prompt under installation
# 
prompt_yn() {
    while true; do
        read -n1 -p "
$@ (y/n)? " yn
        case "${yn}" in
            Y|y)
                echo "y" 
                break;;
            N|n)
                echo "n" 
                break;;
            *)
                ;;
        esac
    done
}

log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_header "                     kTAMV"
log_header "   Klipper Tool Alignment (using) Machine Vision"
log_blank
log_blank
log_important "kTAMV is used to align your printer's toolheads using machine vision."
log_blank
log_info "Usage: $0 [-p <server_port>] [-k <klipper_home_dir>] [-c <klipper_config_dir>] [-j <klipper_enviroment_dir>]"
log_info "[-m <moonraker_home_dir>] [-s <system_dir>]"
log_blank
log_blank
log_important "This script will install the kTAMV client to Klipper and the kTAMV server as a service on port ${PORT}."
log_important "It will update Rasberry Pi OS and install all required packages."
log_important "It will add the base configuration in printer.cfg and moonraker.conf."
log_blank
yn=$(prompt_yn "Do you want to continue?")
echo
case $yn in
    y)
        ;;
    n)
        log_info "You can run this script again later to install kTAMV."
        log_blank
    exit 0
        ;;
esac
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_blank
log_header "                     kTAMV"
log_header "   Klipper Tool Alignment (using) Machine Vision"
log_blank
log_blank
log_important "Do you want to contribute to the development of kTAMV?"
log_info "I would love if you would like to share the images of the nozzle and obtained results taken when finding the nozzle."
log_info "I plan to use it to improve the algorithm and maybe train an AI as the next step."
log_info "You can change this setting later in printer.cfg."
log_blank

yn=$(prompt_yn "Do you want to continue?")
echo
case $yn in
    y)
        log_info "Thank you, this will help a lot!"
        log_blank
        SEND_IMAGES="true"
        ;;
    n)
        log_info "Will not send any info."
        log_blank
        SEND_IMAGES="false"
        ;;
esac



while getopts "k:c:m:ids" arg; do
    case $arg in
        k) KLIPPER_HOME=${OPTARG};;
        m) MOONRAKER_HOME=${OPTARG};;
        c) KLIPPER_CONFIG_HOME=${OPTARG};;
        j) KLIPPER_ENV=${OPTARG};;
        s) SYSTEMDDIR=${OPTARG};;
        p) PORT=${OPTARG};;
    esac
done

function nextfilename {
    local name="$1"
    if [ -d "${name}" ]; then
        printf "%s-%s" ${name%%.*} $(date '+%Y%m%d_%H%M%S')
    else
        printf "%s-%s.%s-old" ${name%%.*} $(date '+%Y%m%d_%H%M%S') ${name#*.}
    fi
}


# Make sure we aren't running as root
verify_ready

# Check that Klipper is installed
check_klipper

# Check that the home directories are valid
verify_home_dirs

# Link the extension to Klipper
link_extension

# Install the update manager to Moonraker
install_update_manager

# Install kTAMV as a systemd service and then add it to the service list moonraker.asvc
install_sysd

# Install the configuration to Klipper
install_klipper_config

log_blank
log_blank
log_important "kTAMV is now installed. Settings can be found in the printer.cfg file."
