-- 0006_embedding_dimension.sql — pin ADR-0015's 384-dimension local embeddings.
-- 0003's vector(1536) was an explicit placeholder and remains immutable.

DO $$
DECLARE
    current_type TEXT;
BEGIN
    SELECT format_type(attribute.atttypid, attribute.atttypmod)
      INTO current_type
      FROM pg_attribute AS attribute
      JOIN pg_class AS relation ON relation.oid = attribute.attrelid
      JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
     WHERE namespace.nspname = 'vec'
       AND relation.relname = 'embeddings'
       AND attribute.attname = 'embedding'
       AND attribute.attnum > 0
       AND NOT attribute.attisdropped;

    IF current_type IS NOT NULL AND current_type <> 'vector(384)' THEN
        IF EXISTS (SELECT 1 FROM vec.embeddings) THEN
            RAISE EXCEPTION
                'cannot change embedding dimension on a non-empty corpus; re-embed explicitly';
        END IF;
        ALTER TABLE vec.embeddings DROP COLUMN embedding;
        ALTER TABLE vec.embeddings ADD COLUMN embedding vector(384) NOT NULL;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS corpus_documents_sha256_uidx
    ON vec.corpus_documents (sha256);
