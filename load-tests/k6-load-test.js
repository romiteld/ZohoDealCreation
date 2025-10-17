/**
 * K6 Load Testing Suite for Well Intake API
 *
 * Tests various scenarios including:
 * - Baseline load
 * - Peak traffic simulation
 * - Stress testing
 * - Spike handling
 * - API endpoint-specific tests
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { SharedArray } from 'k6/data';
import { randomItem } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

// Custom metrics
const errorRate = new Rate('errors');
const emailProcessingDuration = new Trend('email_processing_duration');
const zohoApiDuration = new Trend('zoho_api_duration');
const cacheHitRate = new Rate('cache_hits');
const vaultAlertDuration = new Trend('vault_alert_duration');

// Test configuration
const BASE_URL = __ENV.BASE_URL || 'https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io';
const API_KEY = __ENV.API_KEY || 'test-api-key';

// Load test data
const emailSamples = new SharedArray('emails', function() {
  return [
    {
      subject: "New Financial Advisor - High Net Worth Specialist",
      content: "John Smith, CFA with $180M AUM, 15 years experience...",
      sender: "recruiter@example.com"
    },
    {
      subject: "Executive Candidate - CEO Financial Services",
      content: "Jane Doe, Former CEO of Wealth Management firm...",
      sender: "executive@search.com"
    },
    {
      subject: "Referral - Top Producer from Competition",
      content: "Referred by Steve Perry. Michael Johnson, $2M production...",
      sender: "referral@partner.com"
    }
  ];
});

// Test scenarios
export const options = {
  scenarios: {
    // Scenario 1: Baseline load
    baseline: {
      executor: 'constant-arrival-rate',
      rate: 10,
      timeUnit: '1s',
      duration: '10m',
      preAllocatedVUs: 20,
      maxVUs: 50,
      startTime: '0s',
      tags: { scenario: 'baseline' },
    },

    // Scenario 2: Peak load simulation
    peak_load: {
      executor: 'ramping-arrival-rate',
      startRate: 10,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 200,
      startTime: '11m',
      stages: [
        { duration: '2m', target: 50 },  // Ramp up to 50 RPS
        { duration: '10m', target: 50 }, // Stay at 50 RPS
        { duration: '2m', target: 100 }, // Peak to 100 RPS
        { duration: '5m', target: 100 }, // Hold peak
        { duration: '2m', target: 10 },  // Ramp down
      ],
      tags: { scenario: 'peak_load' },
    },

    // Scenario 3: Stress test
    stress_test: {
      executor: 'ramping-arrival-rate',
      startRate: 10,
      timeUnit: '1s',
      preAllocatedVUs: 100,
      maxVUs: 500,
      startTime: '33m',
      stages: [
        { duration: '5m', target: 100 },  // Ramp to high load
        { duration: '10m', target: 200 }, // Push to stress
        { duration: '10m', target: 300 }, // Extreme stress
        { duration: '5m', target: 10 },   // Recovery
      ],
      tags: { scenario: 'stress_test' },
    },

    // Scenario 4: Spike test
    spike_test: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 300,
      startTime: '64m',
      stages: [
        { duration: '30s', target: 5 },   // Normal load
        { duration: '10s', target: 200 }, // Sudden spike
        { duration: '30s', target: 200 }, // Hold spike
        { duration: '10s', target: 5 },   // Drop
        { duration: '2m', target: 5 },    // Recovery period
      ],
      tags: { scenario: 'spike_test' },
    },

    // Scenario 5: Vault alerts load
    vault_alerts: {
      executor: 'per-vu-iterations',
      vus: 5,
      iterations: 10,
      maxDuration: '30m',
      startTime: '70m',
      tags: { scenario: 'vault_alerts' },
    },
  },

  // Global thresholds
  thresholds: {
    http_req_duration: [
      'p(50)<200',   // 50% of requests under 200ms
      'p(95)<500',   // 95% of requests under 500ms
      'p(99)<1000',  // 99% of requests under 1s
    ],
    http_req_failed: ['rate<0.05'], // Error rate under 5%
    errors: ['rate<0.05'],
    email_processing_duration: ['p(95)<3000'], // 95% under 3s
    zoho_api_duration: ['p(95)<800'],         // 95% under 800ms
    cache_hits: ['rate>0.7'],                 // Cache hit rate > 70%
    vault_alert_duration: ['p(95)<60000'],    // 95% under 60s
  },
};

// Helper functions
function makeRequest(method, endpoint, payload = null, params = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const defaultParams = {
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    tags: { endpoint: endpoint },
  };

  const requestParams = Object.assign({}, defaultParams, params);

  let response;
  if (method === 'GET') {
    response = http.get(url, requestParams);
  } else if (method === 'POST') {
    response = http.post(url, JSON.stringify(payload), requestParams);
  }

  // Track errors
  errorRate.add(response.status !== 200 && response.status !== 201);

  return response;
}

// Main test function
export default function() {
  const scenario = __ENV.scenario || 'mixed';

  group('Email Processing', () => {
    const email = randomItem(emailSamples);
    const startTime = Date.now();

    const response = makeRequest('POST', '/api/process_email', {
      email_content: email.content,
      subject: email.subject,
      sender: email.sender,
      internetMessageId: `msg-${Date.now()}-${__VU}-${__ITER}`,
    });

    emailProcessingDuration.add(Date.now() - startTime);

    check(response, {
      'email processed successfully': (r) => r.status === 200,
      'returns extraction result': (r) => r.json('extraction_result') !== null,
      'includes company record': (r) => r.json('extraction_result.company_record') !== null,
      'processing time < 3s': (r) => r.timings.duration < 3000,
    });

    sleep(1);
  });

  group('Zoho API Operations', () => {
    const startTime = Date.now();

    // Create deal
    const dealResponse = makeRequest('POST', '/api/zoho/deals', {
      deal_name: `Test Deal ${Date.now()}`,
      stage: 'Qualification',
      amount: Math.floor(Math.random() * 1000000),
      closing_date: new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString(),
    });

    zohoApiDuration.add(Date.now() - startTime);

    check(dealResponse, {
      'deal created successfully': (r) => r.status === 201,
      'returns deal ID': (r) => r.json('id') !== null,
      'Zoho API response < 800ms': (r) => r.timings.duration < 800,
    });

    sleep(0.5);
  });

  group('Cache Operations', () => {
    // Test cache warming
    const cacheResponse = makeRequest('GET', '/api/cache/stats');

    if (cacheResponse.status === 200) {
      const stats = cacheResponse.json();
      const hitRate = stats.hits / (stats.hits + stats.misses);
      cacheHitRate.add(hitRate > 0.7);
    }

    check(cacheResponse, {
      'cache stats retrieved': (r) => r.status === 200,
      'cache hit rate > 70%': (r) => {
        const stats = r.json();
        return stats.hits / (stats.hits + stats.misses) > 0.7;
      },
    });
  });

  group('Health Checks', () => {
    const healthResponse = makeRequest('GET', '/health');

    check(healthResponse, {
      'health check passes': (r) => r.status === 200,
      'database connected': (r) => r.json('database') === 'connected',
      'redis connected': (r) => r.json('redis') === 'connected',
      'response time < 100ms': (r) => r.timings.duration < 100,
    });
  });

  // Vault alerts test (only in vault_alerts scenario)
  if (__ENV.scenario === 'vault_alerts') {
    group('Vault Alerts Generation', () => {
      const startTime = Date.now();

      const alertResponse = makeRequest('POST', '/api/vault/generate_alerts', {
        custom_filters: {
          locations: ['New York, NY', 'Chicago, IL'],
          designations: ['CFA', 'CFP'],
          date_range_days: 30,
        },
        max_candidates: 50,
      });

      vaultAlertDuration.add(Date.now() - startTime);

      check(alertResponse, {
        'vault alerts generated': (r) => r.status === 200,
        'includes advisor HTML': (r) => r.json('advisor_html') !== null,
        'includes executive HTML': (r) => r.json('executive_html') !== null,
        'generation time < 60s': (r) => r.timings.duration < 60000,
      });
    });
  }

  // Teams Bot API test
  group('Teams Bot Operations', () => {
    const botResponse = makeRequest('POST', '/api/teams/bot/messages', {
      type: 'message',
      text: 'Show me recent deals',
      from: { id: 'test-user', name: 'Test User' },
      conversation: { id: 'test-conversation' },
    });

    check(botResponse, {
      'bot responds successfully': (r) => r.status === 200,
      'returns activity': (r) => r.json('type') === 'message',
      'response time < 2s': (r) => r.timings.duration < 2000,
    });
  });

  // Random sleep between iterations
  sleep(Math.random() * 2 + 1);
}

// Lifecycle hooks
export function setup() {
  console.log('Load test starting...');
  console.log(`Target: ${BASE_URL}`);

  // Verify API is accessible
  const response = http.get(`${BASE_URL}/health`);
  if (response.status !== 200) {
    throw new Error(`API health check failed: ${response.status}`);
  }

  return { startTime: Date.now() };
}

export function teardown(data) {
  const duration = (Date.now() - data.startTime) / 1000;
  console.log(`Load test completed in ${duration} seconds`);
}

// Custom summary
export function handleSummary(data) {
  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
    'summary.json': JSON.stringify(data),
    'summary.html': htmlReport(data),
  };
}

function textSummary(data, options) {
  // Custom text summary implementation
  let summary = '\n=== Load Test Summary ===\n\n';

  // Add key metrics
  const metrics = data.metrics;
  summary += `Request Duration (p95): ${metrics.http_req_duration.p95}ms\n`;
  summary += `Error Rate: ${metrics.http_req_failed.rate * 100}%\n`;
  summary += `Cache Hit Rate: ${metrics.cache_hits.rate * 100}%\n`;
  summary += `Email Processing (p95): ${metrics.email_processing_duration.p95}ms\n`;

  return summary;
}

function htmlReport(data) {
  // Generate HTML report
  return `
<!DOCTYPE html>
<html>
<head>
  <title>Load Test Report</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    .metric { padding: 10px; margin: 10px 0; border-left: 3px solid #007bff; }
    .pass { border-color: #28a745; }
    .fail { border-color: #dc3545; }
    h1 { color: #333; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
    th, td { padding: 10px; text-align: left; border: 1px solid #ddd; }
    th { background-color: #f8f9fa; }
  </style>
</head>
<body>
  <h1>Well Intake API - Load Test Report</h1>
  <div class="metric ${data.metrics.http_req_failed.rate < 0.05 ? 'pass' : 'fail'}">
    <strong>Error Rate:</strong> ${(data.metrics.http_req_failed.rate * 100).toFixed(2)}%
  </div>
  <div class="metric ${data.metrics.http_req_duration.p95 < 500 ? 'pass' : 'fail'}">
    <strong>Response Time (p95):</strong> ${data.metrics.http_req_duration.p95.toFixed(0)}ms
  </div>
  <div class="metric ${data.metrics.cache_hits.rate > 0.7 ? 'pass' : 'fail'}">
    <strong>Cache Hit Rate:</strong> ${(data.metrics.cache_hits.rate * 100).toFixed(2)}%
  </div>

  <h2>Detailed Metrics</h2>
  <table>
    <tr>
      <th>Metric</th>
      <th>Value</th>
      <th>Threshold</th>
      <th>Status</th>
    </tr>
    ${Object.entries(data.metrics).map(([key, value]) => `
      <tr>
        <td>${key}</td>
        <td>${JSON.stringify(value)}</td>
        <td>${data.thresholds[key] || 'N/A'}</td>
        <td>${value.passes ? '✅' : '❌'}</td>
      </tr>
    `).join('')}
  </table>
</body>
</html>`;
}