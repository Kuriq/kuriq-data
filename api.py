from datetime import datetime, timedelta, timezone
from threading import RLock
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from pipeline import PipelinePlatform, run_pipeline


app = FastAPI(title="Kuriq Data Crawler API", version="1.0.0")
_jobs: dict[str, dict] = {}
_lock = RLock()


@app.get("/health")
def health():
    return {"status": "UP"}


class TriggerRequest(BaseModel):
    platform: PipelinePlatform = "ALL"
    incremental: bool = True
    syncMysql: bool | None = None
    resetChroma: bool = False
    deactivateMissing: bool = False


class JobProgress(BaseModel):
    totalExpected: int = 0
    crawled: int = 0
    newCourses: int = 0
    updatedCourses: int = 0
    failed: int = 0
    percentComplete: float = 0.0


class JobStatusResponse(BaseModel):
    jobId: str
    platform: PipelinePlatform
    status: str
    progress: JobProgress
    startedAt: datetime
    estimatedCompletionAt: datetime | None = None


def _update_progress(job_id: str, updates: dict):
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["progress"].update(updates)


def _run_job(
    job_id: str,
    platform: PipelinePlatform,
    incremental: bool,
    sync_mysql: bool | None,
    reset_chroma: bool,
    deactivate_missing: bool,
):
    try:
        def progress_callback(payload: dict):
            _update_progress(job_id, payload)

        run_pipeline(
            platform=platform,
            incremental=incremental,
            progress_callback=progress_callback,
            reset=reset_chroma,
            sync_mysql=sync_mysql,
            deactivate_missing=deactivate_missing,
        )
        with _lock:
            job = _jobs[job_id]
            job["status"] = "COMPLETED"
            job["progress"]["percentComplete"] = 100
    except Exception:
        with _lock:
            job = _jobs[job_id]
            job["status"] = "FAILED"
            job["progress"]["failed"] += 1


@app.post("/internal/ai/crawler/trigger", status_code=202)
def trigger_crawler(request: TriggerRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid4())
    started_at = datetime.now(timezone(timedelta(hours=9)))
    progress = JobProgress()
    progress_data = progress.model_dump() if hasattr(progress, "model_dump") else progress.dict()
    with _lock:
        _jobs[job_id] = {
            "jobId": job_id,
            "platform": request.platform,
            "status": "IN_PROGRESS",
            "progress": progress_data,
            "startedAt": started_at,
            "estimatedCompletionAt": started_at + timedelta(minutes=30),
        }
    background_tasks.add_task(
        _run_job,
        job_id,
        request.platform,
        request.incremental,
        request.syncMysql,
        request.resetChroma,
        request.deactivateMissing,
    )
    return {"jobId": job_id, "platform": request.platform, "status": "STARTED", "startedAt": started_at}


@app.get("/internal/ai/crawler/status/{jobId}", response_model=JobStatusResponse)
def get_status(jobId: str):
    with _lock:
        job = _jobs.get(jobId)
        if not job:
            raise HTTPException(status_code=404, detail={"code": "CRAWLER_JOB_NOT_FOUND", "message": "크롤링 작업을 찾을 수 없습니다."})
        return job
