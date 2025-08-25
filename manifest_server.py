#!/usr/bin/env python3
"""
Minimal server to serve only the Outlook Add-in manifest and static files
This avoids the heavy dependencies that are causing startup issues
"""

import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Outlook Add-in Manifest Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create static directory and mount it
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Get the base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADDIN_DIR = os.path.join(BASE_DIR, "addin")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "manifest-server"}

@app.api_route("/manifest.xml", methods=["GET", "HEAD"])
async def get_manifest(request: Request):
    """Serve the Outlook Add-in manifest file"""
    manifest_path = os.path.join(ADDIN_DIR, "manifest.xml")
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r') as f:
            content = f.read()
        
        # For HEAD requests, return empty content with proper headers
        if request.method == "HEAD":
            return HTMLResponse(content="", media_type="application/xml")
        
        return HTMLResponse(content=content, media_type="application/xml")
    return {"error": "Manifest file not found"}

@app.api_route("/commands.js", methods=["GET", "HEAD"])
async def get_commands(request: Request):
    """Serve the commands.js file for the add-in"""
    commands_path = os.path.join(ADDIN_DIR, "commands.js")
    if os.path.exists(commands_path):
        with open(commands_path, 'r') as f:
            content = f.read()

        # Update API URL to production
        content = content.replace(
            "http://localhost:8000",
            "https://well-intake-api.azurewebsites.net"
        )

        if request.method == "HEAD":
            return HTMLResponse(content="", media_type="application/javascript")
        return HTMLResponse(content=content, media_type="application/javascript")
    return {"error": "Commands file not found"}

@app.api_route("/commands.html", methods=["GET", "HEAD"])
async def get_commands_html(request: Request):
    """Serve the commands.html host page for function file"""
    html_path = os.path.join(ADDIN_DIR, "commands.html")
    if os.path.exists(html_path):
        with open(html_path, 'r') as f:
            content = f.read()

        # Ensure Office.js and commands.js paths are correct (relative within same host)
        content = content.replace('src="commands.js"', 'src="/commands.js"')

        if request.method == "HEAD":
            return HTMLResponse(content="", media_type="text/html")
        return HTMLResponse(content=content, media_type="text/html")
    return {"error": "Commands HTML not found"}

@app.api_route("/icon-16.png", methods=["GET", "HEAD"])
async def get_icon_16(request: Request):
    """Serve 16x16 icon as real PNG"""
    return _serve_png_icon(16, request)

@app.api_route("/icon-32.png", methods=["GET", "HEAD"])
async def get_icon_32(request: Request):
    """Serve 32x32 icon as real PNG"""
    return _serve_png_icon(32, request)

@app.api_route("/icon-80.png", methods=["GET", "HEAD"])
async def get_icon_80(request: Request):
    """Serve 80x80 icon as real PNG"""
    return _serve_png_icon(80, request)

def _serve_png_icon(size: int, request: Request) -> Response:
    """Generate a simple PNG with TW letters in the center."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        # Fallback: return empty PNG of the right size
        return _empty_png(size, request)

    image = Image.new("RGB", (size, size), "#0078D4")
    draw = ImageDraw.Draw(image)

    # Use default font; adjust font size relative to icon size
    font_size = max(8, int(size * 0.4))
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    text = "TW"
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    draw.text((x, y), text, fill="white", font=font)

    import io
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()

    if request.method == "HEAD":
        return Response(content=b"", media_type="image/png")
    return Response(content=png_bytes, media_type="image/png")

def _empty_png(size: int, request: Request) -> Response:
    import io
    try:
        from PIL import Image
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        content = b"" if request.method == "HEAD" else buf.getvalue()
        return Response(content=content, media_type="image/png")
    except Exception:
        # As an absolute last resort, return an empty body with correct type
        return Response(content=b"" if request.method == "HEAD" else b"\x89PNG\r\n\x1a\n", media_type="image/png")

@app.api_route("/placeholder.html", methods=["GET", "HEAD"])
async def get_placeholder(request: Request):
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
    if request.method == "HEAD":
        return HTMLResponse(content="", media_type="text/html")
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)