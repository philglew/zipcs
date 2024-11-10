import os
import subprocess
import requests
import json

def login_to_azure():
    print("Logging in to Azure using Entra ID...")
    subprocess.run(["az", "login"], check=True)

def create_app_registration(app_name, tenant_id, is_server_app):
    # Create app registration
    create_app_command = [
        "az", "ad", "app", "create",
        "--display-name", app_name,
        "--available-to-other-tenants", "false",
        "--oauth2-allow-implicit-flow", "true",
        "--sign-in-audience", "AzureADMyOrg"
    ]

    result = subprocess.run(create_app_command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error creating app registration: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, create_app_command)
    
    app_info = json.loads(result.stdout)
    return app_info

def create_client_secret(app_id):
    create_secret_command = [
        "az", "ad", "app", "credential", "reset",
        "--id", app_id,
        "--append",
        "--query", "password"
    ]
    result = subprocess.run(create_secret_command, capture_output=True, text=True, check=True)
    return result.stdout.strip()

def assign_owner(app_id):
    # Assign the current logged in user as the owner
    owner = subprocess.run(["az", "ad", "signed-in-user", "show", "--query", "objectId"], capture_output=True, text=True, check=True)
    owner_id = owner.stdout.strip().replace('"', '')
    subprocess.run(["az", "ad", "app", "owner", "add", "--id", app_id, "--owner-object-id", owner_id], check=True)

def main():
    # Step 1: Log in to Azure
    login_to_azure()

    # Step 2: Ask the user about TEST, LIVE, or BOTH
    choice = input("Do you want to create app registrations for TEST or LIVE, or BOTH? (t = TEST, l = LIVE, b = BOTH): ").lower()
    valid_choices = ['t', 'l', 'b']
    if choice not in valid_choices:
        print("Invalid choice. Exiting...")
        return

    environments = []
    if choice == 't':
        environments = ['TEST']
    elif choice == 'l':
        environments = ['LIVE']
    else:
        environments = ['TEST', 'LIVE']

    # Step 3: Ask for Azure Tenant ID
    tenant_id = input("Please enter your Azure Tenant ID: ").strip()

    # Step 4: Create App Registrations
    for env in environments:
        # Create Server App
        server_app_name = f"ZIP {env} - Server App"
        try:
            server_app_info = create_app_registration(server_app_name, tenant_id, True)
        except subprocess.CalledProcessError:
            print(f"Failed to create server app registration for {env}. Exiting...")
            return
        server_app_id = server_app_info['appId']
        assign_owner(server_app_id)

        # Create Client App
        client_app_name = f"ZIP {env} - Client App"
        try:
            client_app_info = create_app_registration(client_app_name, tenant_id, False)
        except subprocess.CalledProcessError:
            print(f"Failed to create client app registration for {env}. Exiting...")
            return
        client_app_id = client_app_info['appId']
        assign_owner(client_app_id)

        # Create a client secret for Client App
        client_secret = create_client_secret(client_app_id)

        # Add the Client App as an authorized application for the Server App
        scope_command = [
            "az", "ad", "app", "permission", "add",
            "--id", server_app_id,
            "--api", server_app_id,
            "--api-permissions", f"{client_app_id}/.default=Scope"
        ]
        result = subprocess.run(scope_command, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error adding client app permissions: {result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, scope_command)

        # Output the result to the user
        print("\nSuccess! Please note the following:")
        print(f"ZIP Server App: {server_app_id}")
        print(f"ZIP Client App: {client_app_id}")
        print(f"ZIP Client App Secret: {client_secret}")
        print(f"Tenant ID: {tenant_id}\n")

if __name__ == "__main__":
    main()
