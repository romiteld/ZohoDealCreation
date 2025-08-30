// Configuration for Well Voice UI
window.WellConfig = {
  // API Configuration
  api: {
    endpoint: 'https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io',
    key: 'e49d2dbcfa4547f5bdc371c5c06aae2afd06914e16e680a7f31c5fc5384ba384',
    timeout: 30000 // 30 seconds
  },

  // Azure Speech Service Configuration
  speech: {
    key: '892f34c92b764c3dbe8e08d204aa85ad',
    region: 'eastus',
    language: 'en-US',
    
    // Recognition settings
    recognition: {
      continuous: true,
      interimResults: true,
      maxSilenceTimeoutMs: 3000,
      endSilenceTimeoutMs: 1500
    },
    
    // Synthesis settings
    synthesis: {
      voice: 'en-US-JennyNeural',
      rate: '+0%',
      pitch: '+0%'
    }
  },

  // Voice Commands Configuration
  commands: {
    // Email processing commands
    processEmail: ['process email', 'analyze email', 'extract data'],
    approveExtraction: ['approve', 'looks good', 'accept', 'confirm'],
    rejectExtraction: ['reject', 'cancel', 'decline', 'not correct'],
    editField: ['edit', 'change', 'modify', 'update'],
    
    // Navigation commands
    nextEmail: ['next email', 'skip', 'move on'],
    previousEmail: ['previous email', 'go back'],
    showQueue: ['show queue', 'email queue', 'pending emails'],
    showMetrics: ['show metrics', 'show stats', 'analytics'],
    
    // Settings commands
    openSettings: ['open settings', 'preferences', 'configuration'],
    toggleMode: ['toggle continuous', 'continuous mode', 'listening mode']
  },

  // UI Configuration
  ui: {
    autoRefreshInterval: 5000, // 5 seconds
    toastDuration: 5000, // 5 seconds
    maxEmailsInQueue: 50,
    enableAnimations: true,
    theme: 'light' // 'light' or 'dark'
  },

  // Learning System Configuration
  learning: {
    enableFeedbackTracking: true,
    confidenceThreshold: 0.8, // Auto-approve if confidence > 80%
    autoSaveEdits: true,
    trackUserPreferences: true
  },

  // WebSocket Configuration
  websocket: {
    reconnectInterval: 3000, // 3 seconds
    maxReconnectAttempts: 5,
    heartbeatInterval: 30000 // 30 seconds
  },

  // Feature Flags
  features: {
    continuousListening: true,
    realTimeTranscription: true,
    autoApproval: false,
    batchProcessing: true,
    voiceFeedback: true,
    darkMode: false
  },

  // Debug Configuration
  debug: {
    enableLogging: true,
    logLevel: 'info', // 'debug', 'info', 'warn', 'error'
    logToConsole: true,
    logToServer: false
  }
};

// Environment-specific overrides
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
  // Development overrides
  window.WellConfig.debug.logLevel = 'debug';
  window.WellConfig.ui.autoRefreshInterval = 2000;
  window.WellConfig.features.darkMode = true;
}

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = window.WellConfig;
}