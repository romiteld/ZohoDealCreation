"""
Global error handlers and exception middleware for the Well Intake API
"""

import logging
import traceback
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError

logger = logging.getLogger(__name__)

async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.error(f"HTTP exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "status_code": exc.status_code,
            "message": str(exc.detail),
            "path": str(request.url.path)
        }
    )

async def starlette_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle Starlette HTTP exceptions"""
    logger.error(f"Starlette HTTP exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "status_code": exc.status_code,
            "message": str(exc.detail),
            "path": str(request.url.path)
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors"""
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Invalid request data",
            "details": exc.errors(),
            "path": str(request.url.path)
        }
    )

async def pydantic_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors"""
    logger.error(f"Pydantic validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Data validation failed",
            "details": exc.errors(),
            "path": str(request.url.path)
        }
    )

async def general_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    error_id = str(hash(str(exc)))
    logger.error(f"Unhandled exception (ID: {error_id}): {str(exc)}\n{traceback.format_exc()}")
    
    # Don't expose internal errors in production
    if request.app.debug:
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "error_id": error_id,
                "message": str(exc),
                "type": exc.__class__.__name__,
                "traceback": traceback.format_exc().split('\n'),
                "path": str(request.url.path)
            }
        )
    else:
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "error_id": error_id,
                "message": "An internal error occurred. Please contact support with the error ID.",
                "path": str(request.url.path)
            }
        )

def register_error_handlers(app):
    """Register all error handlers with the FastAPI app"""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)