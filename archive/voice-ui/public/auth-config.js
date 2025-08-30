// Azure AD B2C Authentication Configuration
class AuthConfig {
  constructor() {
    // Azure AD B2C Configuration
    this.b2cConfig = {
      auth: {
        clientId: this.getConfigValue('AZURE_CLIENT_ID', 'b8b7f7dc-1234-5678-9abc-def123456789'), // Replace with actual client ID
        authority: this.getB2CAuthority(),
        knownAuthorities: [this.getB2CAuthority().replace('https://', '')],
        redirectUri: this.getConfigValue('AZURE_REDIRECT_URI', window.location.origin),
        postLogoutRedirectUri: window.location.origin,
        navigateToLoginRequestUrl: false
      },
      cache: {
        cacheLocation: "sessionStorage", // This configures where your cache will be stored
        storeAuthStateInCookie: false // Set this to "true" if you are having issues on IE11 or Edge
      },
      system: {
        loggerOptions: {
          loggerCallback: (level, message, containsPii) => {
            if (containsPii) return;
            console.log(`[MSAL] ${level}: ${message}`);
          },
          logLevel: this.isProduction() ? 'Error' : 'Info'
        }
      }
    };

    // Login request configuration
    this.loginRequest = {
      scopes: ["openid", "profile", "email"],
      prompt: "select_account"
    };

    // API request configuration
    this.apiRequest = {
      scopes: [`https://${this.getTenantName()}.onmicrosoft.com/voice-api/access`],
      account: null
    };
  }

  getConfigValue(key, defaultValue) {
    // In a real implementation, you'd read from environment variables
    // For now, using hardcoded values that need to be replaced
    const config = {
      'AZURE_CLIENT_ID': 'b8b7f7dc-1234-5678-9abc-def123456789', // Replace with your B2C app client ID
      'AZURE_TENANT_NAME': 'thewell', // Replace with your tenant name
      'AZURE_POLICY_NAME': 'B2C_1_signupsignin1', // Replace with your policy name
      'AZURE_REDIRECT_URI': window.location.origin
    };
    return config[key] || defaultValue;
  }

  getTenantName() {
    return this.getConfigValue('AZURE_TENANT_NAME', 'thewell');
  }

  getPolicyName() {
    return this.getConfigValue('AZURE_POLICY_NAME', 'B2C_1_signupsignin1');
  }

  getB2CAuthority() {
    const tenantName = this.getTenantName();
    const policyName = this.getPolicyName();
    return `https://${tenantName}.b2clogin.com/${tenantName}.onmicrosoft.com/${policyName}`;
  }

  isProduction() {
    return window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';
  }
}

// Create global auth config instance
window.AuthConfig = new AuthConfig();

// B2C Policies configuration
window.b2cPolicies = {
  names: {
    signUpSignIn: window.AuthConfig.getPolicyName(),
    forgotPassword: "B2C_1_password_reset",
    editProfile: "B2C_1_profile_edit"
  },
  authorities: {
    signUpSignIn: {
      authority: window.AuthConfig.getB2CAuthority(),
    },
    forgotPassword: {
      authority: `https://${window.AuthConfig.getTenantName()}.b2clogin.com/${window.AuthConfig.getTenantName()}.onmicrosoft.com/B2C_1_password_reset`,
    },
    editProfile: {
      authority: `https://${window.AuthConfig.getTenantName()}.b2clogin.com/${window.AuthConfig.getTenantName()}.onmicrosoft.com/B2C_1_profile_edit`,
    }
  },
  authorityDomain: `${window.AuthConfig.getTenantName()}.b2clogin.com`
};

// API configuration for token requests
window.apiConfig = {
  b2cScopes: [`https://${window.AuthConfig.getTenantName()}.onmicrosoft.com/voice-api/access`],
  webApi: window.WellConfig?.api?.endpoint || 'https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io'
};