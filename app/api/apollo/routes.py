"""
Apollo.io API Routes - Comprehensive Phone Number Discovery

This module provides specialized endpoints for extracting phone numbers
from Apollo.io with maximum coverage and type differentiation.
"""

import logging
from typing import Dict, Optional, List, Any
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, EmailStr

from app.auth import verify_api_key
from app.apollo_enricher import (
    apollo_unlimited_people_search,
    apollo_unlimited_company_search,
    apollo_deep_enrichment
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/apollo",
    tags=["Apollo.io"],
    dependencies=[Depends(verify_api_key)]
)


class PhoneExtractionRequest(BaseModel):
    """Request model for phone number extraction"""
    email: Optional[EmailStr] = Field(None, description="Email address to search")
    name: Optional[str] = Field(None, description="Full name of the person")
    company: Optional[str] = Field(None, description="Company name or domain")
    job_title: Optional[str] = Field(None, description="Job title for filtering")
    location: Optional[str] = Field(None, description="Location for filtering")
    include_company_phones: bool = Field(True, description="Include company main lines")
    include_employee_phones: bool = Field(True, description="Include employee phone numbers")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com",
                "name": "John Doe",
                "company": "Example Corp",
                "include_company_phones": True,
                "include_employee_phones": True
            }
        }


class PhoneNumber(BaseModel):
    """Model for a phone number with metadata"""
    number: str = Field(..., description="Formatted phone number")
    type: str = Field(..., description="Phone type: mobile, work, company, home, etc.")
    owner: Optional[str] = Field(None, description="Name of the phone owner")
    title: Optional[str] = Field(None, description="Job title of the owner")
    confidence: Optional[float] = Field(None, description="Confidence score")
    source: str = Field("apollo", description="Data source")
    international_format: Optional[str] = Field(None, description="International format with country code")
    raw_number: Optional[str] = Field(None, description="Original unformatted number")


class PhoneExtractionResponse(BaseModel):
    """Response model for phone extraction"""
    success: bool = Field(..., description="Whether extraction was successful")
    primary_contact: Optional[Dict[str, Any]] = Field(None, description="Primary contact information")
    phone_numbers: List[PhoneNumber] = Field(default_factory=list, description="All discovered phone numbers")
    company_info: Optional[Dict[str, Any]] = Field(None, description="Company information if found")
    total_phones_found: int = Field(0, description="Total count of phone numbers found")
    data_completeness: float = Field(0.0, description="Data completeness percentage")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


def format_phone_number(phone: str, country_code: str = "+1") -> Dict[str, str]:
    """
    Format phone number with international format

    Args:
        phone: Raw phone number
        country_code: Default country code if not present

    Returns:
        Dict with formatted versions of the phone number
    """
    import re

    # Remove all non-numeric characters
    clean = re.sub(r'\D', '', phone)

    # Handle different formats
    formatted = {}

    if len(clean) == 10:  # US number without country code
        formatted['raw'] = clean
        formatted['formatted'] = f"({clean[:3]}) {clean[3:6]}-{clean[6:]}"
        formatted['international'] = f"{country_code} {clean[:3]} {clean[3:6]} {clean[6:]}"
    elif len(clean) == 11 and clean[0] == '1':  # US number with country code
        formatted['raw'] = clean
        formatted['formatted'] = f"({clean[1:4]}) {clean[4:7]}-{clean[7:]}"
        formatted['international'] = f"+{clean[0]} {clean[1:4]} {clean[4:7]} {clean[7:]}"
    else:
        # Keep as is for international or unknown formats
        formatted['raw'] = clean
        formatted['formatted'] = phone
        formatted['international'] = phone if phone.startswith('+') else f"{country_code} {phone}"

    return formatted


def extract_phone_from_person(person_data: Dict[str, Any]) -> List[PhoneNumber]:
    """
    Extract all phone numbers from a person's Apollo data

    Args:
        person_data: Person data from Apollo API

    Returns:
        List of PhoneNumber objects
    """
    phones = []

    # Extract from phone_numbers array
    phone_numbers = person_data.get('phone_numbers', [])
    for phone_obj in phone_numbers:
        if phone_obj.get('sanitized_number'):
            formatted = format_phone_number(phone_obj['sanitized_number'])
            phones.append(PhoneNumber(
                number=formatted['formatted'],
                type=phone_obj.get('type', 'unknown'),
                owner=person_data.get('client_name') or person_data.get('name'),
                title=person_data.get('job_title') or person_data.get('title'),
                confidence=person_data.get('confidence_score'),
                international_format=formatted['international'],
                raw_number=phone_obj.get('raw_number') or phone_obj.get('sanitized_number')
            ))

    # Also check individual phone fields
    if person_data.get('phone') and person_data.get('phone') not in [p.raw_number for p in phones]:
        formatted = format_phone_number(person_data['phone'])
        phones.append(PhoneNumber(
            number=formatted['formatted'],
            type='primary',
            owner=person_data.get('client_name') or person_data.get('name'),
            title=person_data.get('job_title') or person_data.get('title'),
            confidence=person_data.get('confidence_score'),
            international_format=formatted['international'],
            raw_number=person_data['phone']
        ))

    if person_data.get('mobile_phone') and person_data.get('mobile_phone') not in [p.raw_number for p in phones]:
        formatted = format_phone_number(person_data['mobile_phone'])
        phones.append(PhoneNumber(
            number=formatted['formatted'],
            type='mobile',
            owner=person_data.get('client_name') or person_data.get('name'),
            title=person_data.get('job_title') or person_data.get('title'),
            confidence=person_data.get('confidence_score'),
            international_format=formatted['international'],
            raw_number=person_data['mobile_phone']
        ))

    if person_data.get('work_phone') and person_data.get('work_phone') not in [p.raw_number for p in phones]:
        formatted = format_phone_number(person_data['work_phone'])
        phones.append(PhoneNumber(
            number=formatted['formatted'],
            type='work',
            owner=person_data.get('client_name') or person_data.get('name'),
            title=person_data.get('job_title') or person_data.get('title'),
            confidence=person_data.get('confidence_score'),
            international_format=formatted['international'],
            raw_number=person_data['work_phone']
        ))

    return phones


def extract_phones_from_company(company_data: Dict[str, Any], include_employees: bool = True) -> List[PhoneNumber]:
    """
    Extract all phone numbers from company data including employee phones

    Args:
        company_data: Company data from Apollo API
        include_employees: Whether to include employee phone numbers

    Returns:
        List of PhoneNumber objects
    """
    phones = []

    # Company main line
    if company_data.get('phone'):
        formatted = format_phone_number(company_data['phone'])
        phones.append(PhoneNumber(
            number=formatted['formatted'],
            type='company_main',
            owner=company_data.get('company_name') or company_data.get('name'),
            title="Main Line",
            confidence=company_data.get('confidence_score'),
            international_format=formatted['international'],
            raw_number=company_data['phone']
        ))

    if include_employees:
        # Key employees
        for employee in company_data.get('key_employees', []):
            if employee.get('phone'):
                formatted = format_phone_number(employee['phone'])
                phones.append(PhoneNumber(
                    number=formatted['formatted'],
                    type='work',
                    owner=employee.get('name'),
                    title=employee.get('title'),
                    confidence=None,
                    international_format=formatted['international'],
                    raw_number=employee['phone']
                ))

        # Decision makers
        for decision_maker in company_data.get('decision_makers', []):
            if decision_maker.get('phone') and decision_maker.get('phone') not in [p.raw_number for p in phones]:
                formatted = format_phone_number(decision_maker['phone'])
                phones.append(PhoneNumber(
                    number=formatted['formatted'],
                    type='executive',
                    owner=decision_maker.get('name'),
                    title=decision_maker.get('title'),
                    confidence=None,
                    international_format=formatted['international'],
                    raw_number=decision_maker['phone']
                ))

        # Recruiters
        for recruiter in company_data.get('recruiters', []):
            if recruiter.get('phone') and recruiter.get('phone') not in [p.raw_number for p in phones]:
                formatted = format_phone_number(recruiter['phone'])
                phones.append(PhoneNumber(
                    number=formatted['formatted'],
                    type='recruiter',
                    owner=recruiter.get('name'),
                    title=recruiter.get('title'),
                    confidence=None,
                    international_format=formatted['international'],
                    raw_number=recruiter['phone']
                ))

    return phones


@router.post("/extract/phones", response_model=PhoneExtractionResponse)
async def extract_phone_numbers(request: PhoneExtractionRequest):
    """
    Extract ALL available phone numbers from Apollo.io

    This endpoint discovers:
    - Personal mobile phones
    - Work/office phones
    - Company main lines
    - Executive phone numbers
    - Recruiter contact numbers

    Returns phone numbers with type classification and formatting.
    """
    try:
        logger.info(f"Phone extraction request: email={request.email}, name={request.name}, company={request.company}")

        if not any([request.email, request.name, request.company]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one of email, name, or company must be provided"
            )

        all_phones: List[PhoneNumber] = []
        primary_contact = None
        company_info = None

        # Step 1: Search for the person if we have email or name
        if request.email or request.name:
            person_data = await apollo_unlimited_people_search(
                email=request.email,
                name=request.name,
                company_domain=request.company if request.company and '.' in request.company else None,
                job_title=request.job_title,
                location=request.location
            )

            if person_data:
                primary_contact = {
                    "name": person_data.get('client_name') or person_data.get('name'),
                    "email": person_data.get('email'),
                    "title": person_data.get('job_title') or person_data.get('title'),
                    "company": person_data.get('firm_company'),
                    "linkedin": person_data.get('linkedin_url'),
                    "location": person_data.get('location')
                }

                # Extract phone numbers from person data
                person_phones = extract_phone_from_person(person_data)
                all_phones.extend(person_phones)

                # Get company info for further enrichment
                if not request.company and person_data.get('firm_company'):
                    request.company = person_data.get('firm_company')
                elif not request.company and person_data.get('company_domain'):
                    request.company = person_data.get('company_domain')

        # Step 2: Search for company phones if requested
        if request.company and request.include_company_phones:
            company_data = await apollo_unlimited_company_search(
                company_name=request.company if not request.company.endswith('.com') else None,
                domain=request.company if request.company.endswith('.com') else None,
                location=request.location
            )

            if company_data:
                company_info = {
                    "name": company_data.get('company_name'),
                    "domain": company_data.get('domain'),
                    "website": company_data.get('website'),
                    "phone": company_data.get('phone'),
                    "industry": company_data.get('industry'),
                    "employee_count": company_data.get('employee_count'),
                    "location": company_data.get('full_address') or company_data.get('city')
                }

                # Extract company and employee phones
                company_phones = extract_phones_from_company(
                    company_data,
                    include_employees=request.include_employee_phones
                )

                # Deduplicate phones based on raw number
                existing_raw_numbers = {p.raw_number for p in all_phones if p.raw_number}
                for phone in company_phones:
                    if not phone.raw_number or phone.raw_number not in existing_raw_numbers:
                        all_phones.append(phone)

        # Step 3: If no phones found yet, try deep enrichment
        if not all_phones and (request.email or request.name or request.company):
            deep_data = await apollo_deep_enrichment(
                email=request.email,
                name=request.name,
                company=request.company,
                extract_all=True
            )

            if deep_data.get('person'):
                person_phones = extract_phone_from_person(deep_data['person'])
                all_phones.extend(person_phones)

            if deep_data.get('company'):
                company_phones = extract_phones_from_company(
                    deep_data['company'],
                    include_employees=request.include_employee_phones
                )

                # Deduplicate
                existing_raw_numbers = {p.raw_number for p in all_phones if p.raw_number}
                for phone in company_phones:
                    if not phone.raw_number or phone.raw_number not in existing_raw_numbers:
                        all_phones.append(phone)

        # Calculate data completeness
        expected_fields = 5  # email, name, mobile, work, company phone
        found_fields = 0
        if primary_contact and primary_contact.get('email'):
            found_fields += 1
        if primary_contact and primary_contact.get('name'):
            found_fields += 1
        if any(p.type == 'mobile' for p in all_phones):
            found_fields += 1
        if any(p.type == 'work' for p in all_phones):
            found_fields += 1
        if any(p.type == 'company_main' for p in all_phones):
            found_fields += 1

        data_completeness = (found_fields / expected_fields) * 100 if expected_fields > 0 else 0

        # Build response
        response = PhoneExtractionResponse(
            success=len(all_phones) > 0,
            primary_contact=primary_contact,
            phone_numbers=all_phones,
            company_info=company_info,
            total_phones_found=len(all_phones),
            data_completeness=data_completeness,
            metadata={
                "search_params": {
                    "email": request.email,
                    "name": request.name,
                    "company": request.company,
                    "job_title": request.job_title,
                    "location": request.location
                },
                "phone_type_breakdown": {
                    "mobile": len([p for p in all_phones if p.type == 'mobile']),
                    "work": len([p for p in all_phones if p.type == 'work']),
                    "company_main": len([p for p in all_phones if p.type == 'company_main']),
                    "executive": len([p for p in all_phones if p.type == 'executive']),
                    "recruiter": len([p for p in all_phones if p.type == 'recruiter']),
                    "other": len([p for p in all_phones if p.type not in ['mobile', 'work', 'company_main', 'executive', 'recruiter']])
                }
            }
        )

        logger.info(f"Phone extraction successful: found {len(all_phones)} phone numbers")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Phone extraction error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Phone extraction failed: {str(e)}"
        )


@router.post("/enrich/contact")
async def enrich_contact(
    email: Optional[EmailStr] = None,
    name: Optional[str] = None,
    company: Optional[str] = None
):
    """
    Comprehensive contact enrichment with phone discovery

    Returns all available contact information including multiple phone numbers.
    """
    try:
        if not any([email, name, company]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one of email, name, or company must be provided"
            )

        # Perform deep enrichment
        result = await apollo_deep_enrichment(
            email=email,
            name=name,
            company=company,
            extract_all=True
        )

        # Extract all phones
        all_phones = []

        if result.get('person'):
            person_phones = extract_phone_from_person(result['person'])
            all_phones.extend(person_phones)

        if result.get('company'):
            company_phones = extract_phones_from_company(result['company'])
            all_phones.extend(company_phones)

        # Add phone summary to result
        result['phone_summary'] = {
            "total_phones": len(all_phones),
            "phones": [p.dict() for p in all_phones],
            "primary_phone": all_phones[0].dict() if all_phones else None
        }

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Contact enrichment error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Contact enrichment failed: {str(e)}"
        )


@router.get("/search/people")
async def search_people(
    query: str,
    limit: int = 10
):
    """
    Search for people in Apollo.io database

    Returns list of people with phone numbers.
    """
    try:
        result = await apollo_unlimited_people_search(
            name=query
        )

        if result and result.get('alternative_matches'):
            # Include main result
            people = [{
                "name": result.get('client_name'),
                "email": result.get('email'),
                "company": result.get('firm_company'),
                "title": result.get('job_title'),
                "phone": result.get('phone'),
                "mobile": result.get('mobile_phone'),
                "work_phone": result.get('work_phone'),
                "linkedin": result.get('linkedin_url')
            }]

            # Add alternatives
            people.extend(result['alternative_matches'][:limit-1])

            return {"people": people, "total": len(people)}

        return {"people": [], "total": 0}

    except Exception as e:
        logger.error(f"People search error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"People search failed: {str(e)}"
        )


@router.get("/search/companies")
async def search_companies(
    query: str,
    limit: int = 5
):
    """
    Search for companies in Apollo.io database

    Returns list of companies with phone numbers.
    """
    try:
        result = await apollo_unlimited_company_search(
            company_name=query
        )

        if result:
            return {
                "companies": [{
                    "name": result.get('company_name'),
                    "domain": result.get('domain'),
                    "phone": result.get('phone'),
                    "website": result.get('website'),
                    "industry": result.get('industry'),
                    "employee_count": result.get('employee_count'),
                    "location": result.get('city')
                }],
                "total": 1
            }

        return {"companies": [], "total": 0}

    except Exception as e:
        logger.error(f"Company search error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Company search failed: {str(e)}"
        )