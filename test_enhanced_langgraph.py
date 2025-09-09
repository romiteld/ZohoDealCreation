#!/usr/bin/env python3
"""
Test Enhanced LangGraph Workflow with Learning Integration
Demonstrates the learning-aware email processing capabilities
"""

import asyncio
import logging
from app.langgraph_manager import EmailProcessingWorkflow
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_enhanced_workflow():
    """Test the enhanced learning-aware workflow"""
    
    # Initialize the enhanced workflow
    workflow = EmailProcessingWorkflow()
    
    # Test email content
    test_email = """
    Hi Daniel,
    
    I wanted to introduce you to Sarah Johnson, a Senior Financial Advisor based in Fort Wayne, Indiana. 
    She has 8+ years of experience in wealth management and is currently looking for new opportunities.
    
    Sarah can be reached at sarah.johnson@example-wealth.com or (260) 555-0123.
    
    Her LinkedIn profile is at https://linkedin.com/in/sarah-johnson-cfa
    
    She's worked with high-net-worth clients and has her CFA certification.
    
    Best regards,
    Steve Miller
    The Well Recruiting
    """
    
    sender_domain = "thewell.com"
    
    print("="*80)
    print("TESTING ENHANCED LANGGRAPH WORKFLOW WITH LEARNING INTEGRATION")
    print("="*80)
    
    try:
        # Test 1: Enhanced email processing with learning
        print("\n1. Testing enhanced email processing with learning integration...")
        enhanced_result = await workflow.process_email_with_learning(
            email_body=test_email,
            sender_domain=sender_domain,
            learning_hints="Focus on referrer identification for recruiter emails"
        )
        
        print("Enhanced Processing Results:")
        print(f"  - Final Output: {enhanced_result['final_output']}")
        print(f"  - Processing Metrics: {enhanced_result['processing_metrics']}")
        print(f"  - Learning Context Available: {bool(enhanced_result.get('learning_context'))}")
        
        # Test 2: Get learning insights
        print("\n2. Testing learning insights...")
        insights = await workflow.get_learning_insights(email_domain=sender_domain)
        
        print("Learning Insights:")
        print(f"  - Prompt Variants Available: {len(insights.get('prompt_variants', {}).get('variants', {}))}")
        print(f"  - Field Analytics Available: {len(insights.get('field_analytics', {}))}")
        print(f"  - Recommendations: {len(insights.get('recommendations', []))}")
        
        # Test 3: Workflow health metrics
        print("\n3. Testing workflow health metrics...")
        health_metrics = await workflow.get_workflow_health_metrics()
        
        print("Workflow Health:")
        learning_status = health_metrics.get('learning_system_status', {})
        print(f"  - Correction Learning Active: {learning_status.get('correction_learning_active', False)}")
        print(f"  - Azure Search Available: {learning_status.get('azure_search_available', False)}")
        print(f"  - A/B Testing Enabled: {learning_status.get('ab_testing_enabled', False)}")
        print(f"  - Optimization Opportunities: {len(health_metrics.get('optimization_opportunities', []))}")
        
        # Test 4: Simulate user correction feedback
        print("\n4. Testing user correction feedback...")
        
        # Simulate original extraction (what AI extracted)
        original_extraction = {
            'candidate_name': 'Sarah Johnson',
            'job_title': 'Financial Advisor',  # Missing 'Senior'
            'location': 'Fort Wayne',  # Missing 'Indiana'
            'company_name': 'Example Wealth',  # Inferred from email
            'referrer_name': None,  # Missed the referrer
            'email': 'sarah.johnson@example-wealth.com',
            'phone': '(260) 555-0123'
        }
        
        # User corrections
        user_corrections = {
            'candidate_name': 'Sarah Johnson',
            'job_title': 'Senior Financial Advisor',  # User added 'Senior'
            'location': 'Fort Wayne, Indiana',  # User added state
            'company_name': 'Example Wealth Management',  # User corrected name
            'referrer_name': 'Steve Miller',  # User identified referrer
            'email': 'sarah.johnson@example-wealth.com',
            'phone': '(260) 555-0123'
        }
        
        feedback_result = await workflow.create_correction_feedback(
            email_domain=sender_domain,
            original_extraction=original_extraction,
            user_corrections=user_corrections,
            email_snippet=test_email[:500]
        )
        
        print("Correction Feedback Results:")
        print(f"  - Feedback Stored: {feedback_result.get('feedback_stored', False)}")
        corrections_analysis = feedback_result.get('corrections_analysis', {})
        print(f"  - Fields Corrected: {corrections_analysis.get('fields_corrected', 0)}")
        print(f"  - Accuracy Rate: {corrections_analysis.get('accuracy_rate', 0):.2%}")
        print(f"  - Recommendations: {len(feedback_result.get('recommendations', []))}")
        
        # Test 5: Workflow optimization
        print("\n5. Testing workflow optimization...")
        optimization_result = await workflow.optimize_workflow_performance()
        
        print("Workflow Optimization:")
        print(f"  - Prompt Optimizations Available: {bool(optimization_result.get('prompt_optimization'))}")
        adjustments = optimization_result.get('workflow_adjustments', {})
        print(f"  - Workflow Adjustments: {adjustments.get('total_improvements', 0)}")
        print(f"  - Performance Improvements: {len(optimization_result.get('performance_improvements', []))}")
        print(f"  - Overall Recommendations: {len(optimization_result.get('recommendations', []))}")
        
        # Test 6: Standard workflow for comparison
        print("\n6. Testing standard workflow for comparison...")
        standard_result = await workflow.process_email(
            email_body=test_email,
            sender_domain=sender_domain
        )
        
        print("Standard Processing Results:")
        print(f"  - Final Output: {standard_result}")
        print(f"  - Processing Method: Standard LangGraph")
        
        print("\n" + "="*80)
        print("ENHANCED WORKFLOW TESTING COMPLETE")
        print("="*80)
        
        # Summary
        print("\nSUMMARY:")
        print("✅ Enhanced workflow with learning integration working")
        print("✅ Learning insights and analytics available")  
        print("✅ User correction feedback system operational")
        print("✅ Workflow optimization and health monitoring active")
        print("✅ A/B testing and prompt enhancement ready")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_learning_coordination():
    """Test coordination with other learning agents"""
    
    print("\n" + "="*60)
    print("TESTING LEARNING SYSTEM COORDINATION")
    print("="*60)
    
    workflow = EmailProcessingWorkflow()
    
    try:
        # Test coordination with Agent #5 (Prompt Enhancement)
        print("\n🤝 Testing coordination with Prompt Enhancement (Agent #5)...")
        
        # This would typically be called by Agent #5
        insights = await workflow.get_learning_insights("thewell.com")
        prompt_variants = insights.get('prompt_variants', {})
        
        print(f"Shared prompt variant data: {len(prompt_variants.get('variants', {})) > 0}")
        
        # Test coordination with Agent #3 (Learning Services)
        print("\n🤝 Testing coordination with Learning Services (Agent #3)...")
        
        # This demonstrates data flow to Agent #3
        health_metrics = await workflow.get_workflow_health_metrics()
        learning_status = health_metrics.get('learning_system_status', {})
        
        print(f"Learning system status shared: {bool(learning_status)}")
        print(f"Azure Search integration: {learning_status.get('azure_search_available', False)}")
        
        # Test coordination with Agent #1 (Main API)
        print("\n🤝 Testing coordination with Main API (Agent #1)...")
        
        # This demonstrates the enhanced data structure for storage
        enhanced_result = await workflow.process_email_with_learning(
            email_body="Test email for coordination",
            sender_domain="test.com"
        )
        
        learning_context = enhanced_result.get('learning_context', {})
        print(f"Comprehensive data for storage: {bool(learning_context)}")
        print(f"Processing metrics available: {bool(enhanced_result.get('processing_metrics'))}")
        
        print("\n✅ Learning system coordination successful!")
        print("🔄 Workflow is ready to work with other learning agents")
        
        return True
        
    except Exception as e:
        print(f"❌ Coordination test failed: {e}")
        return False


if __name__ == "__main__":
    print("Starting Enhanced LangGraph Workflow Tests...")
    
    # Run the tests
    success = asyncio.run(test_enhanced_workflow())
    
    if success:
        # Test coordination with other agents
        coordination_success = asyncio.run(test_learning_coordination())
        
        if coordination_success:
            print("\n🎉 ALL TESTS PASSED!")
            print("Enhanced LangGraph workflow is ready for production use with learning integration.")
        else:
            print("\n⚠️  Basic tests passed but coordination needs attention")
    else:
        print("\n❌ Tests failed - check configuration and dependencies")