/*
 * Copyright (c) Microsoft Corporation. All rights reserved. Licensed under the MIT license.
 * See LICENSE in the project root for license information.
 */

/* global Office */

// Configuration for API connection
const API_BASE_URL = window.API_BASE_URL || 'https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io';
const API_KEY = window.API_KEY || ''; // Will be set via deployment configuration

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
        attachments: (emailData.attachments || [])
          .filter(att => att.content && att.format === 'base64')
          .map(att => ({ filename: att.name, content_base64: att.content, content_type: att.contentType }))
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
  // Create a formatted message from the result
  let message = "✅ Zoho records created successfully!";
  
  if (result.deal_name) {
    message = `✅ Deal created: ${result.deal_name}`;
  } else if (result.message) {
    message = result.message;
  } else if (result.status === 'success') {
    message = "✅ Email successfully processed and sent to Zoho CRM";
  }

  // Show success notification with details
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
  try {
    // Step 1: Extract email data
    showNotification("📧 Reading email content...", Office.MailboxEnums.ItemNotificationMessageType.ProgressIndicator);
    const emailData = await extractEmailData();
    console.log("Extracted email data:", emailData);

    // Step 2: Check for attachments
    if (emailData.attachments && emailData.attachments.length > 0) {
      showNotification(`📎 Processing ${emailData.attachments.length} attachment(s)...`, Office.MailboxEnums.ItemNotificationMessageType.ProgressIndicator);
    }

    // Step 3: Send to backend for AI processing
    showNotification("🤖 Analyzing email with AI...", Office.MailboxEnums.ItemNotificationMessageType.ProgressIndicator);
    
    // Add a slight delay to ensure user sees the message
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Step 4: Process and create Zoho records
    showNotification("📊 Creating Zoho CRM records...", Office.MailboxEnums.ItemNotificationMessageType.ProgressIndicator);
    
    const result = await sendToBackend(emailData);
    console.log("Processing result:", result);

    // Display success results
    displayResults(result);

    // Complete the event
    event.completed();
  } catch (error) {
    console.error("Error processing email:", error);
    
    // Show detailed error notification
    let errorMessage = "❌ Failed to process email";
    
    if (error.message.includes('Cannot connect')) {
      errorMessage = "❌ Cannot connect to server. Please check your connection.";
    } else if (error.message.includes('Server error')) {
      errorMessage = "❌ Server error. Please try again later.";
    } else if (error.message.includes('Zoho')) {
      errorMessage = `❌ Zoho error: ${error.message}`;
    } else {
      errorMessage = `❌ Error: ${error.message}`;
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