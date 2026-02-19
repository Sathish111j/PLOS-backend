import os

import psycopg


def _sync_dsn() -> str:
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:plos_db_secure_2025@supabase-db:5432/plos",
    )
    return dsn.replace("postgresql+asyncpg://", "postgresql://")


def test_kb_tables_exist() -> None:
    table_query = """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
    """
    with psycopg.connect(_sync_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(table_query, ("buckets",))
            assert cursor.fetchone()[0] is True

            cursor.execute(table_query, ("documents",))
            assert cursor.fetchone()[0] is True

            cursor.execute(table_query, ("document_versions",))
            assert cursor.fetchone()[0] is True

            cursor.execute(table_query, ("document_chunks",))
            assert cursor.fetchone()[0] is True

            cursor.execute(table_query, ("document_dedup_signatures",))
            assert cursor.fetchone()[0] is True

            cursor.execute(table_query, ("document_integrity_checks",))
            assert cursor.fetchone()[0] is True


def test_documents_critical_columns_exist() -> None:
    required_columns = {
        "id",
        "bucket_id",
        "content_type",
        "source_type",
        "storage_key",
        "status",
        "search_vector",
        "created_at",
        "updated_at",
    }

    with psycopg.connect(_sync_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'documents'
                """
            )
            found_columns = {row[0] for row in cursor.fetchall()}

    assert required_columns.issubset(found_columns)


def test_document_versions_unique_constraint() -> None:
    with psycopg.connect(_sync_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_constraint c
                    JOIN pg_class t ON c.conrelid = t.oid
                    JOIN pg_namespace n ON t.relnamespace = n.oid
                    WHERE n.nspname = 'public'
                    AND t.relname = 'document_versions'
                    AND c.contype = 'u'
                    AND pg_get_constraintdef(c.oid) ILIKE '%(document_id, version_number)%'
                )
                """
            )
            assert cursor.fetchone()[0] is True


def test_documents_indexes_exist() -> None:
    expected_indexes = {
        "idx_documents_bucket",
        "idx_documents_status",
        "idx_documents_content_type",
        "idx_documents_created_at",
        "idx_documents_search",
        "idx_documents_source_url",
    }

    with psycopg.connect(_sync_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = 'documents'
                """
            )
            found_indexes = {row[0] for row in cursor.fetchall()}

    assert expected_indexes.issubset(found_indexes)


def test_documents_search_trigger_exists() -> None:
    with psycopg.connect(_sync_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_trigger trg
                    JOIN pg_class tbl ON trg.tgrelid = tbl.oid
                    JOIN pg_namespace nsp ON tbl.relnamespace = nsp.oid
                    WHERE nsp.nspname = 'public'
                    AND tbl.relname = 'documents'
                    AND trg.tgname = 'trg_documents_search_vector'
                    AND NOT trg.tgisinternal
                )
                """
            )
            assert cursor.fetchone()[0] is True


def test_document_chunks_indexes_exist() -> None:
    expected_indexes = {
        "idx_document_chunks_document",
        "idx_document_chunks_content_type",
        "idx_document_chunks_tokens",
        "idx_document_chunks_section_heading",
        "idx_document_chunks_metadata",
        "idx_document_chunks_image_ids",
    }

    with psycopg.connect(_sync_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = 'document_chunks'
                """
            )
            found_indexes = {row[0] for row in cursor.fetchall()}

    assert expected_indexes.issubset(found_indexes)


def test_document_dedup_indexes_exist() -> None:
    expected_indexes = {
        "idx_document_dedup_sha256",
        "idx_document_dedup_simhash",
        "idx_document_dedup_simhash_bands",
        "idx_document_dedup_minhash_bands",
    }

    with psycopg.connect(_sync_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = 'document_dedup_signatures'
                """
            )
            found_indexes = {row[0] for row in cursor.fetchall()}

    assert expected_indexes.issubset(found_indexes)
