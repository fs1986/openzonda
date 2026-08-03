-- 0001_init — esquema inicial del proyecto de survey (diseño §8.2).
--
-- Convenciones:
--   * Los identificadores de entidad son UUID en texto: el dominio los genera, no la base.
--     Así una entidad existe y es identificable antes de haberse persistido nunca.
--   * ON DELETE CASCADE en toda la jerarquía de proyecto: borrar un proyecto borra sus
--     sitios, plantas y planos. Las mediciones NO cuelgan de esa cascada por accidente,
--     sino explícitamente, porque perderlas en silencio sería perder trabajo de campo.
--   * `position` conserva el orden que el usuario ve. Sin él, un SELECT devolvería las
--     plantas en el orden que le convenga al motor.

CREATE TABLE project (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    schema_version INTEGER NOT NULL
) STRICT;

CREATE TABLE site (
    id         TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    position   INTEGER NOT NULL DEFAULT 0
) STRICT;

CREATE TABLE floor_plan (
    id                TEXT PRIMARY KEY,
    asset_sha256      TEXT NOT NULL,
    width_px          INTEGER NOT NULL,
    height_px         INTEGER NOT NULL,
    dpi               REAL NOT NULL,
    rotation_degrees  REAL NOT NULL DEFAULT 0.0,
    -- Calibración embebida: una escala pertenece a un plano concreto y no se comparte.
    -- NULL en las cuatro columnas significa «plano sin calibrar», que es un estado
    -- legítimo y distinto de una escala de cero.
    cal_meters_per_pixel   REAL,
    cal_pixel_distance     REAL,
    cal_real_distance_m    REAL,
    cal_click_uncertainty  REAL,
    CHECK (
        (cal_meters_per_pixel IS NULL AND cal_pixel_distance IS NULL
         AND cal_real_distance_m IS NULL AND cal_click_uncertainty IS NULL)
        OR
        (cal_meters_per_pixel IS NOT NULL AND cal_pixel_distance IS NOT NULL
         AND cal_real_distance_m IS NOT NULL AND cal_click_uncertainty IS NOT NULL)
    )
) STRICT;

CREATE TABLE floor (
    id            TEXT PRIMARY KEY,
    site_id       TEXT NOT NULL REFERENCES site(id) ON DELETE CASCADE,
    plan_id       TEXT NOT NULL REFERENCES floor_plan(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    level         INTEGER NOT NULL,
    height_m      REAL,
    position      INTEGER NOT NULL DEFAULT 0,
    UNIQUE (site_id, level)
) STRICT;

CREATE TABLE adapter_profile (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    driver_version  TEXT NOT NULL,
    rssi_offset_db  REAL NOT NULL DEFAULT 0.0
) STRICT;

CREATE TABLE survey_session (
    id                  TEXT PRIMARY KEY,
    floor_id            TEXT REFERENCES floor(id) ON DELETE SET NULL,
    adapter_profile_id  TEXT NOT NULL REFERENCES adapter_profile(id),
    mode                TEXT NOT NULL,
    started_at_utc      TEXT NOT NULL
) STRICT;

CREATE TABLE bss (
    bssid            TEXT PRIMARY KEY,
    ssid             TEXT,
    oui              TEXT NOT NULL,
    security         TEXT,
    ies              BLOB,
    ies_parsed       TEXT,
    qbss_sta_count   INTEGER,
    qbss_chan_util   REAL,
    last_seen_utc    TEXT
) STRICT;

CREATE TABLE measurement (
    id                  INTEGER PRIMARY KEY,
    session_id          TEXT NOT NULL REFERENCES survey_session(id) ON DELETE CASCADE,
    ts_utc              TEXT NOT NULL,
    ts_mono_ns          INTEGER,
    x_px                REAL NOT NULL,
    y_px                REAL NOT NULL,
    -- La procedencia viaja con el dato, no con la muestra entera (diseño §10.1):
    -- en modo continuo la posición es derivada mientras el RSSI sigue observado.
    position_provenance TEXT NOT NULL,
    bssid               TEXT NOT NULL REFERENCES bss(bssid),
    ssid                TEXT,
    -- NULL significa «no disponible», nunca cero. El motivo se guarda aparte para
    -- poder decir *por qué* falta (diseño §5: la mayoría de drivers no dan noise).
    rssi_dbm            REAL,
    rssi_unavailable    TEXT,
    noise_dbm           REAL,
    noise_unavailable   TEXT,
    freq_mhz            INTEGER,
    channel             INTEGER,
    chan_width_mhz      INTEGER,
    phy                 TEXT,
    source              TEXT NOT NULL,
    quality_flags       INTEGER NOT NULL DEFAULT 0,
    CHECK (rssi_dbm IS NULL OR rssi_unavailable IS NULL),
    CHECK (noise_dbm IS NULL OR noise_unavailable IS NULL)
) STRICT;

-- Índices del diseño §8.2.
CREATE INDEX idx_measurement_session_ts ON measurement (session_id, ts_utc);
CREATE INDEX idx_measurement_bssid_session ON measurement (bssid, session_id);
CREATE INDEX idx_site_project ON site (project_id);
CREATE INDEX idx_floor_site ON floor (site_id);
