// API Client - Backend Integration with Azure AD Authentication
class ApiClient {
  constructor() {
    this.config = window.WellConfig.api;
    this.baseUrl = this.config.endpoint;
    this.apiKey = this.config.key;
    this.timeout = this.config.timeout;
    
    // User authentication state
    this.user = null;
    this.isAuthenticated = false;
    
    // Request interceptors
    this.requestInterceptors = [];
    this.responseInterceptors = [];
    
    // WebSocket connection for real-time updates
    this.ws = null;
    this.wsReconnectAttempts = 0;
    
    // Initialize authentication state
    this.initializeAuth();
  }

  // HTTP Methods
  async get(endpoint, params = {}) {
    return this.request('GET', endpoint, null, params);
  }

  async post(endpoint, data = {}, params = {}) {
    return this.request('POST', endpoint, data, params);
  }

  async put(endpoint, data = {}, params = {}) {
    return this.request('PUT', endpoint, data, params);
  }

  async delete(endpoint, params = {}) {
    return this.request('DELETE', endpoint, null, params);
  }

  async request(method, endpoint, data = null, params = {}) {
    try {
      // Build URL
      const url = new URL(endpoint, this.baseUrl);
      
      // Add query parameters
      Object.keys(params).forEach(key => {
        if (params[key] !== undefined && params[key] !== null) {
          url.searchParams.append(key, params[key]);
        }
      });

      // Prepare request options
      const options = {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': this.apiKey,
          'User-Agent': 'WellVoiceUI/1.0'
        },
        signal: AbortSignal.timeout(this.timeout)
      };

      // Add body for POST/PUT requests
      if (data && (method === 'POST' || method === 'PUT')) {
        if (data instanceof FormData) {
          delete options.headers['Content-Type']; // Let browser set it
          options.body = data;
        } else {
          options.body = JSON.stringify(data);
        }
      }

      // Apply request interceptors
      for (const interceptor of this.requestInterceptors) {
        await interceptor(options);
      }

      this.log('Making request:', method, url.toString());
      
      // Make request
      const response = await fetch(url, options);
      
      // Apply response interceptors
      for (const interceptor of this.responseInterceptors) {
        await interceptor(response);
      }

      // Handle response
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const contentType = response.headers.get('content-type');
      let result;
      
      if (contentType && contentType.includes('application/json')) {
        result = await response.json();
      } else {
        result = await response.text();
      }

      this.log('Request successful:', method, endpoint, result);
      return result;

    } catch (error) {
      this.log('Request failed:', method, endpoint, error);
      
      if (error.name === 'TimeoutError') {
        throw new Error('Request timed out. Please check your connection.');
      } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
        throw new Error('Unable to connect to server. Please check your internet connection.');
      }
      
      throw error;
    }
  }

  // Authentication API
  async initializeAuth() {
    try {
      // Check if user is already authenticated
      const userInfo = await this.getUserInfo();
      if (userInfo) {
        this.user = userInfo;
        this.isAuthenticated = true;
        this.log('User authenticated:', userInfo.user_email);
        this.initializeWebSocket();
      } else {
        this.log('User not authenticated');
      }
    } catch (error) {
      this.log('Auth initialization failed:', error);
      this.isAuthenticated = false;
    }
  }

  async getUserInfo() {
    try {
      return await this.get('/api/user/info');
    } catch (error) {
      return null; // User not authenticated
    }
  }

  async getAuthUrl() {
    return this.get('/auth/login');
  }

  async logout() {
    try {
      await this.post('/api/user/logout');
      this.user = null;
      this.isAuthenticated = false;
      
      // Close WebSocket
      if (this.ws) {
        this.ws.close();
        this.ws = null;
      }
      
      this.log('User logged out');
      return true;
    } catch (error) {
      this.log('Logout failed:', error);
      return false;
    }
  }

  async getAuthenticatedUsers() {
    return this.get('/api/auth/users');
  }

  // Email Processing API
  async processEmail(emailData) {
    return this.post('/intake/email', emailData);
  }

  async getEmailQueue() {
    return this.get('/api/emails/queue');
  }

  async getEmailById(emailId) {
    return this.get(`/api/emails/${emailId}`);
  }

  async approveExtraction(emailId, extractedData, edits = {}) {
    return this.put(`/api/emails/${emailId}/approve`, {
      extractedData,
      edits,
      timestamp: new Date().toISOString()
    });
  }

  async rejectExtraction(emailId, reason) {
    return this.put(`/api/emails/${emailId}/reject`, {
      reason,
      timestamp: new Date().toISOString()
    });
  }

  async previewExtraction(emailId, extractedData) {
    return this.post(`/api/emails/${emailId}/preview`, extractedData);
  }

  // Voice Command Processing
  async processVoiceCommand(command, context = {}) {
    return this.post('/api/voice/process', {
      command,
      context,
      timestamp: new Date().toISOString()
    });
  }

  // Learning and Feedback API
  async submitFeedback(emailId, originalData, correctedData, confidence) {
    return this.post('/api/learning/feedback', {
      emailId,
      originalData,
      correctedData,
      confidence,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent
    });
  }

  async getAccuracyMetrics(timeframe = '24h') {
    return this.get('/api/metrics/accuracy', { timeframe });
  }

  async getLearningProgress() {
    return this.get('/api/learning/progress');
  }

  // Cache and Performance API
  async getCacheStatus() {
    return this.get('/cache/status');
  }

  async clearCache(pattern = null) {
    return this.post('/cache/invalidate', pattern ? { pattern } : {});
  }

  async warmupCache() {
    return this.post('/cache/warmup');
  }

  // Health and Status
  async getHealthStatus() {
    return this.get('/health');
  }

  async getSystemMetrics() {
    return this.get('/api/metrics/system');
  }

  // File Upload
  async uploadFile(file, metadata = {}) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('metadata', JSON.stringify(metadata));
    
    return this.post('/api/files/upload', formData);
  }

  // WebSocket Real-time Updates  
  initializeWebSocket() {
    if (!window.WebSocket) {
      this.log('WebSocket not supported');
      return;
    }

    if (!this.isAuthenticated || !this.user) {
      this.log('Cannot initialize WebSocket - user not authenticated');
      return;
    }

    try {
      const wsConfig = window.WellConfig.websocket;
      const userId = this.user.user_id;
      const wsUrl = this.baseUrl.replace(/^http/, 'ws') + `/ws/queue/${userId}`;
      
      this.log('Connecting to WebSocket:', wsUrl);
      this.ws = new WebSocket(wsUrl);
      
      this.ws.onopen = () => {
        this.log('WebSocket connected for user:', userId);
        this.wsReconnectAttempts = 0;
        
        // Request initial queue update
        this.ws.send(JSON.stringify({
          type: 'request_update'
        }));
        
        // Start heartbeat
        this.startHeartbeat();
        
        // Notify UI
        this.dispatchEvent('websocketConnected', { userId });
      };
      
      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.handleWebSocketMessage(message);
        } catch (error) {
          this.log('Failed to parse WebSocket message:', error);
        }
      };
      
      this.ws.onclose = (event) => {
        this.log('WebSocket disconnected:', event.code, event.reason);
        this.scheduleReconnect();
      };
      
      this.ws.onerror = (error) => {
        this.log('WebSocket error:', error);
      };
      
    } catch (error) {
      this.log('Failed to initialize WebSocket:', error);
    }
  }

  handleWebSocketMessage(message) {
    this.log('WebSocket message:', message);
    
    switch (message.type) {
      case 'queue_update':
        this.dispatchEvent('queueUpdate', message.data);
        break;
      
      case 'email_notification':
        this.dispatchEvent('emailNotification', {
          notification_type: message.notification_type,
          email_id: message.email_id,
          data: message.data,
          timestamp: message.timestamp
        });
        break;
      
      case 'pong':
        // Heartbeat response
        break;
      
      case 'processing_status':
        this.dispatchEvent('processingStatus', message.data);
        break;
      
      case 'system_alert':
        this.dispatchEvent('systemAlert', message.data);
        break;
      
      default:
        this.log('Unknown WebSocket message type:', message.type);
    }
  }

  scheduleReconnect() {
    if (this.wsReconnectAttempts >= window.WellConfig.websocket.maxReconnectAttempts) {
      this.log('Max WebSocket reconnect attempts reached');
      return;
    }

    const delay = window.WellConfig.websocket.reconnectInterval * Math.pow(2, this.wsReconnectAttempts);
    this.wsReconnectAttempts++;
    
    this.log(`Scheduling WebSocket reconnect in ${delay}ms (attempt ${this.wsReconnectAttempts})`);
    
    setTimeout(() => {
      this.initializeWebSocket();
    }, delay);
  }

  startHeartbeat() {
    const interval = window.WellConfig.websocket.heartbeatInterval;
    
    this.heartbeatInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, interval);
  }
  
  // Request real-time queue update
  requestQueueUpdate() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'request_update' }));
    }
  }

  stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  // Event System for WebSocket messages
  dispatchEvent(eventType, data) {
    const event = new CustomEvent(`wellapi:${eventType}`, {
      detail: data,
      bubbles: true
    });
    
    document.dispatchEvent(event);
  }

  addEventListener(eventType, handler) {
    document.addEventListener(`wellapi:${eventType}`, handler);
  }

  removeEventListener(eventType, handler) {
    document.removeEventListener(`wellapi:${eventType}`, handler);
  }

  // Request/Response Interceptors
  addRequestInterceptor(interceptor) {
    this.requestInterceptors.push(interceptor);
  }

  addResponseInterceptor(interceptor) {
    this.responseInterceptors.push(interceptor);
  }

  // Utility Methods
  buildFormData(data) {
    const formData = new FormData();
    
    Object.keys(data).forEach(key => {
      const value = data[key];
      if (value instanceof File) {
        formData.append(key, value);
      } else if (typeof value === 'object') {
        formData.append(key, JSON.stringify(value));
      } else {
        formData.append(key, value);
      }
    });
    
    return formData;
  }

  log(...args) {
    if (window.WellConfig.debug.enableLogging && window.WellConfig.debug.logToConsole) {
      console.log('[ApiClient]', ...args);
    }
  }

  // Cleanup
  dispose() {
    this.stopHeartbeat();
    
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  // Getters
  get isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }

  get connectionState() {
    if (!this.ws) return 'disconnected';
    
    switch (this.ws.readyState) {
      case WebSocket.CONNECTING: return 'connecting';
      case WebSocket.OPEN: return 'connected';
      case WebSocket.CLOSING: return 'closing';
      case WebSocket.CLOSED: return 'disconnected';
      default: return 'unknown';
    }
  }
}

// Export for use in main app
window.ApiClient = ApiClient;