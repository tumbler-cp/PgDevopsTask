#!/usr/bin/env python3

import argparse
import subprocess
import re
import logging

DEFAULT_USER = "root"
DEFAULT_INVENTORY_FILE = "inventory.yml"
CHOSEN_INVENTORY_FILE = "chosen.yml"
CONFIG_INVENTORY_FILE = "configtory.ini"
LOAD_CHECK_PLAYBOOK = "load_check.yml"
INSTALL_POSTGRES_PLAYBOOK = "install_postgres.yml"
CONFIG_POSTGRES_PLAYBOOK = "config_postgres.yml"
POSTGRES_CHECK_PLAYBOOK = "check_postgres.yml"
LOAD_WEIGHTS = (0.5, 0.3)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def parse_address(address):
    logging.info(f"Parsing address: {address}")
    addr, _, port = address.partition(':')
    return {"address": addr, "port": port or None, "user": DEFAULT_USER}

def create_inventory(machines, filename):
    logging.info(f"Creating inventory file: {filename}")
    inventory = "---\nall:\n  hosts:\n"
    for machine in machines:
        inventory += (
            f"    {machine['name']}:\n"
            f"      ansible_host: {machine['address']}\n"
            f"      ansible_user: {machine['user']}\n"
        )
        if machine['port']:
            inventory += f"      ansible_port: {machine['port']}\n"
    with open(filename, 'w') as f:
        f.write(inventory)
    logging.info(f"Inventory file {filename} created successfully.")

def create_config_inventory(groups, filename):
    logging.info(f"Creating configuration inventory file: {filename}")
    inventory = ""
    for group, machines in groups.items():
        inventory += f"[{group}]\n"
        for machine in machines:
            inventory += (
                f"{machine['name']} ansible_host={machine['address']} "
                f"ansible_user={machine['user']}"
            )
            if machine['port']:
                inventory += f" ansible_port={machine['port']}"
            inventory += "\n"
    with open(filename, 'w') as f:
        f.write(inventory)
    logging.info(f"Configuration inventory file {filename} created successfully.")

def run_playbook(inventory, playbook):
    logging.info(f"Running playbook: {playbook} with inventory: {inventory}")
    result = subprocess.run(
        ["ansible-playbook", "-i", inventory, playbook],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        logging.info(f"Playbook {playbook} executed successfully.")
        return result.stdout
    else:
        logging.error(f"Playbook {playbook} failed with error: {result.stderr}")
        return None

def extract_load(output, host):
    logging.info(f"Extracting load for host: {host}")
    match = re.search(rf"ok: \[{host}\] => {{\s+\"msg\": \[(.*?)\]\s+}}", output, re.DOTALL)
    values = re.findall(r"\d+\.\d+", match.group(1)) if match else []
    logging.info(f"Load values for {host}: {values}")
    return tuple(map(float, values))

def compare_loads(debian_load, almalinux_load):
    logging.info("Comparing loads between Debian and Almalinux")
    debian_avg = sum(d * w for d, w in zip(debian_load, LOAD_WEIGHTS))
    almalinux_avg = sum(a * w for a, w in zip(almalinux_load, LOAD_WEIGHTS))
    logging.info(f"Debian average load: {debian_avg}, Almalinux average load: {almalinux_avg}")
    return "debian" if debian_avg < almalinux_avg else "almalinux"

def install_postgres():
    logging.info("Installing PostgreSQL on the chosen server.")
    run_playbook(CHOSEN_INVENTORY_FILE, INSTALL_POSTGRES_PLAYBOOK)

def config_postgres():
    logging.info("Configuring PostgreSQL on the chosen server.")
    run_playbook(CONFIG_INVENTORY_FILE, CONFIG_POSTGRES_PLAYBOOK)
    
def check_postgres():
    logging.info("Checking PostgreSQL installation on the chosen server.")
    output = run_playbook(CHOSEN_INVENTORY_FILE, POSTGRES_CHECK_PLAYBOOK)
    if output:
        print("PostgreSQL installation check output:")
        print(output)

def main(debian_addr, almalinux_addr):
    logging.info("Starting the Postgres DevOps Task.")
    print("Initializing the process...")

    machines = [
        {"name": "Debian", **parse_address(debian_addr)},
        {"name": "Almalinux", **parse_address(almalinux_addr)}
    ]
    create_inventory(machines, DEFAULT_INVENTORY_FILE)
    print("Running load check playbook...")
    output = run_playbook(DEFAULT_INVENTORY_FILE, LOAD_CHECK_PLAYBOOK)
    
    if not output:
        print("Error: Load check playbook failed. Check logs for details.")
        return

    debian_load = extract_load(output, "Debian")
    almalinux_load = extract_load(output, "Almalinux")
    
    chosen, app_server = (
        (machines[0], machines[1]) if compare_loads(debian_load, almalinux_load) == "debian"
        else (machines[1], machines[0])
    )
    
    print(f"Chosen server: {chosen['name']}")
    logging.info(f"Chosen server: {chosen['name']}")
    create_inventory([chosen], CHOSEN_INVENTORY_FILE)
    print("Installing PostgreSQL on the chosen server...")
    install_postgres()
    print("Creating configuration inventory...")
    create_config_inventory({"postgres_servers": [chosen], "app_servers": [app_server]}, CONFIG_INVENTORY_FILE)
    print("Configuring PostgreSQL...")
    config_postgres()
    print("Checking PostgreSQL installation...")
    check_postgres()
    print("PostgreSQL setup completed successfully.")
    logging.info("Postgres DevOps Task completed successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Postgres DevOps Task")
    parser.add_argument("addresses", type=str, help="Comma-separated addresses of Debian and Almalinux servers")
    args = parser.parse_args()
    main(*args.addresses.split(','))
