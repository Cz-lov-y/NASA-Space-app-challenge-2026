"""Small process-local job manager for a future human-built research frontend.

Provider access only happens inside an explicitly submitted runner. Creating a
manager or polling never starts research. Do not share one user's credentials or
jobs with other users. This is not a persistent/distributed task queue.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event, RLock
import math
import time
import uuid

from src.regional_research import research_context_key
from src.regional_workflow import research_selected_region


class ResearchJobs:
    """Bound workers/queued requests, deduplicate context and suppress stale results.

    timeout_seconds is a display/result deadline from submission, including queue
    time. Python cannot forcibly stop a running thread or network call. Timed-out
    and cancelled running jobs continue consuming capacity until their runner
    returns; their result is never exposed. Production HTTP adapters have their
    own connect/read timeouts. Injected runners must also bound their I/O.
    """
    def __init__(self, *, max_workers=2, max_pending=4, max_history=64,
                 timeout_seconds=240, runner=research_selected_region, clock=time.monotonic):
        if (not isinstance(max_workers, int) or isinstance(max_workers, bool) or not 1 <= max_workers <= 2
                or not isinstance(max_pending, int) or isinstance(max_pending, bool) or not 0 <= max_pending <= 16
                or not isinstance(max_history, int) or max_history < max_workers + max_pending
                or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
            raise ValueError('Invalid job manager limits')
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='regional-research')
        self._capacity = max_workers + max_pending
        self._history = max_history
        self._timeout = timeout_seconds
        self._runner, self._clock = runner, clock
        self._lock = RLock()
        self._jobs = {}
        self._by_context = {}
        self._closed = False

    def _refresh(self, job):
        if job['state'] in ('cancelled', 'timed_out', 'complete', 'failed'):
            return
        future = job['future']
        finished_at = job['timing']['finished_at']
        deadline = job['submitted_at'] + self._timeout
        if ((finished_at is None and self._clock() >= deadline)
                or (finished_at is not None and finished_at >= deadline)):
            job.update(state='timed_out', error_code='deadline_exceeded')
            job['cancel_event'].set()  # Queued wrapper skips I/O; running work cannot stop.
        elif future.cancelled():
            job.update(state='cancelled', error_code=None)
        elif future.done():
            try:
                report = future.result()
                if not isinstance(report, dict) or report.get('region_id') != job['region_id']:
                    raise ValueError('Invalid runner result')
                job.update(state='complete', report=deepcopy(report), error_code=None)
            except Exception:
                # Never return provider exception strings, tracebacks or keys.
                job.update(state='failed', error_code='research_failed')
        else:
            job['state'] = 'loading' if future.running() else 'queued'

    @staticmethod
    def _snapshot(job):
        result = {k: job[k] for k in ('request_id', 'region_id', 'context_key', 'state', 'error_code')}
        result['report'] = deepcopy(job.get('report')) if job['state'] == 'complete' else None
        return result

    def submit(self, bundle, **provider_kwargs):
        """Submit explicitly; an existing active/successful exact context is reused.

        Reject a full queue with RuntimeError; do not silently queue unlimited
        paid requests. Return an opaque request ID plus selection context key.
        """
        context = bundle['research_context']
        region = bundle['region_id']
        if region != context['region_id']:
            raise ValueError('Region/context mismatch')
        key = research_context_key(context)
        with self._lock:
            if self._closed:
                raise RuntimeError('Research job manager is closed')
            for job in self._jobs.values():
                self._refresh(job)
            previous = self._by_context.get(key)
            if previous in self._jobs:
                job = self._jobs[previous]
                if job['state'] in ('queued', 'loading', 'complete'):
                    return self._snapshot(job)
            active = sum(not job['future'].done() for job in self._jobs.values())
            if active >= self._capacity:
                raise RuntimeError('Research queue is full')
            while len(self._jobs) >= self._history:
                oldest = next((rid for rid,j in self._jobs.items() if j['future'].done()), None)
                if oldest is None:
                    raise RuntimeError('Research queue is full')
                old = self._jobs.pop(oldest)
                if self._by_context.get(old['context_key']) == oldest:
                    self._by_context.pop(old['context_key'])
            request_id = uuid.uuid4().hex
            # Snapshot before leaving the caller: selection mutations cannot alter work.
            snapshot, options, cancelled = deepcopy(bundle), deepcopy(provider_kwargs), Event()
            timing = {'finished_at': None}
            def execute():
                try:
                    if cancelled.is_set():
                        return None
                    return self._runner(snapshot, **options)
                finally:
                    timing['finished_at'] = self._clock()
            future = self._executor.submit(execute)
            job = {'request_id': request_id, 'region_id': region, 'context_key': key,
                   'state': 'queued', 'error_code': None, 'submitted_at': self._clock(),
                   'future': future, 'cancel_event': cancelled, 'timing': timing}
            self._jobs[request_id] = job
            self._by_context[key] = request_id
            self._refresh(job)
            return self._snapshot(job)

    def poll(self, request_id, *, region_id, context_key):
        """Only return a result matching the current selected region AND context.

        Store the latest request_id in the frontend selection state. A response
        for an earlier ID must not replace a later selection's response.
        """
        with self._lock:
            job = self._jobs.get(request_id)
            if job is None:
                return {'request_id': request_id, 'state': 'unknown', 'report': None}
            if job['region_id'] != region_id or job['context_key'] != context_key:
                return {'request_id': request_id, 'state': 'stale', 'report': None}
            self._refresh(job)
            return self._snapshot(job)

    def cancel(self, request_id):
        """Suppress delivery immediately; queued jobs cancel, running calls finish."""
        with self._lock:
            job = self._jobs.get(request_id)
            if job is None:
                return False
            job['cancel_event'].set()
            job.update(state='cancelled', report=None, error_code=None)
            return True

    def close(self, *, wait=False):
        """Reject new work and suppress all results; running I/O may still finish."""
        with self._lock:
            self._closed = True
            for job in self._jobs.values():
                job['cancel_event'].set()
                job.update(state='cancelled', report=None, error_code=None)
        self._executor.shutdown(wait=wait, cancel_futures=True)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
