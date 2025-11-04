import os, sys
import boto3
import time

REGION = "eu-central-1"
CLIENT_ID = "5gsnfi7e3j3p9i3qrnatjr4bju"

class CognitoSession:
    def __init__(self):
        self.id_token = None
        self.access_token = None
        self.refresh_token = None
        self.expiry = 0   # Unixzeit, wann AccessToken abläuft
        self.username = None
        self.password = None
        
        # Company ID (wird später aus Token extrahiert)
        self.company_id = None

    def login(self, username, password):
        self.username = username
        self.password = password
        
        client = boto3.client("cognito-idp", region_name=REGION)
        try:
            resp = client.initiate_auth(
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": username, "PASSWORD": password},
                ClientId=CLIENT_ID,
            )
        except client.exceptions.NotAuthorizedException as e:
            raise Exception("Ungültiger Benutzername oder Passwort") from e
        
        self._store_tokens(resp["AuthenticationResult"])
        
        # Extract company_id from token (if available)
        self._extract_claims()

    def _store_tokens(self, result):
        self.id_token = result["IdToken"]
        self.access_token = result["AccessToken"]
        if "RefreshToken" in result:
            self.refresh_token = result["RefreshToken"]
        self.expiry = int(time.time()) + 500

    def _extract_claims(self):
        """Extrahiert Claims aus dem ID Token (z.B. company_id)"""
        try:
            import base64
            import json
            
            # Decode JWT token (middle part)
            token_parts = self.id_token.split('.')
            if len(token_parts) >= 2:
                # Add padding if needed
                payload = token_parts[1]
                padding = 4 - len(payload) % 4
                if padding != 4:
                    payload += '=' * padding
                
                decoded = base64.b64decode(payload)
                claims = json.loads(decoded)
                
                # Extract company_id (anpassen an deine Claim-Namen)
                self.company_id = claims.get('custom:companyId') or claims.get('companyId') or 'default-company'
                
                print(f"✓ Company ID extrahiert: {self.company_id}")
        except Exception as e:
            print(f"⚠️ Konnte Company ID nicht extrahieren: {e}")
            self.company_id = 'default-company'

    def ensure_valid_token(self):
        """Gibt immer ein gültiges IdToken zurück, erneuert falls nötig."""
        if time.time() < self.expiry:
            return self.id_token
        
        # Ablauf -> Refresh
        client = boto3.client("cognito-idp", region_name=REGION)
        resp = client.initiate_auth(
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={"REFRESH_TOKEN": self.refresh_token},
            ClientId=CLIENT_ID,
        )
        self._store_tokens(resp["AuthenticationResult"])
        
        return self.id_token

    def is_authenticated(self) -> bool:
        """True wenn ein Access-Token gesetzt ist."""
        return bool(self.access_token)