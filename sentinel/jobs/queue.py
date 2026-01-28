"""Simple FIFO job queue."""

from __future__ import annotations

import asyncio
from typing import Optional

from sentinel.jobs.types import Job


class Queue:
    """Thread-safe FIFO job queue with deduplication."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._jobs: list[Job] = []

    async def enqueue(self, job: Job) -> bool:
        """
        Add a job to the end of the queue.

        Returns True if enqueued, False if already present (deduplicated).
        """
        async with self._lock:
            if self.contains(job.id()):
                return False
            self._jobs.append(job)
            return True

    def contains(self, job_id: str) -> bool:
        """Check if a job is in the queue."""
        return any(j.id() == job_id for j in self._jobs)

    def peek(self) -> Optional[Job]:
        """Get the first job without removing it."""
        return self._jobs[0] if self._jobs else None

    async def remove(self, job_id: str) -> Optional[Job]:
        """Remove and return a job by ID."""
        async with self._lock:
            for i, j in enumerate(self._jobs):
                if j.id() == job_id:
                    return self._jobs.pop(i)
            return None

    def get_all(self) -> list[Job]:
        """Get all jobs in queue order."""
        return list(self._jobs)

    def list(self) -> list[str]:
        """Return list of job IDs in order."""
        return [j.id() for j in self._jobs]

    def __len__(self) -> int:
        """Return number of jobs in queue."""
        return len(self._jobs)
