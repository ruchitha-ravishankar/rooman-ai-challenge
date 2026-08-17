"""Anti-Hallucination & Claim-Level Grounding Verification Engine."""

import re
from typing import List, Dict, Optional, Tuple
from app.config import settings
from app.models.document import Chunk, ScoredChunk
from app.models.research import ClaimVerification, VerificationReport
from app.retrieval.bm25 import tokenize

# Meta sentences to exclude from factual claim verification
META_PHRASES = [
    "based on the analysis of the provided",
    "here is a structured summary",
    "the referenced findings confirm",
    "substantiated across verified source passages",
    "in summary,",
    "summary of findings",
    "the following findings"
]


class ClaimVerifier:
    """Verifies that generated assertions are strictly substantiated by the cited source chunks."""

    def __init__(self, pass_threshold: float = settings.VERIFICATION_PASS_THRESHOLD):
        self.pass_threshold = pass_threshold

    def verify_answer(
        self,
        answer_text: str,
        retrieved_chunks: List[ScoredChunk]
    ) -> VerificationReport:
        """Audits an answer by verifying every individual factual claim against cited passages."""
        # Check for explicit refusal/insufficient evidence response
        if self._is_refusal(answer_text):
            return VerificationReport(
                total_claims=0,
                verified_claims=0,
                unverified_claims=0,
                grounding_score=1.0,
                is_fully_grounded=True,
                claim_details=[]
            )

        # Build fast lookup map for retrieved chunks
        chunk_map: Dict[str, Chunk] = {sc.chunk.chunk_id: sc.chunk for sc in retrieved_chunks}

        # Extract claims
        raw_claims = self._extract_claims(answer_text)
        if not raw_claims:
            return VerificationReport(
                total_claims=0,
                verified_claims=0,
                unverified_claims=0,
                grounding_score=1.0,
                is_fully_grounded=True,
                claim_details=[]
            )

        verifications: List[ClaimVerification] = []
        verified_count = 0
        unverified_count = 0

        for idx, (claim_text, citations) in enumerate(raw_claims, start=1):
            if not citations:
                # Check if any chunk directly entails this claim even without citation
                best_chunk_id, best_conf, best_rat = self._find_best_supporting_chunk(claim_text, retrieved_chunks)
                if best_conf >= self.pass_threshold and best_chunk_id:
                    verifications.append(ClaimVerification(
                        claim_id=idx,
                        claim_text=claim_text,
                        cited_marker=None,
                        is_grounded=True,
                        grounding_confidence=round(best_conf, 4),
                        matched_chunk_id=best_chunk_id,
                        rationale=f"Implicit grounding in {best_chunk_id}: {best_rat}"
                    ))
                    verified_count += 1
                else:
                    verifications.append(ClaimVerification(
                        claim_id=idx,
                        claim_text=claim_text,
                        cited_marker=None,
                        is_grounded=False,
                        grounding_confidence=round(best_conf, 4),
                        matched_chunk_id=None,
                        rationale="Uncited assertion lacking sufficient source support."
                    ))
                    unverified_count += 1
                continue

            # Verify against explicitly cited chunk IDs
            best_chunk_id = None
            best_confidence = 0.0
            best_rationale = ""

            for cid in citations:
                if cid not in chunk_map:
                    continue
                
                chunk = chunk_map[cid]
                conf, rationale = self._evaluate_support(claim_text, chunk.text)
                if conf > best_confidence:
                    best_confidence = conf
                    best_chunk_id = cid
                    best_rationale = rationale

            # Fallback check across all chunks if cited chunk didn't meet threshold
            if best_confidence < self.pass_threshold:
                alt_cid, alt_conf, alt_rat = self._find_best_supporting_chunk(claim_text, retrieved_chunks)
                if alt_conf > best_confidence:
                    best_confidence = alt_conf
                    best_chunk_id = alt_cid
                    best_rationale = f"Found in alternative context chunk {alt_cid}: {alt_rat}"

            is_grounded = best_confidence >= self.pass_threshold

            if is_grounded:
                verified_count += 1
            else:
                unverified_count += 1

            if best_chunk_id is None:
                best_rationale = f"Cited chunk ID(s) {citations} were not found in the retrieved context set."
                best_confidence = 0.0

            verifications.append(ClaimVerification(
                claim_id=idx,
                claim_text=claim_text,
                cited_marker=",".join(citations),
                is_grounded=is_grounded,
                grounding_confidence=round(best_confidence, 4),
                matched_chunk_id=best_chunk_id,
                rationale=best_rationale
            ))

        total = len(verifications)
        grounding_score = round(verified_count / max(1, total), 4)

        return VerificationReport(
            total_claims=total,
            verified_claims=verified_count,
            unverified_claims=unverified_count,
            grounding_score=grounding_score,
            is_fully_grounded=(unverified_count == 0 and grounding_score >= self.pass_threshold),
            claim_details=verifications
        )

    def _extract_claims(self, text: str) -> List[Tuple[str, List[str]]]:
        """Extracts substantive factual claims with their explicit citation markers."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        claims = []
        citation_regex = re.compile(r'\[\^([a-zA-Z0-9_#-]+)\]')

        for line in lines:
            # Skip markdown headings and dividers
            if line.startswith("#") or line.startswith("---") or line.startswith("==="):
                continue
            
            line_lower = line.lower()
            if any(meta in line_lower for meta in META_PHRASES):
                continue

            cleaned_line = line.lstrip("-* \t0123456789.")
            line_citations = citation_regex.findall(line)
            
            # Split line into sentences
            sentences = re.split(r'(?<=[.!?])\s+', cleaned_line)
            
            for s in sentences:
                s_clean = s.strip()
                if len(s_clean) < 15:
                    continue

                if any(meta in s_clean.lower() for meta in META_PHRASES):
                    continue

                # Sentence-level citations, or inherit line citations if placed at end of bullet
                s_cits = citation_regex.findall(s_clean) or line_citations
                clean_claim_text = citation_regex.sub('', s_clean).strip()
                
                if clean_claim_text and len(clean_claim_text) > 12:
                    claims.append((clean_claim_text, list(dict.fromkeys(s_cits))))

        return claims

    def _evaluate_support(self, claim_text: str, source_text: str) -> Tuple[float, str]:
        """Calculates factual grounding between claim and source passage."""
        claim_tokens = set(tokenize(claim_text))
        if not claim_tokens:
            return 0.0, "Claim contains no substantive keywords."

        source_tokens = set(tokenize(source_text))
        
        # Token overlap ratio
        overlap = claim_tokens.intersection(source_tokens)
        token_recall = len(overlap) / len(claim_tokens)

        # Check for continuous n-gram matching (2-gram / 3-gram)
        claim_words = claim_text.lower().split()
        ngram_matches = 0
        total_ngrams = max(1, len(claim_words) - 1)

        source_lower = source_text.lower()
        for i in range(len(claim_words) - 1):
            bigram = " ".join(claim_words[i:i+2])
            if bigram in source_lower:
                ngram_matches += 1

        ngram_score = ngram_matches / total_ngrams

        # Combined grounding confidence
        confidence = 0.5 * token_recall + 0.5 * min(1.0, ngram_score * 1.3)

        if confidence >= 0.70:
            rationale = f"Strong grounding: {len(overlap)}/{len(claim_tokens)} key terms and verified continuous phrasing matched."
        elif confidence >= 0.40:
            rationale = f"Substantial grounding: Key terms substantiated in passage ({len(overlap)} terms)."
        else:
            rationale = f"Low grounding: Only {len(overlap)} of {len(claim_tokens)} terms present."

        return min(1.0, confidence), rationale

    def _find_best_supporting_chunk(
        self,
        claim_text: str,
        retrieved_chunks: List[ScoredChunk]
    ) -> Tuple[Optional[str], float, str]:
        """Finds highest supporting chunk from retrieved set."""
        best_cid = None
        best_conf = 0.0
        best_rat = ""

        for sc in retrieved_chunks:
            conf, rat = self._evaluate_support(claim_text, sc.chunk.text)
            if conf > best_conf:
                best_conf = conf
                best_cid = sc.chunk.chunk_id
                best_rat = rat

        return best_cid, best_conf, best_rat

    def _is_refusal(self, text: str) -> bool:
        """Detects if response is an unanswerable refusal statement."""
        refusal_phrases = [
            "insufficient evidence",
            "provided sources do not contain",
            "not mentioned in the provided",
            "no relevant source passages",
            "cannot answer based on the provided"
        ]
        text_lower = text.lower()
        return any(p in text_lower for p in refusal_phrases)
