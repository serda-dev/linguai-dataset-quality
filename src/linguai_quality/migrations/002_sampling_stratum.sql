ALTER TABLE run_controls ADD COLUMN IF NOT EXISTS stratum text NOT NULL DEFAULT 'all'
    CHECK (stratum IN ('all', 'normal', 'noisy_edge', 'structured'));
