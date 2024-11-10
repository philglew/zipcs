import os
import subprocess
import requests
import json
import uuid

def login_to_azure():
    print("Logging in to Azure using Entra ID...")
    subprocess.run(["az", "login"], check=True)

def create_app_registration(app_name, tenant_id, is_server_app):
    # Create app registration
    create_app_command = [
        "az", "ad", "app", "create",
        "--display-name", app_name,
        "--sign-in-audience", "AzureADMyOrg"
    ]

    if not is_server_app:
        create_app_command += [
            "--web-redirect-uris", "https://global.consent.azure-apim.net/redirect/zellis", "https://oauth.powerbi.com/views/oauthredirect.html",
            "--enable-id-token-issuance", "true",
            "--enable-access-token-issuance", "true"
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
        "--query", "password",
        "-o", "tsv"
    ]
    result = subprocess.run(create_secret_command, capture_output=True, text=True, check=True)
    return result.stdout.strip()

def add_application_id_uri(app_id):
    app_id_uri = f"api://{app_id}"
    update_command = [
        "az", "ad", "app", "update",
        "--id", app_id,
        "--identifier-uris", app_id_uri
    ]
    result = subprocess.run(update_command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error updating Application ID URI: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, update_command)

def add_api_scope(app_id):
    scope_definition = json.dumps([
        {
            "adminConsentDescription": "API.Access",
            "adminConsentDisplayName": "API.Access",
            "id": str(uuid.uuid4()),
            "type": "Admin",
            "value": "API.Access"
        }
    ])
    add_scope_command = [
        "az", "ad", "app", "update",
        "--id", app_id,
        "--set", f"oauth2Permissions={scope_definition}"
    ]
    result = subprocess.run(add_scope_command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error adding scope to app registration: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, add_scope_command)

def authorize_client_app(server_app_id, client_app_id):
    authorize_command = [
        "az", "ad", "app", "permission", "add",
        "--id", server_app_id,
        "--api", server_app_id,
        "--api-permissions", f"{client_app_id}/.default=Scope"
    ]
    result = subprocess.run(authorize_command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error authorizing client app: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, authorize_command)

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
        
        # Add Application ID URI to Server App
        try:
            add_application_id_uri(server_app_id)
        except subprocess.CalledProcessError:
            print(f"Failed to add Application ID URI to server app registration for {env}. Exiting...")
            return
        
        # Add scope to Server App
        try:
            add_api_scope(server_app_id)
        except subprocess.CalledProcessError:
            print(f"Failed to add scope to server app registration for {env}. Exiting...")
            return

        # Create Client App
        client_app_name = f"ZIP {env} - Client App"
        try:
            client_app_info = create_app_registration(client_app_name, tenant_id, False)
        except subprocess.CalledProcessError:
            print(f"Failed to create client app registration for {env}. Exiting...")
            return
        client_app_id = client_app_info['appId']

        # Create a client secret for Client App
        client_secret = create_client_secret(client_app_id)

        # Authorize the Client App on the Server App
        try:
            authorize_client_app(server_app_id, client_app_id)
        except subprocess.CalledProcessError:
            print(f"Failed to authorize client app for {env}. Exiting...")
            return

        # Output the result to the user
        print("\nSuccess! Please note the following:")
        print(f"ZIP Server App: {server_app_id}")
        print(f"ZIP Client App: {client_app_id}")
        print(f"ZIP Client App Secret: {client_secret}")
        print(f"Tenant ID: {tenant_id}\n")

if __name__ == "__main__":
    main()
