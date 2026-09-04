import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pestapp.schemas.pest import ReportListResponse
from pestapp.services.pest_store import pest_store
from pestapp.services.pest_service import PestService

router = APIRouter()

@router.get("/reports", response_model=ReportListResponse, summary="获取巡检报告列表")
async def list_reports():
    return ReportListResponse(code=200, message="success", data=pest_store.list_reports())

@router.get("/reports/{report_id}/download", summary="下载巡检报告")
async def download_report(report_id: str):
    report = pest_store.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    base_dir = PestService._get_base_data_dir()
    report_dir = os.path.join(base_dir, "reports")
    file_name = report.get("file_name")
    if not file_name:
        raise HTTPException(status_code=404, detail="Report file missing")

    file_path = os.path.join(report_dir, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Report file not found")

    return FileResponse(file_path, filename=file_name)
