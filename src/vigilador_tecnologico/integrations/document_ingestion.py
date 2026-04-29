from __future__ import annotations

import base64
from dataclasses import dataclass
import csv
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
import zlib
from io import BytesIO
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlparse

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from vigilador_tecnologico.contracts.models import SourceType
from vigilador_tecnologico.integrations.credentials import MissingCredentialError
from vigilador_tecnologico.integrations.gemini import GeminiAdapter, GeminiAdapterError
from vigilador_tecnologico.integrations.model_profiles import (
    GEMINI_ROBOTICS_ER_15_MODEL,
    GEMINI_ROBOTICS_ER_16_MODEL,
    GEMMA_4_26B_MODEL,
)
from vigilador_tecnologico.integrations.retry import call_with_retry


_PDF_STREAM_PATTERN = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.S)
_PDF_LITERAL_PATTERN = re.compile(r"\(((?:\\.|[^\\)])*)\)\s*T[Jj]", re.S)
_PDF_ARRAY_PATTERN = re.compile(r"\[(.*?)\]\s*TJ", re.S)
_DOCX_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_PPTX_NAMESPACE = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_XLSX_NAMESPACE = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL_NAMESPACE = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL_NAMESPACE = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_COMPLEX_SOURCE_TYPES = {"pdf", "image", "docx", "pptx", "sheet"}


@dataclass(slots=True)
class IngestedDocument:
    source_uri: str
    source_type: SourceType
    mime_type: str
    raw_text: str
    page_count: int
    ingestion_engine: str = "local"
    model: str | None = None
    fallback_reason: str | None = None


class DocumentIngestionError(RuntimeError):
    pass


class DocumentIngestionAdapter:
    def ingest(self, source_uri: str, source_type: str | None = None) -> IngestedDocument:
        path = _resolve_source_path(source_uri)
        if not path.exists():
            raise DocumentIngestionError(f"Document not found: {source_uri}")

        resolved_type = _resolve_source_type(path, source_type)
        mime_type = _guess_mime_type(path, resolved_type)

        if resolved_type == "pdf":
            raw_text, page_count = _read_pdf(path)
        elif resolved_type == "docx":
            raw_text, page_count = _read_docx(path)
        elif resolved_type == "pptx":
            raw_text, page_count = _read_pptx(path)
        elif resolved_type == "sheet":
            raw_text, page_count = _read_sheet(path)
        elif resolved_type == "image":
            raw_text, page_count = _read_image(path)
        else:
            raw_text, page_count = _read_text(path)

        return IngestedDocument(
            source_uri=source_uri,
            source_type=resolved_type,
            mime_type=mime_type,
            raw_text=raw_text,
            page_count=page_count,
        )


class ModelDocumentIngestionAdapter:
    def __init__(
        self,
        primary_model: str = GEMINI_ROBOTICS_ER_16_MODEL,
        secondary_model: str = GEMINI_ROBOTICS_ER_15_MODEL,
        fallback_model: str = GEMMA_4_26B_MODEL,
        retry_attempts: int = 2,
        retry_delay_seconds: float = 1.0,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.primary_model = primary_model
        self.secondary_model = secondary_model
        self.fallback_model = fallback_model
        self.retry_attempts = retry_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.timeout_seconds = timeout_seconds

    def ingest(self, source_uri: str, source_type: str | None = None) -> IngestedDocument:
        path = _resolve_source_path(source_uri)
        if not path.exists():
            raise DocumentIngestionError(f"Document not found: {source_uri}")

        resolved_type = _resolve_source_type(path, source_type)
        mime_type = _guess_mime_type(path, resolved_type)
        if resolved_type not in _COMPLEX_SOURCE_TYPES:
            raise DocumentIngestionError(f"Model ingestion is not required for source type: {resolved_type}")

        document_bytes = path.read_bytes()
        last_error: Exception | None = None
        for model in (self.primary_model, self.secondary_model, self.fallback_model):
            try:
                return self._ingest_with_model(
                    model=model,
                    source_uri=source_uri,
                    source_type=resolved_type,
                    mime_type=mime_type,
                    document_bytes=document_bytes,
                )
            except (GeminiAdapterError, MissingCredentialError, DocumentIngestionError, TimeoutError, OSError) as error:
                last_error = error

        if last_error is not None:
            raise DocumentIngestionError(str(last_error)) from last_error
        raise DocumentIngestionError("Model ingestion failed without a provider error")

    def _ingest_with_model(
        self,
        *,
        model: str,
        source_uri: str,
        source_type: SourceType,
        mime_type: str,
        document_bytes: bytes,
    ) -> IngestedDocument:
        adapter = GeminiAdapter(model=model)
        is_robotics = "robotics" in model.lower()

        # Handling for robotics models that don't support PDF natively
        if is_robotics and source_type == "pdf":
            if fitz is None:
                raise DocumentIngestionError(
                    f"Model {model} requires PDF rasterization but 'pymupdf' is not installed."
                )

            # Rasterize PDF to images
            doc = fitz.open(stream=document_bytes, filetype="pdf")
            all_text_parts = []
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72))  # 300 DPI
                img_bytes = pix.tobytes("jpg")

                response = call_with_retry(
                    adapter.generate_content_parts,
                    [
                        {"text": self._prompt(source_type)},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": base64.b64encode(img_bytes).decode("ascii"),
                            }
                        },
                    ],
                    attempts=self.retry_attempts,
                    delay_seconds=self.retry_delay_seconds,
                    system_instruction=self._system_instruction(is_robotics),
                    generation_config={
                        "temperature": 0.0,
                        "responseMimeType": "application/json",
                    },
                    timeout=self.timeout_seconds,
                )
                payload = _parse_model_json_response(response)
                page_text = str(payload.get("raw_text") or payload.get("text") or "")
                if page_text.strip():
                    all_text_parts.append(page_text)

            raw_text = _normalize_text("\n\n".join(all_text_parts))
            page_count = len(doc)
            doc.close()
        else:
            # Standard multimodal path
            response = call_with_retry(
                adapter.generate_content_parts,
                [
                    {"text": self._prompt(source_type)},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(document_bytes).decode("ascii"),
                        }
                    },
                ],
                attempts=self.retry_attempts,
                delay_seconds=self.retry_delay_seconds,
                system_instruction=self._system_instruction(is_robotics),
                generation_config={
                    "temperature": 0.0,
                    "responseMimeType": "application/json",
                },
                timeout=self.timeout_seconds,
            )
            payload = _parse_model_json_response(response)
            raw_text = _normalize_text(str(payload.get("raw_text") or payload.get("text") or ""))
            page_count = _coerce_positive_int(payload.get("page_count"), 1)
        self._validate_model_payload(raw_text=raw_text, page_count=page_count, model=model)
        return IngestedDocument(
            source_uri=source_uri,
            source_type=source_type,
            mime_type=mime_type,
            raw_text=raw_text,
            page_count=page_count,
            ingestion_engine="gemini",
            model=model,
        )

    def _validate_model_payload(self, *, raw_text: str, page_count: int, model: str) -> None:
        if not raw_text.strip():
            raise DocumentIngestionError(f"Model ingestion returned empty raw_text for {model}")
        if page_count < 1:
            raise DocumentIngestionError(f"Model ingestion returned invalid page_count for {model}: {page_count}")

    def _prompt(self, source_type: SourceType) -> str:
        return (
            f"Parse this {source_type} document for a technology surveillance pipeline. "
            "Return JSON with raw_text and page_count. Preserve tables as tab-separated text. "
            "Do not summarize and do not add commentary."
        )

    def _system_instruction(self, is_robotics: bool) -> str:
        if is_robotics:
            return (
                "Be precise. When JSON is requested, reply with ONLY that JSON (no preface, no code block). "
                "Extract all visible text from the document image faithfully."
            )
        return "Extract document text and return only JSON."


class MultimodalDocumentIngestionAdapter:
    def __init__(
        self,
        model_adapter: ModelDocumentIngestionAdapter | None = None,
        local_adapter: DocumentIngestionAdapter | None = None,
    ) -> None:
        self.model_adapter = model_adapter or ModelDocumentIngestionAdapter()
        self.local_adapter = local_adapter or DocumentIngestionAdapter()

    def ingest(self, source_uri: str, source_type: str | None = None) -> IngestedDocument:
        resolved_type = self._resolve_type_for_routing(source_uri, source_type)
        if resolved_type not in _COMPLEX_SOURCE_TYPES:
            return self.local_adapter.ingest(source_uri, source_type)

        try:
            return self.model_adapter.ingest(source_uri, source_type)
        except Exception as error:
            fallback = self.local_adapter.ingest(source_uri, source_type)
            return IngestedDocument(
                source_uri=fallback.source_uri,
                source_type=fallback.source_type,
                mime_type=fallback.mime_type,
                raw_text=fallback.raw_text,
                page_count=fallback.page_count,
                ingestion_engine="local",
                model=fallback.model,
                fallback_reason=str(error),
            )

    def _resolve_type_for_routing(self, source_uri: str, source_type: str | None) -> SourceType:
        try:
            path = _resolve_source_path(source_uri)
            return _resolve_source_type(path, source_type)
        except DocumentIngestionError:
            return "text"


def _resolve_source_path(source_uri: str) -> Path:
    parsed = urlparse(source_uri)
    if parsed.scheme == "file":
        raw_path = unquote(parsed.path)
        if parsed.netloc:
            raw_path = f"//{parsed.netloc}{raw_path}"
        if os.name == "nt" and raw_path.startswith("/") and len(raw_path) > 2 and raw_path[2] == ":":
            raw_path = raw_path.lstrip("/")
        return Path(raw_path).expanduser()
    if parsed.scheme:
        raise DocumentIngestionError(f"Unsupported URI scheme: {parsed.scheme}")
    return Path(source_uri).expanduser()


def _parse_model_json_response(response: dict[str, object]) -> dict[str, object]:
    if isinstance(response.get("raw_text"), str):
        return response

    text = _extract_model_text(response).strip()
    if not text:
        return {}

    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise DocumentIngestionError(f"Model ingestion response is not valid JSON: {text}") from error
    if not isinstance(payload, dict):
        raise DocumentIngestionError("Model ingestion response must be a JSON object")
    return payload


def _extract_model_text(response: dict[str, object]) -> str:
    direct_text = response.get("text")
    if isinstance(direct_text, str):
        return direct_text

    candidates = response.get("candidates")
    if not isinstance(candidates, list):
        return ""

    parts: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        content_parts = content.get("parts")
        if not isinstance(content_parts, list):
            continue
        for part in content_parts:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
    return "\n".join(parts)


def _coerce_positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, parsed)


def _resolve_source_type(path: Path, source_type: str | None) -> SourceType:
    if source_type:
        normalized = source_type.lower().strip()
        if normalized in {"txt", "md", "markdown"}:
            return "text"
        if normalized in {"pdf", "image", "docx", "pptx", "sheet", "text"}:
            return cast(SourceType, normalized)
        raise DocumentIngestionError(f"Unsupported source type: {source_type}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".docx"}:
        return "docx"
    if suffix in {".pptx"}:
        return "pptx"
    if suffix in {".xlsx", ".xlsm", ".csv", ".tsv"}:
        return "sheet"
    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}:
        return "image"
    return "text"


def _guess_mime_type(path: Path, source_type: SourceType) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    if source_type == "pdf":
        return "application/pdf"
    if source_type == "docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if source_type == "pptx":
        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    if source_type == "sheet":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if source_type == "image":
        return "image/*"
    return "text/plain"


def _read_text(path: Path) -> tuple[str, int]:
    return _normalize_text(path.read_text(encoding="utf-8", errors="ignore")), 1


def _read_pdf(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    page_count = max(1, len(re.findall(rb"/Type\s*/Page\b", data)))
    pieces: list[str] = []
    for stream in _iter_pdf_streams(data):
        text = _extract_pdf_text(stream)
        if text:
            pieces.append(text)
    if not pieces:
        pieces.append(_extract_pdf_text(data))
    return _normalize_text("\n\n".join(piece for piece in pieces if piece)), page_count


def _iter_pdf_streams(data: bytes) -> list[bytes]:
    streams: list[bytes] = []
    for match in _PDF_STREAM_PATTERN.finditer(data):
        stream = match.group(1).strip(b"\r\n")
        streams.append(_maybe_decompress(stream))
    return streams


def _maybe_decompress(stream: bytes) -> bytes:
    try:
        return zlib.decompress(stream)
    except Exception:
        return stream


def _extract_pdf_text(data: bytes) -> str:
    text = data.decode("latin-1", errors="ignore")
    pieces: list[str] = []
    for literal in _PDF_LITERAL_PATTERN.finditer(text):
        decoded = _decode_pdf_literal_string(literal.group(1))
        if decoded:
            pieces.append(decoded)
    for array_match in _PDF_ARRAY_PATTERN.finditer(text):
        for literal in re.finditer(r"\(((?:\\.|[^\\)])*)\)", array_match.group(1), re.S):
            decoded = _decode_pdf_literal_string(literal.group(1))
            if decoded:
                pieces.append(decoded)
    if not pieces:
        for literal in re.finditer(r"\(((?:\\.|[^\\)])*)\)", text, re.S):
            decoded = _decode_pdf_literal_string(literal.group(1))
            if decoded:
                pieces.append(decoded)
    return _normalize_text("\n".join(pieces))


def _decode_pdf_literal_string(value: str) -> str:
    output: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        if character != "\\":
            output.append(character)
            index += 1
            continue
        index += 1
        if index >= len(value):
            break
        escape = value[index]
        if escape in "\\()":
            output.append(escape)
        elif escape == "n":
            output.append("\n")
        elif escape == "r":
            output.append("\r")
        elif escape == "t":
            output.append("\t")
        elif escape == "b":
            output.append("\b")
        elif escape == "f":
            output.append("\f")
        elif escape in "01234567":
            octal = escape
            for _ in range(2):
                next_index = index + 1
                if next_index < len(value) and value[next_index] in "01234567":
                    index = next_index
                    octal += value[index]
                else:
                    break
            output.append(chr(int(octal, 8)))
        else:
            output.append(escape)
        index += 1
    return _normalize_text("".join(output))


def _read_docx(path: Path) -> tuple[str, int]:
    with zipfile.ZipFile(path) as archive:
        names = [
            "word/document.xml",
            "word/footnotes.xml",
            "word/endnotes.xml",
        ]
        names.extend(sorted(name for name in archive.namelist() if name.startswith("word/header") or name.startswith("word/footer")))
        sections: list[str] = []
        for name in names:
            if name in archive.namelist():
                extracted = _extract_docx_xml(archive.read(name))
                if extracted:
                    sections.append(extracted)
    return _normalize_text("\n\n".join(sections)), 1 if sections else 0


def _extract_docx_xml(xml_bytes: bytes) -> str:
    root = ET.fromstring(xml_bytes)
    body = root.find(f"{_DOCX_NAMESPACE}body")
    if body is None:
        return _extract_docx_node(root)
    parts: list[str] = []
    for child in body:
        if child.tag == f"{_DOCX_NAMESPACE}p":
            text = _extract_docx_node(child)
        elif child.tag == f"{_DOCX_NAMESPACE}tbl":
            text = _extract_docx_table(child)
        else:
            text = _extract_docx_node(child)
        if text:
            parts.append(text)
    return _normalize_text("\n\n".join(parts))


def _extract_docx_node(node: ET.Element) -> str:
    parts: list[str] = []
    for element in node.iter():
        tag = _local_name(element.tag)
        if tag == "t" and element.text:
            parts.append(element.text)
        elif tag == "tab":
            parts.append("\t")
        elif tag in {"br", "cr"}:
            parts.append("\n")
    return _normalize_text("".join(parts))


def _extract_docx_table(table: ET.Element) -> str:
    rows: list[str] = []
    for row in table.findall(f"{_DOCX_NAMESPACE}tr"):
        cells: list[str] = []
        for cell in row.findall(f"{_DOCX_NAMESPACE}tc"):
            cell_parts: list[str] = []
            for paragraph in cell.findall(f"{_DOCX_NAMESPACE}p"):
                text = _extract_docx_node(paragraph)
                if text:
                    cell_parts.append(text)
            cell_text = _normalize_text(" ".join(cell_parts))
            if cell_text:
                cells.append(cell_text)
        row_text = _normalize_text("\t".join(cells))
        if row_text:
            rows.append(row_text)
    return _normalize_text("\n".join(rows))


def _read_pptx(path: Path) -> tuple[str, int]:
    slide_texts: list[str] = []
    slide_count = 0
    with zipfile.ZipFile(path) as archive:
        slide_names = sorted(
            name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
        )
        for name in slide_names:
            extracted = _extract_pptx_slide(archive.read(name))
            if extracted:
                slide_texts.append(extracted)
                slide_count += 1
    return _normalize_text("\n\n".join(slide_texts)), slide_count


def _extract_pptx_slide(xml_bytes: bytes) -> str:
    root = ET.fromstring(xml_bytes)
    parts = [text.text for text in root.findall(f".//{_PPTX_NAMESPACE}t") if text.text]
    return _normalize_text("\n".join(parts))


def _read_sheet(path: Path) -> tuple[str, int]:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        return _read_delimited_sheet(path, "," if suffix == ".csv" else "\t"), 1
    return _read_xlsx(path)


def _read_delimited_sheet(path: Path, delimiter: str) -> str:
    with path.open(encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        rows: list[str] = []
        for row in reader:
            values = [_normalize_text(cell) for cell in row]
            row_text = _normalize_text("\t".join(values))
            if row_text:
                rows.append(row_text)
    return _normalize_text("\n".join(rows))


def _read_xlsx(path: Path) -> tuple[str, int]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = _load_shared_strings(archive)
        sheet_targets = _load_sheet_targets(archive)
        sheet_texts: list[str] = []
        for sheet_name, target in sheet_targets:
            sheet_path = _normalize_xlsx_target(target)
            if sheet_path not in archive.namelist():
                continue
            extracted = _extract_xlsx_sheet(archive.read(sheet_path), shared_strings)
            if extracted:
                sheet_texts.append(_normalize_text(f"# {sheet_name}\n{extracted}"))
    return _normalize_text("\n\n".join(sheet_texts)), len(sheet_texts)


def _load_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall(f"{_XLSX_NAMESPACE}si"):
        strings.append(_normalize_text("".join(item.itertext())))
    return strings


def _load_sheet_targets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = _load_relationships(archive)
    sheet_targets: list[tuple[str, str]] = []
    sheets = workbook.find(f"{_XLSX_NAMESPACE}sheets")
    if sheets is None:
        return sheet_targets
    for sheet in sheets.findall(f"{_XLSX_NAMESPACE}sheet"):
        name = sheet.attrib.get("name", "Sheet")
        rel_id = sheet.attrib.get(f"{_REL_NAMESPACE}id")
        if not rel_id:
            continue
        target = relationships.get(rel_id)
        if target:
            sheet_targets.append((name, target))
    return sheet_targets


def _load_relationships(archive: zipfile.ZipFile) -> dict[str, str]:
    relationships_path = "xl/_rels/workbook.xml.rels"
    if relationships_path not in archive.namelist():
        return {}
    root = ET.fromstring(archive.read(relationships_path))
    mapping: dict[str, str] = {}
    for relationship in root.findall(f"{_PKG_REL_NAMESPACE}Relationship"):
        rel_id = relationship.attrib.get("Id")
        target = relationship.attrib.get("Target")
        if rel_id and target:
            mapping[rel_id] = target
    return mapping


def _normalize_xlsx_target(target: str) -> str:
    target_path = target.lstrip("/")
    if not target_path.startswith("xl/"):
        target_path = f"xl/{target_path}"
    return target_path


def _extract_xlsx_sheet(xml_bytes: bytes, shared_strings: list[str]) -> str:
    root = ET.fromstring(xml_bytes)
    sheet_data = root.find(f"{_XLSX_NAMESPACE}sheetData")
    if sheet_data is None:
        return ""
    rows: list[str] = []
    for row in sheet_data.findall(f"{_XLSX_NAMESPACE}row"):
        values: list[str] = []
        for cell in row.findall(f"{_XLSX_NAMESPACE}c"):
            values.append(_read_xlsx_cell(cell, shared_strings))
        row_text = _normalize_text("\t".join(values))
        if row_text:
            rows.append(row_text)
    return _normalize_text("\n".join(rows))


def _read_xlsx_cell(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    value = cell.findtext(f"{_XLSX_NAMESPACE}v")
    if cell_type == "s" and value is not None:
        index = int(value)
        if 0 <= index < len(shared_strings):
            return shared_strings[index]
        return ""
    if cell_type == "inlineStr":
        inline_string = cell.find(f"{_XLSX_NAMESPACE}is")
        if inline_string is not None:
            return _normalize_text("".join(inline_string.itertext()))
    if value is not None:
        return _normalize_text(value)
    formula = cell.findtext(f"{_XLSX_NAMESPACE}f")
    return _normalize_text(formula or "")


def _read_image(path: Path) -> tuple[str, int]:
    try:
        from PIL import Image
        import pytesseract

        with Image.open(path) as image:
            text = pytesseract.image_to_string(image)
            return _normalize_text(text), 1
    except Exception:
        pass

    if shutil.which("tesseract"):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = Path(temp_dir) / "ocr_output"
            result = subprocess.run(
                ["tesseract", str(path), str(output_base)],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                text_path = output_base.with_suffix(".txt")
                if text_path.exists():
                    return _normalize_text(text_path.read_text(encoding="utf-8", errors="ignore")), 1
            raise DocumentIngestionError(
                result.stderr.strip() or result.stdout.strip() or "Image OCR failed with tesseract"
            )

    raise DocumentIngestionError("No OCR backend available for image ingestion")


def _normalize_text(value: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    filtered = [line for line in lines if line]
    return "\n".join(filtered).strip()


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag
