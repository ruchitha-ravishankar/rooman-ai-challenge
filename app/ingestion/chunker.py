"""Semantic and Recursive Chunker for document processing."""

import re
from typing import List, Tuple, Optional
from app.config import settings
from app.models.document import Chunk


class SemanticChunker:
    """Chunks documents recursively while preserving section context and sentence boundaries."""

    def __init__(
        self,
        chunk_size: int = settings.CHUNK_SIZE,
        chunk_overlap: int = settings.CHUNK_OVERLAP,
        min_chunk_length: int = settings.MIN_CHUNK_LENGTH
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_length = min_chunk_length

    def chunk_markdown(self, doc_id: str, title: str, content: str) -> List[Chunk]:
        """Splits markdown into sections by header, then chunks each section."""
        # Split by Markdown headers (H1, H2, H3)
        header_pattern = re.compile(r'(^#{1,4}\s+.+$)', re.MULTILINE)
        splits = header_pattern.split(content)
        
        chunks: List[Chunk] = []
        current_section = "Overview"
        current_offset = 0
        chunk_idx = 0
        
        i = 0
        while i < len(splits):
            part = splits[i]
            if header_pattern.match(part):
                current_section = part.lstrip('#').strip()
                current_offset += len(part)
                i += 1
                continue
            
            section_text = part.strip()
            if section_text:
                sub_chunks = self._split_text_into_chunks(
                    text=section_text,
                    doc_id=doc_id,
                    title=title,
                    section=current_section,
                    base_offset=current_offset,
                    start_index=chunk_idx
                )
                chunks.extend(sub_chunks)
                chunk_idx += len(sub_chunks)
            
            current_offset += len(part)
            i += 1
            
        return chunks if chunks else self.chunk_text(doc_id, title, content)

    def chunk_text(
        self,
        doc_id: str,
        title: str,
        text: str,
        section: str = "General",
        page_number: Optional[int] = None
    ) -> List[Chunk]:
        """Generic chunker for plain text using sentence/paragraph boundaries."""
        return self._split_text_into_chunks(
            text=text,
            doc_id=doc_id,
            title=title,
            section=section,
            base_offset=0,
            start_index=0,
            page_number=page_number
        )

    def chunk_pdf_pages(
        self,
        doc_id: str,
        title: str,
        pages_text: List[Tuple[int, str]]
    ) -> List[Chunk]:
        """Chunks PDF pages, retaining page-level provenance."""
        chunks: List[Chunk] = []
        chunk_idx = 0
        offset = 0

        for page_num, ptext in pages_text:
            cleaned = ptext.strip()
            if not cleaned:
                continue

            # Identify any section headers in page text
            page_chunks = self._split_text_into_chunks(
                text=cleaned,
                doc_id=doc_id,
                title=title,
                section=f"Page {page_num}",
                base_offset=offset,
                start_index=chunk_idx,
                page_number=page_num
            )
            chunks.extend(page_chunks)
            chunk_idx += len(page_chunks)
            offset += len(ptext) + 2

        return chunks

    def _split_text_into_chunks(
        self,
        text: str,
        doc_id: str,
        title: str,
        section: str,
        base_offset: int,
        start_index: int,
        page_number: Optional[int] = None
    ) -> List[Chunk]:
        """Splits a block of text into overlapping segments at paragraph/sentence boundaries."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        
        chunks: List[Chunk] = []
        current_chunk_text = ""
        current_chunk_start = 0
        chunk_counter = start_index

        for para in paragraphs:
            # If paragraph itself is larger than chunk_size, split by sentences
            if len(para) > self.chunk_size:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    if len(current_chunk_text) + len(sentence) + 1 <= self.chunk_size:
                        if current_chunk_text:
                            current_chunk_text += " " + sentence
                        else:
                            current_chunk_text = sentence
                            current_chunk_start = text.find(sentence)
                    else:
                        if len(current_chunk_text) >= self.min_chunk_length:
                            chunk_id = f"{doc_id}#c{chunk_counter:03d}"
                            chunks.append(Chunk(
                                chunk_id=chunk_id,
                                doc_id=doc_id,
                                title=title,
                                section=section,
                                chunk_index=chunk_counter,
                                page_number=page_number,
                                char_start=base_offset + max(0, current_chunk_start),
                                char_end=base_offset + max(0, current_chunk_start) + len(current_chunk_text),
                                text=current_chunk_text,
                                token_count=len(current_chunk_text.split())
                            ))
                            chunk_counter += 1
                        
                        # Apply overlap: take the last sentence(s) of previous chunk
                        current_chunk_text = sentence
                        current_chunk_start = text.find(sentence)
            else:
                if len(current_chunk_text) + len(para) + 2 <= self.chunk_size:
                    if current_chunk_text:
                        current_chunk_text += "\n\n" + para
                    else:
                        current_chunk_text = para
                        current_chunk_start = text.find(para)
                else:
                    if len(current_chunk_text) >= self.min_chunk_length:
                        chunk_id = f"{doc_id}#c{chunk_counter:03d}"
                        chunks.append(Chunk(
                            chunk_id=chunk_id,
                            doc_id=doc_id,
                            title=title,
                            section=section,
                            chunk_index=chunk_counter,
                            page_number=page_number,
                            char_start=base_offset + max(0, current_chunk_start),
                            char_end=base_offset + max(0, current_chunk_start) + len(current_chunk_text),
                            text=current_chunk_text,
                            token_count=len(current_chunk_text.split())
                        ))
                        chunk_counter += 1
                    
                    current_chunk_text = para
                    current_chunk_start = text.find(para)

        # Flush remaining buffer
        if current_chunk_text and len(current_chunk_text) >= self.min_chunk_length:
            chunk_id = f"{doc_id}#c{chunk_counter:03d}"
            chunks.append(Chunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                title=title,
                section=section,
                chunk_index=chunk_counter,
                page_number=page_number,
                char_start=base_offset + max(0, current_chunk_start),
                char_end=base_offset + max(0, current_chunk_start) + len(current_chunk_text),
                text=current_chunk_text,
                token_count=len(current_chunk_text.split())
            ))

        return chunks
