"""Universal document loader supporting PDF, Markdown, Plain Text, and JSON."""

import re
from pathlib import Path
from typing import List, Optional, Union
from app.models.document import Document, DocumentMetadata
from app.ingestion.chunker import SemanticChunker


class DocumentLoader:
    """Loads raw documents from disk and parses text + metadata."""

    def __init__(self, chunker: Optional[SemanticChunker] = None):
        self.chunker = chunker or SemanticChunker()

    def load_file(self, file_path: Union[str, Path]) -> Document:
        """Loads a single file by determining its format from extension."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found at: {path}")

        ext = path.suffix.lower()
        if ext == ".pdf":
            return self._load_pdf(path)
        elif ext in [".md", ".markdown"]:
            return self._load_markdown(path)
        elif ext in [".txt", ".text"]:
            return self._load_text(path)
        elif ext == ".json":
            return self._load_json(path)
        else:
            # Fallback to plain text read
            return self._load_text(path)

    def load_directory(self, dir_path: Union[str, Path]) -> List[Document]:
        """Recursively loads all supported document files from a directory."""
        path = Path(dir_path)
        if not path.is_dir():
            raise NotADirectoryError(f"Directory not found: {path}")

        supported_extensions = {".pdf", ".md", ".markdown", ".txt", ".json"}
        documents = []
        for file in sorted(path.iterdir()):
            if file.is_file() and file.suffix.lower() in supported_extensions:
                try:
                    doc = self.load_file(file)
                    documents.append(doc)
                except Exception as e:
                    print(f"Warning: Failed to load {file.name}: {e}")
        return documents

    def _load_pdf(self, path: Path) -> Document:
        """Extracts text and page-level metadata from PDF files."""
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            pages_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                pages_text.append((i + 1, text))
            
            full_text = "\n\n".join([f"[Page {pnum}]\n{ptext}" for pnum, ptext in pages_text])
            doc_id = self._generate_doc_id(path.stem)
            title = self._extract_title_from_text(full_text, default=path.stem.replace("_", " ").title())
            
            metadata = DocumentMetadata(
                doc_id=doc_id,
                title=title,
                source_type="pdf",
                source_path=str(path),
                word_count=len(full_text.split()),
                char_count=len(full_text)
            )
            
            chunks = self.chunker.chunk_pdf_pages(doc_id, title, pages_text)
            return Document(metadata=metadata, raw_text=full_text, chunks=chunks)
        except Exception as e:
            # If pypdf is not available or corrupt, fallback
            raise RuntimeError(f"Error parsing PDF {path.name}: {e}")

    def _load_markdown(self, path: Path) -> Document:
        """Loads markdown files preserving headers and metadata."""
        content = path.read_text(encoding="utf-8")
        doc_id = self._generate_doc_id(path.stem)
        title = self._extract_markdown_title(content, default=path.stem.replace("_", " ").title())
        
        metadata = DocumentMetadata(
            doc_id=doc_id,
            title=title,
            source_type="markdown",
            source_path=str(path),
            word_count=len(content.split()),
            char_count=len(content)
        )
        
        chunks = self.chunker.chunk_markdown(doc_id, title, content)
        return Document(metadata=metadata, raw_text=content, chunks=chunks)

    def _load_text(self, path: Path) -> Document:
        """Loads plain text files."""
        content = path.read_text(encoding="utf-8")
        doc_id = self._generate_doc_id(path.stem)
        title = self._extract_title_from_text(content, default=path.stem.replace("_", " ").title())
        
        metadata = DocumentMetadata(
            doc_id=doc_id,
            title=title,
            source_type="text",
            source_path=str(path),
            word_count=len(content.split()),
            char_count=len(content)
        )
        
        chunks = self.chunker.chunk_text(doc_id, title, content)
        return Document(metadata=metadata, raw_text=content, chunks=chunks)

    def _load_json(self, path: Path) -> Document:
        """Loads structured JSON document formats."""
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        doc_id = self._generate_doc_id(data.get("id", path.stem))
        title = data.get("title", path.stem.replace("_", " ").title())
        text = data.get("content") or data.get("text") or str(data)
        
        metadata = DocumentMetadata(
            doc_id=doc_id,
            title=title,
            source_type="json",
            source_path=str(path),
            author=data.get("author", "Unknown"),
            date_published=data.get("date"),
            word_count=len(text.split()),
            char_count=len(text)
        )
        
        chunks = self.chunker.chunk_text(doc_id, title, text)
        return Document(metadata=metadata, raw_text=text, chunks=chunks)

    def _generate_doc_id(self, name: str) -> str:
        """Generates a clean alphanumeric identifier from a string."""
        clean = re.sub(r'[^a-zA-Z0-9_-]', '_', name).lower()
        return clean.strip('_')

    def _extract_markdown_title(self, content: str, default: str) -> str:
        """Extracts the top-level H1 header if present."""
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return default

    def _extract_title_from_text(self, content: str, default: str) -> str:
        """Heuristically finds the first non-empty line as a title candidate."""
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if lines and len(lines[0]) < 120:
            return lines[0].lstrip('#').strip()
        return default
