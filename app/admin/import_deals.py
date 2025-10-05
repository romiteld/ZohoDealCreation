"""
Admin ETL module for importing and processing Zoho deal exports.
Filters data for Steve Perry and specified date range.
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


class DealImporter:
    """ETL pipeline for Zoho deal exports"""
    
    def __init__(self, data_dir: str = "data/exports"):
        self.data_dir = Path(data_dir)
        self.owner_filter = "Steve Perry"
        self.start_date = datetime(2025, 1, 1)
        self.end_date = datetime(2025, 9, 8)
        
    def parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats from CSV"""
        if not date_str:
            return None
        
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%m/%d/%Y %I:%M %p",
            "%d-%b-%Y",
            "%d-%b-%Y %H:%M"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def load_deals_csv(self, csv_content: str) -> List[Dict[str, Any]]:
        """Load deals from CSV string content"""
        import io
        deals = []
        
        reader = csv.DictReader(io.StringIO(csv_content))
        for row in reader:
            # Parse dates
            created_date = self.parse_date(row.get("Created_Date", ""))
            
            # Create deal record
            deal = {
                "id": row.get("Deal_ID", ""),
                "Candidate_Name": row.get("Candidate_Name", ""),
                "Job_Title": row.get("Job_Title", ""),
                "Firm_Name": row.get("Firm_Name", ""),
                "Location": row.get("Location", ""),
                "Owner": row.get("Owner", ""),
                "Stage": row.get("Stage", ""),
                "Created_Date": created_date,
                "Source": row.get("Source", ""),
                "Source_Detail": row.get("Source_Detail", "")
            }
            deals.append(deal)
        
        return deals
    
    def load_deals(self, filepath: str = None) -> List[Dict[str, Any]]:
        """Load and filter deals CSV"""
        if not filepath:
            filepath = self.data_dir / "Deals_2025_09_10.csv"
        
        deals = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Filter by owner
                    if row.get('Deal Owner') != self.owner_filter:
                        continue
                    
                    # Filter by date range
                    created_date = self.parse_date(row.get('Created Time', ''))
                    closing_date = self.parse_date(row.get('Closing Date', ''))
                    
                    if created_date:
                        if created_date < self.start_date or created_date > self.end_date:
                            if not closing_date or closing_date < self.start_date or closing_date > self.end_date:
                                continue
                    
                    deals.append({
                        'id': row.get('Deal Id'),
                        'name': row.get('Deal Name'),
                        'owner': row.get('Deal Owner'),
                        'company': row.get('Account Name', '').strip(),
                        'amount': row.get('Amount'),
                        'stage': row.get('Stage'),
                        'created_time': row.get('Created Time'),
                        'closing_date': row.get('Closing Date'),
                        'location': row.get('Location', ''),
                        'job_title': row.get('Job Title', ''),
                        'source': row.get('Lead Source', ''),
                        'referrer': row.get('Referrer Name', ''),
                        'description': row.get('Description', '')
                    })
        
        except FileNotFoundError:
            logger.warning(f"Deals file not found: {filepath}")
        except Exception as e:
            logger.error(f"Error loading deals: {e}")
        
        logger.info(f"Loaded {len(deals)} deals for {self.owner_filter}")
        return deals
    
    def load_stage_history(self, filepath: str = None) -> Dict[str, List[Dict]]:
        """Load deal stage history for edit frequency analysis"""
        if not filepath:
            filepath = self.data_dir / "Deals_Stage_History_2025_09_10.csv"
        
        history = defaultdict(list)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    deal_id = row.get('Deal Id')
                    if deal_id:
                        history[deal_id].append({
                            'stage': row.get('Stage'),
                            'changed_time': row.get('Changed Time'),
                            'duration': row.get('Duration'),
                            'changed_by': row.get('Changed By')
                        })
        
        except FileNotFoundError:
            logger.warning(f"Stage history file not found: {filepath}")
        except Exception as e:
            logger.error(f"Error loading stage history: {e}")
        
        return dict(history)
    
    def load_meetings(self, filepath: str = None) -> Dict[str, List[Dict]]:
        """Load meetings data for subject line analysis"""
        if not filepath:
            filepath = self.data_dir / "Meetings_2025_09_10 2.csv"
        
        meetings = defaultdict(list)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    deal_id = row.get('Deal Id') or row.get('Related To')
                    if deal_id:
                        meetings[deal_id].append({
                            'title': row.get('Title', ''),
                            'start_time': row.get('Start DateTime'),
                            'participant': row.get('Participants', ''),
                            'opened': row.get('Email Opened', 'No') == 'Yes',
                            'clicked': row.get('Link Clicked', 'No') == 'Yes'
                        })
        
        except FileNotFoundError:
            logger.warning(f"Meetings file not found: {filepath}")
        except Exception as e:
            logger.error(f"Error loading meetings: {e}")
        
        return dict(meetings)
    
    def load_notes(self, filepath: str = None) -> Dict[str, List[str]]:
        """Load deal notes for evidence extraction"""
        if not filepath:
            filepath = self.data_dir / "Notes_Deals_2025_09_10.csv"
        
        notes = defaultdict(list)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    deal_id = row.get('Deal Id') or row.get('Parent Id')
                    if deal_id and row.get('Note Content'):
                        notes[deal_id].append(row.get('Note Content'))
        
        except FileNotFoundError:
            logger.warning(f"Notes file not found: {filepath}")
        except Exception as e:
            logger.error(f"Error loading notes: {e}")
        
        return dict(notes)
    
    def classify_company(self, company_name: str) -> str:
        """Classify company as National or Independent firm"""
        if not company_name:
            return "Independent firm"
        
        # National firm indicators
        national_indicators = [
            'LPL', 'Raymond James', 'Ameriprise', 'Edward Jones',
            'Wells Fargo', 'Morgan Stanley', 'Merrill Lynch',
            'UBS', 'Charles Schwab', 'Fidelity', 'Vanguard',
            'Northwestern Mutual', 'MassMutual', 'Prudential'
        ]
        
        company_lower = company_name.lower()
        for indicator in national_indicators:
            if indicator.lower() in company_lower:
                return "National firm"
        
        return "Independent firm"
    
    def extract_metro(self, location: str) -> str:
        """Extract metro area from location string"""
        if not location:
            return "Unknown"
        
        # Top 50 metro mappings
        metro_mappings = {
            'New York': 'NYC Metro',
            'Manhattan': 'NYC Metro',
            'Brooklyn': 'NYC Metro',
            'Los Angeles': 'LA Metro',
            'Beverly Hills': 'LA Metro',
            'Chicago': 'Chicago Metro',
            'Houston': 'Houston Metro',
            'Phoenix': 'Phoenix Metro',
            'Philadelphia': 'Philadelphia Metro',
            'San Antonio': 'San Antonio Metro',
            'San Diego': 'San Diego Metro',
            'Dallas': 'DFW Metro',
            'Fort Worth': 'DFW Metro',
            'San Jose': 'Bay Area',
            'San Francisco': 'Bay Area',
            'Oakland': 'Bay Area',
            'Austin': 'Austin Metro',
            'Jacksonville': 'Jacksonville Metro',
            'Columbus': 'Columbus Metro',
            'Charlotte': 'Charlotte Metro',
            'Indianapolis': 'Indianapolis Metro',
            'Seattle': 'Seattle Metro',
            'Denver': 'Denver Metro',
            'Boston': 'Boston Metro',
            'Cambridge': 'Boston Metro',
            'Washington': 'DC Metro',
            'Arlington': 'DC Metro',
            'Nashville': 'Nashville Metro',
            'Detroit': 'Detroit Metro',
            'Memphis': 'Memphis Metro',
            'Portland': 'Portland Metro',
            'Las Vegas': 'Las Vegas Metro',
            'Baltimore': 'Baltimore Metro',
            'Milwaukee': 'Milwaukee Metro',
            'Atlanta': 'Atlanta Metro',
            'Miami': 'Miami Metro',
            'Fort Lauderdale': 'Miami Metro'
        }
        
        location_parts = location.split(',')
        if location_parts:
            city = location_parts[0].strip()
            for key, metro in metro_mappings.items():
                if key.lower() in city.lower():
                    return metro
        
        return location.split(',')[0].strip() if location else "Unknown"
    
    def calculate_selector_priors(self, deals: List[Dict], history: Dict) -> Dict:
        """Calculate BDAT priors based on edit frequency"""
        selector_stats = {
            'mobility': {'edits': 0, 'total': 0},
            'compensation': {'edits': 0, 'total': 0},
            'licenses': {'edits': 0, 'total': 0},
            'skills': {'edits': 0, 'total': 0},
            'availability': {'edits': 0, 'total': 0}
        }
        
        for deal in deals:
            deal_id = deal['id']
            deal_history = history.get(deal_id, [])
            
            # Count edits per selector type
            for selector in selector_stats.keys():
                selector_stats[selector]['total'] += 1
                
                # Estimate edits based on stage changes
                if selector in ['mobility', 'compensation']:
                    # These change more frequently
                    selector_stats[selector]['edits'] += min(len(deal_history), 3)
                else:
                    # These are more stable
                    selector_stats[selector]['edits'] += min(len(deal_history), 1)
        
        # Calculate BDAT parameters
        selector_priors = {}
        for selector, stats in selector_stats.items():
            if stats['total'] > 0:
                error_rate = stats['edits'] / (stats['total'] * 3)  # Normalize by expected changes
                
                # Higher error rate = looser tau_delta and shorter TTL
                if error_rate > 0.3:
                    selector_priors[selector] = {
                        'tau_delta': 0.02,  # Looser threshold
                        'bdat_alpha': 2,    # Shorter TTL
                        'bdat_beta': 8
                    }
                else:
                    selector_priors[selector] = {
                        'tau_delta': 0.005,  # Stricter threshold
                        'bdat_alpha': 5,     # Longer TTL
                        'bdat_beta': 5
                    }
        
        return selector_priors
    
    def generate_subject_priors(self, meetings: Dict) -> List[Dict]:
        """Generate subject line variants with priors from meeting data"""
        subjects = [
            {
                'id': 'v1',
                'text': '🎯 Weekly Talent Update - {date}',
                'alpha': 1,
                'beta': 1
            },
            {
                'id': 'v2',
                'text': 'Your Curated Candidates - {date}',
                'alpha': 1,
                'beta': 1
            },
            {
                'id': 'v3',
                'text': '📊 TalentWell Weekly Digest',
                'alpha': 1,
                'beta': 1
            },
            {
                'id': 'v4',
                'text': 'Steve - New Talent Matches Available',
                'alpha': 1,
                'beta': 1
            },
            {
                'id': 'v5',
                'text': 'Weekly Recruiting Pipeline Update',
                'alpha': 1,
                'beta': 1
            }
        ]
        
        # Analyze meeting titles for patterns
        title_keywords = defaultdict(int)
        opens = defaultdict(int)
        
        for deal_meetings in meetings.values():
            for meeting in deal_meetings:
                title = meeting.get('title', '').lower()
                opened = meeting.get('opened', False)
                
                # Count keyword occurrences
                if 'talent' in title:
                    title_keywords['talent'] += 1
                    if opened:
                        opens['talent'] += 1
                if 'candidate' in title:
                    title_keywords['candidate'] += 1
                    if opened:
                        opens['candidate'] += 1
                if 'weekly' in title:
                    title_keywords['weekly'] += 1
                    if opened:
                        opens['weekly'] += 1
        
        # Update priors based on historical performance
        for subject in subjects:
            text_lower = subject['text'].lower()
            
            # Boost priors for subjects with successful keywords
            if 'talent' in text_lower and opens.get('talent', 0) > 0:
                subject['alpha'] += opens['talent']
                subject['beta'] += max(1, title_keywords['talent'] - opens['talent'])
            
            if 'candidate' in text_lower and opens.get('candidate', 0) > 0:
                subject['alpha'] += opens['candidate']
                subject['beta'] += max(1, title_keywords['candidate'] - opens['candidate'])
            
            if 'weekly' in text_lower and opens.get('weekly', 0) > 0:
                subject['alpha'] += opens['weekly']
                subject['beta'] += max(1, title_keywords['weekly'] - opens['weekly'])
        
        return subjects
    
    def generate_policy_seeds(self, deals: List[Dict], history: Dict, 
                            meetings: Dict, notes: Dict) -> Dict[str, Any]:
        """Generate all policy seed files"""
        
        # 1. Employers classification
        employers = {}
        for deal in deals:
            company = deal['company']
            if company:
                employers[company] = self.classify_company(company)
        
        # 2. City context (metro mappings)
        city_context = {}
        for deal in deals:
            location = deal['location']
            if location:
                city = location.split(',')[0].strip()
                if city:
                    city_context[city] = self.extract_metro(location)
        
        # 3. Subject line priors
        subjects = self.generate_subject_priors(meetings)
        
        # 4. Selector priors
        selector_priors = self.calculate_selector_priors(deals, history)
        
        return {
            'employers': employers,
            'city_context': city_context,
            'subjects': subjects,
            'selector_priors': selector_priors
        }
    
    def save_seeds(self, seeds: Dict[str, Any], output_dir: str = "app/policy/seed"):
        """Save policy seeds to JSON files"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for name, data in seeds.items():
            filepath = output_path / f"{name}.json"
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {name}.json with {len(data)} entries")
    
    def run_import(self, data_dir: str = None) -> Dict[str, Any]:
        """Run complete ETL pipeline"""
        if data_dir:
            self.data_dir = Path(data_dir)
        
        # Load all data sources
        deals = self.load_deals()
        history = self.load_stage_history()
        meetings = self.load_meetings()
        notes = self.load_notes()
        
        # Generate policy seeds
        seeds = self.generate_policy_seeds(deals, history, meetings, notes)
        
        # Save seeds
        self.save_seeds(seeds)
        
        # Return summary
        return {
            'deals_processed': len(deals),
            'owner': self.owner_filter,
            'date_range': f"{self.start_date.date()} to {self.end_date.date()}",
            'seeds_generated': list(seeds.keys()),
            'employers_classified': len(seeds['employers']),
            'metros_mapped': len(seeds['city_context']),
            'subject_variants': len(seeds['subjects']),
            'selectors_configured': len(seeds['selector_priors'])
        }


# FastAPI route handler
async def import_deals_handler(data_dir: Optional[str] = None) -> Dict[str, Any]:
    """Handler for admin import endpoint"""
    try:
        importer = DealImporter(data_dir or "data/exports")
        result = importer.run_import()
        return {
            'status': 'success',
            'summary': result
        }
    except Exception as e:
        logger.error(f"Import failed: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }