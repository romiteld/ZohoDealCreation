// Preview Editor - Deal Preview and Approval Interface
class PreviewEditor {
  constructor(apiClient) {
    this.apiClient = apiClient;
    this.currentEmail = null;
    this.originalData = null;
    this.editedData = null;
    this.isEditing = false;
    
    // DOM elements
    this.previewContent = null;
    this.approveBtn = null;
    this.rejectBtn = null;
    
    // Event callbacks
    this.onDataChanged = null;
    this.onApproved = null;
    this.onRejected = null;
    
    this.initializeElements();
    this.bindEvents();
  }

  initializeElements() {
    this.previewContent = document.getElementById('previewContent');
    this.approveBtn = document.getElementById('approveBtn');
    this.rejectBtn = document.getElementById('rejectBtn');
  }

  bindEvents() {
    if (this.approveBtn) {
      this.approveBtn.addEventListener('click', () => this.approveExtraction());
    }
    
    if (this.rejectBtn) {
      this.rejectBtn.addEventListener('click', () => this.rejectExtraction());
    }
    
    // Listen for voice commands
    document.addEventListener('wellvoice:command', (event) => {
      this.handleVoiceCommand(event.detail);
    });
  }

  async loadEmailPreview(emailId) {
    try {
      this.log('Loading email preview:', emailId);
      
      // Show loading state
      this.showLoadingState();
      
      // Fetch email data
      const emailData = await this.apiClient.getEmailById(emailId);
      
      if (!emailData) {
        throw new Error('Email not found');
      }
      
      this.currentEmail = emailData;
      this.originalData = emailData.extractedData;
      this.editedData = { ...this.originalData }; // Deep copy
      
      // Render preview
      this.renderPreview();
      
      // Enable action buttons
      this.enableActionButtons();
      
      this.log('Email preview loaded successfully');
      
    } catch (error) {
      this.log('Failed to load email preview:', error);
      this.showErrorState(error.message);
    }
  }

  renderPreview() {
    if (!this.currentEmail || !this.previewContent) {
      return;
    }

    const { email, extractedData, confidence, status } = this.currentEmail;
    
    this.previewContent.innerHTML = `
      <div class="preview-header">
        <div class="email-info">
          <h4>Email from ${email.sender}</h4>
          <p class="email-subject">${email.subject}</p>
          <div class="email-meta">
            <span class="confidence-badge confidence-${this.getConfidenceLevel(confidence)}">
              ${Math.round(confidence * 100)}% confidence
            </span>
            <span class="status-badge status-${status}">
              ${status.charAt(0).toUpperCase() + status.slice(1)}
            </span>
          </div>
        </div>
      </div>
      
      <div class="preview-tabs">
        <button class="tab-btn active" data-tab="extracted">Extracted Data</button>
        <button class="tab-btn" data-tab="original">Original Email</button>
        <button class="tab-btn" data-tab="comparison">Side-by-Side</button>
      </div>
      
      <div class="tab-content">
        <div class="tab-pane active" id="extracted-tab">
          ${this.renderExtractedData()}
        </div>
        <div class="tab-pane" id="original-tab">
          ${this.renderOriginalEmail()}
        </div>
        <div class="tab-pane" id="comparison-tab">
          ${this.renderComparison()}
        </div>
      </div>
    `;
    
    // Bind tab events
    this.bindTabEvents();
    
    // Bind edit events
    this.bindEditEvents();
  }

  renderExtractedData() {
    const data = this.editedData;
    
    return `
      <div class="extracted-data">
        <!-- Contact Information -->
        <div class="data-section">
          <h5 class="section-title">
            <i class="fas fa-user"></i>
            Contact Information
          </h5>
          <div class="field-group">
            <div class="field-item">
              <label class="field-label">First Name</label>
              <div class="field-value editable" 
                   contenteditable="true"
                   data-field="firstName"
                   data-original="${data.firstName || ''}">${data.firstName || 'Not provided'}</div>
            </div>
            <div class="field-item">
              <label class="field-label">Last Name</label>
              <div class="field-value editable" 
                   contenteditable="true"
                   data-field="lastName"
                   data-original="${data.lastName || ''}">${data.lastName || 'Not provided'}</div>
            </div>
            <div class="field-item">
              <label class="field-label">Email</label>
              <div class="field-value editable" 
                   contenteditable="true"
                   data-field="email"
                   data-original="${data.email || ''}">${data.email || 'Not provided'}</div>
            </div>
            <div class="field-item">
              <label class="field-label">Phone</label>
              <div class="field-value editable" 
                   contenteditable="true"
                   data-field="phone"
                   data-original="${data.phone || ''}">${data.phone || 'Not provided'}</div>
            </div>
          </div>
        </div>
        
        <!-- Company Information -->
        <div class="data-section">
          <h5 class="section-title">
            <i class="fas fa-building"></i>
            Company Information
          </h5>
          <div class="field-group">
            <div class="field-item">
              <label class="field-label">Company</label>
              <div class="field-value editable" 
                   contenteditable="true"
                   data-field="company"
                   data-original="${data.company || ''}">${data.company || 'Not provided'}</div>
            </div>
            <div class="field-item">
              <label class="field-label">Position</label>
              <div class="field-value editable" 
                   contenteditable="true"
                   data-field="position"
                   data-original="${data.position || ''}">${data.position || 'Not provided'}</div>
            </div>
            <div class="field-item">
              <label class="field-label">Industry</label>
              <div class="field-value editable" 
                   contenteditable="true"
                   data-field="industry"
                   data-original="${data.industry || ''}">${data.industry || 'Not provided'}</div>
            </div>
            <div class="field-item">
              <label class="field-label">Location</label>
              <div class="field-value editable" 
                   contenteditable="true"
                   data-field="location"
                   data-original="${data.location || ''}">${data.location || 'Not provided'}</div>
            </div>
          </div>
        </div>
        
        <!-- Job Requirements -->
        <div class="data-section">
          <h5 class="section-title">
            <i class="fas fa-briefcase"></i>
            Job Requirements
          </h5>
          <div class="field-group">
            <div class="field-item full-width">
              <label class="field-label">Job Title</label>
              <div class="field-value editable" 
                   contenteditable="true"
                   data-field="jobTitle"
                   data-original="${data.jobTitle || ''}">${data.jobTitle || 'Not provided'}</div>
            </div>
            <div class="field-item full-width">
              <label class="field-label">Job Description</label>
              <div class="field-value editable textarea" 
                   contenteditable="true"
                   data-field="jobDescription"
                   data-original="${data.jobDescription || ''}">${data.jobDescription || 'Not provided'}</div>
            </div>
            <div class="field-item">
              <label class="field-label">Salary Range</label>
              <div class="field-value editable" 
                   contenteditable="true"
                   data-field="salaryRange"
                   data-original="${data.salaryRange || ''}">${data.salaryRange || 'Not provided'}</div>
            </div>
            <div class="field-item">
              <label class="field-label">Experience Required</label>
              <div class="field-value editable" 
                   contenteditable="true"
                   data-field="experienceRequired"
                   data-original="${data.experienceRequired || ''}">${data.experienceRequired || 'Not provided'}</div>
            </div>
          </div>
        </div>
        
        <!-- Additional Details -->
        <div class="data-section">
          <h5 class="section-title">
            <i class="fas fa-info-circle"></i>
            Additional Details
          </h5>
          <div class="field-group">
            <div class="field-item">
              <label class="field-label">Source</label>
              <div class="field-value editable" 
                   contenteditable="true"
                   data-field="source"
                   data-original="${data.source || ''}">${data.source || 'Email Inbound'}</div>
            </div>
            <div class="field-item">
              <label class="field-label">Priority</label>
              <select class="field-value select-field" data-field="priority">
                <option value="low" ${data.priority === 'low' ? 'selected' : ''}>Low</option>
                <option value="medium" ${data.priority === 'medium' ? 'selected' : ''}>Medium</option>
                <option value="high" ${data.priority === 'high' ? 'selected' : ''}>High</option>
                <option value="urgent" ${data.priority === 'urgent' ? 'selected' : ''}>Urgent</option>
              </select>
            </div>
            <div class="field-item full-width">
              <label class="field-label">Notes</label>
              <div class="field-value editable textarea" 
                   contenteditable="true"
                   data-field="notes"
                   data-original="${data.notes || ''}">${data.notes || 'No additional notes'}</div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  renderOriginalEmail() {
    const email = this.currentEmail.email;
    
    return `
      <div class="original-email">
        <div class="email-headers">
          <div class="header-row">
            <strong>From:</strong> ${email.sender} &lt;${email.senderEmail}&gt;
          </div>
          <div class="header-row">
            <strong>Subject:</strong> ${email.subject}
          </div>
          <div class="header-row">
            <strong>Date:</strong> ${new Date(email.timestamp).toLocaleString()}
          </div>
        </div>
        
        <div class="email-body">
          <h6>Message:</h6>
          <div class="email-content">
            ${email.body.replace(/\n/g, '<br>')}
          </div>
        </div>
        
        ${email.attachments && email.attachments.length > 0 ? `
          <div class="email-attachments">
            <h6>Attachments:</h6>
            <ul class="attachment-list">
              ${email.attachments.map(att => `
                <li>
                  <i class="fas fa-paperclip"></i>
                  <a href="${att.url}" target="_blank">${att.name}</a>
                  <span class="file-size">(${this.formatFileSize(att.size)})</span>
                </li>
              `).join('')}
            </ul>
          </div>
        ` : ''}
      </div>
    `;
  }

  renderComparison() {
    return `
      <div class="comparison-view">
        <div class="comparison-panels">
          <div class="comparison-panel">
            <h6>Original Email</h6>
            <div class="panel-content">
              ${this.renderOriginalEmail()}
            </div>
          </div>
          <div class="comparison-panel">
            <h6>Extracted Data</h6>
            <div class="panel-content">
              ${this.renderExtractedData()}
            </div>
          </div>
        </div>
      </div>
    `;
  }

  bindTabEvents() {
    const tabBtns = this.previewContent.querySelectorAll('.tab-btn');
    const tabPanes = this.previewContent.querySelectorAll('.tab-pane');
    
    tabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const tabId = btn.dataset.tab;
        
        // Update button states
        tabBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        // Update pane visibility
        tabPanes.forEach(pane => {
          pane.classList.remove('active');
          if (pane.id === `${tabId}-tab`) {
            pane.classList.add('active');
          }
        });
      });
    });
  }

  bindEditEvents() {
    // Editable fields
    const editableFields = this.previewContent.querySelectorAll('.field-value.editable');
    editableFields.forEach(field => {
      field.addEventListener('input', (e) => this.handleFieldEdit(e));
      field.addEventListener('blur', (e) => this.handleFieldBlur(e));
      field.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          e.target.blur();
        }
      });
    });
    
    // Select fields
    const selectFields = this.previewContent.querySelectorAll('.select-field');
    selectFields.forEach(field => {
      field.addEventListener('change', (e) => this.handleFieldEdit(e));
    });
  }

  handleFieldEdit(event) {
    const field = event.target;
    const fieldName = field.dataset.field;
    const value = field.contentEditable === 'true' ? field.textContent.trim() : field.value;
    
    // Update edited data
    this.editedData[fieldName] = value;
    
    // Mark as edited
    field.classList.add('edited');
    this.isEditing = true;
    
    // Update UI to show changes
    this.updateChangeIndicators();
    
    // Notify listeners
    if (this.onDataChanged) {
      this.onDataChanged(fieldName, value, this.editedData);
    }
    
    this.log('Field edited:', fieldName, value);
  }

  handleFieldBlur(event) {
    const field = event.target;
    const fieldName = field.dataset.field;
    const value = field.textContent.trim();
    
    // Validate the field
    const isValid = this.validateField(fieldName, value);
    
    if (!isValid) {
      field.classList.add('invalid');
      this.showFieldError(field, `Invalid ${fieldName}`);
    } else {
      field.classList.remove('invalid');
      this.clearFieldError(field);
    }
  }

  handleVoiceCommand(command) {
    const { type, data } = command;
    
    switch (type) {
      case 'approveExtraction':
        this.approveExtraction();
        break;
        
      case 'rejectExtraction':
        this.rejectExtraction();
        break;
        
      case 'editField':
        if (data.fieldInfo) {
          this.editFieldByVoice(data.fieldInfo.field, data.fieldInfo.value);
        }
        break;
        
      default:
        this.log('Unhandled voice command in preview:', type);
    }
  }

  editFieldByVoice(fieldName, value) {
    const field = this.previewContent.querySelector(`[data-field="${fieldName}"]`);
    
    if (field) {
      if (field.contentEditable === 'true') {
        field.textContent = value;
      } else if (field.tagName === 'SELECT') {
        field.value = value;
      }
      
      // Trigger change event
      field.dispatchEvent(new Event('input', { bubbles: true }));
      
      // Show visual feedback
      field.classList.add('voice-edited');
      setTimeout(() => field.classList.remove('voice-edited'), 2000);
      
      this.log('Field edited by voice:', fieldName, value);
    } else {
      this.log('Field not found for voice edit:', fieldName);
    }
  }

  updateChangeIndicators() {
    if (!this.isEditing) return;
    
    // Show save indicator
    const indicator = document.createElement('div');
    indicator.className = 'unsaved-changes';
    indicator.innerHTML = `
      <i class="fas fa-circle"></i>
      Unsaved changes
    `;
    
    // Add to preview header if not already there
    if (!this.previewContent.querySelector('.unsaved-changes')) {
      const header = this.previewContent.querySelector('.preview-header');
      if (header) {
        header.appendChild(indicator);
      }
    }
  }

  async approveExtraction() {
    if (!this.currentEmail) {
      this.showToast('No email selected', 'warning');
      return;
    }
    
    try {
      this.log('Approving extraction for email:', this.currentEmail.id);
      
      // Disable buttons during processing
      this.disableActionButtons();
      
      // Submit approval with edits
      const result = await this.apiClient.approveExtraction(
        this.currentEmail.id, 
        this.editedData,
        this.getEditDiff()
      );
      
      this.log('Extraction approved successfully:', result);
      
      // Show success feedback
      this.showToast('Deal approved and created in Zoho!', 'success');
      
      // Notify listeners
      if (this.onApproved) {
        this.onApproved(this.currentEmail, this.editedData, result);
      }
      
      // Clear preview
      this.clearPreview();
      
    } catch (error) {
      this.log('Failed to approve extraction:', error);
      this.showToast(`Failed to approve: ${error.message}`, 'error');
      this.enableActionButtons();
    }
  }

  async rejectExtraction() {
    if (!this.currentEmail) {
      this.showToast('No email selected', 'warning');
      return;
    }
    
    const reason = prompt('Please provide a reason for rejection (optional):');
    
    try {
      this.log('Rejecting extraction for email:', this.currentEmail.id);
      
      // Disable buttons during processing
      this.disableActionButtons();
      
      // Submit rejection
      const result = await this.apiClient.rejectExtraction(this.currentEmail.id, reason);
      
      this.log('Extraction rejected successfully:', result);
      
      // Show feedback
      this.showToast('Extraction rejected', 'warning');
      
      // Notify listeners
      if (this.onRejected) {
        this.onRejected(this.currentEmail, reason, result);
      }
      
      // Clear preview
      this.clearPreview();
      
    } catch (error) {
      this.log('Failed to reject extraction:', error);
      this.showToast(`Failed to reject: ${error.message}`, 'error');
      this.enableActionButtons();
    }
  }

  getEditDiff() {
    if (!this.originalData || !this.editedData) {
      return {};
    }
    
    const diff = {};
    
    Object.keys(this.editedData).forEach(key => {
      if (this.originalData[key] !== this.editedData[key]) {
        diff[key] = {
          original: this.originalData[key],
          edited: this.editedData[key]
        };
      }
    });
    
    return diff;
  }

  validateField(fieldName, value) {
    switch (fieldName) {
      case 'email':
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) || value === '';
        
      case 'phone':
        return /^[\+]?[1-9][\d]{0,15}$/.test(value.replace(/[\s\-\(\)]/g, '')) || value === '';
        
      case 'firstName':
      case 'lastName':
        return value.length <= 50;
        
      default:
        return true;
    }
  }

  showFieldError(field, message) {
    // Remove existing error
    this.clearFieldError(field);
    
    // Add error message
    const error = document.createElement('div');
    error.className = 'field-error';
    error.textContent = message;
    
    field.parentNode.appendChild(error);
  }

  clearFieldError(field) {
    const error = field.parentNode.querySelector('.field-error');
    if (error) {
      error.remove();
    }
  }

  getConfidenceLevel(confidence) {
    if (confidence >= 0.8) return 'high';
    if (confidence >= 0.6) return 'medium';
    return 'low';
  }

  formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  enableActionButtons() {
    if (this.approveBtn) {
      this.approveBtn.disabled = false;
    }
    if (this.rejectBtn) {
      this.rejectBtn.disabled = false;
    }
  }

  disableActionButtons() {
    if (this.approveBtn) {
      this.approveBtn.disabled = true;
    }
    if (this.rejectBtn) {
      this.rejectBtn.disabled = true;
    }
  }

  showLoadingState() {
    if (this.previewContent) {
      this.previewContent.innerHTML = `
        <div class="loading-state">
          <i class="fas fa-spinner fa-spin"></i>
          <p>Loading email preview...</p>
        </div>
      `;
    }
    this.disableActionButtons();
  }

  showErrorState(message) {
    if (this.previewContent) {
      this.previewContent.innerHTML = `
        <div class="error-state">
          <i class="fas fa-exclamation-triangle"></i>
          <p>Error: ${message}</p>
          <button class="btn btn-ghost" onclick="location.reload()">
            <i class="fas fa-refresh"></i>
            Retry
          </button>
        </div>
      `;
    }
    this.disableActionButtons();
  }

  clearPreview() {
    this.currentEmail = null;
    this.originalData = null;
    this.editedData = null;
    this.isEditing = false;
    
    if (this.previewContent) {
      this.previewContent.innerHTML = `
        <div class="empty-state">
          <i class="fas fa-file-alt"></i>
          <p>Select an email to preview</p>
        </div>
      `;
    }
    
    this.disableActionButtons();
  }

  showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <i class="toast-icon fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
      <div class="toast-content">
        <div class="toast-message">${message}</div>
      </div>
      <button class="toast-close">&times;</button>
    `;
    
    // Add to container
    const container = document.getElementById('toastContainer');
    if (container) {
      container.appendChild(toast);
      
      // Auto remove
      setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, window.WellConfig.ui.toastDuration);
      
      // Manual close
      toast.querySelector('.toast-close').addEventListener('click', () => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      });
    }
  }

  log(...args) {
    if (window.WellConfig.debug.enableLogging && window.WellConfig.debug.logToConsole) {
      console.log('[PreviewEditor]', ...args);
    }
  }

  // Getters
  get hasUnsavedChanges() {
    return this.isEditing;
  }

  get currentData() {
    return this.editedData;
  }
}

// Export for use in main app
window.PreviewEditor = PreviewEditor;