"""
SQLAlchemy models for Apollo.io enrichment data
Provides ORM models for all Apollo tables with vector search support
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import uuid4
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Text, Integer, Decimal, Boolean, DateTime, Date,
    ForeignKey, Index, UniqueConstraint, CheckConstraint, JSON,
    text, func, and_, or_
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, Session, validates
from sqlalchemy.sql import expression

# Import pgvector support if available
try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False
    # Create a placeholder Vector type
    class Vector:
        def __init__(self, dim):
            self.dim = dim

Base = declarative_base()

# Enums for status fields
class EnrichmentType(PyEnum):
    PERSON = "person"
    COMPANY = "company"
    COMBINED = "combined"

class EnrichmentStatus(PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"

class EmailStatus(PyEnum):
    VALID = "valid"
    INVALID = "invalid"
    CATCH_ALL = "catch-all"
    UNKNOWN = "unknown"

class PhoneType(PyEnum):
    MOBILE = "mobile"
    WORK = "work"
    HOME = "home"
    FAX = "fax"
    OTHER = "other"

class SearchType(PyEnum):
    PERSON = "person"
    COMPANY = "company"
    MIXED = "mixed"


class ApolloEnrichment(Base):
    """Main table for Apollo.io enriched person and company data"""
    __tablename__ = 'apollo_enrichments'

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Enrichment metadata
    enrichment_type = Column(String, nullable=False)
    enrichment_status = Column(String, nullable=False, default=EnrichmentStatus.PENDING.value)
    enrichment_date = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    last_updated = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Request identifiers
    request_id = Column(String, unique=True)
    source_email = Column(String, index=True)
    source_deal_id = Column(String, index=True)

    # Person data fields
    person_id = Column(String, index=True)
    person_first_name = Column(String)
    person_last_name = Column(String)
    person_email = Column(String, index=True)
    person_email_status = Column(String)
    person_email_confidence = Column(Integer)
    person_title = Column(String)
    person_seniority = Column(String)
    person_department = Column(String)
    person_linkedin_url = Column(String, index=True)
    person_twitter_url = Column(String)
    person_github_url = Column(String)
    person_facebook_url = Column(String)
    person_phone_numbers = Column(JSONB, default=list)
    person_employment_history = Column(JSONB, default=list)
    person_education = Column(JSONB, default=list)
    person_location_city = Column(String)
    person_location_state = Column(String)
    person_location_country = Column(String)
    person_location_postal_code = Column(String)

    # Company data fields
    company_id = Column(String, index=True)
    company_name = Column(String, index=True)
    company_domain = Column(String, index=True)
    company_website = Column(String)
    company_phone = Column(String)
    company_industry = Column(String)
    company_sub_industry = Column(String)
    company_description = Column(Text)
    company_logo_url = Column(String)
    company_linkedin_url = Column(String)
    company_twitter_url = Column(String)
    company_facebook_url = Column(String)
    company_employee_count = Column(Integer)
    company_employee_range = Column(String)
    company_annual_revenue = Column(Decimal(15, 2))
    company_revenue_range = Column(String)
    company_funding_total = Column(Decimal(15, 2))
    company_funding_stage = Column(String)
    company_technologies = Column(JSONB, default=list)
    company_keywords = Column(JSONB, default=list)
    company_sic_codes = Column(JSONB, default=list)
    company_naics_codes = Column(JSONB, default=list)
    company_headquarters_city = Column(String)
    company_headquarters_state = Column(String)
    company_headquarters_country = Column(String)
    company_headquarters_postal_code = Column(String)
    company_year_founded = Column(Integer)

    # Data quality and confidence scores
    overall_confidence_score = Column(Decimal(3, 2))
    data_completeness_score = Column(Decimal(3, 2))
    last_verified_date = Column(Date)
    verification_source = Column(String)

    # Vector embeddings (if pgvector is available)
    if HAS_PGVECTOR:
        person_embedding = Column(Vector(1536))
        company_embedding = Column(Vector(1536))
        combined_embedding = Column(Vector(1536))

    # API response metadata
    api_credits_used = Column(Integer, default=0)
    api_response_time_ms = Column(Integer)
    api_rate_limit_remaining = Column(Integer)
    raw_api_response = Column(JSONB)

    # Error handling
    error_message = Column(Text)
    error_code = Column(String)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Audit fields
    created_by = Column(String)
    updated_by = Column(String)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True))

    # Additional metadata
    metadata = Column(JSONB, default=dict)
    tags = Column(ARRAY(String), default=list)
    notes = Column(Text)

    # Relationships
    phone_numbers = relationship("ApolloPhoneNumber", back_populates="enrichment", cascade="all, delete-orphan")

    # Computed property for full name
    @hybrid_property
    def person_full_name(self):
        """Get the full name of the person"""
        if self.person_first_name and self.person_last_name:
            return f"{self.person_first_name} {self.person_last_name}"
        return self.person_first_name or self.person_last_name or None

    @person_full_name.expression
    def person_full_name(cls):
        """SQL expression for full name"""
        return func.coalesce(
            func.concat(cls.person_first_name, ' ', cls.person_last_name),
            cls.person_first_name,
            cls.person_last_name
        )

    # Validation
    @validates('person_email_confidence')
    def validate_confidence(self, key, value):
        """Validate confidence score is between 0 and 100"""
        if value is not None and (value < 0 or value > 100):
            raise ValueError(f"Confidence score must be between 0 and 100, got {value}")
        return value

    @validates('overall_confidence_score', 'data_completeness_score')
    def validate_decimal_score(self, key, value):
        """Validate decimal scores are between 0 and 1"""
        if value is not None and (value < 0 or value > 1):
            raise ValueError(f"{key} must be between 0 and 1, got {value}")
        return value

    def calculate_completeness(self) -> float:
        """Calculate data completeness score"""
        fields = [
            self.person_first_name, self.person_last_name, self.person_email,
            self.person_title, self.person_linkedin_url, self.person_phone_numbers,
            self.person_location_city, self.person_location_state, self.person_location_country,
            self.company_name, self.company_domain, self.company_website,
            self.company_industry, self.company_employee_count, self.company_annual_revenue,
            self.company_headquarters_city, self.company_headquarters_state,
            self.company_headquarters_country, self.company_linkedin_url, self.company_description
        ]

        filled = sum(1 for f in fields if f and (not isinstance(f, list) or len(f) > 0))
        return filled / len(fields)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'enrichment_type': self.enrichment_type,
            'enrichment_status': self.enrichment_status,
            'enrichment_date': self.enrichment_date.isoformat() if self.enrichment_date else None,
            'person': {
                'id': self.person_id,
                'name': self.person_full_name,
                'email': self.person_email,
                'title': self.person_title,
                'linkedin': self.person_linkedin_url,
                'location': {
                    'city': self.person_location_city,
                    'state': self.person_location_state,
                    'country': self.person_location_country
                }
            } if self.person_email else None,
            'company': {
                'id': self.company_id,
                'name': self.company_name,
                'domain': self.company_domain,
                'industry': self.company_industry,
                'size': self.company_employee_count,
                'revenue': float(self.company_annual_revenue) if self.company_annual_revenue else None,
                'location': {
                    'city': self.company_headquarters_city,
                    'state': self.company_headquarters_state,
                    'country': self.company_headquarters_country
                }
            } if self.company_name else None,
            'confidence_score': float(self.overall_confidence_score) if self.overall_confidence_score else None,
            'completeness_score': float(self.data_completeness_score) if self.data_completeness_score else None
        }

    def __repr__(self):
        return f"<ApolloEnrichment(id={self.id}, person={self.person_full_name}, company={self.company_name})>"


class ApolloSearchCache(Base):
    """Cache table for Apollo search results"""
    __tablename__ = 'apollo_search_cache'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Cache key components
    search_type = Column(String, nullable=False)
    search_query = Column(String, nullable=False)
    search_params = Column(JSONB, nullable=False, default=dict)

    # Cache data
    result_count = Column(Integer, default=0)
    results = Column(JSONB, nullable=False, default=list)
    result_ids = Column(ARRAY(String), default=list)

    # Cache metadata
    cached_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True))
    hit_count = Column(Integer, default=0)
    last_accessed = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))

    # Cache validation
    is_valid = Column(Boolean, default=True)
    invalidated_at = Column(DateTime(timezone=True))
    invalidation_reason = Column(String)

    # Performance metrics
    api_response_time_ms = Column(Integer)
    cache_size_bytes = Column(Integer)

    @hybrid_property
    def cache_key(self):
        """Generate cache key from search parameters"""
        import hashlib
        import json
        key_str = f"{self.search_type}{self.search_query}{json.dumps(self.search_params, sort_keys=True)}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    @hybrid_property
    def is_expired(self):
        """Check if cache entry is expired"""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def increment_hit_count(self):
        """Increment hit count and update last accessed time"""
        self.hit_count += 1
        self.last_accessed = datetime.now(timezone.utc)

    def invalidate(self, reason: str = None):
        """Invalidate this cache entry"""
        self.is_valid = False
        self.invalidated_at = datetime.now(timezone.utc)
        self.invalidation_reason = reason

    def __repr__(self):
        return f"<ApolloSearchCache(id={self.id}, type={self.search_type}, hits={self.hit_count})>"


class ApolloMetrics(Base):
    """Metrics table for tracking Apollo API usage"""
    __tablename__ = 'apollo_metrics'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Time bucket
    metric_timestamp = Column(DateTime(timezone=True), nullable=False, unique=True)

    # API call metrics
    total_api_calls = Column(Integer, default=0)
    successful_calls = Column(Integer, default=0)
    failed_calls = Column(Integer, default=0)
    partial_success_calls = Column(Integer, default=0)

    # Call type breakdown
    person_enrichment_calls = Column(Integer, default=0)
    company_enrichment_calls = Column(Integer, default=0)
    search_calls = Column(Integer, default=0)

    # Performance metrics
    avg_response_time_ms = Column(Decimal(10, 2))
    min_response_time_ms = Column(Integer)
    max_response_time_ms = Column(Integer)
    p95_response_time_ms = Column(Integer)
    p99_response_time_ms = Column(Integer)

    # Credit usage
    total_credits_used = Column(Integer, default=0)
    credits_per_person = Column(Decimal(5, 2))
    credits_per_company = Column(Decimal(5, 2))

    # Cache metrics
    cache_hits = Column(Integer, default=0)
    cache_misses = Column(Integer, default=0)

    # Error tracking
    rate_limit_errors = Column(Integer, default=0)
    authentication_errors = Column(Integer, default=0)
    network_errors = Column(Integer, default=0)
    validation_errors = Column(Integer, default=0)

    # Data quality metrics
    avg_completeness_score = Column(Decimal(3, 2))
    avg_confidence_score = Column(Decimal(3, 2))
    records_with_email = Column(Integer, default=0)
    records_with_phone = Column(Integer, default=0)
    records_with_linkedin = Column(Integer, default=0)

    @hybrid_property
    def metric_date(self):
        """Get the date portion of the timestamp"""
        return self.metric_timestamp.date() if self.metric_timestamp else None

    @hybrid_property
    def metric_hour(self):
        """Get the hour portion of the timestamp"""
        return self.metric_timestamp.hour if self.metric_timestamp else None

    @hybrid_property
    def cache_hit_rate(self):
        """Calculate cache hit rate"""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0
        return self.cache_hits / total

    @hybrid_property
    def success_rate(self):
        """Calculate API call success rate"""
        if self.total_api_calls == 0:
            return 0
        return self.successful_calls / self.total_api_calls

    def __repr__(self):
        return f"<ApolloMetrics(timestamp={self.metric_timestamp}, calls={self.total_api_calls})>"


class ApolloPhoneNumber(Base):
    """Normalized phone numbers with validation status"""
    __tablename__ = 'apollo_phone_numbers'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    enrichment_id = Column(UUID(as_uuid=True), ForeignKey('apollo_enrichments.id', ondelete='CASCADE'))

    # Phone number data
    phone_number = Column(String, nullable=False)
    phone_type = Column(String)
    phone_country_code = Column(String)
    phone_area_code = Column(String)
    phone_local_number = Column(String)
    phone_extension = Column(String)

    # Validation status
    is_valid = Column(Boolean)
    is_mobile = Column(Boolean)
    carrier = Column(String)
    line_type = Column(String)
    last_validated = Column(DateTime(timezone=True))

    # Usage tracking
    times_called = Column(Integer, default=0)
    last_called = Column(DateTime(timezone=True))
    call_outcomes = Column(JSONB, default=list)

    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))

    # Relationships
    enrichment = relationship("ApolloEnrichment", back_populates="phone_numbers")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint('enrichment_id', 'phone_number', name='apollo_phone_unique'),
    )

    def __repr__(self):
        return f"<ApolloPhoneNumber(number={self.phone_number}, type={self.phone_type})>"


# Helper functions for vector similarity search (if pgvector is available)
if HAS_PGVECTOR:
    def find_similar_persons(session: Session, embedding: List[float], limit: int = 10, threshold: float = 0.8):
        """Find similar persons using vector similarity"""
        from sqlalchemy import select

        return session.execute(
            select(ApolloEnrichment)
            .where(
                and_(
                    ApolloEnrichment.person_embedding.isnot(None),
                    ApolloEnrichment.is_deleted == False,
                    ApolloEnrichment.person_embedding.cosine_distance(embedding) < (1 - threshold)
                )
            )
            .order_by(ApolloEnrichment.person_embedding.cosine_distance(embedding))
            .limit(limit)
        ).scalars().all()

    def find_similar_companies(session: Session, embedding: List[float], limit: int = 10, threshold: float = 0.8):
        """Find similar companies using vector similarity"""
        from sqlalchemy import select

        return session.execute(
            select(ApolloEnrichment)
            .where(
                and_(
                    ApolloEnrichment.company_embedding.isnot(None),
                    ApolloEnrichment.is_deleted == False,
                    ApolloEnrichment.company_embedding.cosine_distance(embedding) < (1 - threshold)
                )
            )
            .order_by(ApolloEnrichment.company_embedding.cosine_distance(embedding))
            .limit(limit)
        ).scalars().all()


# Create indexes programmatically (useful for runtime index creation)
def create_indexes():
    """Create all necessary indexes for Apollo tables"""
    indexes = [
        # Text search indexes
        Index('idx_apollo_person_fulltext_gin',
              func.to_tsvector('english',
                  func.concat(
                      func.coalesce(ApolloEnrichment.person_first_name, ''), ' ',
                      func.coalesce(ApolloEnrichment.person_last_name, ''), ' ',
                      func.coalesce(ApolloEnrichment.person_email, '')
                  )
              ),
              postgresql_using='gin'
        ),

        Index('idx_apollo_company_fulltext_gin',
              func.to_tsvector('english',
                  func.concat(
                      func.coalesce(ApolloEnrichment.company_name, ''), ' ',
                      func.coalesce(ApolloEnrichment.company_description, ''), ' ',
                      func.coalesce(ApolloEnrichment.company_industry, '')
                  )
              ),
              postgresql_using='gin'
        ),

        # Composite indexes for common queries
        Index('idx_apollo_person_company',
              ApolloEnrichment.person_email,
              ApolloEnrichment.company_domain
        ),

        Index('idx_apollo_status_date',
              ApolloEnrichment.enrichment_status,
              ApolloEnrichment.enrichment_date
        ),

        # Cache optimization indexes
        Index('idx_apollo_cache_lookup',
              ApolloSearchCache.search_type,
              ApolloSearchCache.search_query,
              ApolloSearchCache.is_valid
        ),

        Index('idx_apollo_cache_expiry',
              ApolloSearchCache.expires_at,
              ApolloSearchCache.is_valid
        )
    ]

    return indexes