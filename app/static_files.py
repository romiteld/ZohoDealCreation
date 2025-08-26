"""
Static file serving for Outlook Add-in manifest and related files
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse
import os

router = APIRouter()

# Get the base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDIN_DIR = os.path.join(BASE_DIR, "addin")

@router.get("/manifest.xml")
async def get_manifest():
    """Serve the Outlook Add-in manifest file"""
    manifest_path = os.path.join(ADDIN_DIR, "manifest.xml")
    if os.path.exists(manifest_path):
        # Read and update manifest with production URLs
        with open(manifest_path, 'r') as f:
            content = f.read()
        
        # Replace placeholder URLs with production URLs
        content = content.replace(
            "https://your-static-assets-url.com",
            "https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/static"
        )
        content = content.replace(
            "https://your-domain-for-addin-files.com",
            "https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io"
        )
        content = content.replace(
            "~remoteAppUrl",
            "https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io"
        )
        
        return HTMLResponse(content=content, media_type="application/xml")
    return {"error": "Manifest file not found"}

@router.get("/commands.js")
async def get_commands():
    """Serve the commands.js file for the add-in"""
    commands_path = os.path.join(ADDIN_DIR, "commands.js")
    if os.path.exists(commands_path):
        with open(commands_path, 'r') as f:
            content = f.read()
        
        # Update API URL to production
        content = content.replace(
            "http://localhost:8000",
            "https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io"
        )
        
        return HTMLResponse(content=content, media_type="application/javascript")
    return {"error": "Commands file not found"}

@router.get("/taskpane.html")
async def get_taskpane():
    """Serve the taskpane HTML"""
    taskpane_path = os.path.join(ADDIN_DIR, "taskpane.html")
    if os.path.exists(taskpane_path):
        return FileResponse(taskpane_path, media_type="text/html")
    return {"error": "Taskpane file not found"}

@router.get("/placeholder.html")
async def get_placeholder():
    """Serve a placeholder HTML page"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>The Well Recruiting - Email Intake</title>
    </head>
    <body>
        <h1>The Well Recruiting Solutions</h1>
        <p>Email Intake Add-in for Outlook</p>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.get("/static/icon-16.png")
async def get_icon_16():
    """Serve 16x16 icon"""
    svg_content = """
    <svg width="16" height="16" xmlns="http://www.w3.org/2000/svg">
        <rect width="16" height="16" fill="#0078D4"/>
        <text x="50%" y="50%" text-anchor="middle" dy=".3em" fill="white" font-family="Arial" font-size="5">TW</text>
    </svg>
    """
    return HTMLResponse(content=svg_content, media_type="image/svg+xml")

@router.get("/static/icon-32.png")
async def get_icon_32():
    """Serve 32x32 icon"""
    svg_content = """
    <svg width="32" height="32" xmlns="http://www.w3.org/2000/svg">
        <rect width="32" height="32" fill="#0078D4"/>
        <text x="50%" y="50%" text-anchor="middle" dy=".3em" fill="white" font-family="Arial" font-size="10">TW</text>
    </svg>
    """
    return HTMLResponse(content=svg_content, media_type="image/svg+xml")

@router.get("/static/icon-80.png")
async def get_icon_80():
    """Serve 80x80 icon"""
    svg_content = """
    <svg width="80" height="80" xmlns="http://www.w3.org/2000/svg">
        <rect width="80" height="80" fill="#0078D4"/>
        <text x="50%" y="50%" text-anchor="middle" dy=".3em" fill="white" font-family="Arial" font-size="26">TW</text>
    </svg>
    """
    return HTMLResponse(content=svg_content, media_type="image/svg+xml")

@router.get("/config.js")
async def get_config():
    """Serve the configuration JavaScript file"""
    config_path = os.path.join(ADDIN_DIR, "config.js")
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            content = f.read()
        
        # In production, inject the API key from environment variable
        api_key = os.getenv("API_KEY", "")
        if api_key:
            content = content.replace("window.API_KEY = '';", f"window.API_KEY = '{api_key}';")
        
        return HTMLResponse(content=content, media_type="application/javascript")
    
    # Fallback configuration if file doesn't exist
    api_key = os.getenv("API_KEY", "")
    fallback_content = f"""
    window.API_BASE_URL = 'https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io';
    window.API_KEY = '{api_key}';
    """
    return HTMLResponse(content=fallback_content, media_type="application/javascript")

@router.get("/loader.html")
async def get_loader():
    """Serve the loader HTML that includes config and commands"""
    loader_path = os.path.join(ADDIN_DIR, "loader.html")
    if os.path.exists(loader_path):
        return FileResponse(loader_path, media_type="text/html")
    
    # Fallback loader if file doesn't exist
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="X-UA-Compatible" content="IE=Edge">
        <title>The Well Recruiting - Email Intake</title>
        <script type="text/javascript" src="https://appsforoffice.microsoft.com/lib/1/hosted/office.js"></script>
        <script type="text/javascript" src="/config.js"></script>
        <script type="text/javascript" src="/commands.js"></script>
    </head>
    <body>
        <div style="display: none;">Loading...</div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.get("/results.html")
async def get_results():
    """Serve the results display page"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="X-UA-Compatible" content="IE=Edge">
        <title>Processing Results</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; }
            h1 { color: #0078D4; }
            .result { background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 10px 0; }
            .success { border-left: 4px solid #00a652; }
            .error { border-left: 4px solid #d83b01; }
        </style>
    </head>
    <body>
        <h1>Email Processing Results</h1>
        <div id="results" class="result">
            <p>Loading results...</p>
        </div>
        <script>
            // Load results from localStorage if available
            const results = localStorage.getItem('lastProcessingResult');
            if (results) {
                const data = JSON.parse(results);
                const container = document.getElementById('results');
                container.className = data.status === 'success' ? 'result success' : 'result error';
                container.innerHTML = '<h2>' + (data.message || 'Processing Complete') + '</h2>';
                if (data.deal_id) {
                    container.innerHTML += '<p><strong>Deal ID:</strong> ' + data.deal_id + '</p>';
                }
                if (data.account_id) {
                    container.innerHTML += '<p><strong>Account ID:</strong> ' + data.account_id + '</p>';
                }
                if (data.contact_id) {
                    container.innerHTML += '<p><strong>Contact ID:</strong> ' + data.contact_id + '</p>';
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)