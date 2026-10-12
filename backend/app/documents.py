import csv
import io
from pathlib import Path

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader

ALLOWED_EXTENSIONS = {".csv", ".pdf", ".txt"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_EXTRACTED_CHARS = 40000


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(422, "文本编码不受支持，请使用 UTF-8 或 GB18030")


def extract_document(filename: str, data: bytes) -> tuple[str, list[dict]]:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "仅支持 PDF、CSV、TXT 文件")
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "文件不能为空且不得超过 10 MB")

    try:
        if suffix == ".pdf":
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise HTTPException(422, "暂不支持加密 PDF")
            text = "\n".join(page.extract_text() or "" for page in reader.pages[:80])
            rows = []
        elif suffix == ".csv":
            source = decode_text(data)
            parsed = csv.DictReader(io.StringIO(source))
            if not parsed.fieldnames:
                raise HTTPException(422, "CSV 缺少表头")
            rows = [dict(row) for _, row in zip(range(2000), parsed)]
            if any(None in row or any(value is None for value in row.values()) for row in rows):
                raise HTTPException(422, 'CSV 行列数量不一致')
            text = source
        else:
            text = decode_text(data)
            rows = []
        if '\x00' in text:
            raise HTTPException(422, '文件含二进制空字节，不是有效文本资料')
    except HTTPException:
        raise
    except (ValueError, csv.Error, OSError) as exc:
        raise HTTPException(422, f"文件无法解析：{exc}") from exc
    except Exception as exc:
        raise HTTPException(422, "文件内容无法解析") from exc

    if not text.strip():
        raise HTTPException(422, "文件中没有可提取的文本（扫描版 PDF 暂不支持 OCR）")
    return text[:MAX_EXTRACTED_CHARS], rows


async def read_upload(upload: UploadFile) -> tuple[str, list[dict], int]:
    filename = Path(upload.filename or "").name
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    text, rows = extract_document(filename, data)
    return text, rows, len(data)
