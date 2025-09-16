/**
 * Apollo WebSocket Integration for Real-time Enrichment
 * Streams Apollo.io data directly to Outlook Add-in using Azure SignalR
 * Version 1.0.0 - Enterprise-grade Apollo enrichment with unlimited search
 */

// SignalR Configuration
const SIGNALR_ENDPOINT = 'https://wellintakesignalr0903.service.signalr.net';
const APOLLO_HUB_NAME = 'ApolloEnrichmentHub';

// Apollo Enrichment WebSocket Manager
class ApolloWebSocketManager {
    constructor() {
        this.connection = null;
        this.isConnected = false;
        this.enrichmentCallbacks = new Map();
        this.dataQualityMetrics = {
            totalEnrichments: 0,
            successfulEnrichments: 0,
            averageCompleteness: 0,
            linkedinHitRate: 0,
            phoneDiscoveryRate: 0
        };
    }

    /**
     * Initialize WebSocket connection to SignalR for Apollo enrichment
     */
    async initializeConnection() {
        try {
            // Import SignalR client dynamically
            const signalR = await this.loadSignalRClient();
            
            this.connection = new signalR.HubConnectionBuilder()
                .withUrl(`${SIGNALR_ENDPOINT}/${APOLLO_HUB_NAME}`, {
                    withCredentials: false,
                    transport: signalR.HttpTransportType.WebSockets
                })
                .withAutomaticReconnect([0, 2000, 10000, 30000])
                .configureLogging(signalR.LogLevel.Information)
                .build();

            // Setup event handlers
            this.setupEventHandlers();

            // Start connection
            await this.connection.start();
            this.isConnected = true;
            console.log('🚀 Apollo WebSocket connection established');

            return true;
        } catch (error) {
            console.error('Failed to initialize Apollo WebSocket:', error);
            this.isConnected = false;
            return false;
        }
    }

    /**
     * Load SignalR client library dynamically
     */
    async loadSignalRClient() {
        return new Promise((resolve, reject) => {
            if (window.signalR) {
                resolve(window.signalR);
                return;
            }

            const script = document.createElement('script');
            script.src = 'https://unpkg.com/@microsoft/signalr@latest/dist/browser/signalr.min.js';
            script.onload = () => resolve(window.signalR);
            script.onerror = () => reject(new Error('Failed to load SignalR client'));
            document.head.appendChild(script);
        });
    }

    /**
     * Setup WebSocket event handlers for Apollo enrichment streaming
     */
    setupEventHandlers() {
        // Apollo People Search Results
        this.connection.on('apolloPeopleSearchResult', (data) => {
            console.log('📊 Apollo people search result:', data);
            this.handleApolloPersonEnrichment(data);
        });

        // Apollo Company Intelligence
        this.connection.on('apolloCompanyIntelligence', (data) => {
            console.log('🏢 Apollo company intelligence:', data);
            this.handleApolloCompanyEnrichment(data);
        });

        // Apollo Phone Discovery
        this.connection.on('apolloPhoneDiscovery', (data) => {
            console.log('📞 Apollo phone discovery:', data);
            this.handleApolloPhoneEnrichment(data);
        });

        // Apollo LinkedIn Extraction
        this.connection.on('apolloLinkedInData', (data) => {
            console.log('💼 Apollo LinkedIn data:', data);
            this.handleApolloLinkedInEnrichment(data);
        });

        // Apollo Data Quality Metrics
        this.connection.on('apolloDataQuality', (metrics) => {
            console.log('📈 Apollo data quality metrics:', metrics);
            this.updateDataQualityMetrics(metrics);
        });

        // Apollo Enrichment Progress
        this.connection.on('apolloEnrichmentProgress', (progress) => {
            console.log('⏳ Apollo enrichment progress:', progress);
            this.updateEnrichmentProgress(progress);
        });

        // Connection events
        this.connection.onreconnecting(() => {
            console.log('🔄 Apollo WebSocket reconnecting...');
            this.showEnrichmentStatus('Reconnecting to Apollo services...', 'warning');
        });

        this.connection.onreconnected(() => {
            console.log('✅ Apollo WebSocket reconnected');
            this.showEnrichmentStatus('Connected to Apollo services', 'success');
        });

        this.connection.onclose(() => {
            console.log('❌ Apollo WebSocket connection closed');
            this.isConnected = false;
            this.showEnrichmentStatus('Apollo services disconnected', 'error');
        });
    }

    /**
     * Request Apollo enrichment for email data with streaming response
     */
    async requestApolloEnrichment(emailData, enrichmentOptions = {}) {
        if (!this.isConnected) {
            console.warn('Apollo WebSocket not connected, attempting fallback API call');
            return this.fallbackApolloEnrichment(emailData);
        }

        try {
            const enrichmentId = this.generateEnrichmentId();
            
            // Setup callback for this enrichment request
            this.enrichmentCallbacks.set(enrichmentId, {
                resolve: null,
                reject: null,
                startTime: Date.now(),
                options: enrichmentOptions
            });

            // Send enrichment request through WebSocket
            await this.connection.invoke('RequestApolloEnrichment', {
                enrichmentId: enrichmentId,
                emailData: emailData,
                options: {
                    includePhone: enrichmentOptions.includePhone ?? true,
                    includeLinkedIn: enrichmentOptions.includeLinkedIn ?? true,
                    includeCompanyIntel: enrichmentOptions.includeCompanyIntel ?? true,
                    includeDeepEnrichment: enrichmentOptions.includeDeepEnrichment ?? true,
                    maxResults: enrichmentOptions.maxResults ?? 10,
                    confidenceThreshold: enrichmentOptions.confidenceThreshold ?? 0.8
                }
            });

            console.log(`🔄 Apollo enrichment requested (ID: ${enrichmentId})`);
            this.showEnrichmentStatus('Apollo enrichment in progress...', 'info');

            return enrichmentId;
        } catch (error) {
            console.error('Failed to request Apollo enrichment:', error);
            return this.fallbackApolloEnrichment(emailData);
        }
    }

    /**
     * Handle Apollo person enrichment results
     */
    handleApolloPersonEnrichment(data) {
        const { enrichmentId, person, dataQuality, searchRank } = data;
        
        if (person) {
            // Update contact fields with Apollo data
            this.updateContactFieldsWithApollo(person, dataQuality);
            
            // Show enrichment indicator
            this.showApolloEnrichmentIndicator('contactFirstName', dataQuality.confidence);
            this.showApolloEnrichmentIndicator('candidateEmail', dataQuality.has_email ? 1.0 : 0.0);
            
            // Update data quality dashboard
            this.updateDataQualityDashboard(dataQuality);
        }

        this.completeEnrichmentCallback(enrichmentId, { person, dataQuality });
    }

    /**
     * Handle Apollo company enrichment results
     */
    handleApolloCompanyEnrichment(data) {
        const { enrichmentId, company, technologies, competitors } = data;
        
        if (company) {
            // Update company fields
            this.updateCompanyFieldsWithApollo(company);
            
            // Show company intelligence
            this.displayCompanyIntelligence(company, technologies, competitors);
        }

        this.completeEnrichmentCallback(enrichmentId, { company, technologies, competitors });
    }

    /**
     * Handle Apollo phone discovery results
     */
    handleApolloPhoneEnrichment(data) {
        const { enrichmentId, phoneNumbers, confidence } = data;
        
        if (phoneNumbers && phoneNumbers.length > 0) {
            // Update phone fields with validated numbers
            const primaryPhone = phoneNumbers.find(p => p.type === 'mobile') || phoneNumbers[0];
            this.updatePhoneFieldWithApollo(primaryPhone, confidence);
            
            // Show additional phone numbers if available
            this.displayAdditionalPhoneNumbers(phoneNumbers);
        }

        this.completeEnrichmentCallback(enrichmentId, { phoneNumbers, confidence });
    }

    /**
     * Handle Apollo LinkedIn enrichment results
     */
    handleApolloLinkedInEnrichment(data) {
        const { enrichmentId, linkedinUrl, socialProfiles, professionalInfo } = data;
        
        if (linkedinUrl) {
            // Add LinkedIn URL to notes or create a dedicated field
            this.addLinkedInToNotes(linkedinUrl, professionalInfo);
            
            // Show social profile indicators
            this.displaySocialProfileIndicators(socialProfiles);
        }

        this.completeEnrichmentCallback(enrichmentId, { linkedinUrl, socialProfiles });
    }

    /**
     * Update contact fields with Apollo enrichment data
     */
    updateContactFieldsWithApollo(person, dataQuality) {
        // Enhanced name extraction
        if (person.full_name && dataQuality.confidence > 0.8) {
            const nameParts = person.full_name.split(' ');
            this.updateFieldWithApollo('contactFirstName', nameParts[0] || '', dataQuality.confidence);
            this.updateFieldWithApollo('contactLastName', nameParts.slice(1).join(' ') || '', dataQuality.confidence);
        }

        // Enhanced email with validation
        if (person.email && dataQuality.has_email) {
            this.updateFieldWithApollo('candidateEmail', person.email, 1.0);
        }

        // Enhanced phone with international formatting
        if (person.primary_phone && dataQuality.has_phone) {
            this.updateFieldWithApollo('candidatePhone', person.primary_phone, dataQuality.phone_confidence || 0.9);
        }

        // Location with city/state parsing
        if (person.location) {
            const locationParts = person.location.split(', ');
            this.updateFieldWithApollo('contactCity', locationParts[0] || '', 0.8);
            this.updateFieldWithApollo('contactState', locationParts[1] || '', 0.8);
        }

        // Professional information
        if (person.job_title) {
            this.updateFieldWithApollo('jobTitle', person.job_title, dataQuality.professional_confidence || 0.8);
        }
    }

    /**
     * Update company fields with Apollo intelligence
     */
    updateCompanyFieldsWithApollo(company) {
        if (company.name) {
            this.updateFieldWithApollo('firmName', company.name, 0.9);
        }

        if (company.website) {
            this.updateFieldWithApollo('companyWebsite', company.website, 0.9);
        }

        if (company.phone) {
            this.updateFieldWithApollo('companyPhone', company.phone, 0.8);
        }
    }

    /**
     * Update form field with Apollo data and confidence indicator
     */
    updateFieldWithApollo(fieldId, value, confidence) {
        const field = document.getElementById(fieldId);
        if (field && value && value.trim() !== '') {
            // Only update if current value is empty or has lower confidence
            const currentConfidence = parseFloat(field.dataset.confidence || '0');
            
            if (!field.value || currentConfidence < confidence) {
                field.value = value.trim();
                field.dataset.confidence = confidence.toString();
                field.dataset.enrichedBy = 'apollo';
                
                // Show Apollo enrichment indicator
                this.showApolloEnrichmentIndicator(fieldId, confidence);
            }
        }
    }

    /**
     * Show Apollo enrichment indicator on field
     */
    showApolloEnrichmentIndicator(fieldId, confidence) {
        const indicator = document.getElementById(fieldId + 'Indicator');
        if (indicator) {
            indicator.textContent = `Apollo Enhanced (${Math.round(confidence * 100)}%)`;
            indicator.className = 'apollo-enriched-indicator';
            indicator.style.display = 'inline-block';
            indicator.style.background = confidence > 0.8 ? '#28a745' : '#ffc107';
            indicator.style.color = confidence > 0.8 ? 'white' : '#212529';
        }
    }

    /**
     * Display company intelligence panel
     */
    displayCompanyIntelligence(company, technologies, competitors) {
        // Create or update company intelligence panel
        let panel = document.getElementById('apolloCompanyIntel');
        if (!panel) {
            panel = this.createCompanyIntelligencePanel();
        }

        panel.innerHTML = `
            <div class="apollo-intel-header">
                <h6><span class="icon">🏢</span> Apollo Company Intelligence</h6>
            </div>
            <div class="apollo-intel-content">
                <div class="company-metrics">
                    <span class="metric"><strong>Size:</strong> ${company.size || 'Unknown'}</span>
                    <span class="metric"><strong>Industry:</strong> ${company.industry || 'Unknown'}</span>
                    <span class="metric"><strong>Revenue:</strong> ${company.revenue || 'Unknown'}</span>
                </div>
                ${technologies && technologies.length > 0 ? `
                <div class="tech-stack">
                    <strong>Technologies:</strong>
                    ${technologies.slice(0, 5).map(tech => `<span class="tech-badge">${tech}</span>`).join('')}
                </div>
                ` : ''}
                ${competitors && competitors.length > 0 ? `
                <div class="competitors">
                    <strong>Competitors:</strong> ${competitors.slice(0, 3).join(', ')}
                </div>
                ` : ''}
            </div>
        `;
        
        panel.style.display = 'block';
    }

    /**
     * Create company intelligence panel
     */
    createCompanyIntelligencePanel() {
        const panel = document.createElement('div');
        panel.id = 'apolloCompanyIntel';
        panel.className = 'preview-section apollo-intelligence-panel';
        panel.style.display = 'none';
        
        // Insert after company information section
        const companySection = document.querySelector('.preview-section:has(#firmName)') || 
                              document.querySelector('.preview-section');
        if (companySection && companySection.nextSibling) {
            companySection.parentNode.insertBefore(panel, companySection.nextSibling);
        } else if (companySection) {
            companySection.parentNode.appendChild(panel);
        }
        
        return panel;
    }

    /**
     * Update enrichment progress indicator
     */
    updateEnrichmentProgress(progress) {
        const progressElement = document.getElementById('apolloEnrichmentProgress');
        if (progressElement) {
            progressElement.style.width = `${progress.percentage}%`;
            progressElement.textContent = `${progress.step} (${progress.percentage}%)`;
        }
    }

    /**
     * Show enrichment status message
     */
    showEnrichmentStatus(message, type = 'info') {
        // Create or update status element
        let statusElement = document.getElementById('apolloStatus');
        if (!statusElement) {
            statusElement = document.createElement('div');
            statusElement.id = 'apolloStatus';
            statusElement.className = 'apollo-status-message';
            const header = document.querySelector('.header');
            if (header) {
                header.appendChild(statusElement);
            }
        }

        statusElement.textContent = message;
        statusElement.className = `apollo-status-message apollo-status-${type}`;
        statusElement.style.display = 'block';

        // Auto-hide after 3 seconds for success/info messages
        if (type === 'success' || type === 'info') {
            setTimeout(() => {
                statusElement.style.display = 'none';
            }, 3000);
        }
    }

    /**
     * Fallback Apollo enrichment using direct API calls
     */
    async fallbackApolloEnrichment(emailData) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/apollo/search/people`, {
                method: 'POST',
                headers: {
                    'X-API-Key': API_KEY,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: emailData.candidateEmail,
                    name: emailData.candidateName,
                    company_domain: this.extractDomainFromEmail(emailData.candidateEmail)
                })
            });

            if (response.ok) {
                const data = await response.json();
                if (data.status === 'success' && data.data.person) {
                    this.handleApolloPersonEnrichment({
                        enrichmentId: 'fallback',
                        person: data.data.person,
                        dataQuality: data.data_quality
                    });
                }
                return data;
            }
        } catch (error) {
            console.error('Fallback Apollo enrichment failed:', error);
        }
        return null;
    }

    /**
     * Extract domain from email address
     */
    extractDomainFromEmail(email) {
        if (!email || !email.includes('@')) return null;
        return email.split('@')[1];
    }

    /**
     * Generate unique enrichment ID
     */
    generateEnrichmentId() {
        return `apollo_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * Complete enrichment callback
     */
    completeEnrichmentCallback(enrichmentId, data) {
        const callback = this.enrichmentCallbacks.get(enrichmentId);
        if (callback && callback.resolve) {
            callback.resolve(data);
            this.enrichmentCallbacks.delete(enrichmentId);
        }
    }

    /**
     * Update data quality metrics
     */
    updateDataQualityMetrics(metrics) {
        this.dataQualityMetrics = { ...this.dataQualityMetrics, ...metrics };
        this.displayDataQualityDashboard();
    }

    /**
     * Display data quality dashboard
     */
    displayDataQualityDashboard() {
        let dashboard = document.getElementById('apolloDataQuality');
        if (!dashboard) {
            dashboard = this.createDataQualityDashboard();
        }

        const metrics = this.dataQualityMetrics;
        dashboard.innerHTML = `
            <div class="apollo-quality-header">
                <h6><span class="icon">📊</span> Apollo Data Quality</h6>
            </div>
            <div class="apollo-quality-metrics">
                <div class="quality-metric">
                    <span class="metric-label">Completeness</span>
                    <span class="metric-value">${Math.round(metrics.averageCompleteness)}%</span>
                </div>
                <div class="quality-metric">
                    <span class="metric-label">LinkedIn Hit Rate</span>
                    <span class="metric-value">${Math.round(metrics.linkedinHitRate * 100)}%</span>
                </div>
                <div class="quality-metric">
                    <span class="metric-label">Phone Discovery</span>
                    <span class="metric-value">${Math.round(metrics.phoneDiscoveryRate * 100)}%</span>
                </div>
            </div>
        `;
        
        dashboard.style.display = 'block';
    }

    /**
     * Create data quality dashboard
     */
    createDataQualityDashboard() {
        const dashboard = document.createElement('div');
        dashboard.id = 'apolloDataQuality';
        dashboard.className = 'preview-section apollo-quality-dashboard';
        dashboard.style.display = 'none';
        
        // Insert at the end of form
        const form = document.getElementById('previewForm');
        if (form) {
            form.appendChild(dashboard);
        }
        
        return dashboard;
    }

    /**
     * Disconnect WebSocket
     */
    async disconnect() {
        if (this.connection && this.isConnected) {
            await this.connection.stop();
            this.isConnected = false;
            console.log('Apollo WebSocket disconnected');
        }
    }
}

// Global Apollo WebSocket Manager instance
window.apolloWebSocketManager = new ApolloWebSocketManager();

// Initialize when loaded
document.addEventListener('DOMContentLoaded', async () => {
    console.log('🚀 Initializing Apollo WebSocket Manager...');
    await window.apolloWebSocketManager.initializeConnection();
});