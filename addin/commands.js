/*
 * Copyright (c) Microsoft Corporation. All rights reserved. Licensed under the MIT license.
 * See LICENSE in the project root for license information.
 */

/* global Office */

// Configuration for API connection - Now using Container Apps deployment
const API_BASE_URL = window.API_BASE_URL || 'https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io';
const API_KEY = window.API_KEY || ''; // API key should be injected from config.js

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

Office.onReady(() => {
  // Office is ready - initialization code can go here if needed
});

/**
 * Shows a notification message to the user
 * @param {string} message - The message to display
 * @param {string} type - The type of notification (Information, Error, Warning, Progress)
 */
function showNotification(message, type = Office.MailboxEnums.ItemNotificationMessageType.InformationalMessage) {
  Office.context.mailbox.item.notificationMessages.replaceAsync("processStatus", {
    type: type,
    message: message,
    persistent: type === Office.MailboxEnums.ItemNotificationMessageType.ErrorMessage
  });
}

/**
 * Extracts attachment information from the current email
 * @returns {Promise<Array>} Array of attachment objects
 */
async function getAttachments() {
  return new Promise((resolve, reject) => {
    const item = Office.context.mailbox.item;
    
    if (!item.attachments || item.attachments.length === 0) {
      resolve([]);
      return;
    }

    const attachmentPromises = [];
    
    item.attachments.forEach(attachment => {
      if (attachment.attachmentType === Office.MailboxEnums.AttachmentType.File) {
        attachmentPromises.push(
          new Promise((resolveAttachment) => {
            // For file attachments, we'll get the content if it's under 25MB
            if (attachment.size < 25 * 1024 * 1024) {
              item.getAttachmentContentAsync(
                attachment.id,
                (result) => {
                  if (result.status === Office.AsyncResultStatus.Succeeded) {
                    resolveAttachment({
                      name: attachment.name,
                      contentType: attachment.contentType,
                      size: attachment.size,
                      content: result.value.content,
                      format: result.value.format
                    });
                  } else {
                    // If we can't get content, still include attachment metadata
                    resolveAttachment({
                      name: attachment.name,
                      contentType: attachment.contentType,
                      size: attachment.size,
                      error: "Could not retrieve content"
                    });
                  }
                }
              );
            } else {
              // For large attachments, just send metadata
              resolveAttachment({
                name: attachment.name,
                contentType: attachment.contentType,
                size: attachment.size,
                error: "Attachment too large (>25MB)"
              });
            }
          })
        );
      } else {
        // For inline attachments or cloud attachments
        attachmentPromises.push(
          Promise.resolve({
            name: attachment.name,
            contentType: attachment.contentType,
            size: attachment.size,
            isInline: attachment.isInline,
            attachmentType: attachment.attachmentType
          })
        );
      }
    });

    Promise.all(attachmentPromises)
      .then(attachments => resolve(attachments))
      .catch(error => reject(error));
  });
}

/**
 * Extracts email data from the current item
 * @returns {Promise<Object>} Email data object
 */
async function extractEmailData() {
  return new Promise((resolve, reject) => {
    const item = Office.context.mailbox.item;
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
      cc: item.cc ? item.cc.map(recipient => ({
        displayName: recipient.displayName,
        emailAddress: recipient.emailAddress
      })) : [],
      dateTimeCreated: item.dateTimeCreated,
      dateTimeModified: item.dateTimeModified,
      conversationId: item.conversationId,
      itemId: item.itemId
    };

    // Get body content
    item.body.getAsync(
      Office.CoercionType.Text,
      async (bodyResult) => {
        if (bodyResult.status === Office.AsyncResultStatus.Succeeded) {
          emailData.body = bodyResult.value;
          
          // Get HTML body as well for better formatting preservation
          item.body.getAsync(
            Office.CoercionType.Html,
            async (htmlResult) => {
              if (htmlResult.status === Office.AsyncResultStatus.Succeeded) {
                emailData.bodyHtml = htmlResult.value;
              }
              
              try {
                // Get attachments
                emailData.attachments = await getAttachments();
                resolve(emailData);
              } catch (error) {
                console.error("Error getting attachments:", error);
                emailData.attachments = [];
                resolve(emailData);
              }
            }
          );
        } else {
          reject(new Error("Failed to get email body: " + bodyResult.error.message));
        }
      }
    );
  });
}

/**
 * Attempts to establish WebSocket connection for streaming
 * @param {Object} emailData - The extracted email data
 * @returns {Promise<WebSocket|null>} WebSocket connection or null if unavailable
 */
async function tryWebSocketConnection(emailData) {
  try {
    // First negotiate connection
    const apiKey = API_KEY || window.API_KEY || '';
    const negotiateResponse = await fetch(`${API_BASE_URL}/stream/negotiate`, {
      headers: {
        ...(apiKey ? { 'X-API-Key': apiKey } : {})
      }
    });

    if (!negotiateResponse.ok) {
      console.log('WebSocket negotiate failed, falling back to standard API');
      return null;
    }

    const negotiateData = await negotiateResponse.json();
    
    // Try to establish WebSocket connection
    const wsUrl = negotiateData.url.startsWith('/')
      ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${negotiateData.url}`
      : negotiateData.url;

    const ws = new WebSocket(wsUrl);
    
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        ws.close();
        resolve(null);
      }, 5000); // 5 second timeout

      ws.onopen = () => {
        clearTimeout(timeout);
        console.log('WebSocket connected for streaming');
        resolve(ws);
      };

      ws.onerror = () => {
        clearTimeout(timeout);
        console.log('WebSocket error, falling back to standard API');
        resolve(null);
      };
    });
  } catch (error) {
    console.log('WebSocket setup failed:', error);
    return null;
  }
}

/**
 * Process email with WebSocket streaming for real-time updates
 * @param {WebSocket} ws - WebSocket connection
 * @param {Object} emailData - The extracted email data
 * @param {Function} onProgress - Progress callback
 * @returns {Promise<Object>} Processing result
 */
async function processWithWebSocket(ws, emailData, onProgress) {
  return new Promise((resolve, reject) => {
    let extractedFields = {};
    let finalResult = null;
    let fieldBuffer = '';
    let lastUpdateTime = Date.now();

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
          case 'extraction_start':
            onProgress(3, 'AI Processing', 'Starting extraction...');
            break;
            
          case 'extraction_token':
            // Stream individual tokens for real-time display
            fieldBuffer += data.data.token;
            
            // Update UI periodically (every 100ms)
            if (Date.now() - lastUpdateTime > 100) {
              onProgress(3, 'AI Processing', `Extracting: ${fieldBuffer.slice(-50)}...`);
              lastUpdateTime = Date.now();
            }
            break;
            
          case 'extraction_field':
            // Show extracted field immediately
            const field = data.data.field;
            const value = data.data.value;
            extractedFields[field] = value;
            
            const fieldName = field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            onProgress(3, 'AI Processing', `Found ${fieldName}: ${value}`);
            break;
            
          case 'research_start':
            onProgress(4, 'Company Research', 'Searching company information...');
            break;
            
          case 'research_result':
            if (data.data.status === 'complete') {
              const company = data.data.result?.company_name || 'Unknown';
              onProgress(4, 'Company Research', `Found: ${company}`);
            }
            break;
            
          case 'validation_start':
            onProgress(5, 'Validating Data', 'Cleaning and standardizing...');
            break;
            
          case 'zoho_start':
            onProgress(6, 'Creating Records', 'Sending to Zoho CRM...');
            break;
            
          case 'zoho_progress':
            onProgress(6, 'Creating Records', data.data.message || 'Processing...');
            break;
            
          case 'complete':
            finalResult = data.data.result;
            ws.close();
            resolve(finalResult);
            break;
            
          case 'error':
            ws.close();
            reject(new Error(data.data.error || 'Processing error'));
            break;
        }
      } catch (error) {
        console.error('WebSocket message error:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      reject(new Error('WebSocket connection error'));
    };

    ws.onclose = () => {
      if (!finalResult) {
        reject(new Error('WebSocket connection closed unexpectedly'));
      }
    };

    // Send email data for processing
    ws.send(JSON.stringify({
      type: 'process_email',
      data: {
        sender_email: emailData.from?.emailAddress || '',
        sender_name: emailData.from?.displayName || '',
        subject: emailData.subject || '',
        body: emailData.body || '',
        attachments: (emailData.attachments || [])
          .filter(att => att.content && att.format === 'base64')
          .map(att => ({
            filename: att.name,
            content_base64: att.content,
            content_type: att.contentType
          })),
        user_context: getUserContext()  // Include current Outlook user context
      }
    }));
  });
}

/**
 * Sends email data to the FastAPI backend for processing
 * @param {Object} emailData - The extracted email data
 * @returns {Promise<Object>} Processing result from the backend
 */
async function sendToBackend(emailData) {
  try {
    const baseUrl = API_BASE_URL;
    const apiKey = API_KEY || window.API_KEY || '';
    const response = await fetch(`${baseUrl}/intake/email`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(apiKey ? { 'X-API-Key': apiKey } : {})
      },
      body: JSON.stringify({
        sender_email: emailData.from?.emailAddress || '',
        sender_name: emailData.from?.displayName || '',
        subject: emailData.subject || '',
        body: emailData.body || '',
        dry_run: false, // Create Zoho records when extracting
        attachments: (emailData.attachments || [])
          .filter(att => att.content && att.format === 'base64')
          .map(att => ({ filename: att.name, content_base64: att.content, content_type: att.contentType })),
        user_context: getUserContext()  // Include current Outlook user context
      })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Server error: ${response.status} ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
      throw new Error('Cannot connect to the server. Please ensure the backend is running and accessible.');
    }
    throw error;
  }
}

/**
 * Displays the processing results to the user
 * @param {Object} result - The processing result from the backend
 */
function displayResults(result) {
  // Create a user-friendly success message
  let message = "✓ Successfully sent to Zoho";
  
  if (result.deal_name) {
    // Truncate long deal names for better display
    const dealName = result.deal_name.length > 50 
      ? result.deal_name.substring(0, 47) + "..." 
      : result.deal_name;
    message = `✓ Created: ${dealName}`;
  } else if (result.message && result.message.includes('success')) {
    message = "✓ Email processed successfully";
  } else if (result.message) {
    message = `✓ ${result.message}`;
  }

  // Show success notification
  showNotification(message, Office.MailboxEnums.ItemNotificationMessageType.InformationalMessage);

  // Log details for debugging
  if (result.deal_id) {
    console.log(`Deal ID: ${result.deal_id}`);
    console.log(`Account ID: ${result.account_id}`);
    console.log(`Contact ID: ${result.contact_id}`);
  }

  // Store results for reference
  if (typeof(Storage) !== "undefined") {
    localStorage.setItem('lastZohoResult', JSON.stringify({
      timestamp: new Date().toISOString(),
      ...result
    }));
  }
}

/**
 * Main function to process the email
 * Called when the user clicks the "Send to Zoho" button
 */
async function processEmail(event) {
  const startTime = Date.now();
  let currentStep = 0;
  const totalSteps = 7;
  
  // Enhanced progress visualization with emojis and percentages
  function updateProgress(step, message, subMessage = null) {
    currentStep = step;
    const percentage = Math.round((currentStep / totalSteps) * 100);
    const progressBlocks = '▓'.repeat(currentStep) + '░'.repeat(totalSteps - currentStep);
    
    // Add status emoji based on step
    const statusEmoji = {
      1: '📧', // Reading email
      2: '📎', // Attachments
      3: '🔍', // Analyzing
      4: '🤖', // AI Processing
      5: '☁️', // Uploading
      6: '✍️', // Creating records
      7: '✅'  // Complete
    }[currentStep] || '⏳';
    
    const fullMessage = subMessage 
      ? `${statusEmoji} ${progressBlocks} ${percentage}% - ${message}\n${subMessage}`
      : `${statusEmoji} ${progressBlocks} ${percentage}% - ${message}`;
    
    showNotification(
      fullMessage, 
      Office.MailboxEnums.ItemNotificationMessageType.ProgressIndicator
    );
  }
  
  try {
    // Step 1: Extract email data
    updateProgress(1, "Reading email content");
    const emailData = await extractEmailData();
    console.log("Extracted email data:", emailData);
    
    // Show sender info
    const senderInfo = emailData.from?.displayName || emailData.from?.emailAddress || 'Unknown';
    updateProgress(1, "Reading email", `From: ${senderInfo}`);
    await new Promise(resolve => setTimeout(resolve, 200));

    // Step 2: Check for attachments
    const attachmentCount = emailData.attachments?.length || 0;
    updateProgress(2, 
      attachmentCount > 0 ? "Processing attachments" : "No attachments",
      attachmentCount > 0 ? `${attachmentCount} file(s) detected` : null
    );
    await new Promise(resolve => setTimeout(resolve, 200));

    // Step 3: Analyze email content
    updateProgress(3, "Analyzing email content", "Extracting candidate information");
    await new Promise(resolve => setTimeout(resolve, 300));
    
    // Try to establish WebSocket connection for streaming
    const ws = await tryWebSocketConnection(emailData);
    
    let result;
    if (ws) {
      // Use WebSocket for real-time streaming updates
      console.log("Using WebSocket for streaming updates");
      
      result = await processWithWebSocket(ws, emailData, (step, message, subMessage) => {
        updateProgress(step, message, subMessage);
      });
    } else {
      // Fallback to standard API
      console.log("Using standard API (no WebSocket available)");
      
      // Step 4: AI Processing (this happens during sendToBackend)
      updateProgress(4, "AI Processing", "Using GPT-5-mini to extract data");
      
      // Step 5: Upload attachments if any
      if (attachmentCount > 0) {
        updateProgress(5, "Uploading attachments", "Storing in Azure Blob Storage");
      } else {
        updateProgress(5, "Preparing data", "Formatting for Zoho CRM");
      }
      
      // Send to backend (AI processing + Zoho creation happens here)
      result = await sendToBackend(emailData);
    }
    
    console.log("Processing result:", result);

    // Step 6: Creating Zoho records
    updateProgress(6, "Creating Zoho records", 
      result.deal_name ? `Deal: ${result.deal_name.substring(0, 30)}...` : "Account, Contact & Deal"
    );
    await new Promise(resolve => setTimeout(resolve, 300));

    // Step 7: Complete
    const elapsedTime = ((Date.now() - startTime) / 1000).toFixed(1);
    updateProgress(7, "Complete!", `Processed in ${elapsedTime} seconds`);
    
    // Wait briefly to show completion
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Display success results
    displayResults(result);

    // Complete the event
    event.completed();
  } catch (error) {
    console.error("Error processing email:", error);
    
    // Show user-friendly error notification
    let errorMessage = "Unable to process email";
    
    if (error.message.includes('Cannot connect') || error.message.includes('Failed to fetch')) {
      errorMessage = "Connection error - Please try again in a moment";
    } else if (error.message.includes('403') || error.message.includes('Forbidden')) {
      errorMessage = "Access denied - Please contact your administrator";
    } else if (error.message.includes('Server error') || error.message.includes('500')) {
      errorMessage = "Server is temporarily unavailable - Please try again";
    } else if (error.message.includes('Zoho')) {
      errorMessage = "Zoho connection issue - Please try again";
    } else if (error.message.includes('timeout')) {
      errorMessage = "Request timed out - Please try again";
    } else {
      errorMessage = "Something went wrong - Please try again";
    }
    
    showNotification(
      errorMessage,
      Office.MailboxEnums.ItemNotificationMessageType.ErrorMessage
    );

    // Complete the event even on error
    event.completed();
  }
}

/**
 * Helper function to get authentication token if needed
 * @returns {string} Authentication token
 */
function getAuthToken() {
  // This is a placeholder - implement your authentication logic here
  // You might get this from:
  // 1. Office.context.mailbox.getUserIdentityTokenAsync() for Exchange identity
  // 2. A stored token from your own auth system
  // 3. Environment variables or configuration
  return localStorage.getItem('authToken') || '';
}

/**
 * Registers the function with Office
 */
Office.actions = Office.actions || {};
Office.actions.associate = Office.actions.associate || {};
Office.actions.associate("processEmail", processEmail);

// Export functions for testing purposes
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    processEmail,
    extractEmailData,
    sendToBackend,
    displayResults,
    getAttachments
  };
}