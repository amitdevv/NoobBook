"""
Google Auth Service - Handle Google OAuth 2.0 authentication flow.

Educational Note: This service manages the OAuth 2.0 flow for Google APIs:
1. Generate authorization URL (user visits to grant access)
2. Exchange authorization code for access/refresh tokens
3. Refresh access tokens when they expire (access tokens last ~1 hour)
4. Store tokens securely in Supabase (per-user)

OAuth 2.0 Flow:
    1. User clicks "Connect Google Drive"
    2. We redirect to Google's auth page with our client ID and scopes
    3. User grants permission
    4. Google redirects back with an authorization code
    5. We exchange the code for access + refresh tokens
    6. We store tokens in Supabase users table
    7. When access token expires, we use refresh token to get a new one

Required Setup:
    1. Create project at https://console.cloud.google.com
    2. Enable Google Drive API
    3. Create OAuth 2.0 credentials (Web application)
    4. Add http://localhost:5001/api/v1/google/callback as redirect URI
    5. Copy Client ID and Client Secret to App Settings

Migration Note (2026-01):
    Previously tokens were stored in data/google_tokens.json (single file for all users).
    Now tokens are stored per-user in the Supabase users.google_tokens JSONB column,
    enabling proper multi-user support with isolated Google Drive connections.
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request

from app.services.integrations.supabase import get_supabase


class GoogleAuthService:
    """
    Service class for Google OAuth 2.0 authentication.

    Educational Note: This service handles the complete OAuth lifecycle:
    - Generating auth URLs with appropriate scopes
    - Exchanging auth codes for tokens
    - Refreshing expired tokens
    - Storing and loading credentials from Supabase
    """

    # OAuth scopes we need for Google Drive
    # Educational Note: Scopes define what access we're requesting
    # - drive.readonly: Read files from Drive
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
    ]

    # Redirect URI for OAuth callback
    # Educational Note: Must match exactly what's configured in Google Console
    REDIRECT_URI = 'http://localhost:5001/api/v1/google/callback'

    def __init__(self):
        """Initialize the Google Auth service."""
        self._supabase = None

    @property
    def supabase(self):
        """Lazy load Supabase client to avoid initialization issues."""
        if self._supabase is None:
            self._supabase = get_supabase()
        return self._supabase

    def _get_client_config(self) -> Optional[Dict[str, Any]]:
        """
        Get OAuth client configuration from environment.

        Educational Note: We build the client config dict that google-auth
        expects from our environment variables. This avoids needing a
        client_secrets.json file.

        Returns:
            Client config dict or None if credentials not set
        """
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')

        if not client_id or not client_secret:
            return None

        return {
            'web': {
                'client_id': client_id,
                'client_secret': client_secret,
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'redirect_uris': [self.REDIRECT_URI],
            }
        }

    def _get_default_user_id(self) -> Optional[str]:
        """
        Get the default user ID for single-user mode.

        Educational Note: In single-user mode (using service key), we don't have
        a logged-in user context. We use the first user in the database as the
        default. For multi-user mode with proper auth, the user_id should be
        passed explicitly from the authenticated session.

        Returns:
            User ID string or None if no users exist
        """
        try:
            result = self.supabase.table("users").select("id").limit(1).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]["id"]
            return None
        except Exception as e:
            print(f"Error getting default user: {e}")
            return None

    def is_configured(self) -> bool:
        """
        Check if Google OAuth credentials are configured.

        Returns:
            True if both client ID and secret are set
        """
        return self._get_client_config() is not None

    def is_connected(self, user_id: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Check if we have valid Google credentials for a user.

        Educational Note: This checks if:
        1. User has tokens stored in Supabase
        2. Tokens are valid or can be refreshed

        Args:
            user_id: Optional user ID. If not provided, uses default user (single-user mode)

        Returns:
            Tuple of (is_connected, user_email or None)
        """
        # Use get_credentials() which handles token refresh
        creds = self.get_credentials(user_id)
        if creds and creds.valid:
            # Try to get user info
            email = self._get_user_email(creds)
            return True, email
        return False, None

    def get_auth_url(self, user_id: Optional[str] = None) -> Optional[str]:
        """
        Generate the Google OAuth authorization URL.

        Educational Note: This URL is where users are redirected to grant
        permission. It includes:
        - client_id: Identifies our app
        - scope: What access we're requesting
        - redirect_uri: Where to send user after auth
        - access_type=offline: Request refresh token for long-term access
        - prompt=consent: Always show consent screen (ensures refresh token)
        - state: User ID for multi-user support (identifies who initiated OAuth)

        Args:
            user_id: Optional user ID to include in state parameter

        Returns:
            Authorization URL or None if not configured
        """
        client_config = self._get_client_config()
        if not client_config:
            return None

        # Use provided user_id or get default for single-user mode
        effective_user_id = user_id or self._get_default_user_id()

        flow = Flow.from_client_config(
            client_config,
            scopes=self.SCOPES,
            redirect_uri=self.REDIRECT_URI
        )

        # Generate auth URL
        # access_type='offline' ensures we get a refresh token
        # prompt='consent' forces consent screen to ensure refresh token
        # state parameter carries user_id for the callback
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            prompt='consent',
            include_granted_scopes='true',
            state=effective_user_id or ''  # Pass user_id in state for callback
        )

        return auth_url

    def handle_callback(self, authorization_code: str, user_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Handle the OAuth callback and exchange code for tokens.

        Educational Note: After user grants permission, Google redirects
        to our callback with an authorization code. We exchange this code
        for access and refresh tokens, then store them in Supabase.

        Args:
            authorization_code: The code from Google's redirect
            user_id: User ID from state parameter (for multi-user support)

        Returns:
            Tuple of (success, message or error)
        """
        client_config = self._get_client_config()
        if not client_config:
            return False, "Google OAuth not configured"

        # Use provided user_id or get default for single-user mode
        effective_user_id = user_id or self._get_default_user_id()
        if not effective_user_id:
            return False, "No user found to associate Google tokens with"

        try:
            flow = Flow.from_client_config(
                client_config,
                scopes=self.SCOPES,
                redirect_uri=self.REDIRECT_URI
            )

            # Exchange authorization code for tokens
            flow.fetch_token(code=authorization_code)

            # Get credentials object
            credentials = flow.credentials

            # Save credentials to Supabase
            self._save_credentials(credentials, effective_user_id)

            # Get user email for confirmation
            email = self._get_user_email(credentials)

            return True, f"Successfully connected as {email}" if email else "Successfully connected"

        except Exception as e:
            return False, f"Failed to authenticate: {str(e)}"

    def disconnect(self, user_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Disconnect Google account by removing stored tokens.

        Educational Note: We don't revoke the tokens (which would require
        an API call), we just delete them from Supabase. User can revoke
        access from their Google account settings if desired.

        Args:
            user_id: Optional user ID. If not provided, uses default user

        Returns:
            Tuple of (success, message)
        """
        effective_user_id = user_id or self._get_default_user_id()
        if not effective_user_id:
            return False, "No user found"

        try:
            # Set google_tokens to null in Supabase
            self.supabase.table("users").update(
                {"google_tokens": None}
            ).eq("id", effective_user_id).execute()

            return True, "Google Drive disconnected"
        except Exception as e:
            return False, f"Failed to disconnect: {str(e)}"

    def get_credentials(self, user_id: Optional[str] = None) -> Optional[Credentials]:
        """
        Get valid credentials, refreshing if necessary.

        Educational Note: This is the main method other services should use
        to get credentials for API calls. It handles:
        1. Loading saved credentials from Supabase
        2. Checking if they're expired
        3. Refreshing if needed
        4. Returning valid credentials or None

        Args:
            user_id: Optional user ID. If not provided, uses default user

        Returns:
            Valid Credentials object or None
        """
        effective_user_id = user_id or self._get_default_user_id()
        creds = self._load_credentials(effective_user_id)
        if not creds:
            return None

        # Check if credentials need refresh
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_credentials(creds, effective_user_id)
            except Exception as e:
                print(f"Failed to refresh Google credentials: {e}")
                return None

        return creds if creds.valid else None

    def _load_credentials(self, user_id: Optional[str] = None) -> Optional[Credentials]:
        """
        Load credentials from Supabase for a user.

        Args:
            user_id: User ID to load credentials for

        Returns:
            Credentials object or None if not found/invalid
        """
        if not user_id:
            return None

        try:
            result = self.supabase.table("users").select("google_tokens").eq("id", user_id).execute()

            if not result.data or len(result.data) == 0:
                return None

            token_data = result.data[0].get("google_tokens")
            if not token_data:
                return None

            return Credentials(
                token=token_data.get('token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri=token_data.get('token_uri'),
                client_id=token_data.get('client_id'),
                client_secret=token_data.get('client_secret'),
                scopes=token_data.get('scopes')
            )
        except Exception as e:
            print(f"Error loading Google credentials: {e}")
            return None

    def _save_credentials(self, credentials: Credentials, user_id: str) -> None:
        """
        Save credentials to Supabase for a user.

        Educational Note: We save all credential components so we can
        reconstruct the Credentials object later, including the refresh
        token for getting new access tokens.

        Args:
            credentials: The Credentials object to save
            user_id: User ID to save credentials for
        """
        # Get user email for reference
        email = self._get_user_email(credentials)

        token_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes,
            'google_email': email,
            'saved_at': datetime.now().isoformat()
        }

        try:
            self.supabase.table("users").update(
                {"google_tokens": token_data}
            ).eq("id", user_id).execute()
        except Exception as e:
            print(f"Error saving Google credentials to Supabase: {e}")
            raise

    def _get_user_email(self, credentials: Credentials) -> Optional[str]:
        """
        Get the email of the authenticated user.

        Educational Note: We use Drive API's "about" endpoint to get user info.
        This works with our drive.readonly scope (unlike oauth2 userinfo which
        requires a separate userinfo.email scope).

        Args:
            credentials: Valid credentials

        Returns:
            User email or None
        """
        try:
            from googleapiclient.discovery import build

            # Use Drive API to get user email (works with drive.readonly scope)
            service = build('drive', 'v3', credentials=credentials)
            about = service.about().get(fields='user(emailAddress)').execute()
            return about.get('user', {}).get('emailAddress')
        except Exception as e:
            print(f"Failed to get user email: {e}")
            return None


# Singleton instance
google_auth_service = GoogleAuthService()
