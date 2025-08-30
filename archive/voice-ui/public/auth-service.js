// Microsoft Authentication Service using MSAL.js
class AuthService {
  constructor() {
    this.msalInstance = null;
    this.account = null;
    this.isInitialized = false;
    this.initializationPromise = null;
  }

  async initialize() {
    if (this.initializationPromise) {
      return this.initializationPromise;
    }

    this.initializationPromise = this._initializeInternal();
    return this.initializationPromise;
  }

  async _initializeInternal() {
    try {
      console.log('[AuthService] Initializing MSAL...');
      
      // Check if MSAL is loaded
      if (typeof msal === 'undefined') {
        throw new Error('MSAL library is not loaded. Please ensure @azure/msal-browser is included.');
      }

      // Initialize MSAL instance
      this.msalInstance = new msal.PublicClientApplication(window.AuthConfig.b2cConfig);
      
      // Handle redirect response
      const response = await this.msalInstance.handleRedirectPromise();
      if (response) {
        console.log('[AuthService] Redirect response received:', response);
        this.account = response.account;
      } else {
        // Check if user is already signed in
        const accounts = this.msalInstance.getAllAccounts();
        if (accounts.length > 0) {
          console.log('[AuthService] Found existing account:', accounts[0]);
          this.account = accounts[0];
        }
      }

      this.isInitialized = true;
      console.log('[AuthService] MSAL initialized successfully');
      
      return {
        success: true,
        isAuthenticated: !!this.account,
        account: this.account
      };

    } catch (error) {
      console.error('[AuthService] Failed to initialize MSAL:', error);
      return {
        success: false,
        error: error.message,
        isAuthenticated: false
      };
    }
  }

  async signIn() {
    try {
      if (!this.isInitialized) {
        throw new Error('AuthService not initialized. Call initialize() first.');
      }

      console.log('[AuthService] Starting sign-in flow...');

      // Use redirect flow for better compatibility
      await this.msalInstance.loginRedirect(window.AuthConfig.loginRequest);
      
      // Note: After redirect, the page will reload and handleRedirectPromise will handle the response
      
    } catch (error) {
      console.error('[AuthService] Sign-in failed:', error);
      
      // Handle specific MSAL errors
      if (error instanceof msal.InteractionRequiredAuthError) {
        // Force interactive sign-in
        return this.msalInstance.loginRedirect(window.AuthConfig.loginRequest);
      } else if (error instanceof msal.BrowserAuthError) {
        throw new Error(`Authentication error: ${error.message}`);
      } else {
        throw new Error(`Sign-in failed: ${error.message}`);
      }
    }
  }

  async signOut() {
    try {
      if (!this.isInitialized) {
        throw new Error('AuthService not initialized.');
      }

      console.log('[AuthService] Signing out...');
      
      const logoutRequest = {
        account: this.account,
        postLogoutRedirectUri: window.location.origin
      };

      this.account = null;
      await this.msalInstance.logoutRedirect(logoutRequest);
      
    } catch (error) {
      console.error('[AuthService] Sign-out failed:', error);
      throw new Error(`Sign-out failed: ${error.message}`);
    }
  }

  async getAccessToken() {
    try {
      if (!this.isInitialized || !this.account) {
        throw new Error('User not authenticated');
      }

      const request = {
        ...window.AuthConfig.apiRequest,
        account: this.account
      };

      console.log('[AuthService] Acquiring access token...');

      // Try to get token silently first
      const response = await this.msalInstance.acquireTokenSilent(request);
      console.log('[AuthService] Access token acquired silently');
      return response.accessToken;

    } catch (error) {
      console.error('[AuthService] Silent token acquisition failed:', error);

      if (error instanceof msal.InteractionRequiredAuthError) {
        // Fallback to interactive method
        try {
          const response = await this.msalInstance.acquireTokenRedirect(request);
          return response.accessToken;
        } catch (interactiveError) {
          console.error('[AuthService] Interactive token acquisition failed:', interactiveError);
          throw new Error('Failed to acquire access token');
        }
      } else {
        throw new Error(`Token acquisition failed: ${error.message}`);
      }
    }
  }

  isAuthenticated() {
    return this.isInitialized && !!this.account;
  }

  getCurrentAccount() {
    return this.account;
  }

  getUserInfo() {
    if (!this.account) {
      return null;
    }

    return {
      id: this.account.localAccountId,
      name: this.account.name || this.account.username,
      email: this.account.username,
      tenantId: this.account.tenantId
    };
  }

  // Helper method to create authorization header for API calls
  async getAuthorizationHeader() {
    try {
      const token = await this.getAccessToken();
      return `Bearer ${token}`;
    } catch (error) {
      console.error('[AuthService] Failed to get authorization header:', error);
      return null;
    }
  }

  // Handle MSAL errors gracefully
  handleError(error) {
    console.error('[AuthService] Error occurred:', error);

    if (error instanceof msal.BrowserAuthError) {
      switch (error.errorCode) {
        case 'interaction_in_progress':
          return 'Authentication is already in progress. Please wait.';
        case 'popup_window_error':
          return 'Popup was blocked or closed. Please try again.';
        default:
          return `Browser authentication error: ${error.message}`;
      }
    } else if (error instanceof msal.AuthError) {
      return `Authentication error: ${error.message}`;
    } else {
      return `Unexpected error: ${error.message}`;
    }
  }

  // Cleanup method
  dispose() {
    if (this.msalInstance) {
      // Clear any cached tokens
      this.msalInstance.clearCache();
    }
    this.account = null;
    this.isInitialized = false;
    this.initializationPromise = null;
  }
}

// Create global auth service instance
window.authService = new AuthService();