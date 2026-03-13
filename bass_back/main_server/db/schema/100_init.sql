PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS songs (
  song_id      TEXT PRIMARY KEY,
  title        TEXT NOT NULL,
  artist       TEXT NOT NULL,
  norm_title   TEXT NOT NULL,
  norm_artist  TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_songs_norm_title_norm_artist
ON songs(norm_title, norm_artist);

CREATE TABLE IF NOT EXISTS results (
  result_id      TEXT PRIMARY KEY,
  song_id        TEXT NOT NULL,
  job_id         TEXT NOT NULL,
  status         TEXT NOT NULL,
  error_message  TEXT,
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL,
  FOREIGN KEY(song_id) REFERENCES songs(song_id) ON DELETE CASCADE,
  CHECK (status IN ('queued', 'running', 'done', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_results_song_id
ON results(song_id);

CREATE TABLE IF NOT EXISTS assets (
  asset_id                  TEXT PRIMARY KEY,
  result_id                 TEXT NOT NULL UNIQUE,
  asset_root_path           TEXT NOT NULL,

  audio_original_path       TEXT,
  audio_bass_only_path      TEXT,
  audio_bass_removed_path   TEXT,
  audio_bass_boosted_path   TEXT,

  tab_original_path         TEXT,
  tab_root_path             TEXT,

  created_at                TEXT NOT NULL,
  FOREIGN KEY(result_id) REFERENCES results(result_id) ON DELETE CASCADE
);