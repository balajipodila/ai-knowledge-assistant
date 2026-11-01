from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.services.documents import DocumentService


class RecordingSession:
    def __init__(self) -> None:
        self.statement = None

    def scalar(self, statement):
        self.statement = statement
        return None

    def scalars(self, statement):
        self.statement = statement
        return self

    def all(self):
        return []


def test_document_lookup_always_filters_by_owner() -> None:
    owner_id = uuid4()
    document_id = uuid4()
    session = RecordingSession()

    result = DocumentService().get_document(
        session, user_id=owner_id, document_id=document_id
    )

    compiled = session.statement.compile(dialect=postgresql.dialect())
    assert result is None
    assert owner_id in compiled.params.values()
    assert document_id in compiled.params.values()


def test_document_list_always_filters_by_owner() -> None:
    owner_id = uuid4()
    session = RecordingSession()

    assert DocumentService().list_documents(session, user_id=owner_id) == []

    compiled = session.statement.compile(dialect=postgresql.dialect())
    assert owner_id in compiled.params.values()
