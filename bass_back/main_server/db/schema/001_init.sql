PRAGMA foreign_keys = ON;

-- song_id 테이블 
CREATE TABLE IF NOT EXISTS songs (
  song_id      TEXT PRIMARY KEY,
  title        TEXT NOT NULL,
  artist       TEXT NOT NULL,
  norm_title   TEXT NOT NULL,
  norm_artist  TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL,
  select_count INTEGER NOT NULL DEFAULT 0
);

-- norm_title과 norm_artist는 하나만 있어야함
CREATE UNIQUE INDEX IF NOT EXISTS ux_songs_norm_title_norm_artist
ON songs(norm_title, norm_artist);

-- 다 인덱스로 만들어서  찾기 빠르게
CREATE INDEX IF NOT EXISTS idx_songs_norm_title
ON songs(norm_title);

CREATE INDEX IF NOT EXISTS idx_songs_norm_artist
ON songs(norm_artist);

CREATE INDEX IF NOT EXISTS idx_songs_title_artist
ON songs(title, artist);

CREATE INDEX IF NOT EXISTS idx_songs_select_count_updated_at
ON songs(select_count DESC, updated_at DESC);


-- result_table
CREATE TABLE IF NOT EXISTS results (
  result_id     TEXT PRIMARY KEY,
  song_id       TEXT NOT NULL,
  source_url    TEXT NOT NULL,
  status        TEXT NOT NULL,             -- queued|running|done|failed
  error_message TEXT,

  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,

  FOREIGN KEY(song_id) REFERENCES songs(song_id) ON DELETE CASCADE,
  CHECK (status IN ('queued','running','done','failed'))
);

-- 여기도 다 인덱스로만듬
CREATE INDEX IF NOT EXISTS idx_results_song_id
ON results(song_id);

CREATE INDEX IF NOT EXISTS idx_results_status
ON results(status);

CREATE INDEX IF NOT EXISTS idx_results_created_at
ON results(created_at);

CREATE INDEX IF NOT EXISTS idx_results_updated_at
ON results(updated_at);



-- asset_id
CREATE TABLE IF NOT EXISTS assets (
  asset_id TEXT PRIMARY KEY,
  result_id TEXT NOT NULL,

  original_audio_path TEXT NOT NULL,
  bass_only_path TEXT,
  bass_removed_path TEXT,
  bass_boosted_path TEXT,

  original_tab_path TEXT NOT NULL,
  root_tab_path TEXT NOT NULL,

  created_at TEXT NOT NULL,

  FOREIGN KEY(result_id) REFERENCES results(result_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_assets_result_id
ON assets(result_id);

CREATE INDEX IF NOT EXISTS idx_assets_result_id
ON assets(result_id);