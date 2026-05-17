import json
from collections import defaultdict
from typing import Any


Attestations = dict[str, dict[int, str]]
Prompts = dict[str, dict[str, Any]]


class MergeAuthorshipCalculator:
    def merge_notes(
        self,
        target_note: str | None,
        source_notes: list[str | None],
        final_files: dict[str, list[str]],
    ) -> str:
        merged_attestations: Attestations = defaultdict(dict)
        merged_prompts: Prompts = {}

        target_attestations, target_prompts = self.parse_note(target_note or "")
        self._merge_attestations(
            merged_attestations, target_attestations, final_files, target_priority=True
        )
        merged_prompts.update(target_prompts)

        for source_note in source_notes:
            if not source_note:
                continue
            source_attestations, source_prompts = self.parse_note(source_note)
            self._merge_attestations(
                merged_attestations, source_attestations, final_files, target_priority=False
            )
            merged_prompts.update(source_prompts)

        return self.serialize_note(dict(merged_attestations), merged_prompts)

    def parse_note(self, content: str) -> tuple[Attestations, Prompts]:
        if not content:
            return {}, {}

        body, metadata = self._split_content(content)
        prompts = metadata.get("prompts", {}) if isinstance(metadata, dict) else {}
        attestations: Attestations = defaultdict(dict)
        current_file: str | None = None

        for raw_line in body.splitlines():
            if not raw_line.strip():
                continue
            if not raw_line.startswith(" "):
                current_file = raw_line.strip()
                continue
            if current_file is None:
                continue

            parts = raw_line.strip().split(maxsplit=1)
            if len(parts) != 2:
                continue
            prompt_id, ranges = parts
            for line_number in self._expand_ranges(ranges):
                attestations[current_file][line_number] = prompt_id

        return dict(attestations), prompts

    def serialize_note(self, attestations: Attestations, prompts: Prompts) -> str:
        lines: list[str] = []
        for file_path in sorted(attestations):
            by_prompt: dict[str, list[int]] = defaultdict(list)
            for line_number, prompt_id in sorted(attestations[file_path].items()):
                by_prompt[prompt_id].append(line_number)

            if not by_prompt:
                continue
            lines.append(file_path)
            for prompt_id in sorted(by_prompt):
                lines.append(f"  {prompt_id} {self._compact_ranges(by_prompt[prompt_id])}")

        metadata = {
            "schema_version": "3",
            "prompts": prompts,
        }
        return "\n".join(lines) + "\n---\n" + json.dumps(
            metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    def _merge_attestations(
        self,
        merged: Attestations,
        incoming: Attestations,
        final_files: dict[str, list[str]],
        target_priority: bool,
    ) -> None:
        for file_path, lines in incoming.items():
            if file_path not in final_files:
                continue
            max_line = len(final_files[file_path])
            for line_number, prompt_id in lines.items():
                if line_number < 1 or line_number > max_line:
                    continue
                if target_priority:
                    merged[file_path][line_number] = prompt_id
                else:
                    merged[file_path].setdefault(line_number, prompt_id)

    def _split_content(self, content: str) -> tuple[str, dict[str, Any]]:
        body, separator, metadata_content = content.partition("\n---\n")
        if not separator:
            return content, {}
        return body, json.loads(metadata_content or "{}")

    def _expand_ranges(self, ranges: str) -> list[int]:
        line_numbers: list[int] = []
        for part in ranges.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                start_text, end_text = part.split("-", 1)
                start = int(start_text)
                end = int(end_text)
                line_numbers.extend(range(start, end + 1))
            else:
                line_numbers.append(int(part))
        return line_numbers

    def _compact_ranges(self, line_numbers: list[int]) -> str:
        if not line_numbers:
            return ""

        ranges: list[str] = []
        sorted_lines = sorted(set(line_numbers))
        start = previous = sorted_lines[0]

        for line_number in sorted_lines[1:]:
            if line_number == previous + 1:
                previous = line_number
                continue
            ranges.append(self._format_range(start, previous))
            start = previous = line_number

        ranges.append(self._format_range(start, previous))
        return ",".join(ranges)

    def _format_range(self, start: int, end: int) -> str:
        if start == end:
            return str(start)
        return f"{start}-{end}"
