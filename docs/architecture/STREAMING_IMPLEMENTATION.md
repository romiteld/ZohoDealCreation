# Real-Time Streaming Implementation

## Overview
Implemented Azure SignalR Service integration with WebSocket and SSE fallback for streaming GPT-5-mini responses to the Outlook Add-in. This provides instant feedback with first token displayed in ~200ms and progressive extraction results.

## Implementation Date
2025-08-29

## New Components

### 1. SignalR Manager (`app/signalr_manager.py`)
- **SignalRConnectionManager**: Manages Azure SignalR Service connections
  - Handles WebSocket connections and reconnection logic
  - Generates JWT tokens for secure connections
  - Manages connection queues for event distribution
  - Supports broadcast and targeted messaging

- **StreamingEmailProcessor**: Processes emails with streaming updates
  - Streams extraction tokens in real-time
  - Progressive field extraction with immediate display
  - Company research with timeout handling
  - Validation and cleaning with progress updates

### 2. Streaming Endpoints (`app/streaming_endpoints.py`)
- **WebSocket Endpoint** (`/stream/ws/email-processing`)
  - Primary real-time bidirectional communication
  - Handles connection lifecycle
  - Processes email with streaming updates
  - Automatic reconnection support

- **SSE Endpoint** (`/stream/sse/process-email`)
  - Server-Sent Events fallback
  - Unidirectional streaming
  - Automatic keepalive for long connections
  - Progressive result streaming

- **Batch Endpoint** (`/stream/batch/process-email`)
  - Chunked response streaming
  - NDJSON format for progressive parsing
  - Optional non-streaming mode

- **Negotiate Endpoint** (`/stream/negotiate`)
  - Connection setup and authentication
  - Returns connection mode and credentials
  - Feature detection for client capabilities

### 3. Updated Outlook Add-in (`addin/commands.js`)
- **WebSocket Support**
  - `tryWebSocketConnection()`: Attempts WebSocket connection
  - `processWithWebSocket()`: Handles streaming updates
  - Automatic fallback to standard API

- **Real-time Progress Display**
  - Token-by-token streaming display
  - Field extraction with immediate UI updates
  - Progressive status messages
  - Enhanced user experience with instant feedback

## Event Types

### Streaming Events
- `CONNECTION_ESTABLISHED`: WebSocket connected
- `EXTRACTION_START`: AI processing begins
- `EXTRACTION_TOKEN`: Individual token streamed
- `EXTRACTION_FIELD`: Field extracted and validated
- `RESEARCH_START`: Company research initiated
- `RESEARCH_RESULT`: Research data received
- `VALIDATION_START`: Data validation begins
- `VALIDATION_RESULT`: Cleaned data ready
- `ZOHO_START`: Zoho record creation begins
- `ZOHO_PROGRESS`: Zoho operation updates
- `ZOHO_COMPLETE`: Records created successfully
- `ERROR`: Processing error occurred
- `COMPLETE`: All processing finished

## Performance Metrics

### Target Performance
- **First Token**: < 200ms
- **Field Detection**: < 500ms per field
- **Total Processing**: 2-3 seconds
- **WebSocket Latency**: < 50ms

### Optimizations
- Token streaming for instant feedback
- Parallel processing of extraction and research
- Connection pooling for WebSocket
- Automatic reconnection on failure
- Progressive field updates

## Configuration

### Environment Variables
```bash
# Azure SignalR (optional - falls back to WebSocket)
AZURE_SIGNALR_CONNECTION_STRING=Endpoint=https://...;AccessKey=...;Version=1.0;

# Existing configurations work as-is
API_KEY=your-secure-api-key-here
OPENAI_API_KEY=sk-proj-...
```

### Client Configuration
```javascript
// Automatic WebSocket detection and fallback
const ws = await tryWebSocketConnection(emailData);
if (ws) {
  // Use streaming
  result = await processWithWebSocket(ws, emailData, updateProgress);
} else {
  // Fallback to standard API
  result = await sendToBackend(emailData);
}
```

## Testing

### Test Script (`test_streaming.py`)
Tests all streaming endpoints:
- WebSocket connection and streaming
- SSE fallback mechanism
- Batch streaming with chunks
- Health and metrics endpoints

### Running Tests
```bash
# Start the API server
uvicorn app.main:app --reload --port 8000

# Run streaming tests
python test_streaming.py
```

## Fallback Strategy

1. **Primary**: Azure SignalR Service (if configured)
2. **Secondary**: Direct WebSocket connection
3. **Tertiary**: Server-Sent Events (SSE)
4. **Fallback**: Standard REST API with polling

## Benefits

### User Experience
- **Instant Feedback**: Users see extraction starting immediately
- **Progressive Display**: Fields appear as they're extracted
- **Real-time Status**: Live updates during processing
- **Reduced Perceived Latency**: First token in 200ms vs 2-3 second wait

### Technical Benefits
- **Scalable**: Azure SignalR handles thousands of concurrent connections
- **Resilient**: Multiple fallback options ensure reliability
- **Efficient**: Streaming reduces memory usage for large responses
- **Maintainable**: Clean separation of streaming logic

## Migration Notes

### Deprecated Components
The following files have been removed as they're no longer needed:
- CrewAI-related files (replaced by LangGraph with streaming)
- SQLite patches (no longer using SQLite)
- Static file handlers (integrated into main app)
- Optimized variants (streaming is the optimization)

### Backward Compatibility
- Existing `/intake/email` endpoint unchanged
- Add-in automatically detects and uses streaming when available
- No changes required to existing deployments

## Deployment

### Azure Container Apps
No additional configuration needed - WebSocket support is built-in:
```bash
# Build and push
docker build -t wellintakeregistry.azurecr.io/well-intake-api:latest .
docker push wellintakeregistry.azurecr.io/well-intake-api:latest

# Update container
az containerapp update \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --image wellintakeregistry.azurecr.io/well-intake-api:latest
```

### Azure SignalR Service (Optional)
If using Azure SignalR:
1. Create SignalR Service in Azure Portal
2. Copy connection string
3. Set `AZURE_SIGNALR_CONNECTION_STRING` environment variable
4. Restart container app

## Monitoring

### Metrics Endpoint
```bash
curl -H "X-API-Key: your-api-key" \
  https://well-intake-api.../stream/metrics
```

Returns:
- Active connections
- Connection durations
- Queued events
- Performance statistics

### Health Check
```bash
curl https://well-intake-api.../stream/health
```

Returns:
- Service status
- Feature availability
- Connection counts

## Future Enhancements

1. **Streaming to Database**: Stream extraction results directly to PostgreSQL
2. **Multi-language Support**: Stream translations in real-time
3. **Batch Processing**: Process multiple emails with streaming updates
4. **Analytics Pipeline**: Stream events to Azure Event Hubs for analytics
5. **Client-side Caching**: Cache partial results for instant display