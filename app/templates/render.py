"""
Template rendering functions for TalentWell emails.
Handles single candidate emails using the locked weekly_digest_v1.html template.
"""

import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def render_single_candidate(card_html: str) -> str:
    """
    Render a single candidate email using the locked weekly_digest_v1.html template.
    
    Args:
        card_html: HTML string for the single candidate card
        
    Returns:
        Complete HTML email with the candidate card injected
    """
    try:
        # Load the locked template
        template_path = Path(__file__).parent / "email" / "weekly_digest_v1.html"
        
        if not template_path.exists():
            logger.error(f"Template not found at {template_path}")
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_html = f.read()
        
        # Import AST compiler for safe template manipulation
        from app.templates.ast import ASTCompiler
        
        # Initialize compiler and parse template
        compiler = ASTCompiler()
        ast = compiler.parse_template(template_html)
        
        # Update only the modifiable sections
        updates = {
            'cards': card_html,
            # Keep intro_block as-is from template (no update needed)
            # Subject will remain from template
        }
        
        # Apply updates to modifiable nodes only
        compiler.update_modifiable_content(updates)
        
        # Render back to HTML
        final_html = compiler.render_to_html()
        
        # If AST rendering fails, fallback to simple replacement
        if not final_html or '<html' not in final_html.lower():
            logger.warning("AST rendering incomplete, using fallback method")
            final_html = _fallback_render(template_html, card_html)
        
        return final_html
        
    except Exception as e:
        logger.error(f"Error rendering single candidate email: {e}")
        # Return a minimal valid HTML if all else fails
        return _minimal_template(card_html)


def _fallback_render(template_html: str, card_html: str) -> str:
    """
    Fallback rendering method using simple string replacement.
    Only touches the cards section, preserves everything else.
    """
    # Find the cards container
    import re
    
    # Pattern to find the cards container with example cards
    pattern = r'(<div[^>]*data-ast="cards"[^>]*>)(.*?)(</div>\s*<!--[^>]*Internal Note|</div>\s*<div[^>]*class="internal-note")'
    
    def replacer(match):
        opening_tag = match.group(1)
        closing_section = match.group(3)
        # Replace only the content, keep the container structure
        return f"{opening_tag}\n{card_html}\n{closing_section}"
    
    result = re.sub(pattern, replacer, template_html, flags=re.DOTALL)
    
    if result == template_html:
        # If no replacement happened, try a simpler pattern
        logger.warning("Primary pattern didn't match, trying simpler pattern")
        pattern2 = r'(<div[^>]*class="cards-container"[^>]*>)(.*?)(</div>\s*<!--[^>]*Internal|</div>\s*<div[^>]*internal-note)'
        result = re.sub(pattern2, replacer, template_html, flags=re.DOTALL)
    
    return result


def _minimal_template(card_html: str) -> str:
    """
    Minimal valid HTML template as last resort.
    Maintains basic TalentWell branding and structure.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TalentWell – Candidate Alert</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            border-bottom: 2px solid #0066cc;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #0066cc;
            margin: 0;
            font-size: 28px;
        }}
        .candidate-card {{
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 20px;
            background-color: #fff;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            text-align: center;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>TalentWell Candidate Alert</h1>
        </div>
        
        <div class="intro-block">
            <p>A new candidate match has been identified based on your search criteria.</p>
        </div>
        
        <div class="cards-container">
            {card_html}
        </div>
        
        <div class="footer">
            <p>© 2025 TalentWell | Confidential</p>
            <p>This email contains confidential candidate information. Please do not forward.</p>
        </div>
    </div>
</body>
</html>"""


def render_weekly_digest(cards_html: str, intro_text: Optional[str] = None) -> str:
    """
    Render a weekly digest with multiple candidate cards.
    
    Args:
        cards_html: HTML string containing all candidate cards
        intro_text: Optional custom intro text
        
    Returns:
        Complete HTML email for weekly digest
    """
    try:
        # Load the locked template
        template_path = Path(__file__).parent / "email" / "weekly_digest_v1.html"
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_html = f.read()
        
        from app.templates.ast import ASTCompiler
        
        compiler = ASTCompiler()
        ast = compiler.parse_template(template_html)
        
        # Update modifiable sections
        updates = {'cards': cards_html}
        if intro_text:
            updates['intro_block'] = f'<div class="intro-block">{intro_text}</div>'
        
        compiler.update_modifiable_content(updates)
        
        return compiler.render_to_html()
        
    except Exception as e:
        logger.error(f"Error rendering weekly digest: {e}")
        return _minimal_template(cards_html)