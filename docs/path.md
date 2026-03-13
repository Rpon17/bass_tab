create_job_usecase를 보면 result_path를 아직 경로를 안정함 
이건 호출하는 단계에서 정할거임

{
  "result_id": "def456",
  "song_id": "abc123",
  "status": "done",
  "audio": {
    "original": { "exists": true, "download_url": "/results/def456/audio/original" },
    "bass_only": { "exists": true, "download_url": "/results/def456/audio/bass_only" },
    "bass_boosted": { "exists": false, "download_url": null }
  },
  "tab": {
    "root": { "exists": true, "download_url": "/results/def456/tab/root" },
    "full": { "exists": false, "download_url": null }
  }
}