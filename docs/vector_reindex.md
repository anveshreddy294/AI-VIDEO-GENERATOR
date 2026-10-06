# Historical vector repair

Run from the repository with real Ollama embeddinggemma configured. Stop ingestion and the API server before operating on embedded Qdrant: its persistent directory has an exclusive process lock. Never use a second writer. The command validates the existing 768-dimensional collection and never creates, deletes or rebuilds it.

```powershell
python -m app.db.reindex --dry-run --email <operator-email>
python -m app.db.reindex --apply --email <operator-email>
```

Dry run is the default. The password is prompted without echo. Alternatively supply a verified operator token through `VISUALAI_REINDEX_ACCESS_TOKEN` in the process environment. With no operator token, an explicitly configured backend administrative key is required; it is used only for GET requests. Caller-scoped inspection cannot establish whether records exist outside that caller's RLS visibility. The verified project audit found all canonical source records under the test owner.

The command matches point ID, source, owner, version, layer, text and content-unit references against Supabase source versions/content units. Payload text alone is never canonical evidence. The exact normalized legacy MD5 word-bucket signature identifies historical vectors; dimension alone does not. All replacement generation and validation finishes before writes begin. A changed Qdrant snapshot aborts before writes. Stop concurrent canonical writers too; there is no distributed transaction across Supabase and Qdrant.

Apply replaces vectors at existing IDs and adds only embedding provenance. Missing or mismatched canonical evidence remains untouched. Existing vectors without model metadata receive metadata only when fresh embeddinggemma output confirms cosine similarity >= 0.9999. Their vectors remain unchanged. The comparison tolerance accounts for normalized storage precision; it does not certify an arbitrary model as compatible. Repeated apply skips already verified semantic points. An interrupted apply can be rerun; completed replacements remain independently valid.

Every new point records the actual embedding provider/model/dimension/kind/version. Production semantic queries require those fields to match the actual query model, including explicit fallback. Synthetic test points are labelled `synthetic_test`; isolated mock-mode fixtures are the only retrieval exception. Sources without compatible points raise `RetrievalUnavailable`; the QA API returns HTTP 503 with `RETRIEVAL_UNAVAILABLE`. Exact source-chunk retrieval also requires configured-model provenance.

Short evidence uses a deliberately narrow deterministic grammar: at most 320 characters and two sentences, an explicit named definition (`is`, `means`, `refers to`) using recognized definitional nouns. One complete sentence is retained verbatim with its content ID; prerequisites and related edges are empty. Ambiguous or unsupported wording follows existing fail-closed extraction. Longer evidence retains existing batch limits and grounding validation.

Operational limitation: 82 of the 92 retained historical points have legacy local registry artifacts, but none has a canonical Supabase source/version/content-unit record. Ten have no matching local registry evidence either. Registry artifacts are diagnostic recovery evidence, not a Supabase fallback. Any future promotion needs explicit ownership reconciliation and canonical import. Fourteen retained points also lack content IDs. No old point is deleted.

Existing structural concern: the legacy file-mode pipeline contains an in-memory Qdrant storage fallback. This repair adds provenance to its writes but does not redesign that path; Supabase source ingestion continues to use durable canonical commit then validated indexing. The fixed 768 dimension is an explicit compatibility constraint of the existing collection, not evidence of semantic compatibility.
