// Main Application - Well Voice UI (Standalone Version)
class WellVoiceApp {
  constructor() {
    // Core components
    this.voiceHandler = null;
    
    // State
    this.isProcessing = false;
    this.connectionStatus = 'disconnected';
    this.isAuthenticated = false;
    this.userSession = null;
    
    // DOM elements
    this.elements = {};
    
    // Initialize app
    this.init();
  }

  async init() {
    this.log('Initializing Well Voice UI...');
    
    try {
      // Initialize DOM elements
      this.initializeElements();
      
      // Bind critical login events FIRST
      this.bindLoginEvents();
      
      // Check authentication first
      await this.checkAuthentication();
      
      if (this.isAuthenticated) {
        // Initialize components
        await this.initializeComponents();
        
        // Set up event listeners
        this.bindEvents();
        
        // Update connection status
        this.updateConnectionStatus('ready');
        
        this.log('Application initialized successfully');
        this.showToast('Well Voice UI ready! Click the microphone to start.', 'success');
      } else {
        // Show login modal
        this.showLoginModal();
      }
      
    } catch (error) {
      this.log('Failed to initialize application:', error);
      this.showToast('Failed to initialize application: ' + error.message, 'error');
      this.showErrorState(error.message);
    }
  }

  initializeElements() {
    // Cache frequently used DOM elements
    this.elements = {
      // Voice controls
      voiceBtn: document.getElementById('voiceBtn'),
      transcription: document.getElementById('transcription'),
      confidenceBar: document.getElementById('confidenceBar'),
      confidenceText: document.getElementById('confidenceText'),
      continuousMode: document.getElementById('continuousMode'),
      
      // Connection status
      connectionStatus: document.getElementById('connectionStatus'),
      
      // Settings
      settingsBtn: document.getElementById('settingsBtn'),
      settingsModal: document.getElementById('settingsModal'),
      saveSettings: document.getElementById('saveSettings'),
      
      // Authentication - Microsoft
      loginModal: document.getElementById('loginModal'),
      microsoftSignInBtn: document.getElementById('microsoftSignInBtn'),
      testLoginBtn: document.getElementById('testLoginBtn'),
      authStatus: document.getElementById('authStatus'),
      authStatusText: document.getElementById('authStatusText'),
      authError: document.getElementById('authError'),
      authErrorText: document.getElementById('authErrorText'),
    };
  }

  async initializeComponents() {
    this.log('Initializing voice handler...');
    
    // Initialize voice handler
    this.voiceHandler = new VoiceHandler();
    
    // Set up voice handler callbacks
    this.voiceHandler.onTranscriptUpdate = (transcript, isFinal) => {
      this.handleTranscriptUpdate(transcript, isFinal);
    };
    
    this.voiceHandler.onConfidenceUpdate = (confidence) => {
      this.handleConfidenceUpdate(confidence);
    };
    
    this.voiceHandler.onListeningStateChange = (isListening, isContinuous) => {
      this.handleListeningStateChange(isListening, isContinuous);
    };
    
    this.voiceHandler.onVoiceCommand = (commandType, commandData) => {
      this.handleVoiceCommand(commandType, commandData);
    };
    
    this.voiceHandler.onError = (error) => {
      this.handleVoiceError(error);
    };
    
    this.voiceHandler.onInitialized = (success) => {
      if (this.elements.voiceBtn) {
        this.elements.voiceBtn.disabled = !success;
        if (success) {
          this.showToast('Voice recognition ready - microphone permission granted', 'success');
          this.updateConnectionStatus('ready');
        } else {
          this.showToast('Voice recognition failed to initialize', 'error');
          this.updateConnectionStatus('error');
        }
      }
    };
  }

  bindLoginEvents() {
    // Microsoft Sign-In button - CRITICAL for initial access
    if (this.elements.microsoftSignInBtn) {
      this.elements.microsoftSignInBtn.addEventListener('click', () => {
        this.handleMicrosoftSignIn();
      });
    }

    // Test login button (for development)
    if (this.elements.testLoginBtn) {
      this.elements.testLoginBtn.addEventListener('click', () => {
        this.handleTestLogin();
      });
    }
  }

  bindEvents() {
    // Voice button
    if (this.elements.voiceBtn) {
      this.elements.voiceBtn.addEventListener('click', () => {
        this.toggleVoiceRecognition();
      });
    }

    // Continuous mode toggle
    if (this.elements.continuousMode) {
      this.elements.continuousMode.addEventListener('change', () => {
        if (this.voiceHandler && this.voiceHandler.isListening) {
          this.voiceHandler.stopListening();
          setTimeout(() => {
            this.voiceHandler.startListening(this.elements.continuousMode.checked);
          }, 100);
        }
      });
    }

    // Settings button
    if (this.elements.settingsBtn) {
      this.elements.settingsBtn.addEventListener('click', () => {
        this.openSettings();
      });
    }

    // Settings modal
    if (this.elements.settingsModal) {
      // Close modal when clicking outside
      this.elements.settingsModal.addEventListener('click', (e) => {
        if (e.target === this.elements.settingsModal) {
          this.closeSettings();
        }
      });

      // Close button
      const closeBtn = this.elements.settingsModal.querySelector('.modal-close');
      if (closeBtn) {
        closeBtn.addEventListener('click', () => {
          this.closeSettings();
        });
      }
    }

    // Save settings
    if (this.elements.saveSettings) {
      this.elements.saveSettings.addEventListener('click', () => {
        this.saveSettings();
      });
    }

    // Login events already bound in bindLoginEvents()

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      // Spacebar for voice toggle (when not typing in input)
      if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
        e.preventDefault();
        this.toggleVoiceRecognition();
      }
      
      // Escape to stop listening
      if (e.code === 'Escape' && this.voiceHandler && this.voiceHandler.isListening) {
        this.voiceHandler.stopListening();
      }
    });
  }

  toggleVoiceRecognition() {
    if (!this.voiceHandler) {
      this.showToast('Voice handler not initialized', 'error');
      return;
    }

    if (!this.voiceHandler.isInitialized) {
      this.showToast('Voice recognition is still initializing...', 'warning');
      return;
    }

    try {
      const isContinuous = this.elements.continuousMode ? this.elements.continuousMode.checked : false;
      this.voiceHandler.toggleListening(isContinuous);
    } catch (error) {
      this.log('Error toggling voice recognition:', error);
      this.showToast('Failed to toggle voice recognition', 'error');
    }
  }

  handleTranscriptUpdate(transcript, isFinal) {
    if (!this.elements.transcription) return;

    if (transcript && transcript.trim()) {
      this.elements.transcription.innerHTML = `<span class="${isFinal ? 'final' : 'interim'}">${this.escapeHtml(transcript)}</span>`;
      this.elements.transcription.classList.remove('empty');
    } else {
      this.elements.transcription.innerHTML = '<span class="placeholder-text">Voice commands will appear here...</span>';
      this.elements.transcription.classList.add('empty');
    }
  }

  handleConfidenceUpdate(confidence) {
    if (!this.elements.confidenceBar || !this.elements.confidenceText) return;

    const percentage = Math.round(confidence * 100);
    this.elements.confidenceBar.style.width = `${percentage}%`;
    this.elements.confidenceText.textContent = `${percentage}%`;

    // Update confidence bar color based on confidence level
    this.elements.confidenceBar.className = 'confidence-bar';
    if (confidence > 0.8) {
      this.elements.confidenceBar.classList.add('high-confidence');
    } else if (confidence > 0.5) {
      this.elements.confidenceBar.classList.add('medium-confidence');
    } else {
      this.elements.confidenceBar.classList.add('low-confidence');
    }
  }

  handleListeningStateChange(isListening, isContinuous) {
    this.updateVoiceButtonState(isListening, isContinuous);
    
    if (isListening) {
      this.updateConnectionStatus('listening');
    } else {
      this.updateConnectionStatus('ready');
    }
  }

  handleVoiceCommand(commandType, commandData) {
    this.log('Voice command received:', commandType, commandData);
    
    // Provide voice feedback
    let response = '';
    
    switch (commandType) {
      case 'processEmail':
        response = 'Email processing feature would start here';
        break;
      case 'approveExtraction':
        response = 'Approval feature would execute here';
        break;
      case 'rejectExtraction':
        response = 'Rejection feature would execute here';
        break;
      case 'openSettings':
        this.openSettings();
        response = 'Opening settings';
        break;
      case 'toggleMode':
        if (this.elements.continuousMode) {
          this.elements.continuousMode.checked = !this.elements.continuousMode.checked;
          this.elements.continuousMode.dispatchEvent(new Event('change'));
          response = `Continuous mode ${this.elements.continuousMode.checked ? 'enabled' : 'disabled'}`;
        }
        break;
      case 'freeform':
      default:
        response = `Voice command recognized: "${commandData.transcript}"`;
        break;
    }
    
    if (response) {
      this.showToast(response, 'info');
      
      // Provide voice feedback if enabled
      if (this.voiceHandler && window.WellConfig.features.voiceFeedback) {
        this.voiceHandler.speak(response);
      }
    }
  }

  handleVoiceError(error) {
    this.log('Voice error:', error);
    this.showToast(error, 'error');
    this.updateConnectionStatus('error');
  }

  updateVoiceButtonState(isListening, isContinuous) {
    if (!this.elements.voiceBtn) return;

    const icon = this.elements.voiceBtn.querySelector('.voice-icon i');
    const statusText = this.elements.voiceBtn.querySelector('.voice-status .status-text');
    const pulseRing = this.elements.voiceBtn.querySelector('.pulse-ring');

    if (icon && statusText) {
      if (isListening) {
        icon.className = 'fas fa-stop';
        statusText.textContent = isContinuous ? 'Listening...' : 'Recording...';
        this.elements.voiceBtn.classList.add('listening');
        if (pulseRing) {
          pulseRing.classList.add('active');
        }
      } else {
        icon.className = 'fas fa-microphone';
        statusText.textContent = 'Click to Start';
        this.elements.voiceBtn.classList.remove('listening');
        if (pulseRing) {
          pulseRing.classList.remove('active');
        }
      }
    }
  }

  updateConnectionStatus(status) {
    this.connectionStatus = status;
    
    if (!this.elements.connectionStatus) return;

    const statusIcon = this.elements.connectionStatus.querySelector('i');
    const statusText = this.elements.connectionStatus.childNodes[1];

    let className = 'fas fa-circle';
    let text = '';
    let cssClass = '';

    switch (status) {
      case 'ready':
        className = 'fas fa-circle';
        text = ' Ready';
        cssClass = 'status-ready';
        break;
      case 'listening':
        className = 'fas fa-circle';
        text = ' Listening';
        cssClass = 'status-listening';
        break;
      case 'processing':
        className = 'fas fa-spinner fa-spin';
        text = ' Processing';
        cssClass = 'status-processing';
        break;
      case 'error':
        className = 'fas fa-exclamation-circle';
        text = ' Error';
        cssClass = 'status-error';
        break;
      default:
        className = 'fas fa-circle';
        text = ' Initializing';
        cssClass = 'status-initializing';
    }

    if (statusIcon) {
      statusIcon.className = className;
    }
    if (statusText) {
      statusText.textContent = text;
    }
    
    this.elements.connectionStatus.className = `status-indicator ${cssClass}`;
  }

  openSettings() {
    if (this.elements.settingsModal) {
      this.elements.settingsModal.classList.add('active');
      
      // Load current settings
      const apiEndpoint = document.getElementById('apiEndpoint');
      const speechRegion = document.getElementById('speechRegion');
      const autoApprove = document.getElementById('autoApprove');
      
      if (apiEndpoint) {
        apiEndpoint.value = window.WellConfig.api.endpoint;
      }
      if (speechRegion) {
        speechRegion.value = window.WellConfig.speech.region;
      }
      if (autoApprove) {
        autoApprove.checked = window.WellConfig.features.autoApproval;
      }
    }
  }

  closeSettings() {
    if (this.elements.settingsModal) {
      this.elements.settingsModal.classList.remove('active');
    }
  }

  saveSettings() {
    try {
      const apiEndpoint = document.getElementById('apiEndpoint');
      const speechRegion = document.getElementById('speechRegion');
      const autoApprove = document.getElementById('autoApprove');
      
      if (apiEndpoint && apiEndpoint.value) {
        window.WellConfig.api.endpoint = apiEndpoint.value;
      }
      if (speechRegion && speechRegion.value) {
        window.WellConfig.speech.region = speechRegion.value;
      }
      if (autoApprove) {
        window.WellConfig.features.autoApproval = autoApprove.checked;
      }
      
      // Save to localStorage
      localStorage.setItem('wellconfig', JSON.stringify(window.WellConfig));
      
      this.showToast('Settings saved successfully', 'success');
      this.closeSettings();
      
    } catch (error) {
      this.log('Failed to save settings:', error);
      this.showToast('Failed to save settings', 'error');
    }
  }

  showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icon = this.getToastIcon(type);
    toast.innerHTML = `
      <div class="toast-content">
        <i class="${icon}"></i>
        <span>${this.escapeHtml(message)}</span>
      </div>
      <button class="toast-close">&times;</button>
    `;

    // Add close functionality
    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.addEventListener('click', () => {
      this.removeToast(toast);
    });

    container.appendChild(toast);

    // Auto-remove after duration
    setTimeout(() => {
      this.removeToast(toast);
    }, window.WellConfig.ui.toastDuration || 5000);

    // Trigger animation
    setTimeout(() => {
      toast.classList.add('active');
    }, 10);
  }

  removeToast(toast) {
    if (toast && toast.parentNode) {
      toast.classList.remove('active');
      setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 300);
    }
  }

  getToastIcon(type) {
    switch (type) {
      case 'success': return 'fas fa-check-circle';
      case 'error': return 'fas fa-exclamation-circle';
      case 'warning': return 'fas fa-exclamation-triangle';
      case 'info':
      default: return 'fas fa-info-circle';
    }
  }

  showErrorState(message) {
    this.updateConnectionStatus('error');
    
    // Update UI to show error state
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
      const errorBanner = document.createElement('div');
      errorBanner.className = 'error-banner';
      errorBanner.innerHTML = `
        <i class="fas fa-exclamation-triangle"></i>
        <span>Application Error: ${this.escapeHtml(message)}</span>
        <button onclick="location.reload()">Reload</button>
      `;
      
      mainContent.insertBefore(errorBanner, mainContent.firstChild);
    }
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  log(...args) {
    if (window.WellConfig.debug.enableLogging && window.WellConfig.debug.logToConsole) {
      console.log('[WellVoiceApp]', ...args);
    }
  }

  // Authentication Methods
  async checkAuthentication() {
    try {
      // Show auth status
      this.showAuthStatus('Initializing Microsoft authentication...');
      
      // Initialize Microsoft authentication service
      const result = await window.authService.initialize();
      
      if (result.success) {
        if (result.isAuthenticated) {
          // User is already signed in
          const userInfo = window.authService.getUserInfo();
          this.userSession = {
            email: userInfo.email,
            name: userInfo.name,
            userId: userInfo.id,
            tenantId: userInfo.tenantId,
            provider: 'microsoft'
          };
          this.isAuthenticated = true;
          this.hideAuthStatus();
          this.log('User already authenticated:', userInfo.name);
          return;
        } else {
          // User needs to sign in
          this.hideAuthStatus();
          this.isAuthenticated = false;
        }
      } else {
        // Authentication service failed to initialize
        this.showAuthError('Failed to initialize authentication: ' + result.error);
        this.isAuthenticated = false;
      }
    } catch (error) {
      this.log('Authentication check failed:', error);
      this.showAuthError('Authentication service unavailable');
      this.isAuthenticated = false;
    }
  }

  showLoginModal() {
    if (this.elements.loginModal) {
      this.elements.loginModal.classList.add('active');
      
      // Focus on access code field
      if (this.elements.accessCode) {
        setTimeout(() => {
          this.elements.accessCode.focus();
        }, 100);
      }
    }
  }

  hideLoginModal() {
    if (this.elements.loginModal) {
      this.elements.loginModal.classList.remove('active');
    }
  }

  async handleMicrosoftSignIn() {
    try {
      // Disable the button and show loading state
      this.elements.microsoftSignInBtn.disabled = true;
      this.elements.microsoftSignInBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing in...';
      this.showAuthStatus('Redirecting to Microsoft sign-in...');

      // Initiate Microsoft sign-in flow
      await window.authService.signIn();
      
      // Note: The page will redirect for authentication
      // After successful authentication, the page reloads and handleRedirectPromise in AuthService handles the response
      
    } catch (error) {
      this.log('Microsoft sign-in error:', error);
      this.showAuthError(window.authService.handleError(error));
      
      // Re-enable the button
      this.elements.microsoftSignInBtn.disabled = false;
      this.elements.microsoftSignInBtn.innerHTML = '<i class="fab fa-microsoft"></i> Sign in with Microsoft';
      this.hideAuthStatus();
    }
  }

  async handleTestLogin() {
    // Emergency test login for development/debugging only
    if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
      this.showToast('Test login only available in development', 'warning');
      return;
    }

    try {
      this.userSession = {
        email: 'test@thewell.com',
        name: 'Test User',
        userId: 'test-user-id',
        tenantId: 'test-tenant-id',
        provider: 'test'
      };

      this.isAuthenticated = true;
      this.hideLoginModal();
      this.showToast('Test login successful!', 'success');
      
      // Initialize components now
      await this.initializeComponents();
      this.bindEvents();
      this.updateConnectionStatus('ready');
      
    } catch (error) {
      this.log('Test login error:', error);
      this.showToast('Test login failed', 'error');
    }
  }

  // Get authorization header for API calls
  async getAuthorizationHeader() {
    if (!this.isAuthenticated) {
      throw new Error('User not authenticated');
    }

    if (this.userSession?.provider === 'microsoft') {
      // Get Microsoft access token
      try {
        return await window.authService.getAuthorizationHeader();
      } catch (error) {
        this.log('Failed to get Microsoft access token:', error);
        throw new Error('Failed to get access token');
      }
    } else if (this.userSession?.provider === 'test') {
      // Test mode - return a fake token
      return 'Bearer test-token-' + Date.now();
    } else {
      throw new Error('Unknown authentication provider');
    }
  }

  generateSessionId() {
    return Math.random().toString(36).substr(2, 9) + Date.now().toString(36);
  }

  // Authentication UI Helper Methods
  showAuthStatus(message) {
    if (this.elements.authStatus && this.elements.authStatusText) {
      this.elements.authStatusText.textContent = message;
      this.elements.authStatus.style.display = 'block';
    }
    this.hideAuthError();
  }

  hideAuthStatus() {
    if (this.elements.authStatus) {
      this.elements.authStatus.style.display = 'none';
    }
  }

  showAuthError(message) {
    if (this.elements.authError && this.elements.authErrorText) {
      this.elements.authErrorText.textContent = message;
      this.elements.authError.style.display = 'block';
    }
    this.hideAuthStatus();
    
    // Show test login button in development
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      if (this.elements.testLoginBtn) {
        this.elements.testLoginBtn.style.display = 'inline-block';
      }
    }
  }

  hideAuthError() {
    if (this.elements.authError) {
      this.elements.authError.style.display = 'none';
    }
  }

  async logout() {
    try {
      // Sign out from Microsoft
      await window.authService.signOut();
      
    } catch (error) {
      this.log('Logout error:', error);
    }
    
    // Clean up local state
    this.isAuthenticated = false;
    this.userSession = null;
    
    if (this.voiceHandler) {
      this.voiceHandler.dispose();
      this.voiceHandler = null;
    }
    
    this.showLoginModal();
    this.showToast('You have been logged out', 'info');
  }

  // Cleanup
  dispose() {
    if (this.voiceHandler) {
      this.voiceHandler.dispose();
    }
  }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  // Load saved config from localStorage
  try {
    const savedConfig = localStorage.getItem('wellconfig');
    if (savedConfig) {
      const config = JSON.parse(savedConfig);
      // Merge with default config
      Object.assign(window.WellConfig, config);
    }
  } catch (error) {
    console.warn('Failed to load saved config:', error);
  }

  // Start the application
  window.wellVoiceApp = new WellVoiceApp();
});

// Handle page unload
window.addEventListener('beforeunload', () => {
  if (window.wellVoiceApp) {
    window.wellVoiceApp.dispose();
  }
});