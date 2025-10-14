#!/usr/bin/env python3
"""
Anonymizer Test Suite - Real Vault Candidate Validation

Tests anonymizer.py against REAL vault candidate data from PostgreSQL database.
Validates all anonymization rules and generates detailed before/after comparison report.

Usage:
    python test_anonymizer.py

Output:
    - Console: Real-time progress and summary
    - File: anonymization_test_report.txt (detailed before/after comparisons)
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.jobs.anonymizer import CandidateAnonymizer


class AnonymizerTestSuite:
    """Comprehensive test suite for candidate anonymizer."""

    def __init__(self, database_url: str):
        """Initialize test suite with database connection."""
        self.database_url = database_url
        self.anonymizer = CandidateAnonymizer()
        self.test_results = []

    async def run_tests(self, sample_size: int = 10) -> Dict[str, Any]:
        """
        Run complete test suite against real vault candidates.

        Args:
            sample_size: Number of candidates to test (default: 10)

        Returns:
            Dictionary with test results and metrics
        """
        print("🧪 Anonymizer Test Suite")
        print("=" * 80)
        print(f"Sample Size: {sample_size} candidates")
        print(f"Database: {self.database_url.split('@')[1].split('/')[0]}")  # Hide credentials
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}")
        print()

        # Load sample candidates from database
        print("📊 Loading sample candidates from vault_candidates table...")
        candidates = await self._load_sample_candidates(sample_size)
        print(f"✅ Loaded {len(candidates)} candidates\n")

        if not candidates:
            print("❌ No candidates found in database!")
            return {
                'success': False,
                'error': 'No candidates found in database',
                'tested': 0,
                'passed': 0,
                'failed': 0
            }

        # Test each candidate
        print("🔬 Testing anonymization on each candidate...")
        print("-" * 80)

        passed = 0
        failed = 0

        for idx, candidate in enumerate(candidates, 1):
            print(f"\nCandidate {idx}/{len(candidates)}: {candidate.get('twav_number', 'UNKNOWN')}")
            result = await self._test_candidate(candidate, idx)

            if result['passed']:
                passed += 1
                print("  ✅ ALL RULES APPLIED CORRECTLY")
            else:
                failed += 1
                print(f"  ❌ {len(result['failures'])} RULE(S) FAILED")

            self.test_results.append(result)

        # Generate report
        print("\n" + "=" * 80)
        print("📝 Generating detailed report...")
        report_path = self._generate_report()
        print(f"✅ Report saved to: {report_path}")

        # Calculate metrics
        total_rules = len(self.test_results) * 6  # 6 rules per candidate
        total_passed_rules = sum(6 - len(r['failures']) for r in self.test_results)
        confidentiality_score = (total_passed_rules / total_rules * 100) if total_rules > 0 else 0

        # Print summary
        print("\n" + "=" * 80)
        print("📊 Test Summary")
        print("-" * 80)
        print(f"Total Candidates: {len(candidates)}")
        print(f"Passed: {passed} ({passed/len(candidates)*100:.1f}%)")
        print(f"Failed: {failed} ({failed/len(candidates)*100:.1f}%)")
        print(f"Confidentiality Score: {confidentiality_score:.1f}%")
        print("=" * 80)

        return {
            'success': True,
            'total_candidates': len(candidates),
            'passed': passed,
            'failed': failed,
            'confidentiality_score': confidentiality_score,
            'report_path': report_path,
            'test_results': self.test_results
        }

    async def _load_sample_candidates(self, limit: int) -> List[Dict[str, Any]]:
        """Load sample candidates from database."""
        conn = await asyncpg.connect(self.database_url)

        try:
            # Query with diverse sample (different firms, locations, etc.)
            query = """
                SELECT
                    twav_number, candidate_name, title, city, state, current_location,
                    firm, years_experience, aum, production, licenses, professional_designations,
                    headline, interviewer_notes, top_performance, candidate_experience,
                    availability, compensation, zoom_meeting_url, created_at
                FROM vault_candidates
                ORDER BY RANDOM()
                LIMIT $1
            """

            rows = await conn.fetch(query, limit)
            return [dict(row) for row in rows]

        finally:
            await conn.close()

    async def _test_candidate(self, candidate: Dict[str, Any], idx: int) -> Dict[str, Any]:
        """Test anonymization rules on a single candidate."""
        # Store original values
        original = candidate.copy()

        # Apply anonymization
        anonymized = self.anonymizer.anonymize_candidate(candidate)

        # Check each rule
        failures = []

        # Rule 1: Firm names replaced with generic types
        if original.get('firm'):
            if self._has_specific_firm_name(anonymized.get('firm', '')):
                failures.append('firm_not_anonymized')

        # Rule 2: AUM/production rounded to ranges
        if original.get('aum'):
            if not self._is_range_format(anonymized.get('aum', '')):
                failures.append('aum_not_rounded')

        if original.get('production'):
            if not self._is_range_format(anonymized.get('production', '')):
                failures.append('production_not_rounded')

        # Rule 3: Locations normalized to major metros
        if original.get('city') and original.get('state'):
            orig_location = f"{original['city']}, {original['state']}"
            anon_location = f"{anonymized.get('city', '')}, {anonymized.get('state', '')}"
            if self._has_specific_address(anon_location):
                failures.append('location_not_normalized')

        # Rule 4: University names stripped
        if original.get('professional_designations'):
            if self._has_university_name(anonymized.get('professional_designations', '')):
                failures.append('university_not_stripped')

        # Rule 5: Achievements generalized (check notes/headline)
        if original.get('interviewer_notes'):
            if self._has_specific_firm_name(anonymized.get('interviewer_notes', '')):
                failures.append('notes_not_generalized')

        # Rule 6: Proprietary systems removed
        if original.get('headline'):
            if self._has_proprietary_system(anonymized.get('headline', '')):
                failures.append('proprietary_system_not_removed')

        return {
            'twav': original.get('twav_number', 'UNKNOWN'),
            'original': original,
            'anonymized': anonymized,
            'passed': len(failures) == 0,
            'failures': failures
        }

    def _has_specific_firm_name(self, text: str) -> bool:
        """Check if text contains specific firm names (not anonymized)."""
        if not text:
            return False

        specific_firms = [
            'merrill lynch', 'morgan stanley', 'wells fargo', 'ubs',
            'raymond james', 'edward jones', 'rbc', 'stifel',
            'jpmorgan', 'goldman sachs', 'citigroup', 'bank of america',
            'northwestern mutual', 'massmutual', 'new york life'
        ]

        text_lower = text.lower()
        return any(firm in text_lower for firm in specific_firms)

    def _is_range_format(self, text: str) -> bool:
        """Check if text is in range format (e.g., $1.5B-$2.0B range)."""
        if not text:
            return False

        # Pattern: "$XXX-$YYY range" or "not disclosed"
        range_pattern = r'\$[\d.]+(M|B)?-\$[\d.]+(M|B)?\s+range'
        disclosed_pattern = r'not disclosed'

        import re
        return bool(re.search(range_pattern, text, re.IGNORECASE)) or \
               bool(re.search(disclosed_pattern, text, re.IGNORECASE))

    def _has_specific_address(self, location: str) -> bool:
        """Check if location has specific street address or zip code."""
        if not location:
            return False

        import re
        # Check for zip code
        if re.search(r'\d{5}(-\d{4})?', location):
            return True

        # Check if it's NOT a normalized location (metro areas or 'area' suffix are OK)
        normalized_keywords = ['metro', 'bay area', 'fort worth', 'washington dc', ' area']
        if any(keyword in location.lower() for keyword in normalized_keywords):
            return False

        # If no normalization markers found, it's probably too specific
        return True

    def _has_university_name(self, text: str) -> bool:
        """Check if text contains university names."""
        if not text:
            return False

        university_keywords = ['university', 'college', 'institute', 'school of']
        text_lower = text.lower()

        return any(keyword in text_lower for keyword in university_keywords)

    def _has_proprietary_system(self, text: str) -> bool:
        """Check if text contains proprietary system names."""
        if not text:
            return False

        # Common proprietary system patterns
        import re
        patterns = [
            r'\b[A-Z][a-zA-Z]*(?:Pro|Connect|View|Portal|System|Platform|Suite)\b',
        ]

        for pattern in patterns:
            if re.search(pattern, text):
                return True

        return False

    def _generate_report(self) -> str:
        """Generate detailed before/after comparison report."""
        report_path = project_root / 'anonymization_test_report.txt'

        with open(report_path, 'w', encoding='utf-8') as f:
            # Header
            f.write("🧪 ANONYMIZATION TEST RESULTS\n")
            f.write("=" * 80 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}\n")
            f.write(f"Total Candidates Tested: {len(self.test_results)}\n")
            f.write("=" * 80 + "\n\n")

            # Individual candidate results
            for result in self.test_results:
                self._write_candidate_result(f, result)

            # Overall summary
            passed = sum(1 for r in self.test_results if r['passed'])
            failed = len(self.test_results) - passed
            total_rules = len(self.test_results) * 6
            total_passed_rules = sum(6 - len(r['failures']) for r in self.test_results)
            confidentiality_score = (total_passed_rules / total_rules * 100) if total_rules > 0 else 0

            f.write("\n" + "=" * 80 + "\n")
            f.write("📊 OVERALL SUMMARY\n")
            f.write("=" * 80 + "\n")
            f.write(f"Total Candidates: {len(self.test_results)}\n")
            f.write(f"Passed: {passed}/{len(self.test_results)} ({passed/len(self.test_results)*100:.1f}%)\n")
            f.write(f"Failed: {failed}/{len(self.test_results)} ({failed/len(self.test_results)*100:.1f}%)\n")
            f.write(f"Confidentiality Score: {confidentiality_score:.1f}%\n")
            f.write("=" * 80 + "\n")

        return str(report_path)

    def _write_candidate_result(self, f, result: Dict[str, Any]):
        """Write individual candidate result to report."""
        twav = result['twav']
        original = result['original']
        anonymized = result['anonymized']
        passed = result['passed']
        failures = result['failures']

        f.write(f"Candidate: {twav}\n")
        f.write("-" * 80 + "\n")

        # Firm
        f.write("FIRM:\n")
        f.write(f"  BEFORE: {original.get('firm', 'N/A')}\n")
        f.write(f"  AFTER:  {anonymized.get('firm', 'N/A')}\n")
        f.write(f"  Status: {'✅' if 'firm_not_anonymized' not in failures else '❌'}\n\n")

        # AUM
        f.write("AUM:\n")
        f.write(f"  BEFORE: {original.get('aum', 'N/A')}\n")
        f.write(f"  AFTER:  {anonymized.get('aum', 'N/A')}\n")
        f.write(f"  Status: {'✅' if 'aum_not_rounded' not in failures else '❌'}\n\n")

        # Production
        f.write("PRODUCTION:\n")
        f.write(f"  BEFORE: {original.get('production', 'N/A')}\n")
        f.write(f"  AFTER:  {anonymized.get('production', 'N/A')}\n")
        f.write(f"  Status: {'✅' if 'production_not_rounded' not in failures else '❌'}\n\n")

        # Location
        orig_loc = f"{original.get('city', '')}, {original.get('state', '')}"
        anon_loc = f"{anonymized.get('city', '')}, {anonymized.get('state', '')}"
        f.write("LOCATION:\n")
        f.write(f"  BEFORE: {orig_loc}\n")
        f.write(f"  AFTER:  {anon_loc}\n")
        f.write(f"  Status: {'✅' if 'location_not_normalized' not in failures else '❌'}\n\n")

        # Education
        f.write("EDUCATION:\n")
        f.write(f"  BEFORE: {original.get('professional_designations', 'N/A')[:100]}\n")
        f.write(f"  AFTER:  {anonymized.get('professional_designations', 'N/A')[:100]}\n")
        f.write(f"  Status: {'✅' if 'university_not_stripped' not in failures else '❌'}\n\n")

        # Notes/Achievements
        f.write("NOTES/ACHIEVEMENTS:\n")
        f.write(f"  BEFORE: {original.get('interviewer_notes', 'N/A')[:100]}...\n")
        f.write(f"  AFTER:  {anonymized.get('interviewer_notes', 'N/A')[:100]}...\n")
        f.write(f"  Status: {'✅' if 'notes_not_generalized' not in failures else '❌'}\n\n")

        # Overall
        if passed:
            f.write("✅ ALL RULES APPLIED CORRECTLY\n")
        else:
            f.write(f"❌ {len(failures)} RULE(S) FAILED: {', '.join(failures)}\n")

        f.write("\n" + "=" * 80 + "\n\n")


async def main():
    """Main entry point."""
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("❌ ERROR: DATABASE_URL environment variable not set!")
        print("Please ensure .env.local is loaded or set DATABASE_URL manually.")
        sys.exit(1)

    # Run tests
    test_suite = AnonymizerTestSuite(database_url)
    results = await test_suite.run_tests(sample_size=10)

    # Exit with appropriate code
    if results['success'] and results['failed'] == 0:
        print("\n✅ All tests passed!")
        sys.exit(0)
    elif results['success']:
        print(f"\n⚠️  {results['failed']} test(s) failed. See report for details.")
        sys.exit(1)
    else:
        print("\n❌ Test suite failed to run!")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
