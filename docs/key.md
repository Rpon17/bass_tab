| 역할           | Redis 타입      | 예시 키                 |
| ------------ | ------------- | -------------------- |
| 큐              | list          | `bass:queue:youtube` |
| job 본문        | hash / string | `bass:job:{job_id}`  |
| submitted 집합 | set           | `bass:submitted`     |
| lock           | string        | `bass:lock:{job_id}` |

`bass:queue:youtube` -> 작업 대기중인 job_id를 모은 list형태
`bass:job:{job_id}` -> job이 실제로 들고있는 내용물 hash형태
`bass:submitted`  -> ml_server로 보낸 job_id들의 집합형태
`bass:lock:{job_id}` -> 락을 잠근 하나의 job_id의 string 형태


id는 3개가 있음
Song (song_id)
 └── Result (result_id)
       ├── Asset (asset_id)  bass.wav
       ├── Asset (asset_id)  bass_only.wav
       └── Asset (asset_id)  tab.json

넘겨줄 

result_dir = "songs" / asset_id / "results" / job_id