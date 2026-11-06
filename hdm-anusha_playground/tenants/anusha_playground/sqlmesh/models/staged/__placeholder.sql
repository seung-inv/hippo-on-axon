-- Minimal placeholder model so that SQLMesh recognizes this project.
-- For one thing, it will make `make sqlmesh-info` work.
-- It can be deleted once real models are added.

MODEL (
    name staged.__placeholder,
    kind FULL
);

SELECT
    1 AS _placeholder
