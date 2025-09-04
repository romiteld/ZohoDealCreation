"""
Monitoring dashboard for manifest cache performance and analytics.
Provides a comprehensive HTML dashboard for monitoring manifest cache busting system.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/manifest", tags=["manifest-monitoring"])

@router.get("/dashboard", response_class=HTMLResponse)
async def manifest_dashboard(request: Request):
    """Display comprehensive manifest cache monitoring dashboard."""
    
    try:
        from app.manifest_cache_service import get_manifest_cache_service
        from app.webhook_handlers import get_webhook_handler
        from app.redis_cache_manager import get_cache_manager
        
        # Get services
        manifest_service = await get_manifest_cache_service()
        webhook_handler = get_webhook_handler()
        redis_manager = await get_cache_manager()
        
        # Get metrics
        manifest_status = await manifest_service.get_cache_status()
        webhook_stats = webhook_handler.get_stats()
        redis_metrics = await redis_manager.get_metrics()
        
        # Calculate additional metrics
        current_time = datetime.utcnow()
        uptime_minutes = int((current_time - datetime.fromisoformat(webhook_stats.get('last_processed', current_time.isoformat()))).total_seconds() / 60) if webhook_stats.get('last_processed') else 0
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Manifest Cache Dashboard - The Well</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 20px;
                }}
                
                .dashboard {{
                    max-width: 1400px;
                    margin: 0 auto;
                }}
                
                .header {{
                    background: white;
                    border-radius: 12px;
                    padding: 30px;
                    margin-bottom: 30px;
                    box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                
                .header h1 {{
                    color: #2c3e50;
                    font-size: 2.5rem;
                    margin-bottom: 10px;
                }}
                
                .header p {{
                    color: #7f8c8d;
                    font-size: 1.1rem;
                }}
                
                .grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                
                .card {{
                    background: white;
                    border-radius: 12px;
                    padding: 25px;
                    box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                    transition: transform 0.3s ease;
                }}
                
                .card:hover {{
                    transform: translateY(-5px);
                }}
                
                .card-header {{
                    display: flex;
                    align-items: center;
                    margin-bottom: 20px;
                }}
                
                .card-icon {{
                    width: 40px;
                    height: 40px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin-right: 15px;
                    font-size: 1.2rem;
                }}
                
                .card-title {{
                    font-size: 1.3rem;
                    font-weight: 600;
                    color: #2c3e50;
                }}
                
                .metric {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 8px 0;
                    border-bottom: 1px solid #ecf0f1;
                }}
                
                .metric:last-child {{
                    border-bottom: none;
                }}
                
                .metric-label {{
                    color: #7f8c8d;
                    font-weight: 500;
                }}
                
                .metric-value {{
                    font-weight: 600;
                    color: #2c3e50;
                }}
                
                .status {{
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 0.85rem;
                    font-weight: 600;
                    text-transform: uppercase;
                }}
                
                .status-healthy {{ background: #d4edda; color: #155724; }}
                .status-warning {{ background: #fff3cd; color: #856404; }}
                .status-error {{ background: #f8d7da; color: #721c24; }}
                
                .progress-bar {{
                    height: 8px;
                    background: #ecf0f1;
                    border-radius: 4px;
                    overflow: hidden;
                    margin-top: 8px;
                }}
                
                .progress-fill {{
                    height: 100%;
                    background: linear-gradient(90deg, #4CAF50, #45a049);
                    border-radius: 4px;
                    transition: width 0.3s ease;
                }}
                
                .chart-container {{
                    grid-column: 1 / -1;
                    background: white;
                    border-radius: 12px;
                    padding: 25px;
                    box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                }}
                
                .refresh-info {{
                    text-align: center;
                    color: white;
                    margin-top: 20px;
                    opacity: 0.8;
                }}
                
                .endpoint-list {{
                    list-style: none;
                    padding: 0;
                }}
                
                .endpoint-item {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 10px 0;
                    border-bottom: 1px solid #ecf0f1;
                }}
                
                .endpoint-item:last-child {{
                    border-bottom: none;
                }}
                
                .endpoint-method {{
                    background: #3498db;
                    color: white;
                    padding: 2px 8px;
                    border-radius: 4px;
                    font-size: 0.8rem;
                    font-weight: 600;
                }}
                
                .endpoint-method.post {{
                    background: #e67e22;
                }}
                
                .endpoint-path {{
                    font-family: 'Courier New', monospace;
                    color: #2c3e50;
                    font-weight: 500;
                }}
            </style>
        </head>
        <body>
            <div class="dashboard">
                <div class="header">
                    <h1>📊 Manifest Cache Dashboard</h1>
                    <p>Office Add-in Cache Busting System Monitoring - The Well</p>
                </div>
                
                <div class="grid">
                    <!-- Cache Performance Card -->
                    <div class="card">
                        <div class="card-header">
                            <div class="card-icon" style="background: #3498db20; color: #3498db;">🚀</div>
                            <div class="card-title">Cache Performance</div>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Hit Rate</span>
                            <span class="metric-value">{manifest_status.get('cache_hit_rate', 'N/A')}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Total Requests</span>
                            <span class="metric-value">{manifest_status.get('cache_metrics', {}).get('total_requests', 0):,}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Cache Hits</span>
                            <span class="metric-value">{manifest_status.get('cache_metrics', {}).get('cache_hits', 0):,}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Cache Misses</span>
                            <span class="metric-value">{manifest_status.get('cache_metrics', {}).get('cache_misses', 0):,}</span>
                        </div>
                    </div>
                    
                    <!-- System Status Card -->
                    <div class="card">
                        <div class="card-header">
                            <div class="card-icon" style="background: #2ecc7120; color: #2ecc71;">⚡</div>
                            <div class="card-title">System Status</div>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Redis Connection</span>
                            <span class="status status-{'healthy' if manifest_status.get('redis_connected', False) else 'error'}">
                                {'Connected' if manifest_status.get('redis_connected', False) else 'Disconnected'}
                            </span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Cached Manifests</span>
                            <span class="metric-value">{manifest_status.get('cached_manifests', 0):,}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">A/B Testing</span>
                            <span class="status status-{'healthy' if manifest_status.get('ab_test_enabled', False) else 'warning'}">
                                {'Enabled' if manifest_status.get('ab_test_enabled', False) else 'Disabled'}
                            </span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Templates Configured</span>
                            <span class="metric-value">{manifest_status.get('templates_configured', 0)}</span>
                        </div>
                    </div>
                    
                    <!-- GitHub Webhooks Card -->
                    <div class="card">
                        <div class="card-header">
                            <div class="card-icon" style="background: #9b59b620; color: #9b59b6;">🔗</div>
                            <div class="card-title">GitHub Webhooks</div>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Webhooks Received</span>
                            <span class="metric-value">{webhook_stats.get('webhooks_received', 0):,}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Successfully Processed</span>
                            <span class="metric-value">{webhook_stats.get('webhooks_processed', 0):,}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Cache Invalidations</span>
                            <span class="metric-value">{webhook_stats.get('cache_invalidations', 0):,}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Webhook Secret</span>
                            <span class="status status-{'healthy' if webhook_stats.get('webhook_secret_configured', False) else 'error'}">
                                {'Configured' if webhook_stats.get('webhook_secret_configured', False) else 'Missing'}
                            </span>
                        </div>
                    </div>
                    
                    <!-- Redis Metrics Card -->
                    <div class="card">
                        <div class="card-header">
                            <div class="card-icon" style="background: #e74c3c20; color: #e74c3c;">💾</div>
                            <div class="card-title">Redis Metrics</div>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Memory Used</span>
                            <span class="metric-value">{manifest_status.get('redis_memory_used', 'N/A')}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Connected Clients</span>
                            <span class="metric-value">{manifest_status.get('redis_connected_clients', 0)}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Cache TTL</span>
                            <span class="metric-value">{manifest_status.get('cache_ttl_minutes', 5):.0f} minutes</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Health Status</span>
                            <span class="status status-healthy">{redis_metrics.get('health_status', 'HEALTHY')}</span>
                        </div>
                    </div>
                    
                    <!-- A/B Testing Distribution Card -->
                    <div class="card">
                        <div class="card-header">
                            <div class="card-icon" style="background: #f39c1220; color: #f39c12;">🧪</div>
                            <div class="card-title">A/B Testing</div>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Test Split</span>
                            <span class="metric-value">{manifest_status.get('ab_test_split', 0.5) * 100:.0f}% / {100 - manifest_status.get('ab_test_split', 0.5) * 100:.0f}%</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Variant A Requests</span>
                            <span class="metric-value">{manifest_status.get('cache_metrics', {}).get('a_b_test_distributions', {}).get('variant_a', 0):,}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Variant B Requests</span>
                            <span class="metric-value">{manifest_status.get('cache_metrics', {}).get('a_b_test_distributions', {}).get('variant_b', 0):,}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Beta Requests</span>
                            <span class="metric-value">{manifest_status.get('cache_metrics', {}).get('a_b_test_distributions', {}).get('beta', 0):,}</span>
                        </div>
                    </div>
                    
                    <!-- API Endpoints Card -->
                    <div class="card chart-container">
                        <div class="card-header">
                            <div class="card-icon" style="background: #1abc9c20; color: #1abc9c;">🔧</div>
                            <div class="card-title">Available API Endpoints</div>
                        </div>
                        <ul class="endpoint-list">
                            <li class="endpoint-item">
                                <span class="endpoint-method">GET</span>
                                <span class="endpoint-path">/manifest.xml</span>
                                <span>Main manifest file</span>
                            </li>
                            <li class="endpoint-item">
                                <span class="endpoint-method">GET</span>
                                <span class="endpoint-path">/api/manifest/generate</span>
                                <span>Dynamic manifest generation</span>
                            </li>
                            <li class="endpoint-item">
                                <span class="endpoint-method post">POST</span>
                                <span class="endpoint-path">/api/manifest/warmup</span>
                                <span>Cache warmup</span>
                            </li>
                            <li class="endpoint-item">
                                <span class="endpoint-method post">POST</span>
                                <span class="endpoint-path">/api/manifest/invalidate</span>
                                <span>Cache invalidation</span>
                            </li>
                            <li class="endpoint-item">
                                <span class="endpoint-method">GET</span>
                                <span class="endpoint-path">/api/manifest/status</span>
                                <span>Cache status</span>
                            </li>
                            <li class="endpoint-item">
                                <span class="endpoint-method post">POST</span>
                                <span class="endpoint-path">/api/webhook/github</span>
                                <span>GitHub webhook</span>
                            </li>
                            <li class="endpoint-item">
                                <span class="endpoint-method">GET</span>
                                <span class="endpoint-path">/manifest/dashboard</span>
                                <span>This monitoring dashboard</span>
                            </li>
                        </ul>
                    </div>
                </div>
                
                <div class="refresh-info">
                    <p>📊 Dashboard auto-refreshes every 30 seconds | Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
                    <p>🔗 Webhook URL: <code>https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/webhook/github</code></p>
                </div>
            </div>
            
            <script>
                // Auto-refresh dashboard every 30 seconds
                setTimeout(() => {{
                    location.reload();
                }}, 30000);
                
                // Add smooth animations
                document.addEventListener('DOMContentLoaded', function() {{
                    const cards = document.querySelectorAll('.card');
                    cards.forEach((card, index) => {{
                        card.style.animationDelay = `${{index * 0.1}}s`;
                        card.style.animation = 'fadeInUp 0.6s ease-out forwards';
                    }});
                }});
            </script>
            
            <style>
                @keyframes fadeInUp {{
                    from {{
                        opacity: 0;
                        transform: translateY(30px);
                    }}
                    to {{
                        opacity: 1;
                        transform: translateY(0);
                    }}
                }}
            </style>
        </body>
        </html>
        """
        
        return html_content
        
    except Exception as e:
        logger.error(f"Error generating manifest dashboard: {e}")
        
        # Fallback dashboard
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Manifest Dashboard - Error</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .error {{ background: #ffe6e6; border: 1px solid #ffcccc; padding: 20px; border-radius: 8px; }}
                .retry {{ margin-top: 20px; }}
                .retry a {{ color: #007cba; text-decoration: none; }}
            </style>
        </head>
        <body>
            <h1>🚨 Dashboard Error</h1>
            <div class="error">
                <h3>Failed to load dashboard</h3>
                <p>Error: {str(e)}</p>
                <div class="retry">
                    <a href="/manifest/dashboard">🔄 Retry Dashboard</a> |
                    <a href="/health">🏥 Check API Health</a> |
                    <a href="/api/manifest/status">📊 Basic Status</a>
                </div>
            </div>
            <script>
                // Auto-retry in 10 seconds
                setTimeout(() => location.reload(), 10000);
            </script>
        </body>
        </html>
        """
        
        return error_html