"""
AST compiler for locked email templates.
Only allows specific nodes to be modified while preserving template structure.
"""

import re
import hashlib
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
from html.parser import HTMLParser

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """Types of AST nodes"""
    ROOT = "root"
    INTRO_BLOCK = "intro_block"      # Modifiable
    CARDS = "cards"                  # Modifiable
    SUBJECT = "subject"              # Modifiable
    STATIC = "static"                # Not modifiable
    HEADER = "header"
    FOOTER = "footer"
    CALENDLY = "calendly"
    STYLE = "style"


@dataclass
class ASTNode:
    """AST node representation"""
    node_type: NodeType
    content: str
    attributes: Dict[str, str]
    children: List['ASTNode']
    modifiable: bool
    checksum: Optional[str] = None
    
    def calculate_checksum(self) -> str:
        """Calculate checksum for node content"""
        if self.modifiable:
            return "modifiable"
        
        content_str = f"{self.node_type.value}:{self.content}:{json.dumps(self.attributes)}"
        return hashlib.md5(content_str.encode()).hexdigest()
    
    def verify_checksum(self) -> bool:
        """Verify node hasn't been modified"""
        if self.modifiable:
            return True
        return self.checksum == self.calculate_checksum()


class TemplateParser(HTMLParser):
    """Parse HTML template into AST"""
    
    def __init__(self):
        super().__init__()
        self.ast_stack = []
        self.current_node = None
        self.root = ASTNode(NodeType.ROOT, "", {}, [], False)
        self.in_modifiable_block = False
        
    def handle_starttag(self, tag, attrs):
        """Handle opening HTML tags"""
        attrs_dict = dict(attrs)
        
        # Check for modifiable blocks
        if 'data-ast' in attrs_dict:
            ast_type = attrs_dict['data-ast']
            if ast_type in ['intro_block', 'cards', 'subject']:
                node_type = NodeType[ast_type.upper()]
                node = ASTNode(node_type, "", attrs_dict, [], True)
                self.in_modifiable_block = True
            else:
                node = ASTNode(NodeType.STATIC, "", attrs_dict, [], False)
        else:
            # Special handling for known static elements
            if tag == 'style':
                node = ASTNode(NodeType.STYLE, "", attrs_dict, [], False)
            elif 'calendly' in str(attrs_dict).lower():
                node = ASTNode(NodeType.CALENDLY, "", attrs_dict, [], False)
            else:
                node = ASTNode(NodeType.STATIC, "", attrs_dict, [], False)
        
        # Add to tree
        if self.current_node:
            self.current_node.children.append(node)
            self.ast_stack.append(self.current_node)
        else:
            self.root.children.append(node)
        
        self.current_node = node
    
    def handle_endtag(self, tag):
        """Handle closing HTML tags"""
        if self.ast_stack:
            self.current_node = self.ast_stack.pop()
            self.in_modifiable_block = False
        else:
            self.current_node = None
    
    def handle_data(self, data):
        """Handle text content"""
        if self.current_node:
            self.current_node.content += data


class ASTCompiler:
    """Compile and verify AST for email templates"""
    
    def __init__(self, template_path: str = None):
        self.template_path = template_path
        self.ast = None
        self.snapshot = None
        
    def parse_template(self, html: str) -> ASTNode:
        """Parse HTML template into AST"""
        parser = TemplateParser()
        parser.feed(html)
        self.ast = parser.root
        
        # Calculate checksums for all nodes
        self._calculate_checksums(self.ast)
        
        return self.ast
    
    def _calculate_checksums(self, node: ASTNode):
        """Recursively calculate checksums for all nodes"""
        if not node.modifiable:
            node.checksum = node.calculate_checksum()
        
        for child in node.children:
            self._calculate_checksums(child)
    
    def take_snapshot(self) -> Dict[str, Any]:
        """Take a snapshot of the current AST for testing"""
        self.snapshot = self._serialize_node(self.ast)
        return self.snapshot
    
    def _serialize_node(self, node: ASTNode) -> Dict[str, Any]:
        """Serialize AST node to dictionary"""
        return {
            'type': node.node_type.value,
            'content': node.content if node.modifiable else node.checksum,
            'attributes': node.attributes,
            'modifiable': node.modifiable,
            'children': [self._serialize_node(child) for child in node.children]
        }
    
    def verify_snapshot(self, current_ast: ASTNode) -> bool:
        """Verify current AST matches snapshot (for non-modifiable parts)"""
        current_serialized = self._serialize_node(current_ast)
        return self._compare_snapshots(self.snapshot, current_serialized)
    
    def _compare_snapshots(self, snapshot: Dict, current: Dict) -> bool:
        """Compare two AST snapshots"""
        # If node is modifiable, skip content comparison
        if snapshot.get('modifiable'):
            # Still verify structure
            if snapshot['type'] != current['type']:
                return False
        else:
            # For static nodes, verify everything
            if snapshot['content'] != current['content']:
                logger.error(f"Content mismatch in {snapshot['type']} node")
                return False
        
        # Verify children recursively
        if len(snapshot['children']) != len(current['children']):
            logger.error(f"Children count mismatch in {snapshot['type']} node")
            return False
        
        for s_child, c_child in zip(snapshot['children'], current['children']):
            if not self._compare_snapshots(s_child, c_child):
                return False
        
        return True
    
    def update_modifiable_content(self, updates: Dict[str, str]) -> bool:
        """Update only modifiable nodes in the AST"""
        if not self.ast:
            logger.error("No AST loaded")
            return False
        
        success = True
        for key, value in updates.items():
            if key not in ['intro_block', 'cards', 'subject']:
                logger.warning(f"Attempted to modify non-modifiable node: {key}")
                success = False
                continue
            
            # Find and update the node
            node = self._find_node_by_type(self.ast, NodeType[key.upper()])
            if node:
                node.content = value
            else:
                logger.warning(f"Node not found: {key}")
                success = False
        
        return success
    
    def _find_node_by_type(self, node: ASTNode, node_type: NodeType) -> Optional[ASTNode]:
        """Find a node by type in the AST"""
        if node.node_type == node_type:
            return node
        
        for child in node.children:
            result = self._find_node_by_type(child, node_type)
            if result:
                return result
        
        return None
    
    def render_to_html(self) -> str:
        """Render AST back to HTML"""
        if not self.ast:
            return ""
        
        return self._render_node(self.ast)
    
    def _render_node(self, node: ASTNode) -> str:
        """Recursively render AST node to HTML"""
        if node.node_type == NodeType.ROOT:
            # Just render children for root
            return ''.join(self._render_node(child) for child in node.children)
        
        # Build opening tag
        if node.attributes:
            # Find the original tag name from attributes or use div
            tag = 'div'
            for attr, value in node.attributes.items():
                if attr == 'data-tag':
                    tag = value
                    break
            
            attrs_str = ' '.join(f'{k}="{v}"' for k, v in node.attributes.items() 
                               if k != 'data-tag')
            html = f'<{tag} {attrs_str}>'
        else:
            html = '<div>'
        
        # Add content
        html += node.content
        
        # Add children
        for child in node.children:
            html += self._render_node(child)
        
        # Closing tag
        if node.attributes and 'data-tag' in node.attributes:
            html += f'</{node.attributes["data-tag"]}>'
        else:
            html += '</div>'
        
        return html
    
    def validate_template_structure(self) -> List[str]:
        """Validate template has required structure"""
        errors = []
        
        if not self.ast:
            errors.append("No AST loaded")
            return errors
        
        # Check for required modifiable blocks
        required = [NodeType.INTRO_BLOCK, NodeType.CARDS, NodeType.SUBJECT]
        for req_type in required:
            if not self._find_node_by_type(self.ast, req_type):
                errors.append(f"Missing required node: {req_type.value}")
        
        # Check for Calendly link
        if not self._has_calendly_link(self.ast):
            errors.append("Missing Calendly link")
        
        return errors
    
    def _has_calendly_link(self, node: ASTNode) -> bool:
        """Check if AST contains Calendly link"""
        if node.node_type == NodeType.CALENDLY:
            return True
        
        # Check content for Calendly URL
        if 'calendly.com' in node.content.lower():
            return True
        
        # Check attributes
        for value in node.attributes.values():
            if 'calendly.com' in str(value).lower():
                return True
        
        # Check children
        for child in node.children:
            if self._has_calendly_link(child):
                return True
        
        return False
    
    def render(self, template: str, data: Dict[str, str]) -> str:
        """Compatibility method that combines parse, update, and render steps"""
        self.parse_template(template)
        self.update_modifiable_content(data)
        return self.render_to_html()
    
    def enforce_formatting_rules(self) -> Dict[str, Any]:
        """Enforce specific formatting rules on the template"""
        rules_applied = {
            'bold_headers': 0,
            'location_format': 0,
            'ref_codes': 0
        }
        
        # Find cards node
        cards_node = self._find_node_by_type(self.ast, NodeType.CARDS)
        if cards_node and cards_node.content:
            # Ensure candidate headers are bold
            cards_node.content = re.sub(
                r'<h3>([^<]+)</h3>',
                r'<h3><strong>\1</strong></h3>',
                cards_node.content
            )
            rules_applied['bold_headers'] += 1
            
            # Ensure location includes mobility info
            cards_node.content = re.sub(
                r'Location: ([^<\n]+)',
                r'<strong>Location:</strong> \1',
                cards_node.content
            )
            rules_applied['location_format'] += 1
            
            # Ensure ref codes are present
            if 'REF-' not in cards_node.content:
                logger.warning("Missing reference codes in cards")
        
        return rules_applied