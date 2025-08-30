// Learning Tracker - Human-in-the-loop Learning System
class LearningTracker {
  constructor(apiClient) {
    this.apiClient = apiClient;
    this.sessionData = {
      corrections: [],
      approvals: [],
      rejections: [],
      voiceCommands: [],
      startTime: new Date()
    };
    
    // Learning metrics
    this.metrics = {
      accuracy: 0,
      improvementRate: 0,
      userSatisfaction: 0,
      commonCorrections: {},
      learningProgress: []
    };
    
    // Event tracking
    this.events = [];
    this.maxEvents = 1000;
    
    this.initializeTracking();
  }

  initializeTracking() {
    this.log('Initializing learning tracker');
    
    // Load existing progress
    this.loadLearningProgress();
    
    // Set up periodic sync
    this.syncInterval = setInterval(() => {
      this.syncWithServer();
    }, 30000); // Sync every 30 seconds
    
    // Listen for user interactions
    this.bindEvents();
  }

  bindEvents() {
    // Track all user interactions
    document.addEventListener('click', (e) => this.trackUserAction('click', e));
    document.addEventListener('keydown', (e) => this.trackUserAction('keydown', e));
    
    // Track voice commands
    document.addEventListener('wellvoice:command', (e) => {
      this.trackVoiceCommand(e.detail);
    });
    
    // Track data corrections
    document.addEventListener('welldata:correction', (e) => {
      this.trackDataCorrection(e.detail);
    });
    
    // Track approvals/rejections
    document.addEventListener('welldata:approval', (e) => {
      this.trackApproval(e.detail);
    });
    
    document.addEventListener('welldata:rejection', (e) => {
      this.trackRejection(e.detail);
    });
    
    // Track accuracy feedback
    document.addEventListener('welllearning:feedback', (e) => {
      this.processFeedback(e.detail);
    });
  }

  trackVoiceCommand(commandData) {
    const event = {
      type: 'voice_command',
      timestamp: new Date(),
      data: {
        command: commandData.type,
        transcript: commandData.transcript,
        confidence: commandData.confidence,
        processingTime: commandData.processingTime,
        successful: commandData.successful !== false
      }
    };
    
    this.addEvent(event);
    this.sessionData.voiceCommands.push(event);
    
    this.log('Voice command tracked:', commandData.type);
  }

  trackDataCorrection(correctionData) {
    const { emailId, field, originalValue, correctedValue, confidence } = correctionData;
    
    const correction = {
      type: 'data_correction',
      timestamp: new Date(),
      emailId,
      field,
      originalValue,
      correctedValue,
      confidence,
      userId: this.getUserId()
    };
    
    this.addEvent(correction);
    this.sessionData.corrections.push(correction);
    
    // Update common corrections tracking
    const correctionKey = `${field}:${originalValue}->${correctedValue}`;
    this.metrics.commonCorrections[correctionKey] = 
      (this.metrics.commonCorrections[correctionKey] || 0) + 1;
    
    // Send feedback to API immediately for high-impact corrections
    if (this.isHighImpactCorrection(field, originalValue, correctedValue)) {
      this.submitFeedbackToServer(correction);
    }
    
    this.log('Data correction tracked:', field, originalValue, '->', correctedValue);
  }

  trackApproval(approvalData) {
    const { emailId, extractedData, confidence, hasEdits, processingTime } = approvalData;
    
    const approval = {
      type: 'approval',
      timestamp: new Date(),
      emailId,
      confidence,
      hasEdits: hasEdits || false,
      editCount: hasEdits ? Object.keys(approvalData.edits || {}).length : 0,
      processingTime,
      userId: this.getUserId()
    };
    
    this.addEvent(approval);
    this.sessionData.approvals.push(approval);
    
    // Update accuracy metrics
    this.updateAccuracyMetrics(approval);
    
    this.log('Approval tracked:', emailId, 'confidence:', confidence);
  }

  trackRejection(rejectionData) {
    const { emailId, reason, confidence, issues } = rejectionData;
    
    const rejection = {
      type: 'rejection',
      timestamp: new Date(),
      emailId,
      reason,
      confidence,
      issues: issues || [],
      userId: this.getUserId()
    };
    
    this.addEvent(rejection);
    this.sessionData.rejections.push(rejection);
    
    // Analyze rejection patterns
    this.analyzeRejectionPattern(rejection);
    
    this.log('Rejection tracked:', emailId, 'reason:', reason);
  }

  trackUserAction(actionType, event) {
    // Only track meaningful interactions
    if (!this.isTrackableElement(event.target)) {
      return;
    }
    
    const action = {
      type: 'user_action',
      timestamp: new Date(),
      actionType,
      element: event.target.tagName,
      elementId: event.target.id,
      elementClass: event.target.className,
      key: actionType === 'keydown' ? event.key : null
    };
    
    this.addEvent(action);
  }

  isTrackableElement(element) {
    // Track buttons, inputs, and content editable elements
    return element.tagName === 'BUTTON' ||
           element.tagName === 'INPUT' ||
           element.tagName === 'SELECT' ||
           element.contentEditable === 'true' ||
           element.classList.contains('trackable');
  }

  isHighImpactCorrection(field, originalValue, correctedValue) {
    // Define high-impact fields that should trigger immediate learning
    const highImpactFields = ['firstName', 'lastName', 'email', 'company', 'jobTitle'];
    
    return highImpactFields.includes(field) ||
           (originalValue === '' && correctedValue !== '') ||
           Math.abs(originalValue.length - correctedValue.length) > 5;
  }

  updateAccuracyMetrics(approval) {
    const totalApprovals = this.sessionData.approvals.length;
    const approvalsWithoutEdits = this.sessionData.approvals.filter(a => !a.hasEdits).length;
    
    // Calculate accuracy rate (approvals without edits / total approvals)
    this.metrics.accuracy = totalApprovals > 0 ? 
      (approvalsWithoutEdits / totalApprovals) * 100 : 0;
    
    // Calculate improvement rate based on recent vs older approvals
    if (totalApprovals >= 10) {
      const recentAccuracy = this.calculateRecentAccuracy();
      const historicalAccuracy = this.calculateHistoricalAccuracy();
      this.metrics.improvementRate = recentAccuracy - historicalAccuracy;
    }
    
    this.log('Updated accuracy metrics:', this.metrics.accuracy.toFixed(1) + '%');
  }

  calculateRecentAccuracy() {
    const recentApprovals = this.sessionData.approvals.slice(-5); // Last 5 approvals
    const recentWithoutEdits = recentApprovals.filter(a => !a.hasEdits).length;
    return (recentWithoutEdits / recentApprovals.length) * 100;
  }

  calculateHistoricalAccuracy() {
    if (this.sessionData.approvals.length < 10) return 0;
    
    const historicalApprovals = this.sessionData.approvals.slice(0, -5); // All but last 5
    const historicalWithoutEdits = historicalApprovals.filter(a => !a.hasEdits).length;
    return (historicalWithoutEdits / historicalApprovals.length) * 100;
  }

  analyzeRejectionPattern(rejection) {
    // Analyze common rejection reasons
    const reasons = this.sessionData.rejections.map(r => r.reason);
    const reasonCounts = {};
    
    reasons.forEach(reason => {
      if (reason) {
        reasonCounts[reason] = (reasonCounts[reason] || 0) + 1;
      }
    });
    
    // Identify most common rejection reasons
    const mostCommonReason = Object.entries(reasonCounts)
      .sort(([,a], [,b]) => b - a)[0];
    
    if (mostCommonReason && mostCommonReason[1] > 2) {
      this.log('Common rejection pattern detected:', mostCommonReason[0]);
      
      // Trigger learning improvement for this pattern
      this.triggerPatternImprovement(mostCommonReason[0]);
    }
  }

  triggerPatternImprovement(pattern) {
    // Send pattern analysis to backend for model improvement
    const improvementData = {
      pattern,
      frequency: this.sessionData.rejections.filter(r => r.reason === pattern).length,
      examples: this.sessionData.rejections
        .filter(r => r.reason === pattern)
        .slice(-3) // Last 3 examples
        .map(r => ({
          emailId: r.emailId,
          timestamp: r.timestamp,
          confidence: r.confidence
        }))
    };
    
    this.submitPatternImprovement(improvementData);
  }

  async submitPatternImprovement(data) {
    try {
      await this.apiClient.post('/api/learning/pattern-improvement', data);
      this.log('Pattern improvement submitted:', data.pattern);
    } catch (error) {
      this.log('Failed to submit pattern improvement:', error);
    }
  }

  processFeedback(feedbackData) {
    const { type, rating, comment, context } = feedbackData;
    
    const feedback = {
      type: 'user_feedback',
      timestamp: new Date(),
      feedbackType: type,
      rating,
      comment,
      context,
      userId: this.getUserId()
    };
    
    this.addEvent(feedback);
    
    // Update user satisfaction metric
    if (rating !== undefined) {
      this.updateSatisfactionMetric(rating);
    }
    
    this.log('User feedback processed:', type, rating);
  }

  updateSatisfactionMetric(rating) {
    const feedbacks = this.events
      .filter(e => e.type === 'user_feedback' && e.rating !== undefined)
      .map(e => e.rating);
    
    if (feedbacks.length > 0) {
      this.metrics.userSatisfaction = 
        feedbacks.reduce((sum, r) => sum + r, 0) / feedbacks.length;
    }
  }

  addEvent(event) {
    this.events.push(event);
    
    // Keep only recent events
    if (this.events.length > this.maxEvents) {
      this.events = this.events.slice(-this.maxEvents);
    }
    
    // Auto-save important events
    if (this.isImportantEvent(event)) {
      this.saveEventToLocal(event);
    }
  }

  isImportantEvent(event) {
    return event.type === 'data_correction' ||
           event.type === 'approval' ||
           event.type === 'rejection' ||
           event.type === 'user_feedback';
  }

  saveEventToLocal(event) {
    try {
      const key = `welllearning_${event.type}_${Date.now()}`;
      localStorage.setItem(key, JSON.stringify(event));
    } catch (error) {
      this.log('Failed to save event to localStorage:', error);
    }
  }

  async syncWithServer() {
    if (!window.navigator.onLine) {
      this.log('Offline, skipping sync');
      return;
    }
    
    try {
      // Send session data to server
      const syncData = {
        sessionId: this.getSessionId(),
        timestamp: new Date(),
        metrics: this.metrics,
        summary: this.getSessionSummary(),
        events: this.events.filter(e => e.timestamp > this.lastSyncTime)
      };
      
      await this.apiClient.post('/api/learning/sync', syncData);
      this.lastSyncTime = new Date();
      
      // Get updated learning progress from server
      const progress = await this.apiClient.getLearningProgress();
      this.updateLearningProgress(progress);
      
      this.log('Learning data synced successfully');
      
    } catch (error) {
      this.log('Failed to sync learning data:', error);
    }
  }

  updateLearningProgress(progress) {
    this.metrics.learningProgress = progress.progress || [];
    
    // Update UI metrics
    this.updateMetricsDisplay(progress);
  }

  updateMetricsDisplay(progress) {
    // Update accuracy rate
    const accuracyElement = document.getElementById('accuracyRate');
    if (accuracyElement && progress.accuracy !== undefined) {
      accuracyElement.textContent = Math.round(progress.accuracy) + '%';
    }
    
    // Update processing time
    const processingTimeElement = document.getElementById('processingTime');
    if (processingTimeElement && progress.averageProcessingTime !== undefined) {
      processingTimeElement.textContent = progress.averageProcessingTime.toFixed(1) + 's';
    }
    
    // Update processed count
    const processedElement = document.getElementById('processedToday');
    if (processedElement && progress.processedToday !== undefined) {
      processedElement.textContent = progress.processedToday.toString();
    }
  }

  async submitFeedbackToServer(correctionData) {
    try {
      await this.apiClient.submitFeedback(
        correctionData.emailId,
        { [correctionData.field]: correctionData.originalValue },
        { [correctionData.field]: correctionData.correctedValue },
        correctionData.confidence
      );
      
      this.log('Feedback submitted to server:', correctionData.field);
      
    } catch (error) {
      this.log('Failed to submit feedback:', error);
    }
  }

  getSessionSummary() {
    return {
      duration: Date.now() - this.sessionData.startTime.getTime(),
      totalEvents: this.events.length,
      corrections: this.sessionData.corrections.length,
      approvals: this.sessionData.approvals.length,
      rejections: this.sessionData.rejections.length,
      voiceCommands: this.sessionData.voiceCommands.length,
      accuracy: this.metrics.accuracy,
      userSatisfaction: this.metrics.userSatisfaction
    };
  }

  loadLearningProgress() {
    try {
      const saved = localStorage.getItem('welllearning_progress');
      if (saved) {
        const progress = JSON.parse(saved);
        this.metrics.learningProgress = progress.learningProgress || [];
        this.lastSyncTime = new Date(progress.lastSyncTime || 0);
      }
    } catch (error) {
      this.log('Failed to load learning progress:', error);
    }
  }

  saveLearningProgress() {
    try {
      const data = {
        learningProgress: this.metrics.learningProgress,
        lastSyncTime: this.lastSyncTime || new Date()
      };
      
      localStorage.setItem('welllearning_progress', JSON.stringify(data));
    } catch (error) {
      this.log('Failed to save learning progress:', error);
    }
  }

  // Utility methods
  getUserId() {
    let userId = localStorage.getItem('welllearning_userid');
    if (!userId) {
      userId = 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
      localStorage.setItem('welllearning_userid', userId);
    }
    return userId;
  }

  getSessionId() {
    if (!this.sessionId) {
      this.sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    return this.sessionId;
  }

  // Public API for triggering events
  recordCorrection(emailId, field, originalValue, correctedValue, confidence) {
    this.trackDataCorrection({
      emailId,
      field,
      originalValue,
      correctedValue,
      confidence
    });
  }

  recordApproval(emailId, extractedData, confidence, edits) {
    this.trackApproval({
      emailId,
      extractedData,
      confidence,
      hasEdits: edits && Object.keys(edits).length > 0,
      edits
    });
  }

  recordRejection(emailId, reason, confidence, issues) {
    this.trackRejection({
      emailId,
      reason,
      confidence,
      issues
    });
  }

  recordFeedback(type, rating, comment, context) {
    this.processFeedback({
      type,
      rating,
      comment,
      context
    });
  }

  // Analytics methods
  getAccuracyTrend(days = 7) {
    const cutoff = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
    const recentApprovals = this.sessionData.approvals.filter(a => 
      new Date(a.timestamp) > cutoff
    );
    
    if (recentApprovals.length === 0) return 0;
    
    const accurate = recentApprovals.filter(a => !a.hasEdits).length;
    return (accurate / recentApprovals.length) * 100;
  }

  getCommonCorrections(limit = 5) {
    return Object.entries(this.metrics.commonCorrections)
      .sort(([,a], [,b]) => b - a)
      .slice(0, limit)
      .map(([correction, count]) => ({ correction, count }));
  }

  getVoiceCommandAccuracy() {
    const totalCommands = this.sessionData.voiceCommands.length;
    if (totalCommands === 0) return 0;
    
    const successfulCommands = this.sessionData.voiceCommands.filter(c => 
      c.data.successful
    ).length;
    
    return (successfulCommands / totalCommands) * 100;
  }

  log(...args) {
    if (window.WellConfig.debug.enableLogging && window.WellConfig.debug.logToConsole) {
      console.log('[LearningTracker]', ...args);
    }
  }

  // Cleanup
  dispose() {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
    }
    
    // Save final progress
    this.saveLearningProgress();
    
    // Final sync
    this.syncWithServer();
  }

  // Getters
  get currentMetrics() {
    return { ...this.metrics };
  }

  get sessionStats() {
    return this.getSessionSummary();
  }
}

// Export for use in main app
window.LearningTracker = LearningTracker;