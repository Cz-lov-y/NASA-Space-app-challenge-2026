"""No-network concurrency checks with event-controlled runners."""
from copy import deepcopy
from threading import Event
import time

import pytest

from src.research_jobs import ResearchJobs


def bundle(region='cell'):
    return {'region_id': region, 'research_context': {'region_id': region, 'bbox': [0,0,10,10],
        'dataset_version': 'release-v1', 'period': ['2003', '2024'], 'jurisdictions': [{'name': 'Country'}]}}


def finished(manager, request, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = manager.poll(request['request_id'], region_id=request['region_id'], context_key=request['context_key'])
        if result['state'] not in ('queued','loading'):
            return result
        time.sleep(.005)
    pytest.fail('runner did not finish')


def test_duplicate_jobs_snapshot_selection_and_stale_result_suppression():
    started, release = Event(), Event()
    calls = []
    def runner(data):
        calls.append(deepcopy(data))
        started.set()
        assert release.wait(2)
        return {'region_id': data['region_id'], 'status': 'complete'}
    manager = ResearchJobs(runner=runner)
    try:
        data = bundle()
        request = manager.submit(data)
        assert started.wait(1)
        assert manager.submit(data)['request_id'] == request['request_id']
        data['region_id'] = 'mutated'
        data['research_context']['bbox'] = [10,10,20,20]
        assert calls[0]['region_id'] == 'cell'
        assert manager.poll(request['request_id'], region_id='other', context_key=request['context_key'])['state'] == 'stale'
        release.set()
        result = finished(manager, request)
        assert result['state'] == 'complete' and result['report']['region_id'] == 'cell'
        result['report']['region_id'] = 'external-mutation'
        assert finished(manager, request)['report']['region_id'] == 'cell'
        assert manager.poll(request['request_id'], region_id='cell', context_key='old-version')['report'] is None
        assert len(calls) == 1
    finally:
        release.set()
        manager.close(wait=True)


def test_bounded_queue_and_queued_cancellation_never_starts_provider():
    started, release = Event(), Event()
    calls = []
    def runner(data):
        calls.append(data['region_id'])
        started.set()
        assert release.wait(2)
        return {'region_id': data['region_id']}
    manager = ResearchJobs(max_workers=1,max_pending=1,runner=runner)
    try:
        first = manager.submit(bundle('one'))
        assert started.wait(1)
        second = manager.submit(bundle('two'))
        assert second['state'] == 'queued'
        with pytest.raises(RuntimeError,match='full'):
            manager.submit(bundle('three'))
        assert manager.cancel(second['request_id'])
        # Cancelled physical queue entries still count until dequeued, preventing
        # repeated cancel/submit from growing ThreadPoolExecutor's internal queue.
        with pytest.raises(RuntimeError,match='full'):
            manager.submit(bundle('three'))
        release.set()
        assert finished(manager,first)['state'] == 'complete'
        manager.close(wait=True)
        assert calls == ['one']
        assert manager.poll(second['request_id'],region_id='two',context_key=second['context_key'])['state'] == 'cancelled'
    finally:
        release.set()
        manager.close(wait=True)


def test_deadline_suppresses_late_completion_and_keeps_running_capacity():
    started, release = Event(), Event()
    ticks = [0]
    def runner(data):
        started.set()
        assert release.wait(2)
        return {'region_id': data['region_id']}
    manager = ResearchJobs(max_workers=1,max_pending=0,timeout_seconds=10,runner=runner,clock=lambda:ticks[0])
    try:
        request=manager.submit(bundle())
        assert started.wait(1)
        ticks[0] = 11
        result=finished(manager,request)
        assert result['state']=='timed_out' and result['report'] is None
        with pytest.raises(RuntimeError,match='full'):
            manager.submit(bundle('another'))
        release.set()
        manager.close(wait=True)
        assert finished(manager,request)['report'] is None
    finally:
        release.set()
        manager.close(wait=True)


def test_provider_errors_and_region_mismatch_are_sanitized():
    def fail(data):
        raise RuntimeError('secret-token-dont-display')
    manager=ResearchJobs(runner=fail)
    try:
        result=finished(manager,manager.submit(bundle()))
        assert result['state']=='failed'
        assert result['error_code']=='research_failed'
        assert 'secret-token' not in str(result)
    finally:
        manager.close(wait=True)
    manager=ResearchJobs(runner=lambda data:{'region_id':'wrong'})
    try:
        assert finished(manager,manager.submit(bundle()))['state']=='failed'
    finally:
        manager.close(wait=True)


def test_closed_manager_refuses_work_and_unknown_id_is_empty():
    manager=ResearchJobs(runner=lambda data:{'region_id':data['region_id']})
    manager.close()
    with pytest.raises(RuntimeError,match='closed'):
        manager.submit(bundle())
    assert manager.poll('unknown',region_id='cell',context_key='key')['report'] is None
    assert not manager.cancel('unknown')


def test_completed_before_deadline_still_delivers_when_polled_later():
    ticks=[0]
    manager=ResearchJobs(runner=lambda data:{'region_id':data['region_id']},timeout_seconds=10,clock=lambda:ticks[0])
    try:
        request=manager.submit(bundle())
        # Wait using the Future's lifecycle, without advancing the injected clock.
        manager._jobs[request['request_id']]['future'].result(timeout=1)
        ticks[0]=100
        assert finished(manager,request)['state']=='complete'
    finally:
        manager.close(wait=True)
