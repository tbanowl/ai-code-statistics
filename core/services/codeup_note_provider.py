from core.database.authorship_notes_db import AuthorshipNotesDatabase


class CodeupDatabaseNoteProvider:
    def __init__(self, database: AuthorshipNotesDatabase | None = None):
        self.database = database or AuthorshipNotesDatabase()

    def batch_get_note_contents(
        self, repo_url: str, commit_shas: list[str]
    ) -> dict[str, str]:
        result = self.database.batch_get_notes(repo_url, commit_shas)
        return {note["commit_sha"]: note["content"] for note in result["notes"]}
