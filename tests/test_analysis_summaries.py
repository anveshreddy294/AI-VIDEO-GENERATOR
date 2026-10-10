"""Source-list job summaries are observational and bound to owner/source/version."""
from app.services.pipeline_tracker import DurableJobStore, PipelineJob


def test_analysis_summary_retains_owned_warning_and_excludes_private_payload(tmp_path):
    store = DurableJobStore(tmp_path / 'jobs.sqlite3')
    job = PipelineJob(job_id='JOB_owned', job_type='source_ingestion', status='completed', is_finished=True,
        metadata={'source_owner': 'owner-a', 'source_id': 'source-a', 'source_version': 2, 'private': 'never-export'},
        result={'source_id': 'source-a', 'version': 2, 'content_ready': True,
            'warnings': ['PARTIAL_VISUAL_VERIFICATION', 'private-warning'], 'private_prompt': 'never-export'})
    store.save_job(job)
    summaries = store.source_analysis_summaries('owner-a')
    assert list(summaries) == [('source-a', 2)]
    summary = summaries[('source-a', 2)]
    assert summary['is_finished'] is True
    assert summary['result']['warnings'] == ['PARTIAL_VISUAL_VERIFICATION']
    assert 'never-export' not in str(summary)
    assert store.source_analysis_summaries('owner-b') == {}
    assert store.load_job('JOB_owned').status == 'completed'


def test_analysis_summary_selects_latest_job_for_each_exact_version(tmp_path):
    store = DurableJobStore(tmp_path / 'jobs.sqlite3')
    for job_id, version, created, status in [('JOB_old', 1, '2026-01-01', 'failed'), ('JOB_new', 1, '2026-01-02', 'running'), ('JOB_v2', 2, '2026-01-03', 'running')]:
        store.save_job(PipelineJob(job_id=job_id, job_type='source_ingestion', status=status,
            created_at=created, is_finished=status=='failed',
            metadata={'source_owner': 'owner-a', 'source_id': 'source-a', 'source_version': version}))
    summaries = store.source_analysis_summaries('owner-a')
    assert summaries[('source-a', 1)]['job_id'] == 'JOB_new'
    assert summaries[('source-a', 2)]['job_id'] == 'JOB_v2'
    assert summaries[('source-a', 1)]['is_finished'] is False


def test_asset_scripts_are_fixed_public_code_not_private_export_routes():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    for path in ['/assets/resource-exports.js', '/assets/analysis-results.js']:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('application/javascript')
    assert client.get('/assets/.env').status_code == 404


def test_failed_summary_supports_retry_without_exposing_diagnostic_content(tmp_path):
    from app.services.ingestion.failures import SourceFailure
    store = DurableJobStore(tmp_path / 'jobs.sqlite3')
    failure = SourceFailure(stage='EXTRACTION', code='VISION_EXTRACTION_FAILED', retryable=True,
        message='never-export', label_reference='hidden-model-output', vision_error_code='VISION_TIMEOUT')
    store.save_job(PipelineJob(job_id='JOB_failed', job_type='source_ingestion', status='failed', is_finished=True,
        metadata={'source_owner': 'owner-a', 'source_id': 'source-a', 'source_version': 1}, failure=failure))
    summary = store.source_analysis_summaries('owner-a')[('source-a', 1)]
    assert summary['failure']['retryable'] is True
    assert summary['failure']['vision_error_code'] == 'VISION_TIMEOUT'
    assert 'never-export' not in str(summary)
    assert 'hidden-model-output' not in str(summary)
