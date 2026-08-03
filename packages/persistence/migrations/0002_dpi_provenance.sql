-- 0002_dpi_provenance — el DPI del plano lleva su procedencia (ADR-006, OZ-9a).
--
-- El DPI puede venir del archivo (EXIF → observado) o asumirse por defecto (estimado).
-- Distinguirlos es el invariante de honestidad metrológica: un DPI asumido no puede viajar
-- como si fuera medido. El dominio lo modela con `Measured[float]`; la base lo refleja con
-- esta columna.
--
-- Los planos que ya existieran se marcan 'estimated': no sabemos de dónde salió su DPI, y
-- asumir el caso de menor confianza es lo honesto.
ALTER TABLE floor_plan ADD COLUMN dpi_provenance TEXT NOT NULL DEFAULT 'estimated';
