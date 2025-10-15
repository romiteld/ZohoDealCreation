#!/usr/bin/env python3
"""
Send Well Recruiting Voice Platform technical report to Brandon via email.
Uses Azure Communication Services (same infrastructure as vault alerts).
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from azure.communication.email import EmailClient

# Load environment
load_dotenv('.env.local')

# Email Configuration
ACS_CONNECTION_STRING = os.getenv("ACS_EMAIL_CONNECTION_STRING")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "DoNotReply@389fbf3b-307d-4882-af6a-d86d98329028.azurecomm.net")

def send_report_email():
    """Send the technical report to Brandon."""
    
    if not ACS_CONNECTION_STRING:
        print("❌ ERROR: ACS_EMAIL_CONNECTION_STRING not configured")
        sys.exit(1)
    
    print("=" * 80)
    print("📧 SENDING WELL RECRUITING VOICE PLATFORM REPORT")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"From: {SMTP_FROM_EMAIL}")
    print(f"To: brandon@emailthewell.com")
    print("=" * 80)
    
    # Email subject
    subject = "Well Recruiting Voice Platform - Complete Technical Architecture & MVP Plan"
    
    # Email body (HTML formatted)
    html_body = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 30px;
            text-align: center;
        }
        .header h1 {
            margin: 0 0 10px 0;
            font-size: 32px;
        }
        .header p {
            margin: 0;
            font-size: 18px;
            opacity: 0.9;
        }
        .content {
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        .section {
            margin: 30px 0;
        }
        .section h2 {
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
            margin-top: 40px;
        }
        .section h3 {
            color: #764ba2;
            margin-top: 25px;
        }
        .highlight-box {
            background: #f8f9ff;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }
        .success-box {
            background: #d4edda;
            border-left: 4px solid #28a745;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }
        .warning-box {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            text-align: center;
        }
        .stat-number {
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .stat-label {
            font-size: 14px;
            opacity: 0.9;
        }
        ul, ol {
            line-height: 1.8;
        }
        code {
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
        }
        .footer {
            text-align: center;
            padding: 30px;
            color: #666;
            font-size: 14px;
        }
        .cta-button {
            display: inline-block;
            background: #667eea;
            color: white !important;
            padding: 15px 30px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: bold;
            margin: 20px 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #667eea;
            color: white;
        }
        tr:hover {
            background: #f5f5f5;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 Well Recruiting Voice Platform</h1>
        <p>Complete Integration Architecture & MVP Implementation Plan</p>
        <p style="font-size: 14px; margin-top: 10px; opacity: 0.8;">Prepared by Daniel Romitelli | """ + datetime.now().strftime('%B %d, %Y') + """</p>
    </div>

    <div class="content">
        <div class="section">
            <h2>📋 Executive Summary</h2>
            <p>This comprehensive technical document outlines a <strong>patent-level voice recruiting platform</strong> to replace JustCall, featuring:</p>
            <ul>
                <li><strong>Real-time AI coaching</strong> during recruiter calls</li>
                <li><strong>Zero-touch CRM population</strong> with automatic Zoho deal creation</li>
                <li><strong>Voice-controlled LangGraph orchestration</strong> (Phase 3)</li>
                <li><strong>Seamless integration</strong> with existing Well Intake API and Content Studio</li>
            </ul>
        </div>

        <div class="success-box">
            <h3>✅ Key Decision: Build as Standalone Repository</h3>
            <p>New repository <code>recruiting-voice-platform</code> that communicates with existing systems via shared Azure infrastructure (PostgreSQL, Redis, Service Bus, Azure OpenAI).</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">62-84%</div>
                <div class="stat-label">Cost Reduction vs JustCall</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">6 Weeks</div>
                <div class="stat-label">Time to MVP</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">$5,000</div>
                <div class="stat-label">Phase 1 Development</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">$135/mo</div>
                <div class="stat-label">MVP Operating Cost</div>
            </div>
        </div>

        <div class="section">
            <h2>🏗️ Technical Architecture Overview</h2>
            <h3>Current Azure Infrastructure (Reused)</h3>
            <ul>
                <li><strong>PostgreSQL</strong>: well-intake-db-0903 (shared database - add new schema)</li>
                <li><strong>Redis</strong>: wellintakecache0903 (caching + pub/sub for real-time updates)</li>
                <li><strong>Azure OpenAI</strong>: 2 instances (GPT-4o, GPT-4o-mini)</li>
                <li><strong>Service Bus</strong>: wellintakebus0903 (event-driven communication)</li>
                <li><strong>Blob Storage</strong>: wellintakestorage0903 (call recordings)</li>
                <li><strong>Application Insights</strong>: Unified monitoring</li>
            </ul>

            <h3>New Resources Required</h3>
            <ul>
                <li><strong>Container App</strong>: <code>recruiting-voice-api</code> (Port 8003) - Next.js 14 API</li>
                <li><strong>Container App</strong>: <code>livekit-agent</code> - Python real-time AI processing</li>
                <li><strong>LiveKit Cloud</strong>: SIP trunking, WebRTC, recording ($50-500/mo)</li>
            </ul>
        </div>

        <div class="section">
            <h2>🔄 Inter-Application Communication</h2>
            <p><strong>Communication Patterns Hierarchy:</strong></p>
            <ol>
                <li><strong>Database-First</strong> (Primary) - Shared PostgreSQL as source of truth</li>
                <li><strong>Event-Driven</strong> - Service Bus for async actions</li>
                <li><strong>Redis Pub/Sub</strong> - Real-time UI updates</li>
                <li><strong>REST APIs</strong> - Direct calls when needed</li>
            </ol>

            <h3>Example Integration Flow</h3>
            <div class="highlight-box">
                <p><strong>Voice Call → Zoho Deal Creation:</strong></p>
                <ol>
                    <li>Voice platform writes call data to <code>recruiting_calls</code> table</li>
                    <li>Publishes <code>call.completed</code> event to Service Bus</li>
                    <li>Outlook Intake subscribes and processes with existing LangGraph</li>
                    <li>Creates Zoho deal using existing workflow</li>
                    <li>Updates <code>recruiting_calls.zoho_deal_id</code></li>
                    <li>Teams Bot displays call in query results</li>
                </ol>
            </div>
        </div>

        <div class="section">
            <h2>🎯 MVP Scope - Phase 1 (6 Weeks)</h2>
            <h3>Core Features</h3>
            <ul>
                <li>✅ <strong>LiveKit Integration</strong> - WebRTC + SIP trunking for phone calls</li>
                <li>✅ <strong>Real-Time Transcription</strong> - Azure Speech-to-Text with speaker diarization</li>
                <li>✅ <strong>AI Advisor</strong> - 3 insight types (suggestions, warnings, opportunities)</li>
                <li>✅ <strong>CRM Extraction</strong> - Auto-extract 8 fields during call</li>
                <li>✅ <strong>One-Click Deal Creation</strong> - New endpoint in Outlook Intake</li>
                <li>✅ <strong>Call Recording</strong> - Auto-save to Azure Blob Storage</li>
            </ul>

            <h3>Database Schema</h3>
            <p>New tables added to existing PostgreSQL:</p>
            <ul>
                <li><code>recruiting_calls</code> - Call metadata, transcript, AI analysis</li>
                <li><code>call_insights</code> - Real-time AI suggestions during call</li>
                <li><code>screen_share_analysis</code> - Phase 2</li>
                <li><code>call_compliance</code> - Phase 2</li>
                <li><code>automated_follow_ups</code> - Phase 2</li>
            </ul>
        </div>

        <div class="section">
            <h2>📅 Implementation Timeline</h2>
            <table>
                <thead>
                    <tr>
                        <th>Phase</th>
                        <th>Duration</th>
                        <th>Deliverables</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Week 1-2</strong></td>
                        <td>Infrastructure</td>
                        <td>
                            • Azure resources provisioned<br>
                            • Database schema deployed<br>
                            • LiveKit Cloud configured<br>
                            • CI/CD pipeline setup
                        </td>
                    </tr>
                    <tr>
                        <td><strong>Week 3-4</strong></td>
                        <td>Call Interface</td>
                        <td>
                            • Next.js call UI<br>
                            • LiveKit room management<br>
                            • Azure Speech transcription<br>
                            • LiveKit Python agent
                        </td>
                    </tr>
                    <tr>
                        <td><strong>Week 5-6</strong></td>
                        <td>AI & Integration</td>
                        <td>
                            • Real-time AI advisor<br>
                            • CRM extraction<br>
                            • Outlook Intake endpoint<br>
                            • End-to-end testing
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>💰 Cost Analysis</h2>
            <table>
                <thead>
                    <tr>
                        <th>Scenario</th>
                        <th>Year 1</th>
                        <th>Year 2</th>
                        <th>5-Year Total</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>JustCall (current)</td>
                        <td>$18,000</td>
                        <td>$18,000</td>
                        <td>$90,000</td>
                    </tr>
                    <tr style="background: #d4edda;">
                        <td><strong>Our Platform (Cloud)</strong></td>
                        <td><strong>$6,840</strong></td>
                        <td><strong>$6,840</strong></td>
                        <td><strong>$34,200</strong></td>
                    </tr>
                    <tr style="background: #d4edda;">
                        <td><strong>Our Platform (Self-Hosted)</strong></td>
                        <td><strong>$6,860</strong></td>
                        <td><strong>$1,860</strong></td>
                        <td><strong>$14,300</strong></td>
                    </tr>
                    <tr style="background: #fff3cd;">
                        <td>Savings (Cloud)</td>
                        <td>$11,160</td>
                        <td>$11,160</td>
                        <td>$55,800</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>🚀 Future Phases</h2>
            
            <h3>Phase 2: Advanced Features (Weeks 7-14)</h3>
            <ul>
                <li>Screen share content analysis (OCR, resume parsing)</li>
                <li>Emotion & tone analysis</li>
                <li>Compliance guardian (bias detection)</li>
                <li>Auto-follow-up generation</li>
                <li>Multi-language support</li>
            </ul>

            <h3>Phase 3: LangGraph Voice Orchestration (Weeks 15-26)</h3>
            <ul>
                <li>Voice commands during calls</li>
                <li>Automated CRM updates via voice</li>
                <li>Content Studio integration for follow-ups</li>
                <li>Calendar scheduling via voice</li>
                <li>Web research triggered by voice</li>
            </ul>
        </div>

        <div class="warning-box">
            <h3>❓ Questions for Approval</h3>
            <ol>
                <li><strong>Budget:</strong> Approve $5,000 development + $135/mo LiveKit Cloud?</li>
                <li><strong>Timeline:</strong> Is 6-week MVP acceptable?</li>
                <li><strong>Self-Hosted:</strong> Evaluate at Month 6 or wait longer?</li>
                <li><strong>Phone Numbers:</strong> How many to provision initially? (Recommend 20)</li>
                <li><strong>Mobile App:</strong> iOS first, then Android? Or simultaneous?</li>
                <li><strong>Beta Testers:</strong> Which 5 recruiters should participate?</li>
                <li><strong>JustCall Sunset:</strong> When to cancel? (Recommend 2-week overlap)</li>
            </ol>
        </div>

        <div class="section">
            <h2>📎 Full Document</h2>
            <p>The complete technical document includes:</p>
            <ul>
                <li>Detailed database schema with all fields</li>
                <li>Complete Azure infrastructure audit</li>
                <li>Code examples for all integration patterns</li>
                <li>Repository structure and file organization</li>
                <li>Week-by-week implementation breakdown</li>
                <li>Success criteria and metrics</li>
                <li>Risk analysis and mitigation strategies</li>
            </ul>
            <p><strong>Please reply to this email to request the full 50+ page technical document with all code samples and architecture diagrams.</strong></p>
        </div>

        <div class="success-box" style="text-align: center; margin-top: 40px;">
            <h3 style="margin-top: 0;">✅ Recommendation</h3>
            <p style="font-size: 18px; margin: 20px 0;"><strong>Approve Phase 1 (LiveKit Cloud Option)</strong> to replace JustCall within 6 weeks</p>
            <p style="margin-bottom: 0;">Investment: $5,000 + $135/mo = <strong>62% cheaper than JustCall</strong></p>
        </div>
    </div>

    <div class="footer">
        <p><strong>Prepared by:</strong> Daniel Romitelli, Principal Technology Architect</p>
        <p><strong>The Well Recruiting Solutions</strong></p>
        <p style="margin-top: 20px; font-size: 12px; color: #999;">
            Generated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """<br>
            This document is confidential and proprietary.<br>
            The AI innovations described may be subject to patent filings.
        </p>
    </div>
</body>
</html>
"""
    
    try:
        # Create email client
        email_client = EmailClient.from_connection_string(ACS_CONNECTION_STRING)
        
        # Build message
        message = {
            "content": {
                "subject": subject,
                "html": html_body
            },
            "recipients": {
                "to": [
                    {
                        "address": "brandon@emailthewell.com",
                        "displayName": "Brandon Murphy"
                    }
                ]
            },
            "senderAddress": SMTP_FROM_EMAIL
        }
        
        # Send email
        print("\n🚀 Sending email via Azure Communication Services...")
        poller = email_client.begin_send(message)
        result = poller.result()
        
        message_id = result.get('messageId', 'unknown')
        
        print("=" * 80)
        print("✅ EMAIL SENT SUCCESSFULLY!")
        print("=" * 80)
        print(f"📨 Message ID: {message_id}")
        print(f"📧 Recipient: brandon@emailthewell.com")
        print(f"📝 Subject: {subject}")
        print(f"📄 Report: Well Recruiting Voice Platform - Technical Architecture & MVP Plan")
        print("=" * 80)
        
        return 0
        
    except Exception as e:
        print("=" * 80)
        print(f"❌ ERROR: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    exit_code = send_report_email()
    sys.exit(exit_code)
