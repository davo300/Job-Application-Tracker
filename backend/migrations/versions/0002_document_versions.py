"""Preserve document version metadata while allowing archive/restore."""

from alembic import op

revision = "0002_document_versions"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE FUNCTION protect_document_version() RETURNS trigger AS $$
        BEGIN
            IF ROW(NEW.id, NEW.user_id, NEW.kind, NEW.label, NEW.version_label,
                   NEW.storage_reference, NEW.created_at)
               IS DISTINCT FROM
               ROW(OLD.id, OLD.user_id, OLD.kind, OLD.label, OLD.version_label,
                   OLD.storage_reference, OLD.created_at) THEN
                RAISE EXCEPTION 'Document versions are immutable; create a new version instead';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER immutable_document_version BEFORE UPDATE ON documents
        FOR EACH ROW EXECUTE FUNCTION protect_document_version()
    """)


def downgrade():
    op.execute("DROP TRIGGER immutable_document_version ON documents")
    op.execute("DROP FUNCTION protect_document_version()")
