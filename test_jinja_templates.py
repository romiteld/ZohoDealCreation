#!/usr/bin/env python3
"""
Minimal test for Jinja2 template system without Redis dependencies.
"""

import os
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Any, Dict
from jinja2 import Environment, FileSystemLoader
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

@dataclass
class ManifestConfig:
    """Configuration for manifest template generation."""
    
    # Basic manifest properties
    app_id: str
    version: str
    provider_name: str
    app_name: str
    description: str
    
    # API endpoints and domains
    api_base_url: str
    app_domains: List[str]
    
    # Resources and icons
    icon_16: str
    icon_32: str
    icon_64: str
    icon_80: str
    icon_128: str
    
    # Add-in specific settings
    requested_height: int = 250
    permissions: str = "ReadWriteItem"
    support_url: str = "https://thewell.solutions/"
    
    # Environment-specific settings
    environment: str = "production"
    cache_busting: bool = True
    websocket_enabled: bool = False
    
    # Template metadata
    template_name: str = "default"
    template_version: str = "1.0.0"
    created_at: str = ""
    
    def __post_init__(self):
        """Initialize computed fields."""
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering."""
        data = asdict(self)
        
        # Add computed values for template
        data['cache_version'] = f"v={self.version}" if self.cache_busting else ""
        data['timestamp'] = int(datetime.utcnow().timestamp())
        
        # Build full URLs with cache busting
        if self.cache_busting:
            cache_param = data['cache_version']
            data['commands_url'] = f"{self.api_base_url}/commands.html?{cache_param}"
            data['taskpane_url'] = f"{self.api_base_url}/taskpane.html?{cache_param}"
        else:
            data['commands_url'] = f"{self.api_base_url}/commands.html"
            data['taskpane_url'] = f"{self.api_base_url}/taskpane.html"
        
        return data

class ManifestTemplateEngine:
    """Template engine for generating Outlook manifest files."""
    
    def __init__(self, templates_dir: str = None):
        """Initialize template engine."""
        self.templates_dir = templates_dir or os.path.join(
            os.path.dirname(__file__), 'templates', 'manifests'
        )
        
        # Ensure templates directory exists
        os.makedirs(self.templates_dir, exist_ok=True)
        
        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.env.filters['xmlescape'] = self._xml_escape
    
    def _xml_escape(self, value: str) -> str:
        """Custom Jinja2 filter for XML escaping."""
        if not isinstance(value, str):
            value = str(value)
        
        return (value
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#x27;'))
    
    def create_default_templates(self):
        """Create default manifest templates if they don't exist."""
        template_content = '''<?xml version="1.0" encoding="UTF-8"?>
<OfficeApp xmlns="http://schemas.microsoft.com/office/appforoffice/1.1"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
           xmlns:bt="http://schemas.microsoft.com/office/officeappbasictypes/1.0"
           xmlns:mailappor="http://schemas.microsoft.com/office/mailappversionoverrides/1.0"
           xsi:type="MailApp">
  
  <Id>{{ app_id }}</Id>
  <Version>{{ version }}</Version>
  <ProviderName>{{ provider_name | xmlescape }}</ProviderName>
  <DefaultLocale>en-US</DefaultLocale>
  <DisplayName DefaultValue="{{ app_name | xmlescape }}"/>
  <Description DefaultValue="{{ description | xmlescape }}"/>
  <IconUrl DefaultValue="{{ icon_64 }}"/>
  <HighResolutionIconUrl DefaultValue="{{ icon_128 }}"/>
  <SupportUrl DefaultValue="{{ support_url }}"/>
  
  <AppDomains>
    {% for domain in app_domains -%}
    <AppDomain>{{ domain }}</AppDomain>
    {% endfor %}
  </AppDomains>
  
  <Hosts>
    <Host Name="Mailbox"/>
  </Hosts>
  
  <Requirements>
    <Sets DefaultMinVersion="1.1">
      <Set Name="Mailbox"/>
    </Sets>
  </Requirements>
  
  <FormSettings>
    <Form xsi:type="ItemRead">
      <DesktopSettings>
        <SourceLocation DefaultValue="{{ taskpane_url }}"/>
        <RequestedHeight>{{ requested_height }}</RequestedHeight>
      </DesktopSettings>
    </Form>
  </FormSettings>
  
  <Permissions>{{ permissions }}</Permissions>
  
  <Rule xsi:type="RuleCollection" Mode="Or">
    <Rule xsi:type="ItemIs" ItemType="Message" FormType="Read"/>
  </Rule>
  
  <DisableEntityHighlighting>false</DisableEntityHighlighting>
  
  <VersionOverrides xmlns="http://schemas.microsoft.com/office/mailappversionoverrides" xsi:type="VersionOverridesV1_0">
    <VersionOverrides xmlns="http://schemas.microsoft.com/office/mailappversionoverrides/1.1" xsi:type="VersionOverridesV1_1">
      <Requirements>
        <bt:Sets DefaultMinVersion="1.3">
          <bt:Set Name="Mailbox"/>
        </bt:Sets>
      </Requirements>
      
      <Hosts>
        <Host xsi:type="MailHost">
          <DesktopFormFactor>
            <FunctionFile resid="Commands.Url"/>
            
            <ExtensionPoint xsi:type="MessageReadCommandSurface">
              <OfficeTab id="TabDefault">
                <Group id="msgReadGroup">
                  <Label resid="GroupLabel"/>
                  <Control xsi:type="Button" id="msgReadOpenButton">
                    <Label resid="TaskpaneButton.Label"/>
                    <Supertip>
                      <Title resid="TaskpaneButton.Label"/>
                      <Description resid="TaskpaneButton.Tooltip"/>
                    </Supertip>
                    <Icon>
                      <bt:Image size="16" resid="Icon.16x16"/>
                      <bt:Image size="32" resid="Icon.32x32"/>
                      <bt:Image size="80" resid="Icon.80x80"/>
                    </Icon>
                    <Action xsi:type="ShowTaskpane">
                      <SourceLocation resid="Taskpane.Url"/>
                    </Action>
                  </Control>
                </Group>
              </OfficeTab>
            </ExtensionPoint>
          </DesktopFormFactor>
        </Host>
      </Hosts>
      
      <Resources>
        <bt:Images>
          <bt:Image id="Icon.16x16" DefaultValue="{{ icon_16 }}"/>
          <bt:Image id="Icon.32x32" DefaultValue="{{ icon_32 }}"/>
          <bt:Image id="Icon.64x64" DefaultValue="{{ icon_64 }}"/>
          <bt:Image id="Icon.80x80" DefaultValue="{{ icon_80 }}"/>
          <bt:Image id="Icon.128x128" DefaultValue="{{ icon_128 }}"/>
        </bt:Images>
        
        <bt:Urls>
          <bt:Url id="Commands.Url" DefaultValue="{{ commands_url }}"/>
          <bt:Url id="Taskpane.Url" DefaultValue="{{ taskpane_url }}"/>
        </bt:Urls>
        
        <bt:ShortStrings>
          <bt:String id="GroupLabel" DefaultValue="The Well"/>
          <bt:String id="TaskpaneButton.Label" DefaultValue="Send to Zoho"/>
        </bt:ShortStrings>
        
        <bt:LongStrings>
          <bt:String id="TaskpaneButton.Tooltip" DefaultValue="Process this email and create candidate records in Zoho CRM"/>
        </bt:LongStrings>
      </Resources>
    </VersionOverrides>
  </VersionOverrides>
</OfficeApp>'''
        
        template_path = os.path.join(self.templates_dir, 'default.xml')
        if not os.path.exists(template_path):
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
            print(f"Created template: {template_path}")
    
    def render_manifest(self, config: ManifestConfig) -> str:
        """Render manifest XML from configuration."""
        template = self.env.get_template('default.xml')
        rendered = template.render(**config.to_dict())
        
        # Validate and format XML
        try:
            # Parse and validate XML
            root = ET.fromstring(rendered)
            
            # Pretty print with minidom
            rough_string = ET.tostring(root, encoding='unicode')
            reparsed = minidom.parseString(rough_string)
            
            # Return formatted XML without the XML declaration line
            pretty = reparsed.toprettyxml(indent="  ")
            lines = pretty.split('\n')[1:]  # Remove XML declaration
            return '\n'.join(line for line in lines if line.strip())
            
        except ET.ParseError as e:
            print(f"Invalid XML generated: {e}")
            return rendered  # Return unformatted if parsing fails

def test_manifest_generation():
    """Test manifest generation."""
    print("=== Testing Manifest Template Generation ===")
    
    # Initialize template engine
    engine = ManifestTemplateEngine()
    engine.create_default_templates()
    
    # Create test configuration
    config = ManifestConfig(
        app_id="d2422753-f7f6-4a4a-9e1e-7512f37a50e5",
        version="1.3.0.2",
        provider_name="The Well Recruiting Solutions",
        app_name="The Well - Send to Zoho",
        description="Process recruitment emails and automatically create candidate records in Zoho CRM.",
        api_base_url="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io",
        app_domains=[
            "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io",
            "https://*.azurecontainerapps.io"
        ],
        icon_16="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/icon-16.png",
        icon_32="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/icon-32.png",
        icon_64="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/icon-64.png",
        icon_80="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/icon-80.png",
        icon_128="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/icon-128.png"
    )
    
    try:
        # Generate manifest
        manifest_xml = engine.render_manifest(config)
        
        print(f"✅ Manifest generated successfully! ({len(manifest_xml)} characters)")
        
        # Save test output
        with open('test_manifest_output.xml', 'w', encoding='utf-8') as f:
            f.write(manifest_xml)
        
        print("✅ Saved test manifest to test_manifest_output.xml")
        
        # Show first few lines
        lines = manifest_xml.split('\n')[:15]
        print("\nFirst 15 lines:")
        for i, line in enumerate(lines, 1):
            print(f"{i:2d}: {line}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_manifest_generation()
    print(f"\nResult: {'✅ SUCCESS' if success else '❌ FAILED'}")
    exit(0 if success else 1)