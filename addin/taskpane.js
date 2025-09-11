/**
 * Taskpane JavaScript for Human-in-the-Loop Email Processing
 * Allows users to preview and edit extracted data before sending to Zoho
 * Version 1.4.0.0 - Fresh deployment with cache refresh
 */

// Configuration
const API_BASE_URL = window.API_BASE_URL || 'https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io';
const API_KEY = window.API_KEY || ''; // API key should be injected from config.js

// Global variables
let currentEmailData = null;
let extractedData = null;
let originalExtractedData = null;
let currentExtractedData = null;  // Store current extracted data for learning

// Initialize when Office is ready
// IMPORTANT: Office.initialize is required for Outlook desktop clients
// It must be defined even if using Office.onReady
Office.initialize = function (reason) {
    console.log('Office.initialize called with reason:', reason);
    // Office.onReady will handle the actual initialization
};

// Test API connectivity function (health check only, no dummy data)
async function testAPIConnection() {
    console.log('Testing API connection...');
    try {
        // Test health endpoint first (no API key required)
        const healthResponse = await fetch(`${API_BASE_URL}/health`);
        console.log('Health check response:', healthResponse.status);
        
        if (healthResponse.ok) {
            const healthData = await healthResponse.json();
            console.log('Health data:', healthData);
            return true;
        }
        return false;
    } catch (error) {
        console.error('API connection test failed:', error);
        return false;
    }
}

Office.onReady((info) => {
    console.log('Office.onReady called with info:', info);
    if (info.host === Office.HostType.Outlook) {
        console.log('Host is Outlook, waiting for DOM...');
        
        // Ensure DOM is fully loaded before initializing
        if (document.readyState === 'loading') {
            console.log('DOM still loading, adding DOMContentLoaded listener');
            document.addEventListener('DOMContentLoaded', () => {
                console.log('DOMContentLoaded fired, initializing...');
                testAPIConnection().then(result => {
                    console.log('API connection test result:', result);
                });
                initializeTaskpane();
            });
        } else {
            console.log('DOM already loaded, initializing immediately');
            // DOM is already loaded
            testAPIConnection().then(result => {
                console.log('API connection test result:', result);
            });
            initializeTaskpane();
        }
    } else {
        console.log('Host is not Outlook:', info.host);
    }
});

/**
 * Initialize the taskpane
 */
async function initializeTaskpane() {
    console.log('initializeTaskpane called');
    
    try {
        // Verify critical DOM elements exist
        const criticalElements = ['previewForm', 'loadingState', 'footer', 'candidateName', 'jobTitle'];
        const missingElements = [];
        for (const id of criticalElements) {
            if (!document.getElementById(id)) {
                missingElements.push(id);
            }
        }
        
        if (missingElements.length > 0) {
            console.error('CRITICAL: Missing DOM elements:', missingElements);
            console.error('Document body innerHTML length:', document.body.innerHTML.length);
            console.error('First 500 chars of body:', document.body.innerHTML.substring(0, 500));
            // Try to wait a bit more for DOM
            setTimeout(() => initializeTaskpane(), 500);
            return;
        }
        
        console.log('All critical DOM elements found');
        
        // Verify Office.context is available
        if (!Office || !Office.context || !Office.context.mailbox) {
            console.error('Office.context.mailbox is not available');
            showError('Office Add-in is not properly initialized. Please try reloading.');
            return;
        }
        console.log('Office.context.mailbox is available');
        
        // Verify we have an item
        if (!Office.context.mailbox.item) {
            console.error('No email item available');
            showError('No email selected. Please select an email and try again.');
            return;
        }
        console.log('Email item is available');
        
        // Set up event listeners
        document.getElementById('btnSend').addEventListener('click', handleSendToZoho);
        document.getElementById('btnCancel').addEventListener('click', handleCancel);
        document.getElementById('btnClose').addEventListener('click', handleClose);
        
        // Natural language corrections
        document.getElementById('btnApplyCorrections').addEventListener('click', applyNaturalLanguageCorrections);
        document.getElementById('btnSuggestFixes').addEventListener('click', showSuggestedFixes);
        
        // Custom fields
        document.getElementById('btnAddField').addEventListener('click', showAddFieldModal);
        document.getElementById('btnConfirmAddField').addEventListener('click', addCustomField);
        document.getElementById('btnCancelAddField').addEventListener('click', hideAddFieldModal);
        
        // Track field changes to show edited indicator
        setupFieldTracking();
        
        // Start extraction process
        console.log('About to call extractAndPreview');
        await extractAndPreview();
        console.log('extractAndPreview completed successfully');
        
    } catch (error) {
        console.error('Error in initializeTaskpane:', error);
        console.error('Stack trace:', error.stack);
        showError('Failed to initialize: ' + error.message);
    }
}

/**
 * Show error message to user
 */
function showError(message) {
    console.error('Showing error:', message);
    const errorDiv = document.getElementById('errorMessage');
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }
    // Hide loading state
    showLoadingState(false);
}

/**
 * Set up field tracking to show when user edits AI-extracted values
 */
function setupFieldTracking() {
    const trackedFields = [
        'candidateName', 'candidateEmail', 'candidatePhone', 'linkedinUrl',
        'jobTitle', 'location', 'firmName', 'referrerName',
        'notes', 'calendlyUrl'
    ];
    
    trackedFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.addEventListener('input', function() {
                updateFieldIndicator(fieldId);
            });
        }
    });
}

/**
 * Update field indicator based on changes
 */
function updateFieldIndicator(fieldId) {
    const field = document.getElementById(fieldId);
    const indicator = document.getElementById(fieldId + 'Indicator');
    
    if (!indicator) return;
    
    const originalValue = originalExtractedData?.[fieldId] || '';
    const currentValue = field.value || '';
    
    if (originalValue && currentValue !== originalValue) {
        indicator.textContent = 'Edited';
        indicator.className = 'edited-indicator';
        indicator.style.display = 'inline-block';
    } else if (originalValue) {
        indicator.textContent = 'AI Extracted';
        indicator.className = 'extracted-indicator';
        indicator.style.display = 'inline-block';
    } else {
        indicator.style.display = 'none';
    }
}

/**
 * Extract email data and show preview
 */
async function extractAndPreview() {
    console.log('extractAndPreview function started');
    try {
        // Show loading state with more accurate message
        showLoadingState(true);
        updateLoadingMessage('Reading email content...');
        console.log('Loading state shown');
        
        // Extract email data
        const item = Office.context.mailbox.item;
        currentEmailData = await extractEmailData(item);
        
        // Update loading message for AI extraction
        updateLoadingMessage('AI is analyzing the email (this may take 5-10 seconds)...');
        
        // Debug: Log what we're sending
        console.log('Sending to API:', {
            sender_email: currentEmailData.from?.emailAddress || '',
            subject: currentEmailData.subject || '',
            body_preview: currentEmailData.body?.substring(0, 200) || '',
            api_key_present: !!API_KEY
        });
        
        // Try to use backend AI extraction first, fall back to local if it fails
        try {
            console.log('Attempting to fetch from:', `${API_BASE_URL}/intake/email`);
            console.log('Request headers:', {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY ? 'present' : 'missing'
            });
            
            // Determine if this is a same-origin or cross-origin request
            const currentOrigin = window.location.origin;
            const isSameOrigin = API_BASE_URL.startsWith(currentOrigin);
            console.log('Same origin request:', isSameOrigin);
            
            const fetchOptions = {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(API_KEY ? { 'X-API-Key': API_KEY } : {})
                },
                body: JSON.stringify({
                    sender_email: currentEmailData.from?.emailAddress || '',
                    sender_name: currentEmailData.from?.displayName || '',
                    subject: currentEmailData.subject || '',
                    body: currentEmailData.body || '',
                    dry_run: true  // Don't create Zoho records during preview
                })
            };
            
            // Only set CORS mode and credentials for cross-origin requests
            if (!isSameOrigin) {
                fetchOptions.mode = 'cors';
                fetchOptions.credentials = 'omit'; // Don't include cookies for cross-origin
            }
            
            const extractionResponse = await fetch(`${API_BASE_URL}/intake/email`, fetchOptions);
            
            console.log('Response status:', extractionResponse.status);
            console.log('Response ok:', extractionResponse.ok);
            
            if (extractionResponse.ok) {
                let response;
                let responseText = '';
                try {
                    responseText = await extractionResponse.text();
                    console.log('Raw response length:', responseText.length);
                    console.log('First 500 chars:', responseText.substring(0, 500));
                    
                    // Try to parse the response
                    if (responseText) {
                        response = JSON.parse(responseText);
                    } else {
                        console.error('Empty response from API');
                        throw new Error('Empty response');
                    }
                } catch (parseError) {
                    console.error('Parse error:', parseError);
                    console.error('Response was:', responseText);
                    // Use fallback extraction
                    extractedData = performLocalExtraction(currentEmailData);
                    // Still populate the form even if API fails
                    populateForm(extractedData);
                    showPreviewForm();
                    return; // Exit early
                }
                
                // Handle the response - check for different response structures
                console.log('Response structure:', Object.keys(response));
                
                // The API might return data in different formats
                let extracted = null;
                if (response.extracted) {
                    extracted = response.extracted;
                } else if (response.data) {
                    extracted = response.data;
                } else if (response.candidate_name || response.job_title) {
                    // Direct response
                    extracted = response;
                } else {
                    console.error('Unexpected response structure:', response);
                    extracted = {};
                }
                
                console.log('Using extracted data:', extracted);
                
                // Map the response to our expected format - be more defensive
                extractedData = {
                    candidateName: extracted.candidate_name || extracted.candidateName || '',
                    candidateEmail: extracted.candidate_email || extracted.candidateEmail || extracted.email || '',
                    candidatePhone: extracted.candidate_phone || extracted.candidatePhone || extracted.phone || '',
                    linkedinUrl: extracted.linkedin_url || extracted.linkedinUrl || '',
                    jobTitle: extracted.job_title || extracted.jobTitle || '',
                    location: extracted.location || extracted.candidateLocation || '',
                    firmName: extracted.company_name || extracted.firmName || extracted.firm_name || '',
                    referrerName: extracted.referrer_name || extracted.referrerName || currentEmailData.from?.displayName || '',
                    referrerEmail: extracted.referrer_email || extracted.referrerEmail || currentEmailData.from?.emailAddress || '',
                    notes: extracted.notes || '',
                    calendlyUrl: extracted.calendly_url || extracted.calendlyUrl || '',
                    source: extracted.source || extracted.Source || 'Email Inbound'
                };
            } else {
                // Log the error response
                const errorText = await extractionResponse.text();
                console.error('AI extraction failed with status:', extractionResponse.status, errorText);
                // Fall back to local extraction
                extractedData = performLocalExtraction(currentEmailData);
            }
        } catch (error) {
            console.error('AI extraction failed, using local extraction:', error);
            console.error('Error details:', {
                name: error.name,
                message: error.message,
                stack: error.stack
            });
            
            // Check for specific error types
            if (error.name === 'TypeError' && error.message === 'Failed to fetch') {
                console.error('Network error - possible causes:');
                console.error('1. CORS misconfiguration');
                console.error('2. API endpoint is not reachable');
                console.error('3. Network connectivity issues');
                console.error('4. SSL/TLS certificate issues');
                console.error('API URL:', `${API_BASE_URL}/intake/email`);
                console.error('Current location:', window.location.origin);
            }
            
            // Fall back to local extraction
            extractedData = performLocalExtraction(currentEmailData);
        }
        
        // Store original extracted data for comparison
        originalExtractedData = { ...extractedData };
        console.log('Final extractedData to populate:', extractedData);
        
        // CRITICAL: Ensure we actually have data before populating
        if (!extractedData || Object.keys(extractedData).length === 0) {
            console.error('No extracted data available!');
            extractedData = performLocalExtraction(currentEmailData);
            console.log('Using fallback extraction:', extractedData);
        }
        
        // Populate form with extracted data
        console.log('Calling populateForm with:', extractedData);
        populateForm(extractedData);
        
        // Show preview form - force it to be visible
        console.log('Showing preview form...');
        const previewForm = document.getElementById('previewForm');
        const loadingState = document.getElementById('loadingState');
        const footer = document.getElementById('footer');
        
        if (loadingState) loadingState.style.display = 'none';
        if (previewForm) {
            previewForm.style.display = 'block';
            previewForm.style.visibility = 'visible';
            previewForm.style.opacity = '1';
        }
        if (footer) {
            footer.style.display = 'flex';
            footer.style.visibility = 'visible';
        }
        
        console.log('Form display complete');
        
        // Force visibility as a fallback
        setTimeout(() => {
            const form = document.getElementById('previewForm');
            const footer = document.getElementById('footer');
            const loading = document.getElementById('loadingState');
            
            if (form && form.style.display !== 'block') {
                console.log('Force showing form (fallback)');
                form.style.display = 'block';
            }
            if (footer && footer.style.display !== 'flex') {
                console.log('Force showing footer (fallback)');
                footer.style.display = 'flex';
            }
            if (loading && loading.style.display !== 'none') {
                console.log('Force hiding loading (fallback)');
                loading.style.display = 'none';
            }
        }, 100);
        
        console.log('Form should now be visible');
        
    } catch (error) {
        console.error('Error in extraction:', error);
        // Still show form even if extraction fails
        extractedData = performLocalExtraction(currentEmailData);
        populateForm(extractedData);
        showPreviewForm();
    }
}

/**
 * Local extraction fallback using regex patterns
 */
function performLocalExtraction(emailData) {
    const body = emailData.body || '';
    const subject = emailData.subject || '';
    const extracted = {
        candidateName: '',
        candidateEmail: '',
        candidatePhone: '',
        linkedinUrl: '',
        jobTitle: '',
        location: '',
        firmName: '',
        referrerName: emailData.from?.displayName || '',
        referrerEmail: emailData.from?.emailAddress || '',
        notes: '',
        calendlyUrl: '',
        source: 'Email Inbound'
    };
    
    // Debug logging
    console.log('Extracting from email body:', body.substring(0, 500));
    console.log('Email subject:', subject);
    
    // For Ashley Ethridge recruitment email, look for Invitee pattern
    // Check for "Invitee:" pattern first
    const inviteeMatch = body.match(/Invitee:\s*([^\n]+)/i);
    if (inviteeMatch) {
        extracted.candidateName = inviteeMatch[1].trim();
    } else {
        // Extract candidate name (common patterns)
        const namePatterns = [
            /(?:candidate|introduce|meet|presenting|recommend)\s+(?:is\s+)?([A-Z][a-z]+\s+[A-Z][a-z]+)/i,
            /([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:would be|is|has|for)/i
        ];
        for (const pattern of namePatterns) {
            const match = body.match(pattern);
            if (match) {
                extracted.candidateName = match[1].trim();
                break;
            }
        }
    }
    
    // Extract job title - check for "Event Type:" pattern (from recruiting emails)
    const eventTypeMatch = body.match(/Event Type:\s*([^\n]+)/i);
    if (eventTypeMatch) {
        extracted.jobTitle = eventTypeMatch[1].trim();
    } else {
        // Standard patterns
        const jobPatterns = [
            /(?:position|role|opportunity|job|opening)\s+(?:of|for|as)?\s*([^,\n.]+)/i,
            /(?:Senior|Junior|Lead|Principal|Staff)\s+([^,\n.]+)/i
        ];
        for (const pattern of jobPatterns) {
            const match = body.match(pattern);
            if (match) {
                extracted.jobTitle = match[1].trim();
                break;
            }
        }
    }
    
    // Extract location - check for date/time patterns that include location
    const eventDateMatch = body.match(/Event Date\/Time:\s*[^\(]+\(([^)]+)\)/i);
    if (eventDateMatch) {
        // Try to extract location from timezone/region info
        const locationInfo = eventDateMatch[1].trim();
        if (locationInfo && !locationInfo.toLowerCase().includes('canada')) {
            extracted.location = locationInfo;
        }
    }
    
    // Standard location patterns
    if (!extracted.location) {
        const locationPatterns = [
            /(?:location|based in|located in|area|office)\s*:?\s*([^,\n.]+)/i,
            /in\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:area|office|location)/i
        ];
        for (const pattern of locationPatterns) {
            const match = body.match(pattern);
            if (match) {
                extracted.location = match[1].trim();
                break;
            }
        }
    }
    
    // Extract email - look for "Invitee Email:" pattern first
    const inviteeEmailMatch = body.match(/Invitee Email:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/i);
    if (inviteeEmailMatch) {
        extracted.candidateEmail = inviteeEmailMatch[1].trim();
    } else {
        // Standard email pattern
        const emailPattern = /([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/;
        const emailMatch = body.match(emailPattern);
        if (emailMatch && emailMatch[1] !== extracted.referrerEmail) {
            extracted.candidateEmail = emailMatch[1];
        }
    }
    
    // Extract phone - look for "Text Reminder Number:" pattern first
    const textReminderMatch = body.match(/Text Reminder Number:\s*(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})/i);
    if (textReminderMatch) {
        extracted.candidatePhone = textReminderMatch[1].trim();
    } else {
        // Standard phone pattern
        const phonePattern = /(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})/;
        const phoneMatch = body.match(phonePattern);
        if (phoneMatch) {
            extracted.candidatePhone = phoneMatch[1];
        }
    }
    
    // Extract LinkedIn URL
    const linkedinPattern = /(https?:\/\/)?(www\.)?linkedin\.com\/in\/[a-zA-Z0-9-]+/i;
    const linkedinMatch = body.match(linkedinPattern);
    if (linkedinMatch) {
        extracted.linkedinUrl = linkedinMatch[0];
    }
    
    // Extract Calendly URL
    const calendlyPattern = /(https?:\/\/)?(www\.)?calendly\.com\/[a-zA-Z0-9-/]+/i;
    const calendlyMatch = body.match(calendlyPattern);
    if (calendlyMatch) {
        extracted.calendlyUrl = calendlyMatch[0];
        extracted.source = 'Website Inbound';
    }
    
    // Determine source
    if (body.toLowerCase().includes('referr') || body.toLowerCase().includes('recommend')) {
        extracted.source = 'Referral';
    } else if (body.toLowerCase().includes('twav') || body.toLowerCase().includes('reverse recruit')) {
        extracted.source = 'Reverse Recruiting';
    }
    
    return extracted;
}

/**
 * Extract email data from Outlook item
 */
async function extractEmailData(item) {
    return new Promise((resolve, reject) => {
        const emailData = {
            subject: item.subject,
            from: item.from ? {
                displayName: item.from.displayName,
                emailAddress: item.from.emailAddress
            } : null,
            to: item.to ? item.to.map(recipient => ({
                displayName: recipient.displayName,
                emailAddress: recipient.emailAddress
            })) : [],
            dateTimeCreated: item.dateTimeCreated,
            attachments: []
        };
        
        // Get body content
        item.body.getAsync(
            Office.CoercionType.Text,
            async (bodyResult) => {
                if (bodyResult.status === Office.AsyncResultStatus.Succeeded) {
                    emailData.body = bodyResult.value;
                    
                    // Get attachments
                    if (item.attachments && item.attachments.length > 0) {
                        emailData.attachments = await getAttachments(item);
                    }
                    
                    resolve(emailData);
                } else {
                    reject(new Error('Failed to get email body'));
                }
            }
        );
    });
}

/**
 * Get attachments from email
 */
async function getAttachments(item) {
    const attachments = [];
    
    for (const attachment of item.attachments) {
        if (attachment.attachmentType === Office.MailboxEnums.AttachmentType.File) {
            // For now, just store metadata
            // Actual content will be fetched when sending to Zoho
            attachments.push({
                name: attachment.name,
                size: attachment.size,
                contentType: attachment.contentType,
                id: attachment.id
            });
        }
    }
    
    return attachments;
}

/**
 * Populate form with extracted data
 */
function populateForm(data) {
    console.log('populateForm called with data:', data);
    
    // Defensive: ensure data exists
    if (!data) {
        console.error('No data provided to populateForm!');
        data = {};
    }
    
    // Store the current extracted data for learning
    currentExtractedData = data;
    
    // First, check if the form elements exist
    const candidateNameField = document.getElementById('candidateName');
    if (!candidateNameField) {
        console.error('CRITICAL: candidateName field not found! Form may not be loaded.');
        // Try to wait and retry
        setTimeout(() => {
            console.log('Retrying populateForm after delay...');
            populateForm(data);
        }, 500);
        return;
    }
    
    // Candidate Information - try multiple field name formats
    setValue('candidateName', data.candidateName || data.candidate_name || '');
    setValue('candidateEmail', data.candidateEmail || data.candidate_email || data.email || '');
    setValue('candidatePhone', data.candidatePhone || data.candidate_phone || data.phone || '');
    setValue('linkedinUrl', data.linkedinUrl || data.linkedin_url || '');
    
    // Job Details
    setValue('jobTitle', data.jobTitle || data.job_title || '');
    setValue('location', data.location || data.candidateLocation || '');
    setValue('firmName', data.firmName || data.firm_name || data.company_name || '');
    setValue('source', data.source || data.Source || 'Email Inbound');
    
    // Referrer Information
    setValue('referrerName', data.referrerName || data.referrer_name || currentEmailData?.from?.displayName || '');
    setValue('referrerEmail', data.referrerEmail || data.referrer_email || currentEmailData?.from?.emailAddress || '');
    
    // Additional Information
    setValue('notes', data.notes || '');
    setValue('calendlyUrl', data.calendlyUrl || data.calendly_url || '');
    
    console.log('Form population complete');
    
    // Show attachments if any
    if (currentEmailData?.attachments?.length > 0) {
        showAttachments(currentEmailData.attachments);
    }
    
    // Update indicators
    ['candidateName', 'jobTitle'].forEach(fieldId => {
        const value = document.getElementById(fieldId).value;
        const indicator = document.getElementById(fieldId + 'Indicator');
        if (indicator && value) {
            indicator.style.display = 'inline-block';
        }
    });
}

/**
 * Set form field value
 */
function setValue(fieldId, value) {
    const field = document.getElementById(fieldId);
    if (field) {
        field.value = value || '';
        console.log(`Set ${fieldId} to: ${value || '(empty)'}`);
    } else {
        console.error(`ERROR: Element with ID '${fieldId}' not found in DOM!`);
        // List all available input elements for debugging
        const inputs = document.querySelectorAll('input, select, textarea');
        console.log('Available form elements:', Array.from(inputs).map(el => el.id).filter(id => id));
    }
}

/**
 * Show attachments section
 */
function showAttachments(attachments) {
    const section = document.getElementById('attachmentsSection');
    const list = document.getElementById('attachmentsList');
    
    if (attachments && attachments.length > 0) {
        section.style.display = 'block';
        list.innerHTML = attachments.map(att => `
            <div class="attachment-item">
                <span class="icon">📄</span>
                <span>${att.name} (${formatFileSize(att.size)})</span>
            </div>
        `).join('');
    }
}

/**
 * Format file size
 */
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/**
 * Show loading state
 */
function showLoadingState(show) {
    document.getElementById('loadingState').style.display = show ? 'block' : 'none';
    // Also hide/show the form and footer
    document.getElementById('previewForm').style.display = show ? 'none' : 'block';
    document.getElementById('footer').style.display = show ? 'none' : 'flex';
}

/**
 * Update loading message
 */
function updateLoadingMessage(message) {
    const loadingElement = document.getElementById('loadingState');
    if (loadingElement) {
        const loadingText = loadingElement.querySelector('.loading-text') || loadingElement.querySelector('p');
        if (loadingText) {
            loadingText.textContent = message;
        }
    }
}

/**
 * Show preview form
 */
function showPreviewForm() {
    console.log('showPreviewForm called - hiding loading, showing form');
    // Hide loading state
    document.getElementById('loadingState').style.display = 'none';
    // Show the form
    document.getElementById('previewForm').style.display = 'block';
    // Show the footer
    document.getElementById('footer').style.display = 'flex';
    console.log('Form visibility set to:', document.getElementById('previewForm').style.display);
    console.log('Footer visibility set to:', document.getElementById('footer').style.display);
}

/**
 * Handle Send to Zoho button click
 */
async function handleSendToZoho() {
    try {
        // Validate required fields
        if (!validateForm()) {
            return;
        }
        
        // Hide preview form, show progress
        document.getElementById('previewForm').style.display = 'none';
        document.getElementById('progressSection').style.display = 'block';
        document.getElementById('btnSend').style.display = 'none';
        document.getElementById('btnCancel').style.display = 'none';
        
        // Get form data
        const formData = getFormData();
        
        // Update progress
        await updateProgress(1, 'Preparing data...');
        
        // Get attachment content if needed
        let attachmentData = [];
        if (currentEmailData?.attachments?.length > 0) {
            await updateProgress(2, 'Processing attachments...');
            attachmentData = await getAttachmentContent();
        }
        
        // Send to backend
        await updateProgress(3, 'Sending to AI for processing...');
        
        const response = await fetch(`${API_BASE_URL}/intake/email`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(API_KEY ? { 'X-API-Key': API_KEY } : {})
            },
            body: JSON.stringify({
                sender_email: formData.referrerEmail,
                sender_name: formData.referrerName,
                subject: currentEmailData.subject || '',
                body: currentEmailData.body || '',
                attachments: attachmentData,
                // Send original AI extraction for learning
                ai_extraction: currentExtractedData || {},
                // Send user corrections to learn from
                user_corrections: {
                    candidate_name: formData.candidateName,
                    candidate_email: formData.candidateEmail,
                    phone: formData.candidatePhone,
                    job_title: formData.jobTitle,
                    location: formData.location,
                    company_name: formData.firmName,
                    referrer_name: formData.referrerName
                }
            })
        });
        
        await updateProgress(4, 'Checking for duplicates...');
        await updateProgress(5, 'Creating Zoho records...');
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || `Server error: ${response.status}`);
        }
        
        const result = await response.json();
        
        await updateProgress(6, 'Complete!');
        
        // Show success message
        showSuccess(result);
        
    } catch (error) {
        console.error('Error sending to Zoho:', error);
        showError(error.message);
    }
}

/**
 * Get attachment content
 */
async function getAttachmentContent() {
    const item = Office.context.mailbox.item;
    const attachmentPromises = [];
    
    for (const attachment of currentEmailData.attachments) {
        if (attachment.size < 25 * 1024 * 1024) { // Under 25MB
            attachmentPromises.push(
                new Promise((resolve) => {
                    item.getAttachmentContentAsync(
                        attachment.id,
                        (result) => {
                            if (result.status === Office.AsyncResultStatus.Succeeded) {
                                resolve({
                                    filename: attachment.name,
                                    content_base64: result.value.content,
                                    content_type: attachment.contentType
                                });
                            } else {
                                resolve(null);
                            }
                        }
                    );
                })
            );
        }
    }
    
    const attachments = await Promise.all(attachmentPromises);
    return attachments.filter(a => a !== null);
}

/**
 * Show notification message instead of alert
 */
function showNotification(message, type = 'warning') {
    // Create or update notification element
    let notificationDiv = document.getElementById('validationNotification');
    if (!notificationDiv) {
        notificationDiv = document.createElement('div');
        notificationDiv.id = 'validationNotification';
        notificationDiv.style.cssText = `
            position: fixed;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            padding: 12px 20px;
            border-radius: 6px;
            z-index: 10000;
            font-size: 14px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            transition: opacity 0.3s ease;
        `;
        document.body.appendChild(notificationDiv);
    }
    
    // Set style based on type
    if (type === 'error' || type === 'warning') {
        notificationDiv.style.backgroundColor = '#f8d7da';
        notificationDiv.style.color = '#721c24';
        notificationDiv.style.border = '1px solid #f5c6cb';
    } else if (type === 'success') {
        notificationDiv.style.backgroundColor = '#d4edda';
        notificationDiv.style.color = '#155724';
        notificationDiv.style.border = '1px solid #c3e6cb';
    } else {
        notificationDiv.style.backgroundColor = '#d1ecf1';
        notificationDiv.style.color = '#0c5460';
        notificationDiv.style.border = '1px solid #bee5eb';
    }
    
    // Set message and show
    notificationDiv.textContent = message;
    notificationDiv.style.display = 'block';
    notificationDiv.style.opacity = '1';
    
    // Auto-hide after 4 seconds
    setTimeout(() => {
        notificationDiv.style.opacity = '0';
        setTimeout(() => {
            notificationDiv.style.display = 'none';
        }, 300);
    }, 4000);
}

/**
 * Validate form
 */
function validateForm() {
    const candidateName = document.getElementById('candidateName').value.trim();
    const jobTitle = document.getElementById('jobTitle').value.trim();
    
    if (!candidateName) {
        showNotification('Please enter the candidate name', 'warning');
        document.getElementById('candidateName').focus();
        return false;
    }
    
    if (!jobTitle) {
        showNotification('Please enter the job title', 'warning');
        document.getElementById('jobTitle').focus();
        return false;
    }
    
    return true;
}

/**
 * Get form data
 */
function getFormData() {
    return {
        candidateName: document.getElementById('candidateName').value.trim(),
        candidateEmail: document.getElementById('candidateEmail').value.trim(),
        candidatePhone: document.getElementById('candidatePhone').value.trim(),
        linkedinUrl: document.getElementById('linkedinUrl').value.trim(),
        jobTitle: document.getElementById('jobTitle').value.trim(),
        location: document.getElementById('location').value.trim(),
        firmName: document.getElementById('firmName').value.trim(),
        source: document.getElementById('source').value,
        referrerName: document.getElementById('referrerName').value.trim(),
        referrerEmail: document.getElementById('referrerEmail').value.trim(),
        notes: document.getElementById('notes').value.trim(),
        calendlyUrl: document.getElementById('calendlyUrl').value.trim()
    };
}

/**
 * Update progress display
 */
async function updateProgress(step, message) {
    const progressBar = document.getElementById('progressBar');
    const percentage = Math.round((step / 6) * 100);
    
    progressBar.style.width = percentage + '%';
    progressBar.textContent = percentage + '%';
    
    // Update step list
    document.querySelectorAll('.step-item').forEach((item, index) => {
        if (index < step) {
            item.classList.add('completed');
            item.classList.remove('active');
        } else if (index === step - 1) {
            item.classList.add('active');
        }
    });
    
    // Small delay for visual effect
    await new Promise(resolve => setTimeout(resolve, 500));
}

/**
 * Show success message
 */
function showSuccess(result) {
    const successMessage = document.getElementById('successMessage');
    successMessage.innerHTML = `
        <strong>✅ Success!</strong><br>
        ${result.deal_name ? `Deal created: ${result.deal_name}` : 'Records created in Zoho CRM'}<br>
        <small>Deal ID: ${result.deal_id}</small>
    `;
    successMessage.style.display = 'block';
    
    document.getElementById('btnClose').style.display = 'block';
}

/**
 * Show error message
 */
function showError(message) {
    const errorMessage = document.getElementById('errorMessage');
    if (errorMessage) {
        errorMessage.innerHTML = `<strong>❌ Error:</strong> ${message}`;
        errorMessage.style.display = 'block';
        document.getElementById('btnClose').style.display = 'block';
    } else {
        // Fallback to notification
        showNotification(message, 'error');
    }
}

/**
 * Handle Cancel button
 */
function handleCancel() {
    // Show confirmation message instead of using confirm dialog
    showNotification('Closing task pane...', 'info');
    
    setTimeout(() => {
        // Try to close the taskpane
        if (window.parent && window.parent !== window) {
            // If in an iframe, try to message parent
            try {
                Office.context.ui.messageParent(JSON.stringify({ action: 'cancel' }));
            } catch (e) {
                // If messageParent fails, try to close the window
                window.close();
            }
        } else {
            // Direct window close
            window.close();
        }
    }, 500);
}

/**
 * Handle Close button
 */
function handleClose() {
    // Try to close the taskpane
    if (window.parent && window.parent !== window) {
        // If in an iframe, try to message parent
        try {
            Office.context.ui.messageParent(JSON.stringify({ action: 'close' }));
        } catch (e) {
            // If messageParent fails, try to close the window
            window.close();
        }
    } else {
        // Direct window close
        window.close();
    }
}

/**
 * Apply natural language corrections using AI
 */
async function applyNaturalLanguageCorrections() {
    const prompt = document.getElementById('correctionPrompt').value.trim();
    if (!prompt) return;
    
    try {
        // Show processing indicator
        const btn = document.getElementById('btnApplyCorrections');
        const originalText = btn.innerHTML;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Processing...';
        btn.disabled = true;
        
        // Parse the correction prompt to understand what to change
        const corrections = parseCorrections(prompt);
        
        // Apply corrections to form fields
        for (const correction of corrections) {
            applyCorrection(correction);
        }
        
        // Clear the prompt
        document.getElementById('correctionPrompt').value = '';
        
        // Show success feedback
        showTemporaryMessage('Corrections applied!', 'success');
        
    } catch (error) {
        console.error('Error applying corrections:', error);
        showTemporaryMessage('Could not apply corrections', 'error');
    } finally {
        // Restore button
        const btn = document.getElementById('btnApplyCorrections');
        btn.innerHTML = '<span class="icon">🤖</span> Apply Corrections';
        btn.disabled = false;
    }
}

/**
 * Parse natural language corrections
 */
function parseCorrections(prompt) {
    const corrections = [];
    const lowerPrompt = prompt.toLowerCase();
    
    // Pattern matching for common correction phrases
    const patterns = [
        // Name corrections
        {
            regex: /(?:candidate|name|person) (?:is|should be) ([^,]+?)(?:,|not|$)/i,
            field: 'candidateName',
            extractor: (match) => match[1].trim()
        },
        // Phone corrections
        {
            regex: /(?:phone|number|cell) (?:is|should be|:) ([\d\s\-\(\)\+]+)/i,
            field: 'candidatePhone',
            extractor: (match) => match[1].trim()
        },
        // Email corrections
        {
            regex: /(?:email) (?:is|should be|:) ([^\s,]+@[^\s,]+)/i,
            field: 'candidateEmail',
            extractor: (match) => match[1].trim()
        },
        // Location corrections
        {
            regex: /(?:location|city|place) (?:is|should be) ([^,]+?)(?:,|$)/i,
            field: 'location',
            extractor: (match) => match[1].trim()
        },
        // Job title corrections
        {
            regex: /(?:job|title|position|role) (?:is|should be) ([^,]+?)(?:,|$)/i,
            field: 'jobTitle',
            extractor: (match) => match[1].trim()
        },
        // Company corrections
        {
            regex: /(?:company|firm|organization) (?:is|should be|name) ([^,]+?)(?:,|$)/i,
            field: 'firmName',
            extractor: (match) => match[1].trim()
        }
    ];
    
    // Check for "add" commands
    if (lowerPrompt.includes('add')) {
        patterns.forEach(pattern => {
            const addRegex = new RegExp('add ' + pattern.regex.source.replace(/(?:is|should be)/, ''), 'i');
            const match = prompt.match(addRegex);
            if (match) {
                corrections.push({
                    field: pattern.field,
                    value: pattern.extractor(match),
                    action: 'add'
                });
            }
        });
    }
    
    // Check for corrections/replacements
    patterns.forEach(pattern => {
        const match = prompt.match(pattern.regex);
        if (match) {
            corrections.push({
                field: pattern.field,
                value: pattern.extractor(match),
                action: 'replace'
            });
        }
    });
    
    // Check for "remove" or "delete" commands
    if (lowerPrompt.includes('remove') || lowerPrompt.includes('delete')) {
        const removeMatch = prompt.match(/(?:remove|delete) (?:the )?(candidate name|phone|email|location|job title|company)/i);
        if (removeMatch) {
            const fieldMap = {
                'candidate name': 'candidateName',
                'phone': 'candidatePhone',
                'email': 'candidateEmail',
                'location': 'location',
                'job title': 'jobTitle',
                'company': 'firmName'
            };
            corrections.push({
                field: fieldMap[removeMatch[1].toLowerCase()],
                value: '',
                action: 'clear'
            });
        }
    }
    
    return corrections;
}

/**
 * Apply a single correction to the form
 */
function applyCorrection(correction) {
    const field = document.getElementById(correction.field);
    if (field) {
        const oldValue = field.value;
        field.value = correction.value;
        
        // Trigger change event to update indicators
        field.dispatchEvent(new Event('input'));
        
        // Log the correction for learning
        console.log(`Corrected ${correction.field}: "${oldValue}" → "${correction.value}"`);
    }
}

/**
 * Show suggested fixes based on common corrections
 */
async function showSuggestedFixes() {
    const fixesDiv = document.getElementById('quickFixes');
    const suggestionsDiv = document.getElementById('fixSuggestions');
    
    // Get domain from email
    const domain = currentEmailData?.from?.emailAddress?.split('@')[1] || '';
    
    // Mock suggestions - in production, these would come from the learning system
    const suggestions = [
        { text: 'Change Sr. to Senior in job title', correction: 'job title should be Senior Financial Advisor' },
        { text: 'Add location as Remote', correction: 'location is Remote' },
        { text: 'Fix company name capitalization', correction: 'company is The Well Partners' }
    ];
    
    // Display suggestions as clickable buttons
    suggestionsDiv.innerHTML = suggestions.map((sug, idx) => `
        <button class="btn btn-sm btn-outline-info me-1 mb-1" 
                onclick="applySuggestion('${sug.correction.replace(/'/g, "\\'")}')">
            ${sug.text}
        </button>
    `).join('');
    
    fixesDiv.style.display = 'block';
}

/**
 * Apply a suggested correction
 */
window.applySuggestion = function(correction) {
    document.getElementById('correctionPrompt').value = correction;
    applyNaturalLanguageCorrections();
}

/**
 * Show add field modal
 */
function showAddFieldModal() {
    document.getElementById('addFieldModal').style.display = 'block';
}

/**
 * Hide add field modal
 */
function hideAddFieldModal() {
    document.getElementById('addFieldModal').style.display = 'none';
    // Clear inputs
    document.getElementById('newFieldName').value = '';
    document.getElementById('newFieldType').value = 'text';
    document.getElementById('newFieldValue').value = '';
}

/**
 * Add a custom field to the form
 */
function addCustomField() {
    const fieldName = document.getElementById('newFieldName').value.trim();
    const fieldType = document.getElementById('newFieldType').value;
    const fieldValue = document.getElementById('newFieldValue').value.trim();
    
    if (!fieldName) {
        showNotification('Please enter a field name', 'warning');
        return;
    }
    
    // Create a safe field ID
    const fieldId = 'custom_' + fieldName.toLowerCase().replace(/\s+/g, '_');
    
    // Check if field already exists
    if (document.getElementById(fieldId)) {
        showNotification('This field already exists', 'warning');
        return;
    }
    
    // Create the field HTML
    const fieldHtml = `
        <div class="mb-3 custom-field" data-field-id="${fieldId}">
            <label class="form-label">
                ${fieldName}
                <button type="button" class="btn btn-sm text-danger" onclick="removeCustomField('${fieldId}')">
                    ×
                </button>
            </label>
            <input type="${fieldType}" class="form-control" id="${fieldId}" value="${fieldValue}">
        </div>
    `;
    
    // Add to container
    document.getElementById('customFieldsContainer').insertAdjacentHTML('beforeend', fieldHtml);
    
    // Hide modal
    hideAddFieldModal();
    
    // Add tracking for the new field
    const field = document.getElementById(fieldId);
    if (field) {
        field.addEventListener('input', function() {
            this.setAttribute('data-edited', 'true');
        });
    }
}

/**
 * Remove a custom field
 */
window.removeCustomField = function(fieldId) {
    const fieldDiv = document.querySelector(`[data-field-id="${fieldId}"]`);
    if (fieldDiv) {
        fieldDiv.remove();
    }
}

/**
 * Show temporary message
 */
function showTemporaryMessage(message, type) {
    const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
    const alertHtml = `
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            ${message}
        </div>
    `;
    
    const container = document.getElementById('previewForm');
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = alertHtml;
    container.insertBefore(tempDiv.firstChild, container.firstChild);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
        if (tempDiv.firstChild) {
            tempDiv.firstChild.remove();
        }
    }, 3000);
}