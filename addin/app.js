// Configuration
const API_BASE_URL = 'https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io';
const API_KEY = localStorage.getItem('apiKey') || 'e49d2dbcfa4547f5bdc371c5c06aae2afd06914e16e680a7f31c5fc5384ba384';

// Global variables
let extractedData = null;
let currentFile = null;
let userInfo = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    await loadUserInfo();
    setupEventListeners();
    updateDealNamePreview();
});

// Load user info from Azure AD
async function loadUserInfo() {
    try {
        const response = await fetch('/.auth/me');
        const data = await response.json();
        if (data && data[0]) {
            userInfo = data[0];
            document.getElementById('userName').textContent = 
                userInfo.user_claims?.find(c => c.typ === 'name')?.val || 'User';
        }
    } catch (error) {
        console.error('Error loading user info:', error);
        document.getElementById('userName').textContent = 'User';
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
    showStatus('Processing email file...', 'loading');

    try {
        // Read file content - for now we'll try to extract text from both .msg and .eml
        const emailContent = await readFileAsText(file);
        
        // Extract basic info from the file content
        const senderEmail = extractEmailFromFile(emailContent) || 'unknown@example.com';
        const subject = extractSubjectFromFile(emailContent) || file.name.replace(/\.(msg|eml)$/i, '');
        
        // For .msg files, try to extract the actual email body
        let bodyContent = emailContent;
        if (file.name.endsWith('.msg')) {
            // Try to extract readable text from .msg file
            // MSG files contain readable text mixed with binary, we can extract it
            const textMatch = emailContent.match(/[\x20-\x7E\s]{20,}/g);
            if (textMatch) {
                bodyContent = textMatch.join(' ');
            }
        }
        
        const response = await fetch(`${API_BASE_URL}/intake/email`, {
            method: 'POST',
            headers: {
                'X-API-Key': API_KEY || prompt('Please enter your API key:'),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                sender_email: senderEmail,
                subject: subject,
                body: bodyContent,
                dry_run: true // Important: preview only, don't create in Zoho yet
            })
        });

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();
        extractedData = data.extracted || data;
        
        // Populate form
        populateForm(extractedData);
        
        // Try to extract URLs from the original content
        extractUrlsFromEmail(bodyContent);
        
        // Override with extracted data URLs if available
        if (extractedData) {
            if (extractedData.linkedin_url) {
                document.getElementById('linkedin_url').value = extractedData.linkedin_url;
            }
            if (extractedData.calendly_url) {
                document.getElementById('calendly_url').value = extractedData.calendly_url;
            }
        }
        
        showStatus('Data extracted successfully! Please review and edit as needed.', 'success');
        document.getElementById('extractedForm').style.display = 'block';
        
    } catch (error) {
        console.error('Error processing file:', error);
        showStatus('Error processing file. Please try again.', 'error');
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

// Populate form with extracted data
function populateForm(data) {
    // Split candidate_name into first and last
    if (data.candidate_name) {
        const nameParts = data.candidate_name.split(' ');
        document.getElementById('contact_first').value = nameParts[0] || '';
        document.getElementById('contact_last').value = nameParts.slice(1).join(' ') || '';
    }

    // Map other fields
    const fieldMappings = {
        'email': data.email || data.candidate_email || '',
        'phone': data.phone || '',
        'company': data.company_name || '',
        'website': data.website || '',
        'industry': data.industry || '',
        'job_title': data.job_title || 'Advisor',
        'location': data.location || '',
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

    const payload = {
        sender_email: document.getElementById('email').value,
        subject: `Deal Creation: ${document.getElementById('dealNamePreview').textContent}`,
        body: `Manually created from uploaded email file`,
        user_corrections: {
            candidate_name: `${document.getElementById('contact_first').value} ${document.getElementById('contact_last').value}`,
            email: document.getElementById('email').value,
            phone: document.getElementById('phone').value,
            company_name: document.getElementById('company').value,
            website: document.getElementById('website').value,
            industry: document.getElementById('industry').value,
            job_title: document.getElementById('job_title').value,
            location: document.getElementById('location').value,
            linkedin_url: document.getElementById('linkedin_url').value,
            calendly_url: document.getElementById('calendly_url').value,
            referrer_name: document.getElementById('referrer_name').value,
            referrer_email: document.getElementById('referrer_email').value,
            source: document.getElementById('source').value,
            notes: document.getElementById('notes').value
        }
    };

    try {
        const response = await fetch(`${API_BASE_URL}/intake/email`, {
            method: 'POST',
            headers: {
                'X-API-Key': API_KEY || prompt('Please enter your API key:'),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
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
    window.location.href = '/.auth/logout';
}