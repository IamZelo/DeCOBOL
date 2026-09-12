"""
In-memory thread-safe Job Store and background runner for DeCOBOL.
Conforms to docs/CONTRACTS.md v1.0.0 §6 and §11.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import queue
import threading
import time
import uuid
from typing import Dict, Any, Optional, List

from app.config import settings
from app.orchestrator.events import Event, EventType
from app.orchestrator.graph import run_pipeline
from app.orchestrator.state import ConversionState
from app.tools.registry import call_tool


@dataclass
class Job:
    job_id: str
    raw_cobol: str
    filename: Optional[str]
    options: Dict[str, Any]
    status: str = "queued"  # queued | running | completed | completed_with_warnings | failed
    created_ts: float = field(default_factory=time.time)
    finished_ts: Optional[float] = None
    retry_count: int = 0
    events: List[Event] = field(default_factory=list)
    final_state: Optional[ConversionState] = None
    error: Optional[str] = None
    subscribers: List[queue.Queue] = field(default_factory=list)
    # Set when the job was submitted by path (docs/LOCAL_DEPLOYMENT_WORKFLOW.md)
    # rather than inline cobol_code — the relative path under INPUT_ROOT.
    source_path: Optional[str] = None
    # Relative path under OUTPUT_ROOT the final Java was written to, once the
    # job finishes. None for inline-cobol_code jobs (nowhere meaningful to
    # mirror them to) and for jobs still in progress.
    output_path: Optional[str] = None

    @property
    def duration_ms(self) -> int:
        if self.finished_ts:
            return int((self.finished_ts - self.created_ts) * 1000)
        return int((time.time() - self.created_ts) * 1000)

    def to_summary(self) -> Dict[str, Any]:
        """Compact summary matching CONTRACTS.md §11 GET /api/jobs."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "filename": self.filename,
            "created_ts": round(self.created_ts, 3),
            "finished_ts": round(self.finished_ts, 3) if self.finished_ts else None,
            "duration_ms": self.duration_ms,
            "retry_count": self.retry_count,
            # Additive per docs/LOCAL_DEPLOYMENT_WORKFLOW.md — null for jobs
            # submitted with inline cobol_code.
            "source_path": self.source_path,
            "output_path": self.output_path,
        }

    def to_detail(self) -> Dict[str, Any]:
        """Full Job record matching CONTRACTS.md §11 GET /api/jobs/<id>."""
        result_payload = None

        if self.status in ("completed", "completed_with_warnings", "failed") and self.final_state:
            final = self.final_state
            ast = final.get("parsed_ast") or {}
            class_name = "".join(part.capitalize() for part in ast.get("program_id", "CobolProgram").replace("-", "_").split("_"))
            
            # Rule from §5: optimized_code if non-null, else java_code
            resolved_code = final.get("optimized_code") or final.get("java_code") or ""

            result_payload = {
                "program_id": ast.get("program_id", "UNKNOWN"),
                "class_name": class_name,
                "java_code": resolved_code,
                "validation": final.get("validation"),
                "documentation": final.get("documentation"),
                "parsed_ast": final.get("parsed_ast"),
            }

        agent_results = []
        errors = []
        if self.final_state:
            agent_results = self.final_state.get("agent_results", [])
            errors = self.final_state.get("errors", [])

        return {
            "job_id": self.job_id,
            "status": self.status,
            "filename": self.filename,
            "created_ts": round(self.created_ts, 3),
            "finished_ts": round(self.finished_ts, 3) if self.finished_ts else None,
            "duration_ms": self.duration_ms,
            "retry_count": self.retry_count,
            "source_path": self.source_path,
            "output_path": self.output_path,
            "raw_cobol": self.raw_cobol,
            "result": result_payload,
            "agent_results": agent_results,
            "errors": errors,
            "events": [e.to_dict() for e in self.events],
        }


class JobStore:
    """Thread-safe in-memory store for conversion jobs."""

    def __init__(self):
        self._lock = threading.Lock()
        self._jobs: Dict[str, Job] = {}

    def create_job(
        self,
        raw_cobol: str,
        filename: Optional[str] = "program.cob",
        options: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        source_path: Optional[str] = None,
    ) -> Job:
        job_id = job_id or uuid.uuid4().hex
        job = Job(
            job_id=job_id,
            raw_cobol=raw_cobol,
            filename=filename,
            options=options or {},
            source_path=source_path,
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> List[Dict[str, Any]]:
        with self._lock:
            sorted_jobs = sorted(self._jobs.values(), key=lambda j: j.created_ts, reverse=True)
            return [j.to_summary() for j in sorted_jobs]

    def add_event(self, job_id: str, event: Event) -> None:
        """Appends an event to the job with monotonic seq and broadcasts to subscribers."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            event.job_id = job_id
            event.seq = len(job.events)
            job.events.append(event)
            subscribers = list(job.subscribers)

        for q in subscribers:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass

    def subscribe(self, job_id: str) -> Optional[queue.Queue]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            q: queue.Queue = queue.Queue(maxsize=1000)
            job.subscribers.append(q)
            return q

    def unsubscribe(self, job_id: str, q: queue.Queue) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job and q in job.subscribers:
                job.subscribers.remove(q)


class JobRunner:
    """Manages background job execution via a ThreadPoolExecutor."""

    def __init__(self, store: JobStore, max_workers: Optional[int] = None):
        self.store = store
        self.max_workers = max_workers or settings.max_workers
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)

    def submit_job(self, job: Job) -> None:
        """Submits a conversion job to run asynchronously."""
        self._executor.submit(self._run_job_sync, job.job_id)

    def run_job_wait(self, job: Job) -> Job:
        """Runs the job synchronously and blocks until completion."""
        self._run_job_sync(job.job_id)
        return self.store.get_job(job.job_id) or job

    def _run_job_sync(self, job_id: str) -> None:
        job = self.store.get_job(job_id)
        if not job:
            return

        job.status = "running"

        def event_cb(event: Event):
            self.store.add_event(job_id, event)

        try:
            final_state = run_pipeline(
                job_id=job.job_id,
                raw_cobol=job.raw_cobol,
                filename=job.filename,
                options=job.options,
                event_callback=event_cb,
            )
            job.final_state = final_state
            job.status = final_state.get("status", "completed")
            job.retry_count = final_state.get("retry_count", 0)

            # Per docs/LOCAL_DEPLOYMENT_WORKFLOW.md step 5: a path-submitted
            # job's output lands back on disk under OUTPUT_ROOT, mirroring the
            # input's relative directory. Inline cobol_code jobs (no
            # source_path) have nowhere meaningful to mirror to, so they stay
            # preview-only.
            if job.source_path and job.status != "failed":
                resolved_code = final_state.get("optimized_code") or final_state.get("java_code") or ""
                ast = final_state.get("parsed_ast") or {}
                class_name = "".join(
                    part.capitalize()
                    for part in ast.get("program_id", "CobolProgram").replace("-", "_").split("_")
                ) or "CobolProgram"
                rel_dir = job.source_path.rsplit("/", 1)[0] if "/" in job.source_path else ""
                out_rel_path = f"{rel_dir}/{class_name}.java" if rel_dir else f"{class_name}.java"

                write_res = call_tool("write_output_file", path=out_rel_path, content=resolved_code)
                if write_res.success:
                    job.output_path = out_rel_path
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
        finally:
            job.finished_ts = time.time()
            # Broadcast terminal notification to wake SSE streams
            sentinel_event = Event(
                type=EventType.PIPELINE_FINISHED,
                agent=None,
                message=f"Job terminated with status: {job.status}",
                data={"status": job.status, "duration_ms": job.duration_ms},
            )
            for q in list(job.subscribers):
                try:
                    q.put_nowait(sentinel_event)
                except Exception:
                    pass

    def shutdown(self, wait: bool = False):
        self._executor.shutdown(wait=wait)


# Singletons
job_store = JobStore()
job_runner = JobRunner(job_store)
