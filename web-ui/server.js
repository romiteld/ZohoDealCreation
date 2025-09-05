const express = require('express');
const path = require('path');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();

// Config
const PORT = process.env.PORT || 8080;
const UPSTREAM_API_URL = process.env.UPSTREAM_API_URL || 'https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io';
const API_KEY = process.env.API_KEY || '';

// Static files
const staticDir = __dirname;
app.use(express.static(staticDir));

// API proxy with API key header
app.use('/api', createProxyMiddleware({
  target: UPSTREAM_API_URL,
  changeOrigin: true,
  pathRewrite: {
    '^/api': ''
  },
  onProxyReq: (proxyReq) => {
    if (API_KEY) proxyReq.setHeader('X-API-Key', API_KEY);
  },
  logLevel: 'silent'
}));

// SPA fallback
app.get('*', (req, res) => {
  res.sendFile(path.join(staticDir, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`UI server listening on port ${PORT}`);
});


