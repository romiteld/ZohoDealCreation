// Configuration
// Route API calls through same-origin proxy on App Service to avoid cross-origin/CORS
const API_BASE_URL = '/api';
const API_KEY = localStorage.getItem('apiKey') || 'e49d2dbcfa4547f5bdc371c5c06aae2afd06914e16e680a7f31c5fc5384ba384';

// Global variables
let extractedData = null;
let currentFile = null;
let userInfo = null;
let authToken = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    // BYPASSING AUTH FOR URGENT DEPLOYMENT
    // await checkAuthentication();
    // await loadUserInfo();
    console.log('Auth checks disabled for urgent deployment');
    setupEventListeners();
    updateDealNamePreview();
});

// Check if user is authenticated - NO REDIRECTS, just check status
async function checkAuthentication() {
    try {
        const response = await fetch('/.auth/me');
        const data = await response.json();
        
        if (data && data[0]) {
            // User is authenticated
            sessionStorage.setItem('isAuthenticated', 'true');
            return true;
        }
    } catch (error) {
        console.error('Auth check error:', error);
    }
    
    // Not authenticated - but DON'T redirect, Azure handles that
    return false;
}

// Load user info from Azure AD
async function loadUserInfo() {
    try {
        const response = await fetch('/.auth/me');
        const data = await response.json();
        if (data && data[0]) {
            userInfo = data[0];
            const userName = userInfo.user_claims?.find(c => c.typ === 'name')?.val || 
                            userInfo.user_claims?.find(c => c.typ === 'preferred_username')?.val || 
                            'User';
            document.getElementById('userName').textContent = userName;
            
            // Store user info in session
            sessionStorage.setItem('userName', userName);
            sessionStorage.setItem('userInfo', JSON.stringify(userInfo));
        }
    } catch (error) {
        console.error('Error loading user info:', error);
        document.getElementById('userName').textContent = sessionStorage.getItem('userName') || 'User';
    }
}

// Setup event listeners
function setupEventListeners() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const form = document.getElementById('extractedForm');

    // Drag and drop
    dropZone.addEventListener('click', () => fileInput.click());
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
        });
    });

    dropZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    // Form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await submitToZoho();
    });

    // Update deal name preview on input changes
    const fields = ['contact_first', 'contact_last', 'company', 'job_title', 'location', 'source'];
    fields.forEach(field => {
        document.getElementById(field)?.addEventListener('input', updateDealNamePreview);
    });
}

// Handle file upload
async function handleFile(file) {
    if (!file.name.endsWith('.msg') && !file.name.endsWith('.eml')) {
        showStatus('Please upload a .msg or .eml file', 'error');
        return;
    }

    currentFile = file;
    showStatus('Extracting email content with AI...', 'loading');

    try {
        let senderEmail, subject, bodyContent;
        
        if (file.name.endsWith('.msg')) {
            // Use msg.reader library to parse .msg files
            try {
                const arrayBuffer = await file.arrayBuffer();
                const msgReader = new MSGReader(arrayBuffer);
                const fileData = msgReader.getFileData();
                
                senderEmail = fileData.senderEmail || 'unknown@example.com';
                subject = fileData.subject || file.name.replace(/\.msg$/i, '');
                bodyContent = fileData.body || fileData.bodyHTML || `Email from file: ${file.name}`;
                
                // Ensure body content is a string and not too large
                if (typeof bodyContent !== 'string') {
                    bodyContent = String(bodyContent);
                }
                // Truncate if too large (API might have limits)
                if (bodyContent.length > 50000) {
                    bodyContent = bodyContent.substring(0, 50000) + '... [truncated]';
                }
                
                // Extract URLs from parsed content
                if (bodyContent) {
                    extractUrlsFromEmail(bodyContent);
                }
            } catch (parseError) {
                console.error('Error parsing .msg file:', parseError);
                // Fallback: send minimal valid data
                senderEmail = 'unknown@example.com';
                subject = file.name.replace(/\.msg$/i, '');
                bodyContent = `Unable to parse .msg file: ${file.name}. Error: ${parseError.message}`;
            }
        } else {
            // .eml files can be read as text
            const emailContent = await readFileAsText(file);
            senderEmail = extractEmailFromFile(emailContent) || 'unknown@example.com';
            subject = extractSubjectFromFile(emailContent) || file.name.replace(/\.eml$/i, '');
            bodyContent = emailContent;
            
            // Truncate if too large
            if (bodyContent && bodyContent.length > 50000) {
                bodyContent = bodyContent.substring(0, 50000) + '... [truncated]';
            }
            
            extractUrlsFromEmail(emailContent);
        }
        
        // Ensure all values are valid strings (not undefined/null)
        senderEmail = senderEmail || 'unknown@example.com';
        subject = subject || 'Email Upload';
        bodyContent = bodyContent || 'No body content available';
        
        // Clean up ALL fields - remove any null bytes or invalid characters
        // CRITICAL: This prevents 500 errors from corrupted .msg files
        senderEmail = senderEmail.replace(/\0/g, '').replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '').trim();
        subject = subject.replace(/\0/g, '').replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '').trim();
        bodyContent = bodyContent.replace(/\0/g, '').replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '');
        
        // Use the working /intake/email endpoint with LangGraph AI extraction
        // IMPORTANT: Do not include user_corrections in preview requests, otherwise backend skips AI
        const requestBody = {
            sender_email: senderEmail,
            subject: subject,
            body: bodyContent,
            dry_run: true // Preview only, don't create in Zoho yet
        };
        
        console.log('Sending request with body length:', bodyContent.length);
        
        const response = await fetch(`${API_BASE_URL}/intake/email`, {
            method: 'POST',
            headers: {
                'X-API-Key': API_KEY,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('API Error:', errorText);
            console.error('Request was:', requestBody);
            
            // Try to parse error details
            let errorMessage = `Server error: ${response.status}`;
            try {
                const errorJson = JSON.parse(errorText);
                if (errorJson.detail) {
                    errorMessage = errorJson.detail || errorMessage;
                }
            } catch (e) {
                // If not JSON, use the raw text if available
                if (errorText && errorText.length < 200) {
                    errorMessage = errorText;
                }
            }
            throw new Error(errorMessage);
        }

        const data = await response.json();
        console.log('API Response:', data);
        
        // The response has the extracted data in the 'extracted' field
        extractedData = data.extracted || data;
        console.log('Extracted data to populate:', extractedData);
        
        // Populate form with AI-extracted data
        populateForm(extractedData);
        
        showStatus('Data extracted successfully! Review and submit to create deal.', 'success');
        document.getElementById('extractedForm').style.display = 'block';
        updateDealNamePreview();
        
    } catch (error) {
        console.error('Error processing file:', error);
        showStatus('AI extraction failed. Please try again or fill manually.', 'error');
        document.getElementById('extractedForm').style.display = 'block';
    }
}

// Helper function to read file as text
async function readFileAsText(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = reject;
        reader.readAsText(file);
    });
}

// Extract email address from file content
function extractEmailFromFile(content) {
    const emailMatch = content.match(/From:.*?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/);
    return emailMatch ? emailMatch[1] : 'unknown@example.com';
}

// Extract subject from file content  
function extractSubjectFromFile(content) {
    const subjectMatch = content.match(/Subject:\s*(.+)/);
    return subjectMatch ? subjectMatch[1] : 'Email Import';
}

// Extract URLs from email content
function extractUrlsFromEmail(content) {
    // LinkedIn URL
    const linkedinMatch = content.match(/https?:\/\/(www\.)?linkedin\.com\/in\/[a-zA-Z0-9-]+/gi);
    if (linkedinMatch && linkedinMatch[0]) {
        document.getElementById('linkedin_url').value = linkedinMatch[0];
    }

    // Calendly URL
    const calendlyMatch = content.match(/https?:\/\/calendly\.com\/[a-zA-Z0-9-\/]+/gi);
    if (calendlyMatch && calendlyMatch[0]) {
        document.getElementById('calendly_url').value = calendlyMatch[0];
    }
}

// Poll for enrichment results
async function pollForEnrichment(extractionId) {
    // Add loading indicator to specific fields being enriched
    const enrichmentFields = ['linkedin_url', 'company', 'website', 'industry'];
    enrichmentFields.forEach(field => {
        const element = document.getElementById(field);
        if (element) {
            element.classList.add('loading');
            element.placeholder = 'Researching...';
        }
    });
    
    // Poll every 2 seconds for up to 10 attempts
    let attempts = 0;
    const maxAttempts = 10;
    
    const pollInterval = setInterval(async () => {
        attempts++;
        
        try {
            const response = await fetch(`${API_BASE_URL}/intake/email/status/${extractionId}`, {
                headers: {
                    'X-API-Key': API_KEY
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.status === 'completed' && data.enriched_data) {
                    // Update form with enriched data
                    updateFormWithEnrichedData(data.enriched_data);
                    clearInterval(pollInterval);
                    
                    // Remove loading states
                    enrichmentFields.forEach(field => {
                        const element = document.getElementById(field);
                        if (element) {
                            element.classList.remove('loading');
                            element.placeholder = '';
                        }
                    });
                    
                    showStatus('✓ Company research completed', 'success');
                } else if (data.status === 'failed' || attempts >= maxAttempts) {
                    clearInterval(pollInterval);
                    
                    // Remove loading states
                    enrichmentFields.forEach(field => {
                        const element = document.getElementById(field);
                        if (element) {
                            element.classList.remove('loading');
                            element.placeholder = '';
                        }
                    });
                }
            }
        } catch (error) {
            console.error('Error polling for enrichment:', error);
        }
        
        if (attempts >= maxAttempts) {
            clearInterval(pollInterval);
            enrichmentFields.forEach(field => {
                const element = document.getElementById(field);
                if (element) {
                    element.classList.remove('loading');
                    element.placeholder = '';
                }
            });
        }
    }, 2000);
}

// Update form with enriched data
function updateFormWithEnrichedData(enrichedData) {
    // Only update fields that have new data
    if (enrichedData.company_name && !document.getElementById('company').value) {
        document.getElementById('company').value = enrichedData.company_name;
    }
    if (enrichedData.website && !document.getElementById('website').value) {
        document.getElementById('website').value = enrichedData.website;
    }
    if (enrichedData.industry && !document.getElementById('industry').value) {
        document.getElementById('industry').value = enrichedData.industry;
    }
    if (enrichedData.linkedin_url && !document.getElementById('linkedin_url').value) {
        document.getElementById('linkedin_url').value = enrichedData.linkedin_url;
    }
    
    updateDealNamePreview();
}

// Populate form with extracted data
function populateForm(data) {
    console.log('Populating form with data:', data);
    
    // Handle multiple candidates - take the first one if semicolon-separated
    let candidateName = data.candidate_name || '';
    if (candidateName.includes(';')) {
        candidateName = candidateName.split(';')[0].trim();
    }
    
    // Split candidate_name into first and last
    if (candidateName) {
        const nameParts = candidateName.split(' ');
        document.getElementById('contact_first').value = nameParts[0] || '';
        document.getElementById('contact_last').value = nameParts.slice(1).join(' ') || '';
    }

    // Filter out "The Well" from company name since that's the recipient
    let companyName = data.company_name || '';
    // Handle multiple companies - take first non-"The Well" company
    if (companyName.includes(';')) {
        const companies = companyName.split(';').map(c => c.trim());
        companyName = companies.find(c => 
            !c.toLowerCase().includes('the well') && 
            !c.toLowerCase().includes('well recruiting')
        ) || companies[0] || '';
    }
    if (companyName.toLowerCase().includes('the well') || 
        companyName.toLowerCase().includes('well recruiting')) {
        companyName = ''; // Clear it, this is the recipient not the candidate's company
    }

    // Clean up location - handle multiple locations
    let location = data.location || '';
    if (location.includes(';')) {
        location = location.split(';')[0].trim();
    }
    if (location.includes(',')) {
        // Try to extract city, state from address like "21501 N. 78th Ave #100 Peoria, AZ 85382"
        const parts = location.split(',');
        if (parts.length >= 2) {
            // Get last two parts for city, state
            const city = parts[parts.length - 2].trim().split(' ').pop(); // Get last word before state
            const stateZip = parts[parts.length - 1].trim();
            const state = stateZip.split(' ')[0]; // Get state abbreviation
            if (city && state) {
                location = `${city}, ${state}`;
            }
        }
    }

    // Handle multiple emails - take the first one
    let email = data.email || data.candidate_email || '';
    if (email.includes(';')) {
        email = email.split(';')[0].trim();
    }
    
    // Handle multiple job titles - take the first one
    let jobTitle = data.job_title || 'Advisor';
    if (jobTitle.includes(';')) {
        jobTitle = jobTitle.split(';')[0].trim();
    }
    
    // Map other fields
    const fieldMappings = {
        'email': email,
        'phone': data.phone || '',
        'company': companyName,
        'website': data.website || '',
        'industry': data.industry || '',
        'job_title': jobTitle,
        'location': location,
        'linkedin_url': data.linkedin_url || '',
        'calendly_url': data.calendly_url || '',
        'referrer_name': data.referrer_name || '',
        'referrer_email': data.referrer_email || '',
        'source': determineSource(data),
        'notes': data.notes || ''
    };

    for (const [fieldId, value] of Object.entries(fieldMappings)) {
        const element = document.getElementById(fieldId);
        if (element) {
            element.value = value;
        }
    }

    updateDealNamePreview();
}

// Determine source based on content
function determineSource(data) {
    const content = JSON.stringify(data).toLowerCase();
    if (content.includes('twav') || content.includes('advisor vault')) {
        return 'Reverse Recruiting';
    } else if (data.referrer_name || data.referrer_email) {
        return 'Referral';
    } else if (data.calendly_url) {
        return 'Website Inbound';
    }
    return 'Email Inbound';
}

// Update deal name preview
function updateDealNamePreview() {
    const firstName = document.getElementById('contact_first').value;
    const lastName = document.getElementById('contact_last').value;
    const company = document.getElementById('company').value;
    const jobTitle = document.getElementById('job_title').value;
    const location = document.getElementById('location').value;
    const source = document.getElementById('source').value;

    let dealName = '';
    
    if (jobTitle && location && company) {
        // Format: "Advisor (Fort Wayne) Howard Bailey"
        dealName = `${jobTitle} (${location}) ${company}`;
    } else if (firstName && lastName) {
        // Format: "John Smith – Recruiting Consult" or "John Smith – Referral"
        const suffix = source === 'Referral' ? 'Referral' : 'Recruiting Consult';
        dealName = `${firstName} ${lastName} – ${suffix}`;
    } else if (company) {
        dealName = `${company} – Recruiting Consult`;
    } else {
        dealName = 'New Deal';
    }

    document.getElementById('dealNamePreview').textContent = dealName;
}

// Company lookup from domain
async function lookupCompany() {
    const email = document.getElementById('email').value;
    if (!email) {
        showStatus('Please enter an email address first', 'error');
        return;
    }

    const domain = email.split('@')[1];
    if (!domain) {
        showStatus('Invalid email address', 'error');
        return;
    }

    showStatus('Looking up company information...', 'loading');

    try {
        // Use the backend's existing company lookup if available
        // For now, we'll just extract from domain
        const companyName = domain.split('.')[0];
        document.getElementById('company').value = 
            companyName.charAt(0).toUpperCase() + companyName.slice(1);
        document.getElementById('website').value = `https://${domain}`;
        
        updateDealNamePreview();
        showStatus('Company information updated', 'success');
    } catch (error) {
        showStatus('Could not lookup company information', 'error');
    }
}

// Submit to Zoho
async function submitToZoho() {
    showStatus('Creating deal in Zoho...', 'loading');

    // Ensure required fields have values
    const firstName = document.getElementById('contact_first').value || 'Unknown';
    const lastName = document.getElementById('contact_last').value || 'Contact';
    const email = document.getElementById('email').value || 'unknown@example.com';
    const company = document.getElementById('company').value || 'Unknown Company';
    const jobTitle = document.getElementById('job_title').value || 'Advisor';
    const location = document.getElementById('location').value || 'Unknown Location';

    const payload = {
        sender_email: email,
        subject: `Deal Creation: ${document.getElementById('dealNamePreview').textContent}`,
        body: `Manually created from uploaded email file`,
        user_corrections: {
            candidate_name: `${firstName} ${lastName}`.trim(),
            email: email,
            phone: document.getElementById('phone').value || '',
            company_name: company,
            website: document.getElementById('website').value || '',
            industry: document.getElementById('industry').value || '',
            job_title: jobTitle,
            location: location,
            linkedin_url: document.getElementById('linkedin_url').value || '',
            calendly_url: document.getElementById('calendly_url').value || '',
            referrer_name: document.getElementById('referrer_name').value || '',
            referrer_email: document.getElementById('referrer_email').value || '',
            source: document.getElementById('source').value || 'Email Inbound',
            notes: document.getElementById('notes').value || ''
        }
    };

    try {
        const response = await fetch(`${API_BASE_URL}/intake/email`, {
            method: 'POST',
            headers: {
                'X-API-Key': API_KEY,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Submission Error:', errorText);
            
            // Parse error message if it's JSON
            try {
                const errorData = JSON.parse(errorText);
                if (errorData.message) {
                    throw new Error(errorData.message);
                }
            } catch (e) {
                // Not JSON, use generic error
            }
            throw new Error(`Server error: ${response.status}`);
        }

        const result = await response.json();
        
        // Show success message
        document.getElementById('extractedForm').style.display = 'none';
        document.getElementById('resultMessage').style.display = 'block';
        
        document.getElementById('zohoIds').innerHTML = `
            <strong>Deal ID:</strong> ${result.deal_id || 'N/A'}<br>
            <strong>Account ID:</strong> ${result.account_id || 'N/A'}<br>
            <strong>Contact ID:</strong> ${result.contact_id || 'N/A'}<br>
            <strong>Deal Name:</strong> ${result.deal_name || document.getElementById('dealNamePreview').textContent}
        `;
        
        showStatus('Deal created successfully!', 'success');
        
    } catch (error) {
        console.error('Error creating deal:', error);
        showStatus('Error creating deal. Please try again.', 'error');
    }
}

// Show status messages
function showStatus(message, type) {
    const statusDiv = document.getElementById('uploadStatus');
    statusDiv.textContent = message;
    statusDiv.className = `status-message show ${type}`;
    
    if (type === 'loading') {
        statusDiv.innerHTML = `<span class="spinner"></span> ${message}`;
    }
    
    if (type !== 'loading') {
        setTimeout(() => {
            statusDiv.classList.remove('show');
        }, 5000);
    }
}

// Reset form
function resetForm() {
    document.getElementById('extractedForm').reset();
    document.getElementById('extractedForm').style.display = 'none';
    document.getElementById('fileInput').value = '';
    extractedData = null;
    currentFile = null;
    updateDealNamePreview();
}

// Process another email
function processAnother() {
    document.getElementById('resultMessage').style.display = 'none';
    resetForm();
}

// Logout
function logout() {
    // Clear all session data
    sessionStorage.clear();
    localStorage.removeItem('apiKey');
    // Use the full logout URL with redirect
    window.location.href = '/.auth/logout?post_logout_redirect_uri=/logout.html';
}