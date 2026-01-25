"""Logs endpoints for debugging and diagnostics"""
import logging
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
import io

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/download", response_class=FileResponse)
def download_logs():
    """Download application logs as file"""
    try:
        log_file = "app.log"
        
        if not os.path.exists(log_file):
            raise HTTPException(status_code=404, detail="Log file not found")
        
        # Get file size
        file_size = os.path.getsize(log_file)
        
        # Return file for download
        return FileResponse(
            path=log_file,
            filename=f"app-logs-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log",
            media_type='text/plain'
        )
    except Exception as e:
        logger.error(f"Error downloading logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tail")
def get_logs_tail(lines: int = 100):
    """Get last N lines of logs"""
    try:
        log_file = "app.log"
        
        if not os.path.exists(log_file):
            return {
                "status": "error",
                "message": "Log file not found",
                "logs": []
            }
        
        # Read last N lines
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return {
            "status": "success",
            "total_lines": len(all_lines),
            "returned_lines": len(last_lines),
            "logs": last_lines
        }
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return {
            "status": "error",
            "message": str(e),
            "logs": []
        }


@router.get("/stream")
async def stream_logs(lines: int = 50):
    """Stream logs as text (for real-time viewing)"""
    try:
        log_file = "app.log"
        
        if not os.path.exists(log_file):
            return {"error": "Log file not found"}
        
        # Read last N lines
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        # Stream as text
        content = ''.join(last_lines)
        
        return StreamingResponse(
            iter([content]),
            media_type="text/plain"
        )
    except Exception as e:
        logger.error(f"Error streaming logs: {e}")
        return {"error": str(e)}


@router.get("/summary")
def get_logs_summary():
    """Get summary of recent errors and warnings"""
    try:
        log_file = "app.log"
        
        if not os.path.exists(log_file):
            return {
                "status": "error",
                "message": "Log file not found",
                "errors": [],
                "warnings": [],
                "info_count": 0
            }
        
        errors = []
        warnings = []
        info_count = 0
        
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Parse last 500 lines
        for line in lines[-500:]:
            if "ERROR" in line:
                errors.append(line.strip())
            elif "WARNING" in line:
                warnings.append(line.strip())
            elif "INFO" in line:
                info_count += 1
        
        return {
            "status": "success",
            "error_count": len(errors),
            "warning_count": len(warnings),
            "info_count": info_count,
            "recent_errors": errors[-10:],  # Last 10 errors
            "recent_warnings": warnings[-10:]  # Last 10 warnings
        }
    except Exception as e:
        logger.error(f"Error generating logs summary: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
