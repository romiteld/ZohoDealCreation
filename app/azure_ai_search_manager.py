"""
Azure AI Search Manager for Semantic Email Pattern Learning
Provides semantic search capabilities for learning from user corrections
"""

import os
import json
import logging
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import numpy as np

# Azure AI Search imports
try:
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchIndex,
        SimpleField,
        SearchableField,
        SearchField,
        SearchFieldDataType,
        VectorSearch,
        VectorSearchProfile,
        HnswAlgorithmConfiguration,
        SemanticConfiguration,
        SemanticSearch,
        SemanticPrioritizedFields,
        SemanticField,
        ScoringProfile,
        TextWeights
    )
    from azure.search.documents.models import VectorizedQuery
    from azure.core.credentials import AzureKeyCredential
    AZURE_SEARCH_AVAILABLE = True
except ImportError:
    AZURE_SEARCH_AVAILABLE = False
    SearchClient = None
    SearchIndexClient = None

# OpenAI for embeddings
try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AsyncOpenAI = None

logger = logging.getLogger(__name__)


class EmailPattern(BaseModel):
    """Represents a learned email extraction pattern"""
    id: str = Field(description="Unique pattern ID")
    pattern_type: str = Field(description="Type of pattern: extraction, correction, template")
    email_domain: str = Field(description="Source email domain")
    company_name: Optional[str] = Field(None, description="Company name if identified")
    
    # Pattern content
    email_snippet: str = Field(description="Sample email text that triggered this pattern")
    extraction_fields: Dict[str, Any] = Field(description="Fields extracted from this pattern")
    corrections: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="User corrections applied")
    
    # Semantic search fields
    embedding: Optional[List[float]] = Field(None, description="Vector embedding for semantic search")
    semantic_text: str = Field(description="Combined text for semantic analysis")
    
    # Metrics
    confidence_score: float = Field(default=0.5, description="Confidence in this pattern")
    usage_count: int = Field(default=1, description="Times this pattern has been applied")
    success_rate: float = Field(default=0.0, description="Success rate when applied")
    last_used: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Learning metadata
    field_accuracy: Dict[str, float] = Field(default_factory=dict, description="Per-field accuracy scores")
    common_errors: List[str] = Field(default_factory=list, description="Common extraction errors")
    improvement_suggestions: List[str] = Field(default_factory=list, description="AI-generated improvement hints")


class CompanyTemplate(BaseModel):
    """Company-specific extraction template learned over time"""
    id: str = Field(description="Unique template ID")
    company_domain: str = Field(description="Company email domain")
    company_name: str = Field(description="Company name")
    
    # Template patterns
    common_fields: Dict[str, List[str]] = Field(description="Common values per field")
    field_patterns: Dict[str, str] = Field(description="Regex or pattern per field")
    extraction_rules: Dict[str, Any] = Field(description="Custom extraction rules")
    
    # Semantic profile
    semantic_profile: Optional[List[float]] = Field(None, description="Company semantic profile embedding")
    keywords: List[str] = Field(default_factory=list, description="Key terms for this company")
    
    # Performance
    total_emails: int = Field(default=0, description="Total emails processed")
    accuracy_score: float = Field(default=0.0, description="Overall accuracy")
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class AzureAISearchManager:
    """Manages semantic search and pattern learning using Azure AI Search"""
    
    def __init__(
        self,
        search_endpoint: Optional[str] = None,
        search_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        index_name: str = "well-intake-patterns",
        template_index_name: str = "company-templates"
    ):
        """Initialize Azure AI Search manager"""
        self.search_endpoint = search_endpoint or os.getenv("AZURE_SEARCH_ENDPOINT")
        self.search_key = search_key or os.getenv("AZURE_SEARCH_KEY")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        
        self.index_name = index_name
        self.template_index_name = template_index_name
        
        # Initialize clients
        self.search_client = None
        self.template_search_client = None
        self.index_client = None
        self.openai_client = None
        
        if AZURE_SEARCH_AVAILABLE and self.search_endpoint and self.search_key:
            try:
                credential = AzureKeyCredential(self.search_key)
                self.index_client = SearchIndexClient(
                    endpoint=self.search_endpoint,
                    credential=credential
                )
                
                # Initialize or create indexes
                self._ensure_indexes()
                
                # Create search clients
                self.search_client = SearchClient(
                    endpoint=self.search_endpoint,
                    index_name=self.index_name,
                    credential=credential
                )
                
                self.template_search_client = SearchClient(
                    endpoint=self.search_endpoint,
                    index_name=self.template_index_name,
                    credential=credential
                )
                
                logger.info("Azure AI Search initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Azure AI Search: {e}")
                self.search_client = None
        
        if OPENAI_AVAILABLE and self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
    
    def _ensure_indexes(self):
        """Ensure search indexes exist with proper schema"""
        if not self.index_client:
            return
        
        try:
            # Check if pattern index exists
            existing_indexes = [idx.name for idx in self.index_client.list_indexes()]
            
            if self.index_name not in existing_indexes:
                self._create_pattern_index()
            
            if self.template_index_name not in existing_indexes:
                self._create_template_index()
                
        except Exception as e:
            logger.error(f"Failed to ensure indexes: {e}")
    
    def _create_pattern_index(self):
        """Create the email pattern index with semantic search capabilities"""
        try:
            # Define fields
            fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SearchableField(name="pattern_type", type=SearchFieldDataType.String, 
                              filterable=True, facetable=True),
                SearchableField(name="email_domain", type=SearchFieldDataType.String, 
                              filterable=True, facetable=True),
                SearchableField(name="company_name", type=SearchFieldDataType.String, 
                              filterable=True, facetable=True),
                SearchableField(name="email_snippet", type=SearchFieldDataType.String, 
                              analyzer_name="en.microsoft"),
                SearchableField(name="semantic_text", type=SearchFieldDataType.String, 
                              analyzer_name="en.microsoft"),
                SimpleField(name="extraction_fields", type=SearchFieldDataType.String),
                SimpleField(name="corrections", type=SearchFieldDataType.String),
                SearchField(name="embedding", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                          searchable=True, vector_search_dimensions=1536, 
                          vector_search_profile_name="hnsw-profile"),
                SimpleField(name="confidence_score", type=SearchFieldDataType.Double, 
                          sortable=True, filterable=True),
                SimpleField(name="usage_count", type=SearchFieldDataType.Int32, 
                          sortable=True, filterable=True),
                SimpleField(name="success_rate", type=SearchFieldDataType.Double, 
                          sortable=True, filterable=True),
                SimpleField(name="last_used", type=SearchFieldDataType.DateTimeOffset, 
                          sortable=True, filterable=True),
                SimpleField(name="created_at", type=SearchFieldDataType.DateTimeOffset, 
                          sortable=True, filterable=True),
                SimpleField(name="field_accuracy", type=SearchFieldDataType.String),
                SearchableField(name="common_errors", type=SearchFieldDataType.Collection(SearchFieldDataType.String)),
                SearchableField(name="improvement_suggestions", 
                              type=SearchFieldDataType.Collection(SearchFieldDataType.String))
            ]
            
            # Configure vector search
            vector_search = VectorSearch(
                profiles=[
                    VectorSearchProfile(
                        name="hnsw-profile",
                        algorithm_configuration_name="hnsw-config"
                    )
                ],
                algorithms=[
                    HnswAlgorithmConfiguration(
                        name="hnsw-config",
                        parameters={
                            "m": 4,
                            "efConstruction": 400,
                            "efSearch": 500,
                            "metric": "cosine"
                        }
                    )
                ]
            )
            
            # Configure semantic search
            semantic_config = SemanticConfiguration(
                name="semantic-config",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="email_domain"),
                    content_fields=[
                        SemanticField(field_name="semantic_text"),
                        SemanticField(field_name="email_snippet")
                    ],
                    keywords_fields=[
                        SemanticField(field_name="common_errors"),
                        SemanticField(field_name="improvement_suggestions")
                    ]
                )
            )
            
            semantic_search = SemanticSearch(configurations=[semantic_config])
            
            # Create scoring profile for relevance tuning
            scoring_profile = ScoringProfile(
                name="pattern-scoring",
                text_weights=TextWeights(
                    weights={
                        "email_domain": 2.0,
                        "company_name": 1.5,
                        "semantic_text": 1.0
                    }
                ),
                function_aggregation="sum"
            )
            
            # Create index
            index = SearchIndex(
                name=self.index_name,
                fields=fields,
                vector_search=vector_search,
                semantic_search=semantic_search,
                scoring_profiles=[scoring_profile],
                default_scoring_profile="pattern-scoring"
            )
            
            self.index_client.create_index(index)
            logger.info(f"Created pattern index: {self.index_name}")
            
        except Exception as e:
            logger.error(f"Failed to create pattern index: {e}")
    
    def _create_template_index(self):
        """Create the company template index"""
        try:
            fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SearchableField(name="company_domain", type=SearchFieldDataType.String, 
                              filterable=True, facetable=True),
                SearchableField(name="company_name", type=SearchFieldDataType.String, 
                              filterable=True, facetable=True),
                SimpleField(name="common_fields", type=SearchFieldDataType.String),
                SimpleField(name="field_patterns", type=SearchFieldDataType.String),
                SimpleField(name="extraction_rules", type=SearchFieldDataType.String),
                SearchField(name="semantic_profile", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                          searchable=True, vector_search_dimensions=1536,
                          vector_search_profile_name="template-hnsw"),
                SearchableField(name="keywords", type=SearchFieldDataType.Collection(SearchFieldDataType.String)),
                SimpleField(name="total_emails", type=SearchFieldDataType.Int32, 
                          sortable=True, filterable=True),
                SimpleField(name="accuracy_score", type=SearchFieldDataType.Double, 
                          sortable=True, filterable=True),
                SimpleField(name="last_updated", type=SearchFieldDataType.DateTimeOffset, 
                          sortable=True, filterable=True)
            ]
            
            # Vector search config for templates
            vector_search = VectorSearch(
                profiles=[
                    VectorSearchProfile(
                        name="template-hnsw",
                        algorithm_configuration_name="template-hnsw-config"
                    )
                ],
                algorithms=[
                    HnswAlgorithmConfiguration(
                        name="template-hnsw-config",
                        parameters={
                            "m": 4,
                            "efConstruction": 400,
                            "efSearch": 500,
                            "metric": "cosine"
                        }
                    )
                ]
            )
            
            # Create index
            index = SearchIndex(
                name=self.template_index_name,
                fields=fields,
                vector_search=vector_search
            )
            
            self.index_client.create_index(index)
            logger.info(f"Created template index: {self.template_index_name}")
            
        except Exception as e:
            logger.error(f"Failed to create template index: {e}")
    
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using OpenAI"""
        if not self.openai_client:
            return None
        
        try:
            response = await self.openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None
    
    async def index_email_pattern(
        self,
        email_domain: str,
        email_content: str,
        extraction_result: Dict[str, Any],
        corrections: Optional[Dict[str, Any]] = None,
        confidence_score: float = 0.5
    ) -> bool:
        """Index an email pattern for future learning"""
        if not self.search_client:
            return False
        
        try:
            # Generate pattern ID
            pattern_id = hashlib.md5(
                f"{email_domain}:{email_content[:100]}:{datetime.utcnow().isoformat()}".encode()
            ).hexdigest()
            
            # Create semantic text for search
            semantic_text = self._create_semantic_text(email_content, extraction_result, corrections)
            
            # Generate embedding
            embedding = await self.generate_embedding(semantic_text)
            
            # Identify common errors if corrections exist
            common_errors = []
            field_accuracy = {}
            
            if corrections:
                for field, correction in corrections.items():
                    if extraction_result.get(field) != correction:
                        common_errors.append(f"{field}: '{extraction_result.get(field)}' → '{correction}'")
                        field_accuracy[field] = 0.0
                    else:
                        field_accuracy[field] = 1.0
            
            # Create pattern document
            pattern = EmailPattern(
                id=pattern_id,
                pattern_type="extraction" if not corrections else "correction",
                email_domain=email_domain,
                company_name=extraction_result.get("company_name"),
                email_snippet=email_content[:500],
                extraction_fields=extraction_result,
                corrections=corrections or {},
                embedding=embedding,
                semantic_text=semantic_text,
                confidence_score=confidence_score,
                field_accuracy=field_accuracy,
                common_errors=common_errors,
                improvement_suggestions=self._generate_improvement_suggestions(corrections)
            )
            
            # Convert to document for indexing
            document = {
                "id": pattern.id,
                "pattern_type": pattern.pattern_type,
                "email_domain": pattern.email_domain,
                "company_name": pattern.company_name,
                "email_snippet": pattern.email_snippet,
                "semantic_text": pattern.semantic_text,
                "extraction_fields": json.dumps(pattern.extraction_fields),
                "corrections": json.dumps(pattern.corrections),
                "embedding": pattern.embedding,
                "confidence_score": pattern.confidence_score,
                "usage_count": pattern.usage_count,
                "success_rate": pattern.success_rate,
                "last_used": pattern.last_used.isoformat(),
                "created_at": pattern.created_at.isoformat(),
                "field_accuracy": json.dumps(pattern.field_accuracy),
                "common_errors": pattern.common_errors,
                "improvement_suggestions": pattern.improvement_suggestions
            }
            
            # Upload to Azure Search
            result = self.search_client.upload_documents(documents=[document])
            
            if result[0].succeeded:
                logger.info(f"Indexed pattern {pattern_id} for domain {email_domain}")
                return True
            else:
                logger.error(f"Failed to index pattern: {result[0].error}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to index email pattern: {e}")
            return False
    
    async def search_similar_patterns(
        self,
        email_content: str,
        email_domain: Optional[str] = None,
        top_k: int = 5,
        min_confidence: float = 0.6
    ) -> List[Dict[str, Any]]:
        """Search for similar email patterns using semantic search"""
        if not self.search_client:
            return []
        
        try:
            # Generate embedding for query
            query_embedding = await self.generate_embedding(email_content[:1000])
            
            # Build search query
            search_text = email_content[:500]
            
            # Create vector query if embedding available
            vector_query = None
            if query_embedding:
                vector_query = VectorizedQuery(
                    vector=query_embedding,
                    k_nearest_neighbors=top_k,
                    fields="embedding"
                )
            
            # Add filters
            filter_expr = f"confidence_score ge {min_confidence}"
            if email_domain:
                filter_expr += f" and email_domain eq '{email_domain}'"
            
            # Execute search
            results = self.search_client.search(
                search_text=search_text,
                vector_queries=[vector_query] if vector_query else None,
                filter=filter_expr,
                query_type="semantic" if not vector_query else "simple",
                semantic_configuration_name="semantic-config" if not vector_query else None,
                top=top_k,
                select=[
                    "id", "email_domain", "company_name", "extraction_fields", 
                    "corrections", "confidence_score", "success_rate", 
                    "field_accuracy", "common_errors", "improvement_suggestions"
                ]
            )
            
            # Process results
            patterns = []
            for result in results:
                pattern = {
                    "id": result.get("id"),
                    "email_domain": result.get("email_domain"),
                    "company_name": result.get("company_name"),
                    "extraction_fields": json.loads(result.get("extraction_fields", "{}")),
                    "corrections": json.loads(result.get("corrections", "{}")),
                    "confidence_score": result.get("confidence_score", 0),
                    "success_rate": result.get("success_rate", 0),
                    "field_accuracy": json.loads(result.get("field_accuracy", "{}")),
                    "common_errors": result.get("common_errors", []),
                    "improvement_suggestions": result.get("improvement_suggestions", []),
                    "score": result.get("@search.score", 0),
                    "semantic_score": result.get("@search.reranker_score", 0)
                }
                patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to search similar patterns: {e}")
            return []
    
    async def get_company_template(self, company_domain: str) -> Optional[Dict[str, Any]]:
        """Retrieve company-specific extraction template"""
        if not self.template_search_client:
            return None
        
        try:
            # Search for exact domain match
            results = self.template_search_client.search(
                search_text="",
                filter=f"company_domain eq '{company_domain}'",
                top=1
            )
            
            for result in results:
                return {
                    "id": result.get("id"),
                    "company_domain": result.get("company_domain"),
                    "company_name": result.get("company_name"),
                    "common_fields": json.loads(result.get("common_fields", "{}")),
                    "field_patterns": json.loads(result.get("field_patterns", "{}")),
                    "extraction_rules": json.loads(result.get("extraction_rules", "{}")),
                    "keywords": result.get("keywords", []),
                    "total_emails": result.get("total_emails", 0),
                    "accuracy_score": result.get("accuracy_score", 0)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get company template: {e}")
            return None
    
    async def update_company_template(
        self,
        company_domain: str,
        extraction_data: Dict[str, Any],
        corrections: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update or create company-specific template"""
        if not self.template_search_client:
            return False
        
        try:
            # Get existing template or create new
            existing = await self.get_company_template(company_domain)
            
            if existing:
                template_id = existing["id"]
                common_fields = existing["common_fields"]
                field_patterns = existing["field_patterns"]
                total_emails = existing["total_emails"] + 1
                
                # Update common fields with new values
                for field, value in extraction_data.items():
                    if value and field != "company_name":
                        if field not in common_fields:
                            common_fields[field] = []
                        if value not in common_fields[field]:
                            common_fields[field].append(value)
                            # Keep only top 10 most common
                            common_fields[field] = common_fields[field][-10:]
                
                # Calculate new accuracy if corrections provided
                accuracy_score = existing["accuracy_score"]
                if corrections:
                    correct_fields = sum(1 for f in extraction_data 
                                       if extraction_data.get(f) == corrections.get(f))
                    current_accuracy = correct_fields / len(extraction_data) if extraction_data else 0
                    # Weighted average
                    accuracy_score = (accuracy_score * (total_emails - 1) + current_accuracy) / total_emails
                
            else:
                # Create new template
                template_id = hashlib.md5(f"{company_domain}:template".encode()).hexdigest()
                common_fields = {
                    field: [value] for field, value in extraction_data.items() 
                    if value and field != "company_name"
                }
                field_patterns = {}
                total_emails = 1
                accuracy_score = 1.0 if not corrections else sum(
                    1 for f in extraction_data if extraction_data.get(f) == corrections.get(f)
                ) / len(extraction_data)
            
            # Generate semantic profile
            profile_text = f"{company_domain} {extraction_data.get('company_name', '')} " + \
                          " ".join(str(v) for v in extraction_data.values() if v)
            semantic_profile = await self.generate_embedding(profile_text)
            
            # Extract keywords
            keywords = self._extract_keywords(extraction_data, common_fields)
            
            # Create template document
            document = {
                "id": template_id,
                "company_domain": company_domain,
                "company_name": extraction_data.get("company_name", ""),
                "common_fields": json.dumps(common_fields),
                "field_patterns": json.dumps(field_patterns),
                "extraction_rules": json.dumps({}),
                "semantic_profile": semantic_profile,
                "keywords": keywords,
                "total_emails": total_emails,
                "accuracy_score": accuracy_score,
                "last_updated": datetime.utcnow().isoformat()
            }
            
            # Upload to Azure Search
            result = self.template_search_client.upload_documents(documents=[document])
            
            if result[0].succeeded:
                logger.info(f"Updated template for {company_domain}")
                return True
            else:
                logger.error(f"Failed to update template: {result[0].error}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update company template: {e}")
            return False
    
    async def get_learning_insights(
        self,
        email_domain: Optional[str] = None,
        field_name: Optional[str] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """Get learning insights and statistics"""
        if not self.search_client:
            return {}
        
        try:
            # Build filter
            cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
            filter_expr = f"last_used ge {cutoff_date}T00:00:00Z"
            
            if email_domain:
                filter_expr += f" and email_domain eq '{email_domain}'"
            
            # Search for patterns
            results = self.search_client.search(
                search_text="*",
                filter=filter_expr,
                top=100,
                select=["field_accuracy", "common_errors", "confidence_score", "success_rate"]
            )
            
            # Aggregate insights
            total_patterns = 0
            field_accuracies = {}
            all_errors = []
            avg_confidence = 0
            avg_success = 0
            
            for result in results:
                total_patterns += 1
                
                # Field accuracies
                accuracies = json.loads(result.get("field_accuracy", "{}"))
                for field, acc in accuracies.items():
                    if field not in field_accuracies:
                        field_accuracies[field] = []
                    field_accuracies[field].append(acc)
                
                # Common errors
                all_errors.extend(result.get("common_errors", []))
                
                # Scores
                avg_confidence += result.get("confidence_score", 0)
                avg_success += result.get("success_rate", 0)
            
            # Calculate averages
            if total_patterns > 0:
                avg_confidence /= total_patterns
                avg_success /= total_patterns
            
            # Calculate per-field average accuracy
            field_avg_accuracy = {}
            for field, accs in field_accuracies.items():
                if accs:
                    field_avg_accuracy[field] = sum(accs) / len(accs)
            
            # Find most common errors
            error_counts = {}
            for error in all_errors:
                error_counts[error] = error_counts.get(error, 0) + 1
            
            top_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                "total_patterns": total_patterns,
                "average_confidence": round(avg_confidence, 3),
                "average_success_rate": round(avg_success, 3),
                "field_accuracy": {k: round(v, 3) for k, v in field_avg_accuracy.items()},
                "top_errors": [{"error": e, "count": c} for e, c in top_errors],
                "period_days": days_back,
                "domain_filter": email_domain,
                "insights": self._generate_insights(field_avg_accuracy, top_errors)
            }
            
        except Exception as e:
            logger.error(f"Failed to get learning insights: {e}")
            return {}
    
    def _create_semantic_text(
        self,
        email_content: str,
        extraction: Dict[str, Any],
        corrections: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create semantic text for indexing and search"""
        parts = [email_content[:500]]
        
        # Add extraction data
        for field, value in extraction.items():
            if value:
                parts.append(f"{field}: {value}")
        
        # Add corrections if available
        if corrections:
            for field, value in corrections.items():
                if value and value != extraction.get(field):
                    parts.append(f"corrected {field}: {value}")
        
        return " ".join(parts)
    
    def _generate_improvement_suggestions(
        self,
        corrections: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Generate improvement suggestions based on corrections"""
        if not corrections:
            return []
        
        suggestions = []
        
        for field, corrected_value in corrections.items():
            if corrected_value:
                suggestions.append(f"Pay attention to {field} extraction")
                
                # Specific suggestions based on field
                if field == "location" and "," in str(corrected_value):
                    suggestions.append("Include full location with city and state")
                elif field == "job_title":
                    suggestions.append("Ensure complete job title including seniority level")
                elif field == "company_name":
                    suggestions.append("Use official company name, not abbreviations")
        
        return list(set(suggestions))[:5]  # Return top 5 unique suggestions
    
    def _extract_keywords(
        self,
        extraction_data: Dict[str, Any],
        common_fields: Dict[str, List[str]]
    ) -> List[str]:
        """Extract keywords from extraction data"""
        keywords = []
        
        # Add unique values from extraction
        for field, value in extraction_data.items():
            if value and isinstance(value, str):
                # Split and add meaningful words
                words = str(value).split()
                keywords.extend([w for w in words if len(w) > 3])
        
        # Add common patterns
        for field, values in common_fields.items():
            if values:
                keywords.append(f"{field}:{values[0]}")
        
        return list(set(keywords))[:20]  # Top 20 unique keywords
    
    def _generate_insights(
        self,
        field_accuracy: Dict[str, float],
        top_errors: List[Tuple[str, int]]
    ) -> List[str]:
        """Generate actionable insights from learning data"""
        insights = []
        
        # Field accuracy insights
        if field_accuracy:
            worst_field = min(field_accuracy.items(), key=lambda x: x[1])
            if worst_field[1] < 0.7:
                insights.append(
                    f"Field '{worst_field[0]}' has low accuracy ({worst_field[1]:.1%}). "
                    f"Consider adjusting extraction prompts."
                )
            
            best_field = max(field_accuracy.items(), key=lambda x: x[1])
            if best_field[1] > 0.9:
                insights.append(
                    f"Field '{best_field[0]}' extraction is highly accurate ({best_field[1]:.1%})."
                )
        
        # Error pattern insights
        if top_errors:
            most_common = top_errors[0]
            if most_common[1] > 5:
                field_match = most_common[0].split(":")[0] if ":" in most_common[0] else None
                if field_match:
                    insights.append(
                        f"Frequent correction needed for '{field_match}' field. "
                        f"Pattern: {most_common[0]}"
                    )
        
        # General recommendations
        if len(insights) < 2:
            insights.append("Continue collecting correction data for better insights.")
        
        return insights