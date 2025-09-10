#!/usr/bin/env python3
"""
Test script for TalentWell Service implementation
"""
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

# Add app directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

async def test_admin_etl():
    """Test the Admin ETL module"""
    print("\n=== Testing Admin ETL Module ===")
    
    from app.admin.import_deals import DealImporter
    
    # Create sample CSV data
    sample_csv = """Deal_ID,Candidate_Name,Job_Title,Firm_Name,Location,Owner,Stage,Created_Date,Source,Source_Detail
    123,John Smith,Senior Engineer,Google,San Francisco CA,Steve Perry,Interview Complete,2025-08-15,Referral,Jane Doe
    456,Sarah Johnson,Product Manager,Amazon,Seattle WA,Steve Perry,Offer Extended,2025-08-20,Website Inbound,
    789,Mike Chen,Data Scientist,Microsoft,Redmond WA,Other Owner,Interview Complete,2025-08-18,Email Inbound,
    """
    
    importer = DealImporter()
    
    # Test loading and filtering
    deals = importer.load_deals_csv(sample_csv)
    print(f"Loaded {len(deals)} deals")
    
    filtered = importer.filter_by_owner(deals, "Steve Perry")
    print(f"Filtered to {len(filtered)} deals for Steve Perry")
    
    # Test policy generation
    policies = importer.generate_policy_seeds(filtered)
    print(f"Generated policies:")
    print(f"  - Employers: {len(policies['employers'])}")
    print(f"  - Cities: {len(policies['city_context'])}")
    print(f"  - Subjects: {len(policies['subjects'])}")
    print(f"  - Selectors: {len(policies['selector_priors'])}")
    
    return True


async def test_policy_loader():
    """Test the Policy Loader"""
    print("\n=== Testing Policy Loader ===")
    
    from app.policy.loader import PolicyLoader
    
    # Create mock Redis client for testing
    class MockRedis:
        def __init__(self):
            self.data = {}
        
        async def set(self, key, value, ex=None):
            self.data[key] = value
            return True
        
        async def get(self, key):
            return self.data.get(key)
    
    mock_redis = MockRedis()
    loader = PolicyLoader(mock_redis)
    
    # Test loading policies
    seed_dir = Path("app/policy/seed")
    if seed_dir.exists():
        await loader.load_all_policies()
        print(f"Loaded policies into mock Redis:")
        print(f"  - Total keys: {len(mock_redis.data)}")
        
        # Check a few keys
        test_keys = [
            "policy:employers:google",
            "geo:metro:san_francisco_ca",
            "c3:tau:talentwell_digest"
        ]
        
        for key in test_keys:
            value = await mock_redis.get(key)
            print(f"  - {key}: {value.decode() if value else 'Not found'}")
    
    return True


async def test_evidence_extraction():
    """Test Evidence Extraction"""
    print("\n=== Testing Evidence Extraction ===")
    
    from app.extract.evidence import EvidenceExtractor
    
    extractor = EvidenceExtractor()
    
    # Create sample deal with transcript
    deal = {
        "id": "123",
        "Candidate_Name": "John Smith",
        "Job_Title": "Senior Engineer",
        "transcript": "John has 10 years of experience in Python and led a team of 5 engineers at Google.",
        "Skills": "Python, Leadership, Cloud Architecture"
    }
    
    enhanced_data = {
        "technical_skills": ["Python", "Cloud", "Kubernetes"],
        "years_experience": 10,
        "leadership": True
    }
    
    # Extract bullets
    bullets = await extractor.extract_bullets(deal, enhanced_data)
    
    print(f"Extracted {len(bullets)} bullets:")
    for i, bullet in enumerate(bullets[:3], 1):
        print(f"  {i}. {bullet.text}")
        print(f"     - Confidence: {bullet.confidence:.2f}")
        if bullet.source_snippet:
            print(f"     - Evidence: '{bullet.source_snippet[:50]}...'")
    
    return True


async def test_ast_compiler():
    """Test AST Template Compiler"""
    print("\n=== Testing AST Compiler ===")
    
    from app.templates.ast import ASTCompiler
    
    compiler = ASTCompiler()
    
    # Test template with placeholders
    template = """
    <html>
    <head><title data-ast="subject">Test Subject</title></head>
    <body>
        <div data-ast="intro_block">Default intro</div>
        <div data-ast="cards">Default cards</div>
    </body>
    </html>
    """
    
    # Test rendering
    data = {
        "subject": "Weekly Digest - Test",
        "intro_block": "Welcome to this week's digest!",
        "cards": "<div>Card 1</div><div>Card 2</div>"
    }
    
    rendered = compiler.render(template, data)
    
    # Verify content was replaced
    assert "Weekly Digest - Test" in rendered
    assert "Welcome to this week's digest!" in rendered
    assert "Card 1" in rendered
    
    print("AST compilation successful")
    print(f"  - Template nodes: {len(compiler.allowed_nodes)}")
    print(f"  - Rendered length: {len(rendered)} chars")
    
    return True


async def test_bandit():
    """Test Thompson Sampling Bandit"""
    print("\n=== Testing Subject Bandit ===")
    
    from app.bandits.subject_bandit import SubjectLineBandit as SubjectBandit
    
    # Create mock Redis
    class MockRedis:
        def __init__(self):
            self.data = {}
        
        async def get(self, key):
            if "subjects.json" in key:
                # Return sample subjects
                return json.dumps([
                    {"variant_id": "control", "text": "Weekly Digest", "alpha": 10, "beta": 10},
                    {"variant_id": "test_a", "text": "Top Candidates", "alpha": 8, "beta": 12}
                ]).encode()
            return self.data.get(key)
        
        async def set(self, key, value, ex=None):
            self.data[key] = value
            return True
        
        async def hincrby(self, key, field, amount):
            if key not in self.data:
                self.data[key] = {}
            if field not in self.data[key]:
                self.data[key][field] = 0
            self.data[key][field] += amount
            return self.data[key][field]
    
    mock_redis = MockRedis()
    bandit = SubjectBandit(mock_redis)
    await bandit.initialize()
    
    # Test selection
    selected = await bandit.select_variant("steve_perry")
    print(f"Selected variant: {selected['variant_id']}")
    print(f"  - Text: {selected['text']}")
    print(f"  - Probability: {selected['probability']:.3f}")
    
    # Test update
    await bandit.update_variant("steve_perry", selected['variant_id'], opened=True, clicked=True)
    print("Updated variant with positive feedback")
    
    return True


async def test_curator_integration():
    """Test TalentWell Curator Integration"""
    print("\n=== Testing TalentWell Curator ===")
    
    from app.jobs.talentwell_curator import TalentWellCurator, DigestCard
    from app.extract.evidence import BulletPoint, EvidenceType
    
    curator = TalentWellCurator()
    
    # Create sample card
    card = DigestCard(
        deal_id="123",
        candidate_name="John Smith",
        job_title="Senior Engineer",
        company="Google",
        location="San Francisco, CA",
        bullets=[
            BulletPoint(
                text="10+ years Python experience",
                evidence_type=EvidenceType.TRANSCRIPT,
                confidence=0.9,
                source_snippet="10 years of experience in Python"
            ),
            BulletPoint(
                text="Led team of 5 engineers",
                evidence_type=EvidenceType.CRM_FIELD,
                confidence=0.85,
                crm_field="Leadership_Experience"
            )
        ],
        metro_area="San Francisco Bay Area",
        firm_type="tech",
        evidence_score=0.875
    )
    
    # Test card formatting
    html = curator._format_card_html(card)
    assert "John Smith" in html
    assert "Senior Engineer" in html
    assert "10+ years Python" in html
    
    print("Curator card generation successful")
    print(f"  - Card HTML length: {len(html)} chars")
    print(f"  - Evidence score: {card.evidence_score:.3f}")
    
    return True


async def main():
    """Run all tests"""
    print("=" * 60)
    print("TalentWell Service Implementation Tests")
    print("=" * 60)
    
    tests = [
        ("Admin ETL", test_admin_etl),
        ("Policy Loader", test_policy_loader),
        ("Evidence Extraction", test_evidence_extraction),
        ("AST Compiler", test_ast_compiler),
        ("Thompson Sampling", test_bandit),
        ("Curator Integration", test_curator_integration)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, "✓ PASSED" if result else "✗ FAILED"))
        except Exception as e:
            print(f"\n❌ Error in {name}: {e}")
            results.append((name, f"✗ ERROR: {str(e)[:50]}"))
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for name, status in results:
        print(f"{name:.<30} {status}")
    
    passed = sum(1 for _, s in results if "PASSED" in s)
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All tests passed! TalentWell Service is ready.")
    else:
        print("\n⚠️ Some tests failed. Please review the errors above.")


if __name__ == "__main__":
    asyncio.run(main())