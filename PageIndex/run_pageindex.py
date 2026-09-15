import argparse
import hashlib
import os
import json
from pathlib import Path
from pageindex import *
from pageindex.page_index_md import md_to_tree
from pageindex.utils import ConfigLoader, get_pdf_name, print_tree

# Example CLI:
#   python run_pageindex.py --pdf_path ./doc.pdf --demo
#   python run_pageindex.py --pdf_path ./doc.pdf --cpu --max-pages 10
#   python run_pageindex.py --pdf_path ./doc.pdf --gpu
#   python run_pageindex.py --pdf_path ./doc.pdf --no-summaries --benchmark
#   python run_pageindex.py --pdf_path ./doc.pdf --resume


def _pdf_sha256(pdf_path: str) -> str:
    """Return a hex SHA-256 digest of the PDF file for cache keying."""
    h = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _cache_path(output_dir: str) -> str:
    return os.path.join(output_dir, "structure.json.hash")


def _is_cached(pdf_path: str, output_dir: str) -> bool:
    """Return True if structure.json exists and was produced from the same PDF content."""
    structure_file = os.path.join(output_dir, "structure.json")
    if not os.path.isfile(structure_file):
        return False
    cache_file = _cache_path(output_dir)
    if not os.path.isfile(cache_file):
        return False
    current_hash = _pdf_sha256(pdf_path)
    with open(cache_file, "r") as f:
        stored_hash = f.read().strip()
    return current_hash == stored_hash


def _write_cache(pdf_path: str, output_dir: str) -> None:
    """Write the PDF hash alongside the output file."""
    with open(_cache_path(output_dir), "w") as f:
        f.write(_pdf_sha256(pdf_path))

_SCRIPT_DIR = Path(__file__).resolve().parent


def _resolve_existing_file(path_str: str, label: str) -> str:
    raw = Path(path_str).expanduser()
    candidates = [
        raw,
        Path.cwd() / raw,
        _SCRIPT_DIR / raw,
    ]
    parts = raw.parts
    if len(parts) >= 2 and parts[0] == "PageIndex":
        rest = Path(*parts[1:])
        candidates.append(_SCRIPT_DIR / rest)
    seen = set()
    ordered = []
    for c in candidates:
        try:
            resolved = c.resolve()
        except (OSError, RuntimeError):
            continue
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            ordered.append(resolved)
    for p in ordered:
        if p.is_file():
            return str(p)
    raise ValueError(
        f"{label} not found: {path_str!r}. "
        f"If your shell cwd is already inside PageIndex/, use e.g. "
        f"'examples/documents/your.pdf' instead of 'PageIndex/examples/...'."
    )


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(description='Process PDF or Markdown document and generate structure')
    parser.add_argument('--pdf_path', type=str, help='Path to the PDF file')
    parser.add_argument('--md_path', type=str, help='Path to the Markdown file')

    parser.add_argument('--model', type=str, default=None, help='Model to use (overrides config.yaml)')

    parser.add_argument('--cpu', action='store_true', default=False,
                      help='Use CPU profile (default when neither --cpu nor --gpu is set)')
    parser.add_argument('--gpu', action='store_true', default=False,
                      help='Use GPU profile (overrides CPU)')
    parser.add_argument('--demo', action='store_true', default=False,
                      help='PoC demo: CPU profile, max_pages=10, shallow tree')
    parser.add_argument('--max-pages', type=int, default=None,
                      help='Truncate PDF to first N pages')
    parser.add_argument('--resume', action='store_true', default=False,
                      help='Resume from existing checkpoints in results/<pdf>/')
    parser.add_argument('--no-summaries', action='store_true', default=False,
                      help='Build tree without summaries (retrieval-only validation)')
    parser.add_argument('--benchmark', action='store_true', default=False,
                      help='Run lightweight retrieval benchmark after indexing')

    parser.add_argument('--toc-check-pages', type=int, default=None,
                      help='Number of pages to check for table of contents (PDF only)')
    parser.add_argument('--max-pages-per-node', type=int, default=None,
                      help='Maximum number of pages per node (PDF only)')
    parser.add_argument('--max-tokens-per-node', type=int, default=None,
                      help='Maximum number of tokens per node (PDF only)')

    parser.add_argument('--if-add-node-id', type=str, default=None,
                      help='Whether to add node id to the node')
    parser.add_argument('--if-add-node-summary', type=str, default=None,
                      help='Whether to add summary to the node')
    parser.add_argument('--if-add-doc-description', type=str, default=None,
                      help='Whether to add doc description to the doc')
    parser.add_argument('--if-add-node-text', type=str, default=None,
                      help='Whether to add text to the node')

    parser.add_argument('--test-mode', action='store_true', default=False,
                      help='Alias for --demo (backward compatible)')
    parser.add_argument('--no-gemini-fallback', action='store_true', default=False,
                      help='Disable Gemini API fallback; fail if local Ollama inference fails')
    parser.add_argument('--force-reindex', action='store_true', default=False,
                      help='Re-index even if a cached structure.json already exists for this PDF')
    parser.add_argument('--quality', action='store_true', default=False,
                      help='Quality mode: route chapter_summary and outline stages to qwen2.5-coder:7b')
    parser.add_argument('--max-quality', action='store_true', default=False,
                      help='Enterprise mode: max quality, long timeouts, NVIDIA hybrid fallback')
    parser.add_argument('--quality-level', type=str, default=None,
                      choices=['fast', 'balanced', 'high'],
                      help='Quality tier: fast (default), balanced (--max-quality default), high (max accuracy)')
    parser.add_argument('--fail-on-missing-model', action='store_true', default=False,
                      help='Exit immediately if the configured Ollama model is not pulled')
    parser.add_argument('--pdf-parser', type=str, default=None, choices=['PyPDF2', 'PyMuPDF'],
                      help='PDF text extractor (PyMuPDF for merged/scanned PDFs that break PyPDF2)')
    parser.add_argument('--if-thinning', type=str, default='no',
                      help='Whether to apply tree thinning for markdown (markdown only)')
    parser.add_argument('--thinning-threshold', type=int, default=5000,
                      help='Minimum token threshold for thinning (markdown only)')
    parser.add_argument('--summary-token-threshold', type=int, default=200,
                      help='Token threshold for generating summaries (markdown only)')
    args = parser.parse_args()

    if not args.pdf_path and not args.md_path:
        raise ValueError("Either --pdf_path or --md_path must be specified")
    if args.pdf_path and args.md_path:
        raise ValueError("Only one of --pdf_path or --md_path can be specified")

    demo = args.demo or args.test_mode
    mode = "gpu" if args.gpu else "cpu"
    if demo:
        mode = "cpu"

    if args.pdf_path:
        if not args.pdf_path.lower().endswith('.pdf'):
            raise ValueError("PDF file must have .pdf extension")
        pdf_path = _resolve_existing_file(args.pdf_path, "PDF file")

        pdf_name = get_pdf_name(pdf_path)
        output_dir = os.path.join('./results', pdf_name)
        os.makedirs(output_dir, exist_ok=True)

        if not args.force_reindex and not args.resume and _is_cached(pdf_path, output_dir):
            print(f'Cache hit: {output_dir}/structure.json is up-to-date for this PDF. Skipping re-index.')
            print('Use --force-reindex to override.')
            with open(os.path.join(output_dir, 'structure.json'), 'r', encoding='utf-8') as f:
                toc_with_page_number = json.load(f)
            print("\n" + "=" * 72)
            print("FULL DOCUMENT TREE (from cache) — run_pageindex")
            print("=" * 72)
            print_tree(toc_with_page_number.get("structure", []))
        else:
            # In demo mode, default max_pages to 5 if user didn't specify
            effective_max_pages = args.max_pages
            if demo and effective_max_pages is None:
                effective_max_pages = 5
                print(f"[PageIndex] demo mode: auto-limiting to {effective_max_pages} pages", flush=True)

            quality_level = args.quality_level
            if args.max_quality and not quality_level:
                quality_level = 'balanced'

            user_opt = {
                'mode': mode,
                'demo': demo,
                'resume': args.resume,
                'benchmark': args.benchmark,
                'no_summaries': args.no_summaries if args.no_summaries else None,
                'max_pages': effective_max_pages,
                'model': args.model,
                'enable_gemini_fallback': 'no' if args.no_gemini_fallback else None,
                'model_not_found_behavior': 'fail' if args.fail_on_missing_model else None,
                'toc_check_page_num': args.toc_check_pages,
                'max_page_num_each_node': args.max_pages_per_node,
                'max_token_num_each_node': args.max_tokens_per_node,
                'if_add_node_id': args.if_add_node_id,
                'if_add_node_summary': 'no' if args.no_summaries else args.if_add_node_summary,
                'if_add_doc_description': args.if_add_doc_description,
                'if_add_node_text': args.if_add_node_text,
                'pdf_parser': args.pdf_parser,
                'max_quality': True if (args.max_quality or quality_level == 'high') else None,
                'quality': True if (args.quality or args.max_quality or quality_level in ('balanced', 'high')) else None,
                'quality_level': quality_level,
            }
            opt = ConfigLoader().load({k: v for k, v in user_opt.items() if v is not None})

            effective_ql = getattr(opt, 'quality_level', quality_level or 'fast')
            if effective_ql == 'high':
                print(
                    "[PageIndex] quality-level=high: NVIDIA→qwen2.5:3b, hybrid subsections, title polish",
                    flush=True,
                )
            elif args.max_quality or effective_ql == 'balanced':
                print(
                    "[PageIndex] max-quality / balanced: NVIDIA NIM first, local fallback qwen2.5:3b",
                    flush=True,
                )
            elif args.quality:
                from pageindex.model_router import set_quality_mode
                # Pull quality overrides from config if present
                quality_overrides = getattr(opt, 'quality_mode', None)
                if isinstance(quality_overrides, dict):
                    stage_overrides = {
                        k: v for k, v in quality_overrides.items()
                        if not k.startswith('inference_') and not k.startswith('max_')
                    }
                    set_quality_mode(enabled=True, quality_overrides=stage_overrides or None)
                    # Also apply timeout/token overrides from quality_mode section
                    for key in ('inference_timeout_seconds', 'max_prompt_tokens', 'max_context_tokens'):
                        val = quality_overrides.get(key)
                        if val is not None:
                            setattr(opt, key, int(val))
                else:
                    set_quality_mode(enabled=True)
                print("[PageIndex] quality mode: NVIDIA→qwen2.5:3b for heavy stages", flush=True)

            toc_with_page_number = page_index_main(pdf_path, opt)
            print("\n" + "=" * 72)
            print("FULL DOCUMENT TREE (post-indexing) — run_pageindex")
            print("=" * 72)
            print_tree(toc_with_page_number.get("structure", []))
            _write_cache(pdf_path, output_dir)
            print(f'Artifacts directory: {output_dir}/')
            print(f'Available files: {", ".join(sorted(f for f in os.listdir(output_dir) if f.endswith(".json")))}')

    elif args.md_path:
        if not args.md_path.lower().endswith(('.md', '.markdown')):
            raise ValueError("Markdown file must have .md or .markdown extension")
        md_path = _resolve_existing_file(args.md_path, "Markdown file")

        print('Processing markdown file...')
        import asyncio

        from pageindex.utils import ConfigLoader
        config_loader = ConfigLoader()

        user_opt = {
            'mode': mode,
            'demo': demo,
            'model': args.model,
            'if_add_node_summary': args.if_add_node_summary,
            'if_add_doc_description': args.if_add_doc_description,
            'if_add_node_text': args.if_add_node_text,
            'if_add_node_id': args.if_add_node_id,
        }
        opt = config_loader.load({k: v for k, v in user_opt.items() if v is not None})

        toc_with_page_number = asyncio.run(md_to_tree(
            md_path=md_path,
            if_thinning=args.if_thinning.lower() == 'yes',
            min_token_threshold=args.thinning_threshold,
            if_add_node_summary=opt.if_add_node_summary,
            summary_token_threshold=args.summary_token_threshold,
            model=opt.model,
            if_add_doc_description=opt.if_add_doc_description,
            if_add_node_text=opt.if_add_node_text,
            if_add_node_id=opt.if_add_node_id
        ))

        print("\n" + "=" * 72)
        print("FULL DOCUMENT TREE (post-indexing) — run_pageindex")
        print("=" * 72)
        print_tree(toc_with_page_number.get("structure", []))
        print('Parsing done, saving to file...')

        md_name = os.path.splitext(os.path.basename(md_path))[0]
        output_dir = os.path.join('./results', md_name)
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'structure.json')

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(toc_with_page_number, f, indent=2, ensure_ascii=False)

        print(f'Tree structure saved to: {output_file}')
