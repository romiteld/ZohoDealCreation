# Apollo.io People Search Production API

## Overview

The Apollo.io People Search endpoint provides unlimited access to comprehensive contact enrichment without consuming API credits. This production-ready endpoint maximizes data extraction, including LinkedIn URLs, phone numbers, emails, and complete company information.

## Endpoint

```
POST /api/apollo/search/people
```

## Authentication

Include your API key in the request headers:

```
X-API-Key: your-api-key
```

## Request Parameters

All parameters are optional. Providing more parameters will result in more targeted searches.

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `email` | string | Email address to search (exact or partial) | "john.smith@example.com" |
| `name` | string | Person's full name | "John Smith" |
| `company_domain` | string | Company domain to filter results | "example.com" |
| `job_title` | string | Job title or role | "Software Engineer" |
| `location` | string | Location (city, state, or country) | "San Francisco" |
| `page` | integer | Page number for pagination (1-100) | 1 |
| `per_page` | integer | Results per page (1-100, default: 25) | 25 |

## Response Structure

### Successful Response

```json
{
  "status": "success",
  "data": {
    "person": {
      // Core Identity
      "id": "apollo-unique-id",
      "full_name": "John Smith",
      "first_name": "John",
      "last_name": "Smith",
      "email": "john.smith@example.com",

      // Professional Information
      "job_title": "Senior Software Engineer",
      "headline": "Building scalable systems",
      "seniority": "senior",

      // Contact Information
      "phone_numbers": [
        {
          "raw_number": "+1-555-123-4567",
          "sanitized_number": "+15551234567",
          "type": "work"
        }
      ],
      "primary_phone": "+15551234567",
      "mobile_phone": "+15559876543",
      "work_phone": "+15551234567",

      // Social Profiles (Critical Fields)
      "linkedin_url": "https://linkedin.com/in/johnsmith",
      "twitter_url": "https://twitter.com/johnsmith",
      "facebook_url": "https://facebook.com/johnsmith",
      "github_url": "https://github.com/johnsmith",

      // Location
      "city": "San Francisco",
      "state": "California",
      "country": "United States",
      "location": "San Francisco, California",
      "time_zone": "America/Los_Angeles",

      // Company Information
      "company": {
        "name": "Example Corp",
        "domain": "example.com",
        "website": "https://www.example.com",
        "linkedin_url": "https://linkedin.com/company/example",
        "twitter_url": "https://twitter.com/example",
        "facebook_url": "https://facebook.com/example",
        "size": "1000-5000",
        "industry": "Software Development",
        "keywords": ["SaaS", "B2B", "Enterprise"],
        "location": "San Francisco, CA",
        "phone": "+1-800-EXAMPLE",
        "founded_year": 2010,
        "revenue": "$100M-$500M",
        "funding": "$150M",
        "technologies": ["Python", "React", "AWS"]
      },

      // Metadata
      "confidence_score": 0.95,
      "last_updated": "2024-01-15T10:30:00Z",
      "alternative_matches": []
    },
    "search_rank": 1,
    "total_results": 1,
    "page": 1,
    "per_page": 25
  },
  "data_quality": {
    "completeness_score": 85.5,
    "critical_completeness": 100.0,
    "total_fields": 35,
    "filled_fields": 30,
    "has_linkedin": true,
    "has_phone": true,
    "has_email": true,
    "has_company_website": true
  },
  "search_criteria": {
    "email": null,
    "name": "John Smith",
    "company_domain": "example.com",
    "job_title": null,
    "location": null
  },
  "cache_hit": false,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Empty Result Response

```json
{
  "status": "success",
  "data": {
    "people": [],
    "total_count": 0,
    "page": 1,
    "per_page": 25
  },
  "message": "No matching people found",
  "search_criteria": {
    "email": "nonexistent@example.com",
    "name": null,
    "company_domain": null,
    "job_title": null,
    "location": null
  },
  "cache_hit": false
}
```

### Error Response

```json
{
  "status": "error",
  "error": {
    "message": "Apollo API key not configured",
    "type": "ConfigurationError",
    "search_params": {
      "email": "test@example.com",
      "name": null,
      "company_domain": null,
      "job_title": null,
      "location": null,
      "page": 1,
      "per_page": 25
    }
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Data Quality Metrics

The endpoint provides comprehensive data quality metrics:

- **completeness_score**: Overall percentage of fields populated (0-100)
- **critical_completeness**: Percentage of critical fields populated (email, LinkedIn, phone, name, company)
- **has_linkedin**: Boolean indicating if LinkedIn URL is available
- **has_phone**: Boolean indicating if phone number is available
- **has_email**: Boolean indicating if email is available
- **has_company_website**: Boolean indicating if company website is available

## Caching Strategy

The endpoint implements intelligent caching to optimize performance and reduce API calls:

### Cache Duration
- **Successful results**: Cached for 24 hours in Redis, 7 days in PostgreSQL
- **Empty results**: Cached for 5 minutes to prevent repeated failed searches
- **Cache key**: Generated from search parameters using MD5 hash

### Cache Hit Indication
The response includes a `cache_hit` field indicating whether the result was served from cache.

### Cache Management Endpoints

#### Get Cache Status
```
GET /api/apollo/cache/status
```

Returns comprehensive cache statistics including hit rates, top searches, and data quality metrics.

#### Cleanup Expired Cache
```
POST /api/apollo/cache/cleanup
```

Removes expired cache entries and returns updated statistics.

#### Export High-Value Cache
```
GET /api/apollo/cache/export?min_completeness=80
```

Exports cached results with high data completeness for backup or analysis.

## Usage Examples

### Search by Email

```bash
curl -X POST "https://api.example.com/api/apollo/search/people" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john.smith@example.com"
  }'
```

### Search by Name and Company

```bash
curl -X POST "https://api.example.com/api/apollo/search/people" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Smith",
    "company_domain": "example.com"
  }'
```

### Search with Filters and Pagination

```bash
curl -X POST "https://api.example.com/api/apollo/search/people" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "job_title": "Software Engineer",
    "location": "San Francisco",
    "page": 2,
    "per_page": 50
  }'
```

## Python Client Example

```python
import httpx
import asyncio

async def search_person(email=None, name=None, company_domain=None):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.example.com/api/apollo/search/people",
            headers={
                "X-API-Key": "your-api-key",
                "Content-Type": "application/json"
            },
            json={
                "email": email,
                "name": name,
                "company_domain": company_domain
            }
        )

        if response.status_code == 200:
            data = response.json()
            if data["data"]["person"]:
                person = data["data"]["person"]
                print(f"Found: {person['full_name']}")
                print(f"Email: {person['email']}")
                print(f"LinkedIn: {person['linkedin_url']}")
                print(f"Company: {person['company']['name']}")
                print(f"Data Completeness: {data['data_quality']['completeness_score']}%")
            else:
                print("No person found")
        else:
            print(f"Error: {response.status_code}")

# Run the search
asyncio.run(search_person(name="John Smith", company_domain="example.com"))
```

## Best Practices

1. **Use Multiple Search Criteria**: Combining parameters like name + company_domain yields better results than single parameters.

2. **Check Data Quality**: Use the `completeness_score` to assess data quality before using the results.

3. **Leverage Caching**: The same searches will be served from cache, reducing latency from ~2-3s to <100ms.

4. **Handle Empty Results**: Check if `data.person` exists before accessing fields.

5. **Monitor Cache Performance**: Use `/api/apollo/cache/status` to monitor cache hit rates and optimize search patterns.

6. **Pagination for Bulk Searches**: Use pagination parameters when searching for multiple results.

## Rate Limits

- **Unlimited searches**: No credit consumption for people search
- **API rate limit**: 100 requests per minute (configurable)
- **Cache warmup**: Automatic for frequently searched patterns

## Data Fields Reference

### Critical Fields (Always Extract)
- `email`: Primary email address
- `linkedin_url`: LinkedIn profile URL
- `phone_numbers`: All available phone numbers
- `full_name`: Complete name
- `company.website`: Company website URL

### Professional Fields
- `job_title`: Current position
- `seniority`: Seniority level
- `headline`: Professional headline

### Social Profiles
- `linkedin_url`: LinkedIn profile
- `twitter_url`: Twitter profile
- `facebook_url`: Facebook profile
- `github_url`: GitHub profile

### Company Intelligence
- `company.name`: Company name
- `company.domain`: Primary domain
- `company.size`: Employee count range
- `company.industry`: Industry classification
- `company.technologies`: Tech stack
- `company.revenue`: Revenue range
- `company.funding`: Total funding

## Error Handling

Common error codes and their meanings:

| Status Code | Error Type | Description |
|------------|------------|-------------|
| 400 | Bad Request | Invalid parameters provided |
| 401 | Unauthorized | Invalid or missing API key |
| 404 | Not Found | No matching person found |
| 429 | Rate Limited | Too many requests |
| 500 | Server Error | Internal server error |
| 503 | Service Unavailable | Apollo API temporarily unavailable |

## Monitoring and Analytics

Track endpoint performance using:

1. **Cache hit rate**: Target >60% for production
2. **Average completeness score**: Monitor data quality trends
3. **Response time**: <100ms for cached, 2-3s for new searches
4. **Top searches**: Identify common search patterns
5. **LinkedIn coverage**: Percentage of results with LinkedIn URLs

## Support

For issues or questions:
- Check cache status: `GET /api/apollo/cache/status`
- Review logs for detailed error messages
- Contact support with correlation IDs from error responses