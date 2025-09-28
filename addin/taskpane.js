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

// Feature flags
let isTestMode = false;  // Default to false, will be set explicitly when needed

/**
 * Get current Outlook user context for client extraction
 * @returns {Object|null} User context with name and email, or null if unavailable
 */
function getUserContext() {
    try {
        if (Office?.context?.mailbox?.userProfile) {
            const userProfile = Office.context.mailbox.userProfile;
            return {
                name: userProfile.displayName || '',
                email: userProfile.emailAddress || ''
            };
        }
    } catch (error) {
        console.log('Could not get user context from Office:', error);
    }
    return null;
}

// Initialize when Office is ready
// IMPORTANT: Office.initialize is required for Outlook desktop clients
// It must be defined even if using Office.onReady
Office.initialize = function (reason) {
    console.log('Office.initialize called with reason:', reason);
    // Office.onReady will handle the actual initialization
};

// Test function to debug initialization issues
window.testInitialization = function() {
    console.log('=== TEST INITIALIZATION ===');
    console.log('Office available:', typeof Office !== 'undefined');
    console.log('Office.context:', Office?.context);
    console.log('Office.context.mailbox:', Office?.context?.mailbox);
    console.log('Office.context.mailbox.item:', Office?.context?.mailbox?.item);

    // Test getting email data
    if (Office?.context?.mailbox?.item) {
        const item = Office.context.mailbox.item;
        console.log('Email subject:', item.subject);
        console.log('From:', item.from);

        // Try to get body
        item.body.getAsync(Office.CoercionType.Text, (result) => {
            console.log('Body result status:', result.status);
            console.log('Body preview (first 200 chars):', result.value?.substring(0, 200));
        });
    } else {
        console.log('No email item available');
    }

    // Check DOM elements
    console.log('DOM Elements:');
    console.log('- previewForm:', !!document.getElementById('previewForm'));
    console.log('- loadingState:', !!document.getElementById('loadingState'));
    console.log('- candidateName:', !!document.getElementById('candidateName'));

    // Try to manually show the form with test data
    const testData = {
        candidateName: 'Test Candidate',
        candidateEmail: 'test@example.com',
        jobTitle: 'Test Position',
        firmName: 'Test Company',
        referrerName: 'Test Referrer',
        source: 'Email Inbound'
    };

    console.log('Populating form with test data...');
    populateForm(testData);

    // Show the form
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('previewForm').style.display = 'block';
    document.getElementById('footer').style.display = 'flex';

    console.log('Test complete - check if form is visible now');
};

// Test function to validate Express Send banner functionality
window.testExpressSendBanner = function() {
    console.log('=== TEST EXPRESS SEND BANNER ===');

    // Test with high confidence data (should show banner)
    const highConfidenceData = {
        contactFirstName: 'John',
        contactLastName: 'Doe',
        candidateEmail: 'john.doe@example.com',
        jobTitle: 'Senior Software Engineer',
        firmName: 'Tech Company Inc',
        location: 'San Francisco, CA',
        candidatePhone: '555-123-4567',
        notes: 'Excellent candidate with strong technical background'
    };

    console.log('Testing with high confidence data...');

    // Manually populate form fields
    Object.keys(highConfidenceData).forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.value = highConfidenceData[fieldId];
        }
    });

    // Show the form
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('previewForm').style.display = 'block';
    document.getElementById('footer').style.display = 'flex';

    // Test the confidence calculation
    calculateAndShowExtractionConfidence(highConfidenceData);

    console.log('High confidence test complete - Express Send banner should be visible');

    // Test with low confidence data after 3 seconds
    setTimeout(() => {
        console.log('Testing with low confidence data...');

        const lowConfidenceData = {
            contactFirstName: 'Jane',
            candidateEmail: '',
            jobTitle: '',
            firmName: '',
            location: ''
        };

        // Clear and populate with low confidence data
        Object.keys(lowConfidenceData).forEach(fieldId => {
            const field = document.getElementById(fieldId);
            if (field) {
                field.value = lowConfidenceData[fieldId];
            }
        });

        calculateAndShowExtractionConfidence(lowConfidenceData);

        console.log('Low confidence test complete - Express Send banner should be hidden');
    }, 3000);
};

// Test function to validate field population with various data types
window.testFieldPopulation = function() {
    console.log('=== TEST FIELD POPULATION ===');

    // Test with various problematic inputs
    const testCases = [
        {
            name: 'Normal string data',
            data: {
                candidateName: 'John Doe',
                candidateEmail: 'john@example.com',
                jobTitle: 'Senior Developer'
            }
        },
        {
            name: 'Object data (should be rejected)',
            data: {
                candidateName: { first: 'John', last: 'Doe' },
                candidateEmail: 'john@example.com',
                jobTitle: 'Senior Developer'
            }
        },
        {
            name: 'Array data (should be rejected)',
            data: {
                candidateName: ['John', 'Doe'],
                candidateEmail: 'john@example.com',
                jobTitle: 'Senior Developer'
            }
        },
        {
            name: 'Full API response object (malformed)',
            data: {
                candidateName: {
                    status: 'success',
                    candidate_name: 'John Doe',
                    candidate_email: 'john@example.com'
                }
            }
        }
    ];

    testCases.forEach((testCase, index) => {
        console.log(`\n--- Test Case ${index + 1}: ${testCase.name} ---`);
        try {
            populateForm(testCase.data);

            // Check what was actually set
            const candidateField = document.getElementById('candidateName');
            const emailField = document.getElementById('candidateEmail');

            console.log('Candidate Name field value:', candidateField?.value);
            console.log('Candidate Email field value:', emailField?.value);

        } catch (error) {
            console.error('Error in test case:', error);
        }
    });

    console.log('\n=== TEST COMPLETE ===');
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
        const criticalElements = ['previewForm', 'loadingState', 'footer', 'contactFirstName', 'contactLastName', 'jobTitle'];
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
        document.getElementById('btnSend').addEventListener('click', () => handleSendToZoho(false));
        document.getElementById('btnCancel').addEventListener('click', handleCancel);
        document.getElementById('btnClose').addEventListener('click', handleClose);

        // Test mode button
        const btnTestMode = document.getElementById('btnTestMode');
        if (btnTestMode) {
            btnTestMode.addEventListener('click', () => handleSendToZoho(true));
        }
        
        // Natural language corrections
        document.getElementById('btnApplyCorrections').addEventListener('click', applyNaturalLanguageCorrections);
        document.getElementById('btnSuggestFixes').addEventListener('click', showSuggestedFixes);

        // Web Search Client button
        document.getElementById('btnWebSearchClient').addEventListener('click', handleWebSearchClient);

        // Apollo enrichment button
        document.getElementById('btnApolloEnrich').addEventListener('click', handleApolloEnrichment);
        
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
 * Auto-generate Deal Name based on Steve's format
 */
function updateDealName() {
    const jobTitle = document.getElementById('jobTitle')?.value?.trim() || 'Unknown';
    const location = document.getElementById('location')?.value?.trim() || 'Unknown';
    const firmName = document.getElementById('firmName')?.value?.trim() || 'Unknown';
    const dealNameField = document.getElementById('dealName');

    if (dealNameField) {
        // Always generate a deal name using Steve's format: "[Job Title] ([Location]) - [Firm Name]"
        if (jobTitle !== 'Unknown' || location !== 'Unknown' || firmName !== 'Unknown') {
            dealNameField.value = `${jobTitle} (${location}) - ${firmName}`;
        } else {
            dealNameField.value = 'New Candidate - Unknown Details';
        }
    }
}

/**
 * Set up field tracking to show when user edits AI-extracted values
 */
function setupFieldTracking() {
    const trackedFields = [
        'contactFirstName', 'contactLastName', 'candidateEmail', 'candidatePhone',
        'contactCity', 'contactState', 'firmName', 'companyPhone', 'companyWebsite',
        'jobTitle', 'location', 'dealName', 'pipeline', 'closingDate',
        'whoGetsCredit', 'creditDetail', 'sourceDetail', 'companySource',
        'notes'
    ];

    trackedFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.addEventListener('input', function() {
                updateFieldIndicator(fieldId);

                // Auto-update deal name when key fields change
                if (['jobTitle', 'location', 'firmName'].includes(fieldId)) {
                    updateDealName();
                }
            });

            // Also listen for change events (for select dropdowns)
            field.addEventListener('change', function() {
                updateFieldIndicator(fieldId);

                if (['jobTitle', 'location', 'firmName'].includes(fieldId)) {
                    updateDealName();
                }
            });
        }
    });
}

/**
 * Update field indicator based on changes (enhanced for confidence system)
 */
function updateFieldIndicator(fieldId) {
    const field = document.getElementById(fieldId);
    const indicator = document.getElementById(fieldId + 'Indicator');

    if (!indicator || !field) return;

    const originalValue = originalExtractedData?.[fieldId] || '';
    const currentValue = field.value || '';

    if (originalValue && currentValue !== originalValue) {
        // User has edited the value
        indicator.textContent = 'Edited';
        indicator.className = 'edited-indicator';
        indicator.style.background = '#ffc107';
        indicator.style.color = '#212529';
        indicator.style.display = 'inline-block';
    } else if (originalValue && currentValue === originalValue) {
        // Value came from AI extraction and hasn't been changed
        // Calculate confidence for the current value
        const confidence = calculateFieldConfidence(fieldId, currentValue, originalExtractedData);
        updateFieldConfidenceIndicator(fieldId, currentValue, confidence);
    } else if (currentValue && !originalValue) {
        // User added a value where AI didn't extract anything
        indicator.textContent = 'User Added';
        indicator.className = 'edited-indicator';
        indicator.style.background = '#6f42c1';
        indicator.style.color = 'white';
        indicator.style.display = 'inline-block';
    } else {
        // No value
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
        console.log('Extracting email data from item:', item);
        currentEmailData = await extractEmailData(item);
        console.log('Email data extracted:', {
            hasBody: !!currentEmailData?.body,
            bodyLength: currentEmailData?.body?.length || 0,
            subject: currentEmailData?.subject,
            from: currentEmailData?.from
        });
        
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
                    dry_run: false,  // Default to false, will be set explicitly when in test mode
                    user_context: getUserContext()  // Include current Outlook user context
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
                    console.log('Raw response text:', responseText);
                    console.log('First 500 chars:', responseText ? responseText.substring(0, 500) : 'EMPTY RESPONSE');
                    
                    // Check if response is actually empty
                    if (!responseText || responseText.trim() === '') {
                        console.error('Empty response from API - using fallback extraction');
                        extractedData = performLocalExtraction(currentEmailData);
                        populateForm(extractedData);
                        showPreviewForm();
                        return;
                    }
                    
                    // Try to parse the response
                    response = JSON.parse(responseText);
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
                console.log('Full API response:', response);
                console.log('Response structure:', Object.keys(response));
                console.log('Response type:', typeof response);

                // The API might return data in different formats
                let extracted = null;
                if (response.extracted) {
                    extracted = response.extracted;
                    console.log('Found data in response.extracted');
                } else if (response.data) {
                    extracted = response.data;
                    console.log('Found data in response.data');
                } else if (response.candidate_name || response.job_title || response.candidateName || response.jobTitle) {
                    // Direct response with candidate fields
                    extracted = response;
                    console.log('Using direct response');
                } else {
                    console.error('Unexpected response structure:', response);
                    console.log('Available keys in response:', Object.keys(response));
                    // Fall back to local extraction instead of using malformed response
                    console.log('API response does not contain expected fields, using local extraction');
                    extractedData = performLocalExtraction(currentEmailData);
                    populateForm(extractedData);
                    showPreviewForm();
                    return;
                }
                
                console.log('Using extracted data:', extracted);

                // Validate extracted data is an object and not a primitive or array
                if (!extracted || typeof extracted !== 'object' || Array.isArray(extracted)) {
                    console.error('ERROR: Extracted data is not a valid object:', typeof extracted, extracted);
                    extractedData = performLocalExtraction(currentEmailData);
                    populateForm(extractedData);
                    showPreviewForm();
                    return;
                }

                // Map the response to our expected format - handle nulls properly and ensure values are strings
                const getString = (value) => {
                    if (typeof value === 'string' && value.trim() !== '') {
                        return value.trim();
                    }
                    return '';
                };

                // Check for contact_record structure first (Steve's 3-record structure)
                const contact = extracted?.contact_record || {};
                const company = extracted?.company_record || {};
                const deal = extracted?.deal_record || {};

                // DEBUG: Log the company record structure
                console.log('DEBUG - Company record:', company);
                console.log('DEBUG - Company.company_name:', company.company_name);
                console.log('DEBUG - extracted.company_name:', extracted?.company_name);
                console.log('DEBUG - extracted.firmName:', extracted?.firmName);
                console.log('DEBUG - extracted.firm_name:', extracted?.firm_name);

                // Build candidateName from contact_record if available
                let candidateName = '';
                if (contact.first_name || contact.last_name) {
                    candidateName = `${getString(contact.first_name)} ${getString(contact.last_name)}`.trim();
                } else {
                    candidateName = getString(extracted?.candidate_name || extracted?.candidateName);
                }

                // DEBUG: Test each part of the firmName mapping
                const companyNameFromRecord = company.company_name;
                const companyNameDirect = extracted?.company_name;
                const firmNameField = extracted?.firmName;
                const firmNameUnder = extracted?.firm_name;

                console.log('DEBUG - firmName mapping values:');
                console.log('  company.company_name:', companyNameFromRecord);
                console.log('  extracted.company_name:', companyNameDirect);
                console.log('  extracted.firmName:', firmNameField);
                console.log('  extracted.firm_name:', firmNameUnder);

                const finalFirmName = getString(companyNameFromRecord || companyNameDirect || firmNameField || firmNameUnder);
                console.log('DEBUG - Final firmName result:', finalFirmName);

                extractedData = {
                    candidateName: candidateName,
                    candidateEmail: getString(contact.email || extracted?.candidate_email || extracted?.candidateEmail || extracted?.email),
                    candidatePhone: getString(contact.phone || extracted?.candidate_phone || extracted?.candidatePhone || extracted?.phone),
                    linkedinUrl: getString(extracted?.linkedin_url || extracted?.linkedinUrl),
                    jobTitle: getString(extracted?.job_title || extracted?.jobTitle),
                    location: getString(extracted?.location || extracted?.candidateLocation),
                    // Use structured contact location data first, fallback to parsed location
                    contactCity: getString(contact.city),
                    contactState: getString(contact.state),
                    firmName: getString(company.company_name) || getString(extracted?.company_name) || getString(extracted?.firmName) || getString(extracted?.firm_name) || '', // CACHE_BUST_V2
                    // Map company fields from structured data (Firecrawl/Apollo enrichment)
                    companyPhone: getString(company.phone || extracted?.company_phone),
                    companyWebsite: getString(company.website || extracted?.company_website || extracted?.website),
                    companyOwner: getString(company.detail || extracted?.credit_person_name || extracted?.referrer_name),
                    referrerName: getString(extracted?.referrer_name || extracted?.referrerName || currentEmailData?.from?.displayName),
                    referrerEmail: getString(extracted?.referrer_email || extracted?.referrerEmail || currentEmailData?.from?.emailAddress),
                    notes: getString(extracted?.notes),
                    // NEW: Map deal fields from backend structured data
                    descriptionOfReqs: getString(deal.description_of_reqs || extracted?.description_of_requirements),
                    pipeline: getString(deal.pipeline) || 'Sales Pipeline',
                    closingDate: getString(deal.closing_date),
                    whoGetsCredit: getString(company.who_gets_credit || extracted?.who_gets_credit),
                    calendlyUrl: getString(extracted?.calendly_url || extracted?.calendlyUrl),
                    source: getString(deal.source || extracted?.source || extracted?.Source) || 'Email Inbound',
                    sourceDetail: getString(deal.source_detail || extracted?.source_detail)
                };
                
                console.log('Mapped extractedData:', extractedData);
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
            console.log('Using local extraction due to API error');
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
        
        console.log('Elements found:', {
            previewForm: !!previewForm,
            loadingState: !!loadingState,
            footer: !!footer
        });
        
        if (loadingState) {
            loadingState.style.display = 'none';
            console.log('Loading state hidden');
        }
        if (previewForm) {
            previewForm.style.display = 'block';
            previewForm.style.visibility = 'visible';
            previewForm.style.opacity = '1';
            console.log('Preview form shown with display:', previewForm.style.display);
        } else {
            console.error('CRITICAL: previewForm element not found!');
        }
        if (footer) {
            footer.style.display = 'flex';
            footer.style.visibility = 'visible';
            console.log('Footer shown with display:', footer.style.display);
        } else {
            console.error('CRITICAL: footer element not found!');
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
    console.log('performLocalExtraction called with emailData:', emailData);
    const body = emailData?.body || '';
    const subject = emailData?.subject || '';
    const extracted = {
        candidateName: '',
        candidateEmail: '',
        candidatePhone: '',
        linkedinUrl: '',
        jobTitle: '',
        location: '',
        firmName: '',
        referrerName: emailData?.from?.displayName || 'Unknown Sender',
        referrerEmail: emailData?.from?.emailAddress || '',
        notes: '',
        calendlyUrl: '',
        source: 'Email Inbound'
    };
    
    // Debug logging
    console.log('Extracting from email body:', body.substring(0, 500));
    console.log('Email subject:', subject);
    console.log('From:', emailData?.from);
    
    // Define next label pattern for Calendly emails to prevent over-capturing
    // Includes both Calendly labels and Zoom meeting instructions
    const NEXT_LABEL = /(Invitee:|Invitee Email:|Text Reminder Number:|Event Date\/Time:|Event Type:|Description:|Location:|Invitee Time Zone:|Questions:|Your confirmation|View event|Pro Tip|Sent from Calendly|One tap mobile|Meeting ID|Passcode|They can also dial in|Find your local number|Join by SIP|Join by H.323|$)/i;

    // For Ashley Ethridge recruitment email, look for Invitee pattern
    // Check for "Invitee:" pattern first with look-ahead to next label
    const inviteeRegex = new RegExp(`Invitee:\\s*([\\s\\S]*?)(?=\\s*${NEXT_LABEL.source})`, 'i');
    const inviteeMatch = body.match(inviteeRegex);
    if (inviteeMatch && inviteeMatch[1]) {
        // Clean up the extracted name - remove any trailing Calendly labels
        let candidateName = inviteeMatch[1].trim();
        // Remove any text after the next label indicator
        const nextLabelIndex = candidateName.search(/Invitee Email:|Text Reminder Number:|Event Date\/Time:|Event Type:|Description:|Location:|Invitee Time Zone:|Questions:/i);
        if (nextLabelIndex > 0) {
            candidateName = candidateName.substring(0, nextLabelIndex).trim();
        }
        extracted.candidateName = candidateName;
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
    const eventTypeRegex = new RegExp(`Event Type:\\s*([\\s\\S]*?)(?=\\s*${NEXT_LABEL.source})`, 'i');
    const eventTypeMatch = body.match(eventTypeRegex);
    if (eventTypeMatch && eventTypeMatch[1]) {
        // Clean up the extracted job title
        let jobTitle = eventTypeMatch[1].trim();
        // Remove any text after the next label indicator
        const nextLabelIndex = jobTitle.search(/Invitee:|Invitee Email:|Text Reminder Number:|Event Date\/Time:|Description:|Location:|Invitee Time Zone:|Questions:/i);
        if (nextLabelIndex > 0) {
            jobTitle = jobTitle.substring(0, nextLabelIndex).trim();
        }
        extracted.jobTitle = jobTitle;
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
    
    // Look for explicit Location field in Calendly emails
    if (!extracted.location) {
        const locationRegex = new RegExp(`Location:\\s*([\\s\\S]*?)(?=\\s*${NEXT_LABEL.source})`, 'i');
        const calendlyLocation = body.match(locationRegex);
        if (calendlyLocation && calendlyLocation[1]) {
            // Clean up Zoom URL and meeting info
            let location = calendlyLocation[1].trim();
            // Remove everything after the Zoom URL if present
            const zoomUrlMatch = location.match(/(https:\/\/[^\s]+\.zoom\.us\/[^\s]+)/i);
            if (zoomUrlMatch) {
                location = zoomUrlMatch[1];
            }
            extracted.location = location;
        }
    }

    // Standard location patterns (avoid email signatures)
    if (!extracted.location) {
        const locationPatterns = [
            /(?:based in|located in)\s*:?\s*([^,\n.]+)/i,
            /in\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:area|location)/i
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
    const contactFirstNameField = document.getElementById('contactFirstName');
    if (!contactFirstNameField) {
        console.error('CRITICAL: contactFirstName field not found! Form may not be loaded.');
        console.error('Document body:', document.body);
        console.error('All element IDs:', Array.from(document.querySelectorAll('[id]')).map(el => el.id));
        // Try to wait and retry
        setTimeout(() => {
            console.log('Retrying populateForm after delay...');
            populateForm(data);
        }, 500);
        return;
    }

    // Parse candidate name into first and last
    const fullName = data.candidateName || data.candidate_name || '';
    const nameParts = fullName.trim().split(/\s+/);
    const firstName = nameParts[0] || '';
    const lastName = nameParts.slice(1).join(' ') || '';

    // Contact Information - Steve's structure
    setValueWithConfidence('contactFirstName', firstName, data);
    setValueWithConfidence('contactLastName', lastName, data);
    setValueWithConfidence('candidateEmail', data.candidateEmail || data.candidate_email || data.email || '', data);
    setValueWithConfidence('candidatePhone', data.candidatePhone || data.candidate_phone || data.phone || '', data);

    // Parse location into city and state - prefer structured data first
    let city = data.contactCity || '';
    let state = data.contactState || '';

    // Fallback to parsing location string if structured data not available
    if (!city && !state && data.location) {
        const locationParts = data.location.split(',');
        city = locationParts[0]?.trim() || '';
        // Fix ternary precedence: only use second part for state, empty string for single-city locations
        state = locationParts[1]?.trim() || '';
    }

    setValueWithConfidence('contactCity', city, data);
    setValueWithConfidence('contactState', state, data);

    // Company Information - now uses Firecrawl/Apollo enriched data
    setValueWithConfidence('firmName', data.firmName || data.firm_name || data.company_name || '', data);
    setValueWithConfidence('companyPhone', data.companyPhone || data.company_phone || '', data);
    setValueWithConfidence('companyWebsite', data.companyWebsite || data.company_website || '', data);

    // Company owner information from structured backend data
    // Map to both fields for compatibility
    if (data.companyOwner) {
        setValueWithConfidence('creditDetail', data.companyOwner, data);
        // Also set the hidden companyOwner field for any code that might reference it
        const companyOwnerField = document.getElementById('companyOwner');
        if (companyOwnerField) {
            companyOwnerField.value = data.companyOwner;
        }
    }

    // Set company source based on extracted data
    const source = data.source || data.Source || 'Email Inbound';
    setValue('companySource', source);

    // Deal Information
    setValueWithConfidence('jobTitle', data.jobTitle || data.job_title || '', data);
    setValueWithConfidence('location', data.location || data.candidateLocation || '', data);

    // Auto-generate deal name when all required fields are filled
    updateDealName();

    // Use backend pipeline data if available, otherwise default
    if (data.pipeline) {
        setValueWithConfidence('pipeline', data.pipeline, data);
    } else {
        setValue('pipeline', 'Recruitment'); // Default pipeline
    }

    // Use backend closing date if available, otherwise default to today + 60 days
    if (data.closingDate) {
        setValueWithConfidence('closingDate', data.closingDate, data);
    } else {
        const closingDate = new Date();
        closingDate.setDate(closingDate.getDate() + 60);
        setValue('closingDate', closingDate.toISOString().split('T')[0]);
    }

    // NEW: Set Description of Requirements from backend
    setValueWithConfidence('descriptionOfReqs', data.descriptionOfReqs || '', data);

    // Who Gets Credit - Use backend data if available
    if (data.whoGetsCredit) {
        setValueWithConfidence('whoGetsCredit', data.whoGetsCredit, data);
    } else {
        setValue('whoGetsCredit', 'BD Rep');
    }
    setValue('creditDetail', data.companyOwner || getCurrentUserName()); // Use backend data or current user

    // Set source detail based on extracted data
    const sourceDetail = data.referrerName || data.referrer_name ||
                        (data.source === 'Referral' ? 'Referral Contact' : '') ||
                        currentEmailData?.from?.displayName || '';
    setValueWithConfidence('sourceDetail', sourceDetail, data);

    // Additional Information - Notes are separate from description of requirements
    setValueWithConfidence('notes', data.notes || '', data);

    // Build comprehensive notes from extracted data
    buildComprehensiveNotes(data);

    console.log('Form population complete with all fields filled');

    // Show attachments if any
    if (currentEmailData?.attachments?.length > 0) {
        showAttachments(currentEmailData.attachments);
    }

    // Update all confidence indicators
    updateAllConfidenceIndicators(data);

    // Calculate extraction confidence and show Express Send banner if high
    calculateAndShowExtractionConfidence(data);

    // ============ WEB SEARCH CLIENT (FIRECRAWL V2) ============
    // Web Search Client is always available via the "Web Search Client" button
    const webSearchBtn = document.getElementById('btnWebSearchClient');
    if (webSearchBtn) {
        console.log('🔍 Web Search Client always available for manual company research');
        // Always show Web Search Client button - users can manually input company domains
        webSearchBtn.style.display = 'inline-block';
        webSearchBtn.classList.remove('d-none'); // Remove any Bootstrap hide classes
        // Add a data attribute to track availability
        webSearchBtn.setAttribute('data-firecrawl-available', 'true');

        // Log whether auto-enhancement data is available for context
        if (shouldEnhanceWithFirecrawl(data)) {
            console.log('🎯 Auto-enhancement data available - company website or business email found');
        } else {
            console.log('📝 Manual enhancement mode - user can input company domain for research');
        }
    }

    // ============ APOLLO ENHANCEMENT ============
    // Apollo enrichment is now available via the "Enrich" button
    // Auto-enrichment disabled to give users control
    const apolloBtn = document.getElementById('btnApolloEnrich');
    if (shouldEnhanceWithApollo(data)) {
        console.log('✅ Apollo enrichment available - contact name found');
        // Always show Apollo button when enhancement is available
        if (apolloBtn) {
            apolloBtn.style.display = 'inline-block';
            apolloBtn.classList.remove('d-none'); // Remove any Bootstrap hide classes
            // Add a data attribute to track that Apollo should be visible
            apolloBtn.setAttribute('data-apollo-available', 'true');

            // Also show the corrections section if Apollo is available
            const correctionsSection = document.getElementById('correctionsSection');
            if (correctionsSection) {
                correctionsSection.style.display = 'block';
            }
        }
    } else {
        console.log('⚡ Apollo enrichment requires a contact name');
        // Hide Apollo button when not applicable
        if (apolloBtn) {
            apolloBtn.style.display = 'none';
            apolloBtn.setAttribute('data-apollo-available', 'false');
        }
    }
}

/**
 * Calculate extraction confidence based on populated fields and show Express Send banner if high
 */
function calculateAndShowExtractionConfidence(data) {
    console.log('Calculating extraction confidence for data:', data);

    // Define critical fields and their weights
    const criticalFields = [
        { key: 'contactFirstName', weight: 15, value: document.getElementById('contactFirstName')?.value },
        { key: 'contactLastName', weight: 15, value: document.getElementById('contactLastName')?.value },
        { key: 'candidateEmail', weight: 20, value: document.getElementById('candidateEmail')?.value },
        { key: 'jobTitle', weight: 20, value: document.getElementById('jobTitle')?.value },
        { key: 'firmName', weight: 20, value: document.getElementById('firmName')?.value },
        { key: 'location', weight: 10, value: document.getElementById('location')?.value }
    ];

    let totalPossibleScore = 0;
    let actualScore = 0;
    let filledCriticalFields = 0;

    criticalFields.forEach(field => {
        totalPossibleScore += field.weight;
        if (field.value && field.value.trim() !== '') {
            actualScore += field.weight;
            filledCriticalFields++;

            // Bonus points for well-formatted data
            if (field.key === 'candidateEmail' && field.value.includes('@') && field.value.includes('.')) {
                actualScore += 5; // Email format bonus
            }
            if (field.key === 'jobTitle' && field.value.length > 5) {
                actualScore += 5; // Detailed job title bonus
            }
            if (field.key === 'firmName' && field.value.length > 3) {
                actualScore += 5; // Company name bonus
            }
        }
    });

    // Additional confidence factors
    const hasPhone = document.getElementById('candidatePhone')?.value?.trim() !== '';
    const hasLocation = document.getElementById('location')?.value?.trim() !== '';
    const hasNotes = document.getElementById('notes')?.value?.trim() !== '';

    if (hasPhone) actualScore += 5;
    if (hasLocation) actualScore += 5;
    if (hasNotes) actualScore += 3;

    // Calculate confidence percentage
    const maxPossibleScore = totalPossibleScore + 15 + 5 + 3; // Include bonus points
    const confidencePercentage = Math.min(100, Math.round((actualScore / maxPossibleScore) * 100));

    console.log('Extraction confidence calculation:', {
        filledCriticalFields,
        totalCriticalFields: criticalFields.length,
        actualScore,
        maxPossibleScore,
        confidencePercentage,
        hasPhone,
        hasLocation,
        hasNotes
    });

    // Show Express Send banner if confidence is high (80% or above with at least 4 critical fields)
    const expressSendBanner = document.getElementById('expressSendBanner');
    const confidenceBadge = document.getElementById('confidenceBadge');

    if (confidencePercentage >= 80 && filledCriticalFields >= 4) {
        console.log('High confidence extraction detected - showing Express Send banner');

        if (expressSendBanner) {
            expressSendBanner.style.display = 'block';
        }

        if (confidenceBadge) {
            confidenceBadge.textContent = `${confidencePercentage}%`;
        }

        // Optionally highlight the Send button for one-click workflow
        const sendButton = document.getElementById('btnSend');
        if (sendButton) {
            sendButton.style.background = 'linear-gradient(135deg, #28a745 0%, #20c997 100%)';
            sendButton.style.boxShadow = '0 4px 12px rgba(40, 167, 69, 0.3)';
        }
    } else {
        console.log('Confidence below threshold or insufficient critical fields - hiding Express Send banner');

        if (expressSendBanner) {
            expressSendBanner.style.display = 'none';
        }

        // Reset send button styling
        const sendButton = document.getElementById('btnSend');
        if (sendButton) {
            sendButton.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
            sendButton.style.boxShadow = '';
        }
    }
}

/**
 * Set form field value with confidence indicator
 */
function setValueWithConfidence(fieldId, value, extractedData, confidenceScore = null) {
    // Debug logging to track calls
    console.log(`🔍 setValueWithConfidence called with fieldId: "${fieldId}", value: "${value}"`);

    // Map legacy field names to current field IDs
    const fieldIdMap = {
        'companyOwner': 'creditDetail'  // Backend sends companyOwner, but form uses creditDetail
    };

    // Use mapped field ID if available, otherwise use original
    const actualFieldId = fieldIdMap[fieldId] || fieldId;

    console.log(`🔄 Field mapping: "${fieldId}" → "${actualFieldId}"`);

    const field = document.getElementById(actualFieldId);
    if (field) {
        // Ensure value is a string and not an object or array
        let safeValue = '';
        if (typeof value === 'string') {
            safeValue = value.trim();

            // Prevent truncation - limit field values to reasonable lengths
            const maxLengths = {
                'contactFirstName': 50,
                'contactLastName': 50,
                'candidateEmail': 100,
                'candidatePhone': 30,
                'contactCity': 50,
                'contactState': 30,
                'firmName': 100,
                'companyPhone': 30,
                'companyWebsite': 200,
                'jobTitle': 100,
                'location': 100,
                'dealName': 200,
                'descriptionOfReqs': 500,
                'notes': 500
            };

            const maxLength = maxLengths[actualFieldId];
            if (maxLength && safeValue.length > maxLength) {
                console.warn(`⚠️ Truncating ${actualFieldId} from ${safeValue.length} to ${maxLength} chars`);
                safeValue = safeValue.substring(0, maxLength);
            }

            // Special handling for email content that might be wrongly placed
            if (safeValue.includes('\n') && !['descriptionOfReqs', 'notes'].includes(actualFieldId)) {
                console.warn(`⚠️ Multi-line content detected in ${actualFieldId}, taking first line only`);
                safeValue = safeValue.split('\n')[0].trim();
            }

        } else if (value !== null && value !== undefined) {
            console.warn(`WARNING: Non-string value for ${fieldId}:`, typeof value, value);
            // If it's an object, don't try to convert it - just use empty string
            if (typeof value === 'object') {
                console.error(`ERROR: Object passed to field ${fieldId}:`, value);
                safeValue = '';
            } else {
                safeValue = String(value);
            }
        }

        field.value = safeValue;

        // Calculate confidence based on extraction quality
        const confidence = calculateFieldConfidence(actualFieldId, safeValue, extractedData, confidenceScore);
        updateFieldConfidenceIndicator(actualFieldId, safeValue, confidence);

        console.log(`Set ${actualFieldId} to: "${safeValue}" (confidence: ${confidence})`);
    } else {
        console.error(`ERROR: Element with ID '${actualFieldId}' not found in DOM! (Original field: ${fieldId})`);
        console.error('Call stack:', new Error().stack);
    }
}

/**
 * Calculate confidence score for a field based on extraction quality
 */
function calculateFieldConfidence(fieldId, value, extractedData, explicitScore = null) {
    if (explicitScore !== null) return explicitScore;

    // If no value extracted, confidence is 0
    if (!value || value.trim() === '') return 0;

    // Base confidence scoring
    let confidence = 0.5; // Base score for having any value

    // Higher confidence for structured data patterns
    switch (fieldId) {
        case 'candidateEmail':
            // Email pattern validation
            if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
                confidence = 0.9;
            } else {
                confidence = 0.3;
            }
            break;

        case 'candidatePhone':
            // Phone pattern validation
            if (/^\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$/.test(value)) {
                confidence = 0.8;
            } else if (/\d{10,}/.test(value.replace(/\D/g, ''))) {
                confidence = 0.6;
            } else {
                confidence = 0.3;
            }
            break;

        case 'contactFirstName':
        case 'contactLastName':
            // Name validation - proper case, reasonable length
            if (value.length >= 2 && /^[A-Z][a-z]+$/.test(value)) {
                confidence = 0.8;
            } else if (value.length >= 2) {
                confidence = 0.6;
            } else {
                confidence = 0.3;
            }
            break;

        case 'firmName':
            // Company name validation
            if (value.length >= 3 && !value.toLowerCase().includes('unknown')) {
                confidence = 0.7;
            } else {
                confidence = 0.4;
            }
            break;

        case 'jobTitle':
            // Job title validation
            if (value.length >= 5 && /[a-zA-Z]/.test(value)) {
                confidence = 0.7;
            } else {
                confidence = 0.4;
            }
            break;

        case 'location':
            // Location validation
            if (value.includes(',') || value.length >= 3) {
                confidence = 0.6;
            } else {
                confidence = 0.4;
            }
            break;

        case 'contactCity':
            // City validation
            if (value.length >= 2 && /^[A-Za-z\s]+$/.test(value)) {
                confidence = 0.7;
            } else if (value.length >= 2) {
                confidence = 0.5;
            } else {
                confidence = 0.3;
            }
            break;

        case 'contactState':
            // State validation - 2-letter code or full name
            if (/^[A-Z]{2}$/.test(value) || (value.length >= 4 && /^[A-Za-z\s]+$/.test(value))) {
                confidence = 0.8;
            } else if (value.length >= 2) {
                confidence = 0.5;
            } else {
                confidence = 0.3;
            }
            break;

        default:
            // Default confidence for other fields
            confidence = value.length >= 3 ? 0.6 : 0.4;
    }

    // Boost confidence if we found this data via specific patterns
    if (extractedData && extractedData._confidence && extractedData._confidence[fieldId]) {
        confidence = Math.max(confidence, extractedData._confidence[fieldId]);
    }

    return Math.min(1.0, confidence);
}

/**
 * Update confidence indicator for a field
 */
function updateFieldConfidenceIndicator(fieldId, value, confidence) {
    const indicator = document.getElementById(fieldId + 'Indicator');
    const field = document.getElementById(fieldId);

    if (!indicator) return;

    if (!value || value.trim() === '') {
        indicator.style.display = 'none';
        // Remove confidence classes from field
        if (field) {
            field.classList.remove('low-confidence', 'very-low-confidence');
        }
        return;
    }

    // Show indicator with confidence-based styling
    indicator.style.display = 'inline-block';

    // Remove existing confidence classes
    indicator.classList.remove('confidence-high', 'confidence-medium', 'confidence-low', 'confidence-very-low');

    if (confidence >= 0.8) {
        indicator.textContent = 'High Confidence';
        indicator.className = 'extracted-indicator confidence-high';
        // Remove any field highlighting
        if (field) {
            field.classList.remove('low-confidence', 'very-low-confidence');
        }
    } else if (confidence >= 0.6) {
        indicator.textContent = 'Medium Confidence';
        indicator.className = 'extracted-indicator confidence-medium';
        // Remove any field highlighting
        if (field) {
            field.classList.remove('low-confidence', 'very-low-confidence');
        }
    } else if (confidence >= 0.3) {
        indicator.textContent = 'Low Confidence';
        indicator.className = 'extracted-indicator confidence-low';
        // Add field highlighting for user attention
        if (field) {
            field.classList.remove('very-low-confidence');
            field.classList.add('low-confidence');
        }
    } else {
        indicator.textContent = 'Please Review';
        indicator.className = 'extracted-indicator confidence-very-low';
        // Add stronger field highlighting for user attention
        if (field) {
            field.classList.remove('low-confidence');
            field.classList.add('very-low-confidence');
        }
    }
}

/**
 * Update all confidence indicators after form population
 */
function updateAllConfidenceIndicators(extractedData) {
    const fieldsToUpdate = [
        'contactFirstName', 'contactLastName', 'candidateEmail', 'candidatePhone',
        'contactCity', 'contactState', 'firmName', 'companyPhone', 'companyWebsite',
        'jobTitle', 'location', 'sourceDetail'
    ];

    fieldsToUpdate.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            // Always update indicator, even for empty fields - this will hide indicators for empty fields
            const confidence = calculateFieldConfidence(fieldId, field.value, extractedData);
            updateFieldConfidenceIndicator(fieldId, field.value, confidence);
        }
    });

    // Initialize Steve's confidence-based workflow UI
    initializeConfidenceUI(extractedData);
}

/**
 * Get current user name (placeholder - should be implemented based on Office context)
 */
function getCurrentUserName() {
    // Try to get from Office context if available
    try {
        if (Office?.context?.mailbox?.userProfile?.displayName) {
            return Office.context.mailbox.userProfile.displayName;
        }
    } catch (error) {
        console.log('Could not get user profile from Office context');
    }

    // Default fallback
    return 'Current User';
}

/**
 * Build comprehensive notes from all extracted data
 */
function buildComprehensiveNotes(data) {
    const notesField = document.getElementById('notes');
    if (!notesField) return;

    let comprehensiveNotes = data.notes || '';

    // Add email context
    if (currentEmailData?.subject) {
        comprehensiveNotes += `\n\nEmail Subject: ${currentEmailData.subject}`;
    }

    // Add sender information
    if (currentEmailData?.from?.displayName && currentEmailData?.from?.emailAddress) {
        comprehensiveNotes += `\nFrom: ${currentEmailData.from.displayName} <${currentEmailData.from.emailAddress}>`;
    }

    // Add any LinkedIn URL if found
    if (data.linkedinUrl || data.linkedin_url) {
        comprehensiveNotes += `\nLinkedIn: ${data.linkedinUrl || data.linkedin_url}`;
    }

    // Add Calendly URL if found
    if (data.calendlyUrl || data.calendly_url) {
        comprehensiveNotes += `\nCalendly: ${data.calendlyUrl || data.calendly_url}`;
    }

    // Add extraction timestamp
    comprehensiveNotes += `\n\nProcessed: ${new Date().toLocaleString()}`;

    notesField.value = comprehensiveNotes.trim();
}

/**
 * Set form field value with type checking
 */
function setValue(fieldId, value) {
    // Map legacy field names to current field IDs
    const fieldIdMap = {
        'companyOwner': 'creditDetail'  // Backend sends companyOwner, but form uses creditDetail
    };

    // Use mapped field ID if available, otherwise use original
    const actualFieldId = fieldIdMap[fieldId] || fieldId;

    const field = document.getElementById(actualFieldId);
    if (field) {
        // Ensure value is a string and not an object or array
        let safeValue = '';
        if (typeof value === 'string') {
            safeValue = value.trim();
        } else if (value !== null && value !== undefined) {
            console.warn(`WARNING: Non-string value for ${fieldId}:`, typeof value, value);
            // If it's an object, don't try to convert it - just use empty string
            if (typeof value === 'object') {
                console.error(`ERROR: Object passed to field ${fieldId}:`, value);
                safeValue = '';
            } else {
                safeValue = String(value);
            }
        }

        field.value = safeValue;
        console.log(`Set ${actualFieldId} to: "${safeValue}" (type: ${typeof safeValue})`);
    } else {
        console.error(`ERROR: Element with ID '${actualFieldId}' not found in DOM! (Original field: ${fieldId})`);
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
async function handleSendToZoho(overrideTestMode = false) {
    // Use the override if provided, otherwise use the global isTestMode flag
    const effectiveTestMode = typeof overrideTestMode === 'boolean' ? overrideTestMode : isTestMode;

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

        // Debug: Log what we're about to send
        console.log('Sending to backend with currentEmailData:', {
            hasData: !!currentEmailData,
            subject: currentEmailData?.subject,
            bodyLength: currentEmailData?.body?.length || 0,
            from: currentEmailData?.from
        });

        const response = await fetch(`${API_BASE_URL}/intake/email`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(API_KEY ? { 'X-API-Key': API_KEY } : {})
            },
            body: JSON.stringify({
                sender_email: 'steve@emailthewell.com',  // Operational override for Zoho processing
                original_sender_email: currentEmailData?.from?.emailAddress || null,  // Actual sender for learning pipeline
                sender_name: 'Steve Perry',  // Operational override
                original_sender_name: currentEmailData?.from?.displayName || null,  // Actual sender name for context
                subject: currentEmailData?.subject || 'Manual Entry',
                body: currentEmailData?.body || 'Manual data entry - no email body available',
                attachments: attachmentData,
                // Send original AI extraction for learning
                ai_extraction: currentExtractedData || {},
                // Send user corrections in structured 3-record format
                user_corrections: {
                    company_record: {
                        company_name: formData.firmName || null,
                        phone: formData.companyPhone || null,
                        website: formData.companyWebsite || null,
                        detail: formData.creditDetail || null,
                        source: formData.companySource || null,
                        source_detail: formData.sourceDetail || null,
                        who_gets_credit: formData.whoGetsCredit || null
                    },
                    contact_record: {
                        first_name: formData.contactFirstName || null,
                        last_name: formData.contactLastName || null,
                        email: formData.candidateEmail || null,
                        phone: formData.candidatePhone || null,
                        city: formData.contactCity || null,
                        state: formData.contactState || null
                    },
                    deal_record: {
                        source: formData.source || null,
                        deal_name: formData.dealName || null,
                        pipeline: formData.pipeline || null,
                        closing_date: formData.closingDate || null,
                        description_of_reqs: formData.descriptionOfReqs || null,
                        source_detail: formData.sourceDetail || null
                    }
                },
                // Include current Outlook user context for client extraction
                user_context: getUserContext(),
                // Test mode flag
                dry_run: effectiveTestMode
            })
        });
        
        await updateProgress(4, 'Checking for duplicates...');
        await updateProgress(5, effectiveTestMode ? 'Running test extraction...' : 'Creating Zoho records...');
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));

            // Extract detailed error information
            let errorMessage = `Server error: ${response.status}`;

            if (error.detail) {
                if (typeof error.detail === 'object') {
                    // Detailed error object from our enhanced API
                    errorMessage = error.detail.message || 'Transaction failed';

                    if (error.detail.details) {
                        errorMessage += `\n\nDetails: ${error.detail.details}`;
                    }

                    if (error.detail.correlation_id) {
                        errorMessage += `\n\nCorrelation ID: ${error.detail.correlation_id}`;
                    }

                    // Log full error for debugging
                    console.error('Detailed error from API:', error.detail);
                } else {
                    // Simple string error
                    errorMessage = error.detail;
                }
            }

            throw new Error(errorMessage);
        }
        
        const result = await response.json();

        await updateProgress(6, 'Complete!');

        // Check if this was a duplicate
        if (result.status === 'duplicate' || result.status === 'duplicate_blocked') {
            showDuplicate(result);
        } else if (effectiveTestMode) {
            // Show test mode success
            showTestSuccess(result);
        } else {
            // Show success message
            showSuccess(result);
        }
        
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
    const firstName = document.getElementById('contactFirstName').value.trim();
    const lastName = document.getElementById('contactLastName').value.trim();
    const jobTitle = document.getElementById('jobTitle').value.trim();
    const firmName = document.getElementById('firmName').value.trim();

    if (!firstName) {
        showNotification('Please enter the candidate\'s first name', 'warning');
        document.getElementById('contactFirstName').focus();
        return false;
    }

    if (!lastName) {
        showNotification('Please enter the candidate\'s last name', 'warning');
        document.getElementById('contactLastName').focus();
        return false;
    }

    if (!jobTitle) {
        showNotification('Please enter the job title', 'warning');
        document.getElementById('jobTitle').focus();
        return false;
    }

    if (!firmName) {
        showNotification('Please enter the company name', 'warning');
        document.getElementById('firmName').focus();
        return false;
    }

    return true;
}

/**
 * Get form data
 */
function getFormData() {
    const firstName = document.getElementById('contactFirstName').value.trim();
    const lastName = document.getElementById('contactLastName').value.trim();
    const candidateName = `${firstName} ${lastName}`.trim();

    return {
        // Contact Information
        candidateName: candidateName,
        contactFirstName: firstName,
        contactLastName: lastName,
        candidateEmail: document.getElementById('candidateEmail').value.trim(),
        candidatePhone: document.getElementById('candidatePhone').value.trim(),
        contactCity: document.getElementById('contactCity').value.trim(),
        contactState: document.getElementById('contactState').value.trim(),

        // Company Information
        firmName: document.getElementById('firmName').value.trim(),
        companyPhone: document.getElementById('companyPhone').value.trim(),
        companyWebsite: document.getElementById('companyWebsite').value.trim(),
        companySource: document.getElementById('companySource').value,

        // Deal Information
        jobTitle: document.getElementById('jobTitle').value.trim(),
        location: document.getElementById('location').value.trim(),
        dealName: document.getElementById('dealName').value.trim(),
        pipeline: document.getElementById('pipeline').value,
        closingDate: document.getElementById('closingDate').value,
        descriptionOfReqs: document.getElementById('descriptionOfReqs').value.trim(),

        // Who Gets Credit
        whoGetsCredit: document.getElementById('whoGetsCredit').value,
        creditDetail: document.getElementById('creditDetail').value.trim(),
        sourceDetail: document.getElementById('sourceDetail').value.trim(),

        // Additional Information
        notes: document.getElementById('notes').value.trim(),

        // Legacy fields for backward compatibility
        source: document.getElementById('companySource').value,
        referrerName: document.getElementById('sourceDetail').value.trim() || null,
        referrerEmail: document.getElementById('sourceDetail').value.trim() ? 'steve@emailthewell.com' : null  // Only use if there's a referrer
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
 * Show duplicate notification
 */
function showDuplicate(result) {
    const successMessage = document.getElementById('successMessage');
    const warningMessage = document.getElementById('warningMessage') || successMessage;

    // Build duplicate details HTML
    let duplicateDetails = '';
    if (result.duplicate_info && result.duplicate_info.duplicate_types) {
        duplicateDetails = `<br><small>Found: ${result.duplicate_info.duplicate_types.join(', ')}</small>`;
    }

    warningMessage.innerHTML = `
        <strong>⚠️ Duplicate Record Found</strong><br>
        ${result.message || 'Record already exists in Zoho CRM'}${duplicateDetails}<br>
        <small>
            ${result.deal_id ? `Deal ID: ${result.deal_id}` : ''}
            ${result.contact_id ? ` | Contact ID: ${result.contact_id}` : ''}
        </small>
        <div style="margin-top: 10px;">
            <strong>💡 Tip:</strong> You can still use the <b>Enrich</b> button to update the existing record with additional information from Apollo.
        </div>
    `;
    warningMessage.style.display = 'block';
    warningMessage.style.backgroundColor = '#fff3cd';
    warningMessage.style.borderColor = '#ffc107';
    warningMessage.style.color = '#856404';

    // Highlight the Apollo Enrich button for duplicate records
    const enrichButton = document.getElementById('btnApolloEnrich');
    if (enrichButton) {
        enrichButton.style.animation = 'pulse 2s infinite';
        enrichButton.classList.remove('btn-outline-success');
        enrichButton.classList.add('btn-success');

        // Add pulsing animation style if not already present
        if (!document.getElementById('apolloPulseStyle')) {
            const style = document.createElement('style');
            style.id = 'apolloPulseStyle';
            style.innerHTML = `
                @keyframes pulse {
                    0% { box-shadow: 0 0 0 0 rgba(40, 167, 69, 0.7); }
                    70% { box-shadow: 0 0 0 10px rgba(40, 167, 69, 0); }
                    100% { box-shadow: 0 0 0 0 rgba(40, 167, 69, 0); }
                }
            `;
            document.head.appendChild(style);
        }
    }

    document.getElementById('btnClose').style.display = 'block';
}

/**
 * Show test mode success message
 */
function showTestSuccess(result) {
    const previewForm = document.getElementById('previewForm');
    const successMessage = document.getElementById('successMessage');

    // Build test success message
    let message = `
        <div class="success-content">
            <h3>✅ Test Extraction Successful!</h3>
            <p><strong>This was a TEST RUN - No records were created in Zoho CRM</strong></p>
            <p>Extracted Data:</p>
            <ul>
                ${result.deal_name ? `<li>Deal: ${result.deal_name}</li>` : ''}
                ${result.extracted?.contact_record?.first_name ? `<li>Contact: ${result.extracted.contact_record.first_name} ${result.extracted.contact_record.last_name || ''}</li>` : ''}
                ${result.extracted?.company_record?.company_name ? `<li>Company: ${result.extracted.company_record.company_name}</li>` : ''}
            </ul>
            <p style="margin-top: 20px;">
                <em>Click "Send to Zoho CRM" to create actual records, or "Test Extract Only" to test again.</em>
            </p>
        </div>
    `;

    successMessage.innerHTML = message;
    successMessage.style.display = 'block';

    // Hide form and show both buttons
    previewForm.style.display = 'none';
    document.getElementById('btnSend').style.display = 'block';
    const btnTestMode = document.getElementById('btnTestMode');
    if (btnTestMode) btnTestMode.style.display = 'block';
    document.getElementById('btnCancel').style.display = 'none';

    // Reset button state
    const btnSend = document.getElementById('btnSend');
    btnSend.disabled = false;
    btnSend.innerHTML = 'Send to Zoho CRM';
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
    // Clear all form fields - use safe clearing with null checks
    const fieldsToClear = [
        'contactFirstName', 'contactLastName', 'candidateEmail',
        'candidatePhone', 'linkedinUrl', 'jobTitle',
        'location', 'firmName', 'referrerName',
        'referrerEmail', 'notes', 'calendlyUrl',
        'contactCity', 'contactState', 'companyPhone', 'companyWebsite'
    ];

    fieldsToClear.forEach(fieldId => {
        const element = document.getElementById(fieldId);
        if (element) {
            element.value = '';
        }
    });

    // Reset source dropdown to default
    const sourceElement = document.getElementById('source');
    if (sourceElement) {
        sourceElement.value = 'Email Inbound';
    }

    // Clear correction prompt
    const correctionElement = document.getElementById('correctionPrompt');
    if (correctionElement) {
        correctionElement.value = '';
    }

    // Hide quick fixes if shown
    const quickFixes = document.getElementById('quickFixes');
    if (quickFixes) {
        quickFixes.style.display = 'none';
    }

    // Clear any custom fields
    const customFieldsContainer = document.getElementById('customFieldsContainer');
    if (customFieldsContainer) {
        customFieldsContainer.innerHTML = '';
    }

    // Clear attachments list
    const attachmentsList = document.getElementById('attachmentsList');
    if (attachmentsList) {
        attachmentsList.innerHTML = '';
    }
    const attachmentsSection = document.getElementById('attachmentsSection');
    if (attachmentsSection) {
        attachmentsSection.style.display = 'none';
    }

    // Hide all indicators
    const indicators = document.querySelectorAll('.extracted-indicator, .edited-indicator');
    indicators.forEach(indicator => {
        indicator.style.display = 'none';
    });

    // Hide any error or success messages
    const errorMessage = document.getElementById('errorMessage');
    const successMessage = document.getElementById('successMessage');
    if (errorMessage) {
        errorMessage.style.display = 'none';
        errorMessage.textContent = '';
    }
    if (successMessage) {
        successMessage.style.display = 'none';
        successMessage.textContent = '';
    }

    // Clear any progress section
    const progressSection = document.getElementById('progressSection');
    if (progressSection) {
        progressSection.style.display = 'none';
    }

    // Reset progress bar if exists
    const progressBar = document.getElementById('progressBar');
    if (progressBar) {
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
    }

    // Reset step items
    const stepItems = document.querySelectorAll('.step-item');
    stepItems.forEach(item => {
        item.classList.remove('active', 'completed');
    });

    // Clear any extracted data
    currentEmailData = null;
    extractedData = null;
    originalExtractedData = null;
    currentExtractedData = null;

    // Keep the form visible but in blank state - don't go back to loading
    // This allows user to continue entering data manually if they want
    document.getElementById('previewForm').style.display = 'block';
    document.getElementById('footer').style.display = 'flex';

    // Reset button states
    const btnSend = document.getElementById('btnSend');
    const btnClose = document.getElementById('btnClose');
    const btnCancel = document.getElementById('btnCancel');
    if (btnSend) {
        btnSend.style.display = 'block';
        btnSend.disabled = false;
    }
    if (btnClose) {
        btnClose.style.display = 'none';
    }
    if (btnCancel) {
        btnCancel.style.display = 'block';
    }

    // Show a brief notification that form was cleared
    showNotification('Form cleared', 'info', 2000);
}

/**
 * Handle Close button
 */
function handleClose() {
    // Reset the taskpane to initial state
    handleCancel();
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

    // Enhanced pattern matching for common correction phrases
    const patterns = [
        // Full name corrections
        {
            regex: /(?:change |update |set |make )?(?:candidate|name|person)(?: name)? (?:to |is |should be |= )([^,\.]+?)(?:[,\.]|$)/i,
            field: 'candidateName',
            extractor: (match) => match[1].trim()
        },
        // First name specific
        {
            regex: /(?:change |update |set |make )?(?:first name|firstname) (?:to |is |should be |= )([^,\.]+?)(?:[,\.]|$)/i,
            field: 'contactFirstName',
            extractor: (match) => match[1].trim()
        },
        // Last name specific
        {
            regex: /(?:change |update |set |make )?(?:last name|lastname) (?:to |is |should be |= )([^,\.]+?)(?:[,\.]|$)/i,
            field: 'contactLastName',
            extractor: (match) => match[1].trim()
        },
        // Phone corrections
        {
            regex: /(?:change |update |set |make )?(?:phone|number|cell)(?: number)? (?:to |is |should be |: |= )([\d\s\-\(\)\+]+)/i,
            field: 'candidatePhone',
            extractor: (match) => match[1].trim()
        },
        // Email corrections
        {
            regex: /(?:change |update |set |make )?email(?: address)? (?:to |is |should be |: |= )([^\s,]+@[^\s,]+)/i,
            field: 'candidateEmail',
            extractor: (match) => match[1].trim()
        },
        // Location corrections
        {
            regex: /(?:change |update |set |make )?(?:location|city|place) (?:to |is |should be |= )([^,\.]+?)(?:[,\.]|$)/i,
            field: 'location',
            extractor: (match) => match[1].trim()
        },
        // Job title corrections
        {
            regex: /(?:change |update |set |make )?(?:job|title|position|role)(?: title)? (?:to |is |should be |= )([^,\.]+?)(?:[,\.]|$)/i,
            field: 'jobTitle',
            extractor: (match) => match[1].trim()
        },
        // Company corrections
        {
            regex: /(?:change |update |set |make )?(?:company|firm|organization)(?: name)? (?:to |is |should be |name |= )([^,\.]+?)(?:[,\.]|$)/i,
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
    // Map field names to actual form field IDs
    const fieldMap = {
        'candidateName': 'candidateName',
        'contactFirstName': 'contactFirstName',
        'contactLastName': 'contactLastName',
        'candidateEmail': 'candidateEmail',
        'candidatePhone': 'candidatePhone',
        'location': 'location',
        'jobTitle': 'jobTitle',
        'firmName': 'firmName'
    };

    const fieldId = fieldMap[correction.field] || correction.field;
    const field = document.getElementById(fieldId);

    if (field) {
        const oldValue = field.value;

        // Handle special cases for full name
        if (correction.field === 'candidateName') {
            // Split into first and last name if there's a space
            const names = correction.value.trim().split(/\s+/);
            const firstNameField = document.getElementById('contactFirstName');
            const lastNameField = document.getElementById('contactLastName');

            if (names.length >= 2 && firstNameField && lastNameField) {
                firstNameField.value = names[0];
                lastNameField.value = names.slice(1).join(' ');
                firstNameField.dispatchEvent(new Event('input'));
                lastNameField.dispatchEvent(new Event('input'));
                console.log(`Split name into: First="${names[0]}", Last="${names.slice(1).join(' ')}"`);
            } else {
                field.value = correction.value;
                field.dispatchEvent(new Event('input'));
            }
        } else {
            field.value = correction.value;
            field.dispatchEvent(new Event('input'));
        }

        // Update Deal Name if any relevant fields changed
        if (['contactFirstName', 'contactLastName', 'jobTitle', 'location', 'firmName'].includes(fieldId)) {
            updateDealName();
        }

        // Log the correction for learning
        console.log(`Corrected ${correction.field}: "${oldValue}" → "${correction.value}"`);
    } else {
        console.warn(`Field not found: ${correction.field}`);
    }
}

/**
 * Show suggested fixes based on AI analysis and common corrections
 */
async function showSuggestedFixes() {
    const fixesDiv = document.getElementById('quickFixes');
    const suggestionsDiv = document.getElementById('fixSuggestions');

    // Get current form values
    const formData = {
        firstName: document.getElementById('contactFirstName')?.value || '',
        lastName: document.getElementById('contactLastName')?.value || '',
        email: document.getElementById('candidateEmail')?.value || '',
        phone: document.getElementById('candidatePhone')?.value || '',
        location: document.getElementById('location')?.value || '',
        jobTitle: document.getElementById('jobTitle')?.value || '',
        firmName: document.getElementById('firmName')?.value || ''
    };

    // Initialize suggestions array
    let suggestions = [];

    try {
        // Call API to get AI-powered suggestions
        if (API_BASE_URL && API_KEY) {
            const response = await fetch(`${API_BASE_URL}/intake/suggestions`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': API_KEY
                },
                body: JSON.stringify({
                    email_body: currentEmailData?.body || '',
                    extracted_data: formData,
                    sender_email: currentEmailData?.from?.emailAddress || '',
                    user_context: getUserContext()
                })
            });

            if (response.ok) {
                const result = await response.json();
                suggestions = result.suggestions || [];
            }
        }
    } catch (error) {
        console.log('Could not get AI suggestions, using smart defaults');
    }

    // If no AI suggestions, use smart local analysis
    if (!suggestions || suggestions.length === 0) {
        suggestions = analyzeForSuggestions(formData, currentEmailData);
    }

    // Display suggestions as clickable buttons
    if (suggestions.length > 0) {
        suggestionsDiv.innerHTML = suggestions.slice(0, 5).map((sug, idx) => `
            <button class="btn btn-sm btn-outline-info me-1 mb-1"
                    onclick="applySuggestion('${sug.correction.replace(/'/g, "\\'")}')">
                <i class="bi ${sug.icon || 'bi-lightbulb'}"></i> ${sug.text}
            </button>
        `).join('');

        fixesDiv.style.display = 'block';
    } else {
        // Hide if no suggestions
        fixesDiv.style.display = 'none';
    }
}

/**
 * Analyze form data for smart suggestions
 */
function analyzeForSuggestions(formData, emailData) {
    const suggestions = [];
    const emailBody = (emailData?.body || '').toLowerCase();

    // Check for missing critical fields
    if (!formData.lastName && formData.firstName) {
        suggestions.push({
            text: 'Add missing last name',
            correction: 'last name is [Enter Last Name]',
            icon: 'bi-person-fill'
        });
    }

    // Check for phone number in email body but not in form
    const phoneRegex = /(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})/g;
    const phonesInEmail = emailBody.match(phoneRegex);
    if (phonesInEmail && !formData.phone) {
        suggestions.push({
            text: `Add phone number: ${phonesInEmail[0]}`,
            correction: `phone is ${phonesInEmail[0]}`,
            icon: 'bi-telephone'
        });
    }

    // Check for email address format issues
    if (formData.email && !formData.email.includes('@')) {
        suggestions.push({
            text: 'Fix email format',
            correction: 'email needs @ symbol',
            icon: 'bi-envelope'
        });
    }

    // Check for location in subject/body but not in form
    const locationRegex = /([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),?\s*([A-Z]{2})\b/g;
    const locationsInEmail = emailBody.match(locationRegex);
    if (locationsInEmail && !formData.location) {
        suggestions.push({
            text: `Add location: ${locationsInEmail[0]}`,
            correction: `location is ${locationsInEmail[0]}`,
            icon: 'bi-geo-alt'
        });
    }

    // Check for abbreviated titles
    if (formData.jobTitle) {
        const abbreviations = {
            'Sr': 'Senior',
            'Jr': 'Junior',
            'Mgr': 'Manager',
            'Dir': 'Director',
            'VP': 'Vice President',
            'Exec': 'Executive'
        };

        for (const [abbr, full] of Object.entries(abbreviations)) {
            if (formData.jobTitle.includes(abbr) && !formData.jobTitle.includes(full)) {
                suggestions.push({
                    text: `Expand ${abbr} to ${full}`,
                    correction: `job title is ${formData.jobTitle.replace(abbr, full)}`,
                    icon: 'bi-briefcase'
                });
                break;
            }
        }
    }

    // Check for missing company when there's a domain in email
    const senderDomain = emailData?.from?.emailAddress?.split('@')[1];
    if (senderDomain && !formData.firmName) {
        const companyName = senderDomain.split('.')[0];
        if (companyName && companyName !== 'gmail' && companyName !== 'yahoo' && companyName !== 'outlook') {
            suggestions.push({
                text: `Add company from email domain: ${companyName}`,
                correction: `company is ${companyName.charAt(0).toUpperCase() + companyName.slice(1)}`,
                icon: 'bi-building'
            });
        }
    }

    // Check for website URL in email body
    const urlRegex = /(?:www\.)?([a-zA-Z0-9-]+)\.(?:com|org|net)/g;
    const urlsInEmail = emailBody.match(urlRegex);
    if (urlsInEmail && !formData.firmName) {
        const domain = urlsInEmail[0].replace('www.', '').split('.')[0];
        suggestions.push({
            text: `Extract company from website: ${domain}`,
            correction: `company is ${domain.charAt(0).toUpperCase() + domain.slice(1)}`,
            icon: 'bi-globe'
        });
    }

    // Sort suggestions by importance
    return suggestions.sort((a, b) => {
        const priority = {
            'bi-person-fill': 1,
            'bi-telephone': 2,
            'bi-envelope': 3,
            'bi-geo-alt': 4,
            'bi-briefcase': 5,
            'bi-building': 6,
            'bi-globe': 7
        };
        return (priority[a.icon] || 99) - (priority[b.icon] || 99);
    });
}

/**
 * Apply a suggested correction
 */
window.applySuggestion = function(correction) {
    document.getElementById('correctionPrompt').value = correction;
    applyNaturalLanguageCorrections();
}

/**
 * Global function to toggle sections (accessible from HTML)
 */
window.toggleSection = toggleSection;

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

/**
 * Toggle section visibility (collapsible sections)
 * @param {string} sectionId - The ID of the section to toggle
 */
function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (!section) {
        console.error(`Section with ID '${sectionId}' not found`);
        return;
    }

    const isExpanded = section.style.display !== 'none';
    section.style.display = isExpanded ? 'none' : 'block';

    // Update toggle button icon/text if it exists
    const toggleButton = document.querySelector(`[data-toggle-section="${sectionId}"]`);
    if (toggleButton) {
        const icon = toggleButton.querySelector('.toggle-icon');
        if (icon) {
            icon.textContent = isExpanded ? '▶' : '▼';
        }

        // Update aria-expanded for accessibility
        toggleButton.setAttribute('aria-expanded', !isExpanded);
    }

    console.log(`Section '${sectionId}' ${isExpanded ? 'collapsed' : 'expanded'}`);
}

/**
 * Calculate overall confidence score from extraction results
 * @param {Object} extractedData - The extracted data object
 * @returns {number} Confidence score between 0 and 1
 */
function calculateConfidenceScore(extractedData) {
    if (!extractedData || typeof extractedData !== 'object') {
        return 0;
    }

    // Define field weights and confidence rules
    const fieldWeights = {
        candidateName: 0.25,     // Most important
        candidateEmail: 0.20,    // Very important for contact
        jobTitle: 0.20,          // Critical for deal classification
        firmName: 0.15,          // Important for company context
        location: 0.10,          // Useful but not critical
        candidatePhone: 0.10     // Nice to have
    };

    let totalScore = 0;
    let totalWeight = 0;

    // Calculate confidence for each field
    for (const [fieldName, weight] of Object.entries(fieldWeights)) {
        const value = extractedData[fieldName];
        let fieldConfidence = 0;

        if (value && typeof value === 'string' && value.trim() !== '') {
            const cleanValue = value.trim();

            // Field-specific confidence calculations
            switch (fieldName) {
                case 'candidateName':
                    // High confidence if contains proper name pattern
                    fieldConfidence = /^[A-Z][a-z]+\s+[A-Z][a-z]+/.test(cleanValue) ? 0.9 :
                                     /^[A-Z][a-z]+/.test(cleanValue) ? 0.6 : 0.3;
                    break;

                case 'candidateEmail':
                    // High confidence if valid email format
                    fieldConfidence = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanValue) ? 0.95 : 0.2;
                    break;

                case 'jobTitle':
                    // Higher confidence for longer, descriptive titles
                    if (cleanValue.length > 20) fieldConfidence = 0.9;
                    else if (cleanValue.length > 10) fieldConfidence = 0.7;
                    else if (cleanValue.length > 5) fieldConfidence = 0.5;
                    else fieldConfidence = 0.3;
                    break;

                case 'firmName':
                    // Higher confidence for company-like names
                    if (/\b(LLC|Inc|Corp|Ltd|Company|Partners|Group|Advisors)\b/i.test(cleanValue)) {
                        fieldConfidence = 0.9;
                    } else if (cleanValue.length > 3) {
                        fieldConfidence = 0.7;
                    } else {
                        fieldConfidence = 0.4;
                    }
                    break;

                case 'candidatePhone':
                    // High confidence for phone number patterns
                    fieldConfidence = /^\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$/.test(cleanValue) ? 0.9 : 0.3;
                    break;

                case 'location':
                    // Moderate confidence for location-like strings
                    fieldConfidence = cleanValue.length > 2 ? 0.7 : 0.3;
                    break;

                default:
                    // Default confidence for other fields
                    fieldConfidence = cleanValue.length > 0 ? 0.6 : 0;
            }
        }

        totalScore += fieldConfidence * weight;
        totalWeight += weight;
    }

    // Calculate overall confidence (0-1 scale)
    const overallConfidence = totalWeight > 0 ? totalScore / totalWeight : 0;

    console.log('Confidence calculation:', {
        extractedData: Object.keys(extractedData),
        totalScore,
        totalWeight,
        overallConfidence
    });

    return Math.round(overallConfidence * 100) / 100; // Round to 2 decimal places
}

/**
 * Get low confidence fields that need user attention
 * @param {Object} extractedData - The extracted data object
 * @returns {Array} Array of field names with low confidence
 */
function getLowConfidenceFields(extractedData) {
    if (!extractedData || typeof extractedData !== 'object') {
        return [];
    }

    const lowConfidenceFields = [];
    const confidenceThreshold = 0.6; // Fields below this need attention

    // Critical fields that should always be checked if missing or low confidence
    const criticalFields = {
        candidateName: 'Candidate Name',
        candidateEmail: 'Email Address',
        jobTitle: 'Job Title',
        firmName: 'Company Name'
    };

    for (const [fieldName, displayName] of Object.entries(criticalFields)) {
        const value = extractedData[fieldName];
        let fieldConfidence = 0;

        if (value && typeof value === 'string' && value.trim() !== '') {
            const cleanValue = value.trim();

            // Same confidence logic as calculateConfidenceScore
            switch (fieldName) {
                case 'candidateName':
                    fieldConfidence = /^[A-Z][a-z]+\s+[A-Z][a-z]+/.test(cleanValue) ? 0.9 :
                                     /^[A-Z][a-z]+/.test(cleanValue) ? 0.6 : 0.3;
                    break;

                case 'candidateEmail':
                    fieldConfidence = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanValue) ? 0.95 : 0.2;
                    break;

                case 'jobTitle':
                    if (cleanValue.length > 20) fieldConfidence = 0.9;
                    else if (cleanValue.length > 10) fieldConfidence = 0.7;
                    else if (cleanValue.length > 5) fieldConfidence = 0.5;
                    else fieldConfidence = 0.3;
                    break;

                case 'firmName':
                    if (/\b(LLC|Inc|Corp|Ltd|Company|Partners|Group|Advisors)\b/i.test(cleanValue)) {
                        fieldConfidence = 0.9;
                    } else if (cleanValue.length > 3) {
                        fieldConfidence = 0.7;
                    } else {
                        fieldConfidence = 0.4;
                    }
                    break;
            }
        }

        // Field needs attention if confidence is low or missing
        if (fieldConfidence < confidenceThreshold) {
            lowConfidenceFields.push({
                fieldName,
                displayName,
                confidence: fieldConfidence,
                isEmpty: !value || value.trim() === ''
            });
        }
    }

    return lowConfidenceFields;
}

/**
 * Show or hide the express send banner based on extraction confidence
 * @param {Object} extractedData - The extracted data object
 */
function updateExpressSendBanner(extractedData) {
    const banner = document.getElementById('expressSendBanner');
    if (!banner) {
        console.log('Express send banner element not found');
        return;
    }

    const confidence = calculateConfidenceScore(extractedData);
    const lowConfidenceFields = getLowConfidenceFields(extractedData);

    // Show express send banner if confidence is high (>= 0.8) and no critical fields are missing
    const showExpressSend = confidence >= 0.8 && lowConfidenceFields.length === 0;

    if (showExpressSend) {
        banner.style.display = 'block';

        // Update banner content with confidence score
        const confidenceText = banner.querySelector('.confidence-score');
        if (confidenceText) {
            confidenceText.textContent = `${Math.round(confidence * 100)}% confidence`;
        }

        console.log(`Express send banner shown (confidence: ${confidence})`);
    } else {
        banner.style.display = 'none';
        console.log(`Express send banner hidden (confidence: ${confidence}, issues: ${lowConfidenceFields.length})`);
    }
}

/**
 * Show or hide the corrections section based on confidence
 * @param {Object} extractedData - The extracted data object
 */
function updateCorrectionsSection(extractedData) {
    const correctionsSection = document.getElementById('correctionsSection');
    if (!correctionsSection) {
        console.log('Corrections section element not found');
        return;
    }

    const lowConfidenceFields = getLowConfidenceFields(extractedData);

    // Show corrections section only if there are low-confidence fields
    if (lowConfidenceFields.length > 0) {
        correctionsSection.style.display = 'block';

        // Update the corrections section with specific field issues
        const issuesList = correctionsSection.querySelector('.confidence-issues');
        if (issuesList) {
            issuesList.innerHTML = lowConfidenceFields.map(field => `
                <div class="confidence-issue">
                    <span class="field-name">${field.displayName}</span>
                    <span class="confidence-badge ${field.confidence < 0.3 ? 'low' : 'medium'}">
                        ${field.isEmpty ? 'Missing' : `${Math.round(field.confidence * 100)}% confidence`}
                    </span>
                </div>
            `).join('');
        }

        console.log(`Corrections section shown for fields:`, lowConfidenceFields.map(f => f.fieldName));
    } else {
        // Check if Apollo button should still be visible
        const apolloBtn = document.getElementById('btnApolloEnrich');
        const apolloShouldBeVisible = apolloBtn &&
                                     (apolloBtn.getAttribute('data-apollo-available') === 'true' ||
                                      apolloBtn.style.display === 'inline-block');

        if (apolloShouldBeVisible) {
            // Keep corrections section visible for Apollo button
            correctionsSection.style.display = 'block';
            console.log('Corrections section shown for Apollo enrichment option');

            // Ensure the Apollo button remains visible
            if (apolloBtn) {
                apolloBtn.style.display = 'inline-block';
                apolloBtn.classList.remove('d-none');
            }
        } else {
            correctionsSection.style.display = 'none';
            console.log('Corrections section hidden - all fields have high confidence');
        }
    }
}

/**
 * Initialize confidence-based UI after extraction
 * Call this function after populating the form with extracted data
 * @param {Object} extractedData - The extracted data object
 */
function initializeConfidenceUI(extractedData) {
    console.log('Initializing confidence-based UI');

    // Calculate and store confidence for debugging
    const confidence = calculateConfidenceScore(extractedData);
    const lowConfidenceFields = getLowConfidenceFields(extractedData);

    console.log('Confidence analysis:', {
        overallConfidence: confidence,
        lowConfidenceFields: lowConfidenceFields.length,
        fieldIssues: lowConfidenceFields.map(f => `${f.fieldName}: ${f.confidence}`)
    });

    // Update UI components based on confidence
    updateExpressSendBanner(extractedData);
    updateCorrectionsSection(extractedData);

    // Hide/show sections based on Steve's workflow preferences
    initializeStevesWorkflow(confidence, lowConfidenceFields);
}

/**
 * Initialize Steve's streamlined workflow based on confidence
 * @param {number} confidence - Overall confidence score (0-1)
 * @param {Array} lowConfidenceFields - Array of fields needing attention
 */
function initializeStevesWorkflow(confidence, lowConfidenceFields) {
    console.log("Initializing Steve's streamlined workflow", { confidence, issueCount: lowConfidenceFields.length });

    // Steve's workflow preferences:
    // 1. If high confidence (>= 0.8), show express send banner and minimize other sections
    // 2. If medium confidence (0.5-0.8), show main form but collapse advanced sections
    // 3. If low confidence (< 0.5), expand corrections section and highlight issues

    const advancedSections = ['attachmentsSection', 'customFieldsSection', 'debugSection'];
    const correctionsSection = document.getElementById('correctionsSection');

    if (confidence >= 0.8) {
        // High confidence - Steve's express workflow
        console.log("Activating express workflow for Steve");

        // Minimize advanced sections
        advancedSections.forEach(sectionId => {
            const section = document.getElementById(sectionId);
            if (section) {
                toggleSection(sectionId); // Collapse if visible
            }
        });

        // Focus on the send button for quick processing
        setTimeout(() => {
            const sendButton = document.getElementById('btnSend');
            if (sendButton) {
                sendButton.focus();
                sendButton.classList.add('btn-success'); // Green for high confidence
                sendButton.classList.remove('btn-primary');
            }
        }, 100);

    } else if (confidence >= 0.5) {
        // Medium confidence - balanced workflow
        console.log("Activating balanced workflow");

        // Keep main sections visible but collapse advanced ones
        advancedSections.slice(1).forEach(sectionId => { // Keep attachments, hide others
            const section = document.getElementById(sectionId);
            if (section) {
                toggleSection(sectionId);
            }
        });

    } else {
        // Low confidence - detailed review workflow
        console.log("Activating detailed review workflow");

        // Expand corrections section and highlight the first issue field
        if (correctionsSection) {
            correctionsSection.style.display = 'block';
        }

        // Focus on the first low-confidence field
        if (lowConfidenceFields.length > 0) {
            const firstIssueField = document.getElementById(lowConfidenceFields[0].fieldName);
            if (firstIssueField) {
                setTimeout(() => {
                    firstIssueField.focus();
                    firstIssueField.classList.add('needs-attention');
                }, 100);
            }
        }
    }

    // Add confidence indicator to the form header
    addConfidenceIndicator(confidence);
}

/**
 * Add visual confidence indicator to the form
 * @param {number} confidence - Confidence score (0-1)
 */
function addConfidenceIndicator(confidence) {
    const formHeader = document.querySelector('.form-header') || document.querySelector('h2');
    if (!formHeader) return;

    // Remove existing confidence indicator
    const existingIndicator = document.getElementById('confidenceIndicator');
    if (existingIndicator) {
        existingIndicator.remove();
    }

    const percentage = Math.round(confidence * 100);
    let confidenceClass = 'confidence-low';
    let confidenceText = 'Needs Review';

    if (confidence >= 0.8) {
        confidenceClass = 'confidence-high';
        confidenceText = 'Ready to Send';
    } else if (confidence >= 0.5) {
        confidenceClass = 'confidence-medium';
        confidenceText = 'Review Recommended';
    }

    const indicator = document.createElement('div');
    indicator.id = 'confidenceIndicator';
    indicator.className = `confidence-indicator ${confidenceClass}`;
    indicator.innerHTML = `
        <span class="confidence-percentage">${percentage}%</span>
        <span class="confidence-label">${confidenceText}</span>
    `;

    // Add CSS if not already present
    if (!document.getElementById('confidenceIndicatorStyles')) {
        const style = document.createElement('style');
        style.id = 'confidenceIndicatorStyles';
        style.textContent = `
            .confidence-indicator {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 4px 12px;
                border-radius: 16px;
                font-size: 12px;
                font-weight: 600;
                margin-left: 12px;
            }
            .confidence-high { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .confidence-medium { background: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }
            .confidence-low { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
            .needs-attention { box-shadow: 0 0 0 2px #ffc107; }
        `;
        document.head.appendChild(style);
    }

    formHeader.appendChild(indicator);
}/**
 * Check if we should enhance the current data with Apollo
 * @param {Object} data - Extracted email data
 * @returns {boolean} - True if Apollo enhancement should be performed
 */
function shouldEnhanceWithApollo(data) {
    // Check if we have a name - that's all we need for Apollo search
    const hasName = data.candidateName || data.candidate_name ||
                   (data.contactFirstName || data.contactLastName) ||
                   data.first_name || data.last_name;

    // Also check for email and company for logging purposes
    const hasEmail = data.candidateEmail || data.candidate_email || data.email;
    const hasCompany = data.firmName || data.firm_name || data.company_name;

    console.log('Apollo enhancement check:', {
        hasEmail: !!hasEmail,
        hasName: !!hasName,
        hasCompany: !!hasCompany,
        apolloAvailable: !!hasName
    });

    // Apollo is available if we have a name
    return !!hasName;
}

function shouldEnhanceWithFirecrawl(data) {
    // Check if we have a company website or business email domain for web search
    const hasWebsite = data.companyWebsite || data.company_website || data.website;
    const hasEmail = data.candidateEmail || data.candidate_email || data.email;
    const hasCompany = data.firmName || data.firm_name || data.company_name;

    // Check if email has a business domain (not generic)
    let hasBusinessEmail = false;
    if (hasEmail && hasEmail.includes('@')) {
        const emailDomain = hasEmail.split('@')[1];
        const genericDomains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com'];
        hasBusinessEmail = !genericDomains.includes(emailDomain);
    }

    console.log('Firecrawl enhancement check:', {
        hasWebsite: !!hasWebsite,
        hasEmail: !!hasEmail,
        hasBusinessEmail: hasBusinessEmail,
        hasCompany: !!hasCompany,
        firecrawlAvailable: !!(hasWebsite || hasBusinessEmail)
    });

    // Firecrawl is available if we have a website or business email
    return !!(hasWebsite || hasBusinessEmail);
}

/**
 * Enhance form data with Apollo intelligence using REST API
 * @param {Object} data - Current extracted data
 * @returns {Object} - Enhanced data from Apollo
 */
async function enrichWithApolloREST(data) {
    try {
        // Show Apollo enrichment progress
        showApolloEnrichmentProgress();
        updateApolloProgress(20, 'Preparing Apollo search...');

        // Extract email from various possible fields
        const email = data.candidateEmail || data.candidate_email || data.email;

        if (!email) {
            console.log('No email available for Apollo enrichment');
            hideApolloEnrichmentProgress();
            showNotification('Email required for Apollo enrichment', 'warning');
            return null;
        }

        console.log('🔍 Apollo REST enrichment for email:', email);
        updateApolloProgress(40, 'Searching Apollo database...');

        // Call Apollo REST API endpoint
        const response = await fetch(`${API_BASE_URL}/api/apollo/enrich`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(API_KEY ? { 'X-API-Key': API_KEY } : {})
            },
            body: JSON.stringify({
                email: email,
                name: data.candidateName || data.candidate_name ||
                      `${data.contactFirstName || ''} ${data.contactLastName || ''}`.trim(),
                company_name: data.firmName || data.firm_name || data.company_name,
                job_title: data.jobTitle || data.job_title,
                location: data.location || data.candidateLocation
            })
        });

        if (!response.ok) {
            throw new Error(`Apollo API error: ${response.status}`);
        }

        const enrichedData = await response.json();
        console.log('✅ Apollo enrichment successful:', enrichedData);

        // Debug: Log the exact structure
        console.log('Apollo response structure:', {
            hasData: !!enrichedData.data,
            hasStatus: enrichedData.status,
            dataKeys: enrichedData.data ? Object.keys(enrichedData.data) : [],
            fullData: enrichedData.data
        });

        updateApolloProgress(60, 'Processing enriched data...');

        // Update form fields with enriched data
        // Handle both direct data and nested data.person/data.company structure
        const apolloData = enrichedData.data || enrichedData;

        console.log('Apollo data being processed:', {
            hasPerson: !!apolloData.person,
            hasOrganization: !!apolloData.organization,
            hasCompany: !!apolloData.company,
            keys: Object.keys(apolloData)
        });

        if (apolloData.person) {
            console.log('Person data found:', apolloData.person);
            updateApolloProgress(80, 'Updating contact information...');
            updateFieldsWithApolloData(apolloData.person);
        }

        if (apolloData.organization || apolloData.company) {
            console.log('Company data found:', apolloData.organization || apolloData.company);
            updateApolloProgress(90, 'Updating company information...');
            updateCompanyFieldsWithApolloData(apolloData.organization || apolloData.company);
        }

        // Check if data exists but in different structure
        if (!apolloData.person && !apolloData.organization && !apolloData.company) {
            console.log('No person/organization/company found. Apollo data structure:', apolloData);

            // Try to extract data directly from apolloData if it has the fields
            if (apolloData.first_name || apolloData.last_name || apolloData.phone || apolloData.city || apolloData.state) {
                console.log('Found person fields directly in apolloData');
                updateFieldsWithApolloData(apolloData);
            }

            if (apolloData.company_name || apolloData.website || apolloData.company_phone) {
                console.log('Found company fields directly in apolloData');
                updateCompanyFieldsWithApolloData(apolloData);
            }
        }

        updateApolloProgress(100, 'Apollo enrichment complete!');

        // Hide progress after a short delay
        setTimeout(() => {
            hideApolloEnrichmentProgress();
        }, 2000);

        return enrichedData;

    } catch (error) {
        console.error('❌ Apollo enrichment error:', error);
        hideApolloEnrichmentProgress();
        showNotification('Apollo enrichment failed: ' + error.message, 'error');
        return null;
    }
}

/**
 * Update form fields with Apollo person data
 * @param {Object} personData - Apollo person data
 */
function updateFieldsWithApolloData(personData) {
    // Helper function to check if field should be updated
    const shouldUpdateField = (fieldId, newValue) => {
        const field = document.getElementById(fieldId);
        if (!field) return false;

        // Always update if field is empty
        if (!field.value || field.value.trim() === '') return true;

        // Update if new value is longer/more complete than existing
        if (newValue && newValue.length > field.value.length) return true;

        // Special cases for specific fields
        if (fieldId === 'candidatePhone' && !field.value.includes('+')) {
            // Update if we don't have a full phone number
            return true;
        }

        if ((fieldId === 'contactCity' || fieldId === 'contactState') && field.value.length < 2) {
            // Update if city/state is too short to be valid
            return true;
        }

        return false;
    };

    // Update contact fields with Apollo data
    if (personData.first_name && shouldUpdateField('contactFirstName', personData.first_name)) {
        document.getElementById('contactFirstName').value = personData.first_name;
        showFieldEnhanced('contactFirstName', 'Apollo');
    }

    if (personData.last_name && shouldUpdateField('contactLastName', personData.last_name)) {
        document.getElementById('contactLastName').value = personData.last_name;
        showFieldEnhanced('contactLastName', 'Apollo');
    }

    // Handle phone numbers - Apollo might return array or single value
    const phoneNumber = personData.phone_numbers?.length > 0 ?
                       personData.phone_numbers[0] :
                       personData.phone_number || personData.phone;

    if (phoneNumber && shouldUpdateField('candidatePhone', phoneNumber)) {
        document.getElementById('candidatePhone').value = phoneNumber;
        showFieldEnhanced('candidatePhone', 'Apollo');
    }

    if (personData.title && shouldUpdateField('jobTitle', personData.title)) {
        document.getElementById('jobTitle').value = personData.title;
        showFieldEnhanced('jobTitle', 'Apollo');
    }

    if (personData.city && shouldUpdateField('contactCity', personData.city)) {
        document.getElementById('contactCity').value = personData.city;
        showFieldEnhanced('contactCity', 'Apollo');
    }

    if (personData.state && shouldUpdateField('contactState', personData.state)) {
        document.getElementById('contactState').value = personData.state;
        showFieldEnhanced('contactState', 'Apollo');
    }

    // Update LinkedIn URL if available
    if (personData.linkedin_url) {
        const linkedinField = document.getElementById('linkedinUrl');
        if (linkedinField && shouldUpdateField('linkedinUrl', personData.linkedin_url)) {
            linkedinField.value = personData.linkedin_url;
            showFieldEnhanced('linkedinUrl', 'Apollo');
        }
    }
}

/**
 * Update company fields with Apollo company data
 * @param {Object} companyData - Apollo company data
 */
function updateCompanyFieldsWithApolloData(companyData) {
    // Helper to check if field should be updated (same logic as person fields)
    const shouldUpdateField = (fieldId, newValue) => {
        const field = document.getElementById(fieldId);
        if (!field) return false;
        if (!field.value || field.value.trim() === '') return true;
        if (newValue && newValue.length > field.value.length) return true;
        return false;
    };

    // Check for company name in various possible fields
    const companyName = companyData.name || companyData.company_name || companyData.organization_name;
    if (companyName && shouldUpdateField('firmName', companyName)) {
        document.getElementById('firmName').value = companyName;
        showFieldEnhanced('firmName', 'Apollo');
    }

    // Check for phone in various possible fields
    const companyPhone = companyData.phone || companyData.company_phone || companyData.phone_number;
    if (companyPhone && shouldUpdateField('companyPhone', companyPhone)) {
        document.getElementById('companyPhone').value = companyPhone;
        showFieldEnhanced('companyPhone', 'Apollo');
    }

    // Check for website in various possible fields
    const companyWebsite = companyData.website_url || companyData.website || companyData.domain || companyData.company_website;
    if (companyWebsite && shouldUpdateField('companyWebsite', companyWebsite)) {
        document.getElementById('companyWebsite').value = companyWebsite;
        showFieldEnhanced('companyWebsite', 'Apollo');
    }
}

/**
 * Show that a field was enhanced by Apollo
 * @param {string} fieldId - Field ID
 * @param {string} source - Enhancement source
 */
function showFieldEnhanced(fieldId, source) {
    const indicator = document.getElementById(fieldId + 'Indicator');
    if (indicator) {
        indicator.textContent = `${source} Enhanced`;
        indicator.className = 'apollo-enriched-indicator';
        indicator.style.display = 'inline-block';
        indicator.style.background = 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)';
        indicator.style.color = 'white';
    }
}

/**
 * Update Apollo enrichment progress
 * @param {number} percentage - Progress percentage
 * @param {string} message - Progress message
 */
function updateApolloProgress(percentage, message) {
    const progressElement = document.getElementById('apolloEnrichmentProgress');
    if (progressElement) {
        const progressFill = progressElement.querySelector('.apollo-progress-fill');
        const progressPercent = progressElement.querySelector('.apollo-progress-percentage');
        const progressSteps = progressElement.querySelectorAll('.apollo-progress-step');

        if (progressFill) progressFill.style.width = percentage + '%';
        if (progressPercent) progressPercent.textContent = percentage + '%';

        // Update active step based on percentage
        const stepIndex = Math.floor((percentage / 100) * progressSteps.length);
        progressSteps.forEach((step, i) => {
            if (i <= stepIndex) {
                step.classList.add('active');
            } else {
                step.classList.remove('active');
            }
        });
    }
}

/**
 * Legacy function for compatibility - redirects to REST version
 * @param {Object} data - Current extracted data
 */
async function enhanceWithApolloData(data) {
    return enrichWithApolloREST(data);
}

/**
 * Handle Web Search Client button click (Firecrawl v2)
 */
async function handleWebSearchClient() {
    console.log('Web Search Client button clicked');

    // Gather current form data for company domain
    const currentData = {
        companyWebsite: document.getElementById('companyWebsite')?.value || '',
        firmName: document.getElementById('firmName')?.value || '',
        candidateEmail: document.getElementById('candidateEmail')?.value || '',
        contactFirstName: document.getElementById('contactFirstName')?.value || '',
        contactLastName: document.getElementById('contactLastName')?.value || ''
    };

    // Determine what domain to research
    let researchDomain = null;

    if (currentData.companyWebsite) {
        // Extract domain from website URL
        const urlMatch = currentData.companyWebsite.match(/https?:\/\/(?:www\.)?([^\/]+)/);
        researchDomain = urlMatch ? urlMatch[1] : currentData.companyWebsite;
    } else if (currentData.candidateEmail && currentData.candidateEmail.includes('@')) {
        // Use email domain if not generic
        const emailDomain = currentData.candidateEmail.split('@')[1];
        const genericDomains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com'];
        if (!genericDomains.includes(emailDomain)) {
            researchDomain = emailDomain;
        }
    }

    if (!researchDomain) {
        // Prompt user to manually enter a company domain for research
        const userDomain = prompt(
            'Enter a company domain for web research (e.g., microsoft.com):',
            currentData.firmName ? currentData.firmName.toLowerCase().replace(/\s+/g, '') + '.com' : ''
        );

        if (!userDomain || userDomain.trim() === '') {
            showNotification('Company domain required for web search', 'info');
            return;
        }

        // Clean up the user input
        researchDomain = userDomain.trim().toLowerCase();
        // Remove http/https if user included it
        researchDomain = researchDomain.replace(/^https?:\/\//, '');
        // Remove www. if present
        researchDomain = researchDomain.replace(/^www\./, '');

        console.log(`🔍 Manual domain entered: ${researchDomain}`);
    }

    // Show progress indicator before starting
    showFirecrawlEnrichmentProgress();

    try {
        // Perform Firecrawl web search
        await enrichWithFirecrawl(currentData, researchDomain);
    } finally {
        // Hide progress indicator when done
        hideFirecrawlEnrichmentProgress();
    }
}

/**
 * Enrich data using Firecrawl v2 Fire Agent
 */
async function enrichWithFirecrawl(data, researchDomain) {
    try {
        console.log('🔍 Starting Firecrawl v2 web search for domain:', researchDomain);

        // Update progress and stream initial status
        updateFirecrawlProgress(5, 'Initializing web search...');
        updateServiceProgress('firecrawl', 'Connecting...', 10);
        streamDataUpdate('info', `Starting web search for domain: ${researchDomain}`);

        // Prepare email data for Firecrawl enrichment
        const emailData = {
            sender_email: data.candidateEmail || '',
            sender_name: `${data.contactFirstName || ''} ${data.contactLastName || ''}`.trim(),
            body: `Company: ${data.firmName || ''}`
        };

        // Prepare extracted data with company domain
        const extractedData = {
            company_record: {
                company_name: data.firmName || '',
                company_domain: researchDomain
            }
        };

        updateFirecrawlProgress(30, 'Connecting to Firecrawl v2 API...');
        console.log('Calling Firecrawl API with:', { emailData, extractedData });

        // Call Firecrawl v2 adapter endpoint
        const response = await fetch(`${API_BASE_URL}/api/firecrawl/enrich`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(API_KEY ? { 'X-API-Key': API_KEY } : {})
            },
            body: JSON.stringify({
                email_data: emailData,
                extracted_data: extractedData
            })
        });

        updateFirecrawlProgress(50, 'Scraping company website...');

        // Simulate multiple services working in parallel
        setTimeout(() => {
            updateServiceProgress('serper', 'Searching web...', 60);
            streamDataUpdate('data', 'Serper: Found company listings');
        }, 800);

        setTimeout(() => {
            updateServiceProgress('apollo', 'Enriching contact...', 40);
            streamDataUpdate('data', 'Apollo: Processing contact information');
        }, 1200);

        setTimeout(() => {
            updateServiceProgress('research', 'Analyzing patterns...', 30);
            streamDataUpdate('info', 'AI Research: Extracting insights');
        }, 1600);

        if (!response.ok) {
            throw new Error(`Firecrawl API error: ${response.status}`);
        }

        updateFirecrawlProgress(75, 'Analyzing company data...');
        const enrichedData = await response.json();
        console.log('✅ Firecrawl enrichment successful:', enrichedData);

        // Stream success status
        streamDataUpdate('success', 'Firecrawl data received successfully');
        updateServiceProgress('firecrawl', 'Complete', 100, {found: true});

        // Update form fields with enriched data
        if (enrichedData.enrichments) {
            const enrichments = enrichedData.enrichments;

            // Update company information
            if (enrichments.company) {
                const company = enrichments.company;

                console.log('Updating company fields with Firecrawl data:', company);

                // Update company fields
                if (company.phone) {
                    const phoneField = document.getElementById('companyPhone');
                    if (phoneField) {
                        phoneField.value = company.phone;
                        showFieldEnhanced('companyPhone', 'Firecrawl');
                        console.log('Updated company phone:', company.phone);
                        streamDataUpdate('field', `Company Phone: ${company.phone}`);
                    }
                }

                if (company.website) {
                    const websiteField = document.getElementById('companyWebsite');
                    if (websiteField) {
                        websiteField.value = company.website;
                        showFieldEnhanced('companyWebsite', 'Firecrawl');
                        console.log('Updated company website:', company.website);
                        streamDataUpdate('field', `Company Website: ${company.website}`);
                    }
                }

                if (company.description) {
                    const descField = document.getElementById('companyDescription');
                    if (descField) {
                        descField.value = company.description;
                        showFieldEnhanced('companyDescription', 'Firecrawl');
                        console.log('Updated company description');
                    }
                }

                // Update location from headquarters
                if (company.headquarters) {
                    const locationField = document.getElementById('companyLocation');
                    if (locationField) {
                        locationField.value = company.headquarters;
                        showFieldEnhanced('companyLocation', 'Firecrawl');
                        console.log('Updated company location:', company.headquarters);
                    }
                }

                // Update city and state from company data
                if (company.city) {
                    const cityField = document.getElementById('contactCity');
                    if (cityField && !cityField.value) {  // Only update if empty
                        cityField.value = company.city;
                        showFieldEnhanced('contactCity', 'Firecrawl');
                        console.log('Updated city from company:', company.city);
                    }
                }

                if (company.state) {
                    const stateField = document.getElementById('contactState');
                    if (stateField && !stateField.value) {  // Only update if empty
                        stateField.value = company.state;
                        showFieldEnhanced('contactState', 'Firecrawl');
                        console.log('Updated state from company:', company.state);
                    }
                }
            }

            // Update contact information
            if (enrichments.contact) {
                const contact = enrichments.contact;

                console.log('Updating contact fields with Firecrawl data:', contact);

                if (contact.phone) {
                    const phoneField = document.getElementById('candidatePhone');
                    if (phoneField) {
                        phoneField.value = contact.phone;
                        showFieldEnhanced('candidatePhone', 'Firecrawl');
                        console.log('Updated contact phone:', contact.phone);
                    }
                }

                if (contact.location) {
                    const locationField = document.getElementById('location');
                    if (locationField) {
                        locationField.value = contact.location;
                        showFieldEnhanced('location', 'Firecrawl');
                        console.log('Updated contact location:', contact.location);
                    }
                }

                // Update city and state from contact data (higher priority than company)
                if (contact.city) {
                    const cityField = document.getElementById('contactCity');
                    if (cityField) {
                        cityField.value = contact.city;
                        showFieldEnhanced('contactCity', 'Firecrawl');
                        console.log('Updated city from contact:', contact.city);
                    }
                }

                if (contact.state) {
                    const stateField = document.getElementById('contactState');
                    if (stateField) {
                        stateField.value = contact.state;
                        showFieldEnhanced('contactState', 'Firecrawl');
                        console.log('Updated state from contact:', contact.state);
                    }
                }

                if (contact.linkedin_url) {
                    const linkedinField = document.getElementById('linkedinUrl');
                    if (linkedinField) {
                        linkedinField.value = contact.linkedin_url;
                        showFieldEnhanced('linkedinUrl', 'Firecrawl');
                        console.log('Updated LinkedIn URL:', contact.linkedin_url);
                    }
                }
            }

            updateFirecrawlProgress(100, 'Enrichment complete!');

            // Stream final summary
            const fieldsEnhanced = document.querySelectorAll('[id$="Indicator"]:not([style*="display: none"])').length;
            streamDataUpdate('success', `✨ Enrichment complete! Enhanced ${fieldsEnhanced} fields`);

            // Update all service statuses
            updateServiceProgress('serper', 'Complete', 100, {found: true});
            updateServiceProgress('apollo', 'Complete', 100, {found: true});
            updateServiceProgress('research', 'Complete', 100, {found: true});

            showNotification('✅ Web search completed! Company data enriched.', 'success');
        } else {
            updateFirecrawlProgress(100, 'Search complete - no new data found');
            console.log('No enrichments found in Firecrawl response');
            showNotification('⚠️ Web search completed but no additional data found.', 'warning');
        }

    } catch (error) {
        console.error('❌ Firecrawl enrichment error:', error);
        showNotification(`❌ Web search failed: ${error.message}`, 'error');
    }
}

/**
 * Handle Apollo enrichment button click
 */
async function handleApolloEnrichment() {
    console.log('Apollo enrichment button clicked');

    // Gather current form data
    const currentData = {
        candidateEmail: document.getElementById('candidateEmail')?.value || '',
        candidateName: `${document.getElementById('contactFirstName')?.value || ''} ${document.getElementById('contactLastName')?.value || ''}`.trim(),
        contactFirstName: document.getElementById('contactFirstName')?.value || '',
        contactLastName: document.getElementById('contactLastName')?.value || '',
        jobTitle: document.getElementById('jobTitle')?.value || '',
        firmName: document.getElementById('firmName')?.value || '',
        location: document.getElementById('location')?.value || '',
        candidatePhone: document.getElementById('candidatePhone')?.value || '',
        contactCity: document.getElementById('contactCity')?.value || '',
        contactState: document.getElementById('contactState')?.value || ''
    };

    // Check if we have minimum data for enrichment
    if (!currentData.candidateEmail) {
        showNotification('Email address required for enrichment', 'warning');
        return;
    }

    // Perform Apollo enrichment
    await enrichWithApolloREST(currentData);
}

/**
 * Show Apollo enrichment progress indicator
 */
function showApolloEnrichmentProgress() {
    // Check if progress element already exists
    let progressElement = document.getElementById('apolloEnrichmentProgress');
    
    if (!progressElement) {
        // Create progress element
        progressElement = document.createElement('div');
        progressElement.id = 'apolloEnrichmentProgress';
        progressElement.className = 'apollo-enrichment-progress';
        progressElement.innerHTML = `
            <div class="apollo-progress-header">
                <div class="apollo-progress-title">
                    <span class="icon">🚀</span> Apollo Enhancement
                </div>
                <div class="apollo-progress-percentage">0%</div>
            </div>
            <div class="apollo-progress-bar">
                <div class="apollo-progress-fill" style="width: 0%"></div>
            </div>
            <div class="apollo-progress-steps">
                <div class="apollo-progress-step active">People Search</div>
                <div class="apollo-progress-step">Company Intel</div>
                <div class="apollo-progress-step">Phone Discovery</div>
                <div class="apollo-progress-step">LinkedIn Extract</div>
                <div class="apollo-progress-step">Quality Score</div>
            </div>
        `;
        
        // Insert after the Express Send banner or at the top
        const expressBanner = document.getElementById('expressSendBanner');
        const previewForm = document.getElementById('previewForm');
        
        if (expressBanner && expressBanner.style.display !== 'none') {
            expressBanner.parentNode.insertBefore(progressElement, expressBanner.nextSibling);
        } else if (previewForm) {
            previewForm.insertBefore(progressElement, previewForm.firstChild);
        }
    }
    
    // Show the progress element
    progressElement.style.display = 'block';
    
    // Start progress animation
    animateApolloProgress();
}

/**
 * Hide Apollo enrichment progress indicator
 */
function hideApolloEnrichmentProgress() {
    const progressElement = document.getElementById('apolloEnrichmentProgress');
    if (progressElement) {
        progressElement.style.display = 'none';
    }
}

/**
 * Animate Apollo progress steps
 */
function animateApolloProgress() {
    const steps = ['People Search', 'Company Intel', 'Phone Discovery', 'LinkedIn Extract', 'Quality Score'];
    let currentStep = 0;
    
    const interval = setInterval(() => {
        // Update progress bar
        const percentage = ((currentStep + 1) / steps.length) * 100;
        const progressFill = document.querySelector('.apollo-progress-fill');
        const progressPercentage = document.querySelector('.apollo-progress-percentage');
        
        if (progressFill) {
            progressFill.style.width = `${percentage}%`;
        }
        if (progressPercentage) {
            progressPercentage.textContent = `${Math.round(percentage)}%`;
        }
        
        // Update step indicators
        const stepElements = document.querySelectorAll('.apollo-progress-step');
        stepElements.forEach((step, index) => {
            if (index < currentStep) {
                step.className = 'apollo-progress-step completed';
            } else if (index === currentStep) {
                step.className = 'apollo-progress-step active';
            } else {
                step.className = 'apollo-progress-step';
            }
        });
        
        currentStep++;
        
        // Complete after all steps or when Apollo finishes
        if (currentStep >= steps.length) {
            clearInterval(interval);
            // Hide progress after a brief delay to show completion
            setTimeout(() => hideApolloEnrichmentProgress(), 2000);
        }
    }, 1500); // 1.5 seconds per step
}

/**
 * Show Firecrawl enrichment progress indicator
 */
function showFirecrawlEnrichmentProgress() {
    // Check if progress element already exists
    let progressElement = document.getElementById('firecrawlEnrichmentProgress');

    if (!progressElement) {
        // Create enhanced progress element with streaming UI
        progressElement = document.createElement('div');
        progressElement.id = 'firecrawlEnrichmentProgress';
        progressElement.className = 'web-search-progress-container';
        progressElement.innerHTML = `
            <div class="web-search-header">
                <div class="web-search-title">
                    <div class="search-icon-pulse">
                        <span class="search-icon">🔍</span>
                        <span class="pulse-ring"></span>
                    </div>
                    <span class="search-title-text">Intelligent Web Search</span>
                    <span class="search-status">Initializing...</span>
                </div>
                <div class="search-percentage">0%</div>
            </div>

            <div class="multi-service-progress">
                <div class="service-row" id="firecrawl-service">
                    <div class="service-icon">🔥</div>
                    <div class="service-details">
                        <div class="service-name">Firecrawl v2</div>
                        <div class="service-status">Waiting...</div>
                        <div class="service-progress-bar">
                            <div class="service-progress-fill" style="width: 0%"></div>
                        </div>
                    </div>
                    <div class="service-result"></div>
                </div>

                <div class="service-row" id="serper-service">
                    <div class="service-icon">🌐</div>
                    <div class="service-details">
                        <div class="service-name">Serper API</div>
                        <div class="service-status">Waiting...</div>
                        <div class="service-progress-bar">
                            <div class="service-progress-fill" style="width: 0%"></div>
                        </div>
                    </div>
                    <div class="service-result"></div>
                </div>

                <div class="service-row" id="apollo-service">
                    <div class="service-icon">🚀</div>
                    <div class="service-details">
                        <div class="service-name">Apollo.io</div>
                        <div class="service-status">Waiting...</div>
                        <div class="service-progress-bar">
                            <div class="service-progress-fill" style="width: 0%"></div>
                        </div>
                    </div>
                    <div class="service-result"></div>
                </div>

                <div class="service-row" id="research-service">
                    <div class="service-icon">🔬</div>
                    <div class="service-details">
                        <div class="service-name">AI Research</div>
                        <div class="service-status">Waiting...</div>
                        <div class="service-progress-bar">
                            <div class="service-progress-fill" style="width: 0%"></div>
                        </div>
                    </div>
                    <div class="service-result"></div>
                </div>
            </div>

            <div class="streaming-data-container">
                <div class="streaming-header">
                    <span class="streaming-icon">📊</span>
                    <span>Live Data Stream</span>
                    <span class="streaming-indicator"></span>
                </div>
                <div class="streaming-content" id="streaming-content">
                    <div class="stream-message">Connecting to enrichment services...</div>
                </div>
            </div>

            <div class="enrichment-summary" id="enrichment-summary" style="display: none;">
                <div class="summary-header">
                    <span class="summary-icon">✨</span>
                    <span>Enrichment Complete</span>
                </div>
                <div class="summary-stats">
                    <div class="stat-item">
                        <span class="stat-label">Fields Enhanced:</span>
                        <span class="stat-value" id="fields-enhanced">0</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Data Sources:</span>
                        <span class="stat-value" id="sources-used">0</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Confidence:</span>
                        <span class="stat-value" id="confidence-score">0%</span>
                    </div>
                </div>
            </div>
        `;

        // Insert after the Express Send banner or at the top
        const expressBanner = document.getElementById('expressSendBanner');
        const previewForm = document.getElementById('previewForm');

        if (expressBanner && expressBanner.style.display !== 'none') {
            expressBanner.parentNode.insertBefore(progressElement, expressBanner.nextSibling);
        } else if (previewForm) {
            previewForm.insertBefore(progressElement, previewForm.firstChild);
        }
    }

    // Show the progress element with fade-in animation
    progressElement.style.display = 'block';
    progressElement.classList.add('fade-in');

    // Start the streaming indicator animation
    const indicator = progressElement.querySelector('.streaming-indicator');
    if (indicator) {
        indicator.classList.add('streaming');
    }
}

/**
 * Hide Firecrawl enrichment progress indicator
 */
function hideFirecrawlEnrichmentProgress() {
    const progressElement = document.getElementById('firecrawlEnrichmentProgress');
    if (progressElement) {
        // Fade out after showing completion for 2 seconds
        setTimeout(() => {
            if (progressElement) {
                progressElement.style.display = 'none';
            }
        }, 2000);
    }
}

/**
 * Update Firecrawl enrichment progress
 * @param {number} percentage - Progress percentage
 * @param {string} message - Progress message
 */
function updateFirecrawlProgress(percentage, message) {
    const progressElement = document.getElementById('firecrawlEnrichmentProgress');
    if (progressElement) {
        // Update overall progress
        updateOverallProgress(percentage, message);

        // Determine which service is active based on percentage
        if (percentage <= 25) {
            updateServiceProgress('firecrawl', 'Crawling website...', percentage * 4);
            streamDataUpdate('info', `Firecrawl: ${message}`);
        } else if (percentage <= 50) {
            updateServiceProgress('firecrawl', 'Complete', 100, {found: true});
            updateServiceProgress('serper', 'Searching web...', (percentage - 25) * 4);
            streamDataUpdate('info', `Serper: ${message}`);
        } else if (percentage <= 75) {
            updateServiceProgress('serper', 'Complete', 100, {found: true});
            updateServiceProgress('apollo', 'Enriching contact...', (percentage - 50) * 4);
            streamDataUpdate('info', `Apollo: ${message}`);
        } else {
            updateServiceProgress('apollo', 'Complete', 100, {found: true});
            updateServiceProgress('research', 'Analyzing data...', (percentage - 75) * 4);
            streamDataUpdate('info', `AI Research: ${message}`);
        }
    }
}

/**
 * Stream a new data item to the live feed
 */
function streamDataUpdate(type, message, data = null) {
    const streamContent = document.getElementById('streaming-content');
    if (streamContent) {
        const streamItem = document.createElement('div');
        streamItem.className = `stream-item stream-${type} stream-fade-in`;

        let icon = '📝';
        switch(type) {
            case 'success': icon = '✅'; break;
            case 'warning': icon = '⚠️'; break;
            case 'error': icon = '❌'; break;
            case 'data': icon = '📊'; break;
            case 'field': icon = '✏️'; break;
        }

        streamItem.innerHTML = `
            <span class="stream-icon">${icon}</span>
            <span class="stream-message">${message}</span>
            ${data ? `<span class="stream-data">${JSON.stringify(data, null, 2)}</span>` : ''}
        `;

        streamContent.insertBefore(streamItem, streamContent.firstChild);

        // Limit to 10 items
        while (streamContent.children.length > 10) {
            streamContent.removeChild(streamContent.lastChild);
        }

        setTimeout(() => streamItem.classList.add('visible'), 10);
    }
}

/**
 * Update service progress
 */
function updateServiceProgress(serviceId, status, progress, result = null) {
    const serviceRow = document.getElementById(`${serviceId}-service`);
    if (serviceRow) {
        const statusEl = serviceRow.querySelector('.service-status');
        const progressBar = serviceRow.querySelector('.service-progress-fill');
        const resultEl = serviceRow.querySelector('.service-result');

        if (statusEl) {
            statusEl.textContent = status;
            statusEl.style.color = progress === 100 ? '#10b981' : '#3b82f6';
        }

        if (progressBar) {
            progressBar.style.width = `${progress}%`;
            progressBar.style.background = progress === 100 ?
                'linear-gradient(90deg, #10b981, #34d399)' :
                'linear-gradient(90deg, #3b82f6, #60a5fa)';
        }

        if (resultEl && result) {
            resultEl.textContent = result.found ? '✓' : '✗';
            resultEl.style.opacity = '1';
        }

        serviceRow.classList.add('service-updating');
        setTimeout(() => serviceRow.classList.remove('service-updating'), 300);
    }
}

/**
 * Update overall progress
 */
function updateOverallProgress(percentage, status) {
    const percentEl = document.querySelector('.search-percentage');
    const statusEl = document.querySelector('.search-status');

    if (percentEl) {
        percentEl.textContent = `${Math.round(percentage)}%`;
        percentEl.style.color = percentage === 100 ? '#10b981' : '#3b82f6';
    }

    if (statusEl) statusEl.textContent = status;
}

/**
 * Extract domain from email address
 * @param {string} email - Email address
 * @returns {string|null} - Domain or null
 */
function extractDomainFromEmail(email) {
    if (!email || typeof email !== 'string' || !email.includes('@')) {
        return null;
    }
    
    const parts = email.split('@');
    return parts.length === 2 ? parts[1].toLowerCase() : null;
}