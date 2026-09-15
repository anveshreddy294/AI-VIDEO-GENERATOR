try:
    import litellm

    litellm.drop_params = True
except ImportError:
    litellm = None

try:
    from rapidfuzz import fuzz as _fuzz
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False

import math
import ollama
import logging
import os
import re
import textwrap
from datetime import datetime
import time
import json
import PyPDF2
import copy
import asyncio
import pymupdf
from io import BytesIO
from dotenv import load_dotenv
load_dotenv()
import yaml
from pathlib import Path
from types import SimpleNamespace as config

from .local_llm import (
    OLLAMA_MODEL,
    PipelineStageFailure,
    TokenBudgetExceeded,
    configure_from_opt,
    generate_structured,
    get_runtime_summary,
    print_runtime_summary,
    reset_runtime_summary,
)
from .schemas import DocDescription, PlainSummary, SummaryBatch
from . import extractive
from .pedagogy_metadata import enrich_node_metadata

SUMMARY_BATCH_SIZE = 2
MAX_PROMPT_TOKENS_DEFAULT = 3500
PROMPT_OVERHEAD_TOKENS = 400
EXTRACTIVE_MIN_CONFIDENCE = 0.55

_GARBLED_RE = re.compile(r"/G\d{2,3}")


def _is_garbled_ocr(text: str) -> bool:
    """Return True when text is mostly PDF glyph codes (/G65…), making SLM useless."""
    if not text:
        return False
    hits = len(_GARBLED_RE.findall(text[:2000]))
    return hits > 10 and (hits / max(len(text[:2000]), 1)) > 0.02
EXTRACTIVE_MAX_SENTENCES = 3
SLM_FALLBACK_RATIO_MAX = 0.50
_slm_calls_budget: dict = {"used": 0, "max": None}

# Backward compatibility: support CHATGPT_API_KEY as alias for OPENAI_API_KEY
if not os.getenv("OPENAI_API_KEY") and os.getenv("CHATGPT_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.getenv("CHATGPT_API_KEY")

# LiteLLM reads GEMINI_API_KEY for gemini/* models (set in .env; loaded above via python-dotenv)
if not os.getenv("GEMINI_API_KEY") and os.getenv("GOOGLE_API_KEY"):
    os.environ["GEMINI_API_KEY"] = os.getenv("GOOGLE_API_KEY")

def _normalize_litellm_model(model):
    """Map deprecated/invalid IDs to names the Gemini API accepts (LiteLLM gemini/*)."""
    if not model:
        return model
    model = model.removeprefix("litellm/")
    # Many Google AI Studio projects no longer expose 1.x model IDs (404). Use current Flash.
    aliases = {
        "gemini/gemini-1.5-flash-latest": "gemini/gemini-2.5-flash-lite",
        "gemini/gemini-1.5-flash": "gemini/gemini-2.5-flash-lite",
        "gemini/gemini-1.5-pro-latest": "gemini/gemini-2.5-flash-lite",
        "gemini/gemini-1.5-pro": "gemini/gemini-2.5-flash-lite",
        "gemini/gemini-1.0-pro-latest": "gemini/gemini-2.5-flash-lite",
    }
    return aliases.get(model, model)


def count_tokens(text, model=None):
    if not text:
        return 0
    if litellm is None:
        return max(1, len(text) // 4)
    m = _normalize_litellm_model(model) if model else model
    return litellm.token_counter(model=m, text=text)


def ollama_text_completion(
    model, prompt, chat_history=None, return_finish_reason=False
):
    """Free-form text from Ollama (no JSON schema). Used for TOC text extraction continuations."""
    max_retries = 10
    messages = (
        list(chat_history) + [{"role": "user", "content": prompt}]
        if chat_history
        else [{"role": "user", "content": prompt}]
    )
    client = ollama.Client()
    for i in range(max_retries):
        try:
            response = client.chat(
                model=OLLAMA_MODEL, messages=messages, stream=False
            )
            content = response.message.content or ""
            if return_finish_reason:
                return content, "finished"
            return content
        except Exception as e:
            print("************* Retrying *************")
            logging.error(f"Error: {e}")
            if i < max_retries - 1:
                time.sleep(1)
            else:
                logging.error("Max retries reached for prompt: " + prompt)
                if return_finish_reason:
                    return "", "error"
                return ""
            
            
def get_json_content(response):
    start_idx = response.find("```json")
    if start_idx != -1:
        start_idx += 7
        response = response[start_idx:]
        
    end_idx = response.rfind("```")
    if end_idx != -1:
        response = response[:end_idx]
    
    json_content = response.strip()
    return json_content
         

def extract_json(content):
    try:
        # First, try to extract JSON enclosed within ```json and ```
        start_idx = content.find("```json")
        if start_idx != -1:
            start_idx += 7  # Adjust index to start after the delimiter
            end_idx = content.rfind("```")
            json_content = content[start_idx:end_idx].strip()
        else:
            # If no delimiters, assume entire content could be JSON
            json_content = content.strip()

        # Clean up common issues that might cause parsing errors
        json_content = json_content.replace('None', 'null')  # Replace Python None with JSON null
        json_content = json_content.replace('\n', ' ').replace('\r', ' ')  # Remove newlines
        json_content = ' '.join(json_content.split())  # Normalize whitespace

        # Attempt to parse and return the JSON object
        return json.loads(json_content)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to extract JSON: {e}")
        # Try to clean up the content further if initial parsing fails
        try:
            # Remove any trailing commas before closing brackets/braces
            json_content = json_content.replace(',]', ']').replace(',}', '}')
            return json.loads(json_content)
        except:
            logging.error("Failed to parse JSON even after cleanup")
            return {}
    except Exception as e:
        logging.error(f"Unexpected error while extracting JSON: {e}")
        return {}

def write_node_id(data, node_id=0):
    if isinstance(data, dict):
        data['node_id'] = str(node_id).zfill(4)
        node_id += 1
        for key in list(data.keys()):
            if 'nodes' in key:
                node_id = write_node_id(data[key], node_id)
    elif isinstance(data, list):
        for index in range(len(data)):
            node_id = write_node_id(data[index], node_id)
    return node_id

def get_nodes(structure):
    if isinstance(structure, dict):
        structure_node = copy.deepcopy(structure)
        structure_node.pop('nodes', None)
        nodes = [structure_node]
        for key in list(structure.keys()):
            if 'nodes' in key:
                nodes.extend(get_nodes(structure[key]))
        return nodes
    elif isinstance(structure, list):
        nodes = []
        for item in structure:
            nodes.extend(get_nodes(item))
        return nodes
    
def _child_list(node: dict) -> list:
    return node.get("nodes") or node.get("children") or []


def children_to_nodes(structure):
    """Normalize exported `children` key back to in-memory `nodes` for processing."""
    if isinstance(structure, dict):
        ch = structure.pop("children", None)
        if ch is not None and "nodes" not in structure:
            structure["nodes"] = [children_to_nodes(c) for c in ch]
        elif "nodes" in structure:
            structure["nodes"] = [children_to_nodes(c) for c in structure["nodes"]]
        return structure
    if isinstance(structure, list):
        return [children_to_nodes(n) for n in structure]
    return structure


def structure_to_list(structure):
    if isinstance(structure, dict):
        nodes = []
        nodes.append(structure)
        ch = _child_list(structure)
        if ch:
            nodes.extend(structure_to_list(ch))
        return nodes
    elif isinstance(structure, list):
        nodes = []
        for item in structure:
            nodes.extend(structure_to_list(item))
        return nodes

    
def get_leaf_nodes(structure):
    if isinstance(structure, dict):
        if not structure['nodes']:
            structure_node = copy.deepcopy(structure)
            structure_node.pop('nodes', None)
            return [structure_node]
        else:
            leaf_nodes = []
            for key in list(structure.keys()):
                if 'nodes' in key:
                    leaf_nodes.extend(get_leaf_nodes(structure[key]))
            return leaf_nodes
    elif isinstance(structure, list):
        leaf_nodes = []
        for item in structure:
            leaf_nodes.extend(get_leaf_nodes(item))
        return leaf_nodes

def is_leaf_node(data, node_id):
    # Helper function to find the node by its node_id
    def find_node(data, node_id):
        if isinstance(data, dict):
            if data.get('node_id') == node_id:
                return data
            for key in data.keys():
                if 'nodes' in key:
                    result = find_node(data[key], node_id)
                    if result:
                        return result
        elif isinstance(data, list):
            for item in data:
                result = find_node(item, node_id)
                if result:
                    return result
        return None

    # Find the node with the given node_id
    node = find_node(data, node_id)

    # Check if the node is a leaf node
    if node and not node.get('nodes'):
        return True
    return False

def get_last_node(structure):
    return structure[-1]


def extract_text_from_pdf(pdf_path):
    pdf_reader = PyPDF2.PdfReader(pdf_path)
    ###return text not list 
    text=""
    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        text+=page.extract_text()
    return text

def get_pdf_title(pdf_path):
    pdf_reader = PyPDF2.PdfReader(pdf_path)
    meta = pdf_reader.metadata
    title = meta.title if meta and meta.title else 'Untitled'
    return title

def get_text_of_pages(pdf_path, start_page, end_page, tag=True):
    pdf_reader = PyPDF2.PdfReader(pdf_path)
    text = ""
    for page_num in range(start_page-1, end_page):
        page = pdf_reader.pages[page_num]
        page_text = page.extract_text()
        if tag:
            text += f"<start_index_{page_num+1}>\n{page_text}\n<end_index_{page_num+1}>\n"
        else:
            text += page_text
    return text

def get_first_start_page_from_text(text):
    start_page = -1
    start_page_match = re.search(r'<start_index_(\d+)>', text)
    if start_page_match:
        start_page = int(start_page_match.group(1))
    return start_page

def get_last_start_page_from_text(text):
    start_page = -1
    # Find all matches of start_index tags
    start_page_matches = re.finditer(r'<start_index_(\d+)>', text)
    # Convert iterator to list and get the last match if any exist
    matches_list = list(start_page_matches)
    if matches_list:
        start_page = int(matches_list[-1].group(1))
    return start_page


def sanitize_filename(filename, replacement='-'):
    # In Linux, only '/' and '\0' (null) are invalid in filenames.
    # Null can't be represented in strings, so we only handle '/'.
    return filename.replace('/', replacement)

def get_pdf_name(pdf_path):
    # Extract PDF name
    if isinstance(pdf_path, str):
        pdf_name = os.path.basename(pdf_path)
    elif isinstance(pdf_path, BytesIO):
        pdf_reader = PyPDF2.PdfReader(pdf_path)
        meta = pdf_reader.metadata
        pdf_name = meta.title if meta and meta.title else 'Untitled'
        pdf_name = sanitize_filename(pdf_name)
    return pdf_name


class JsonLogger:
    def __init__(self, file_path):
        # Extract PDF name for logger name
        pdf_name = get_pdf_name(file_path)
            
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = f"{pdf_name}_{current_time}.json"
        os.makedirs("./logs", exist_ok=True)
        # Initialize empty list to store all messages
        self.log_data = []

    def log(self, level, message, **kwargs):
        if isinstance(message, dict):
            self.log_data.append(message)
        else:
            self.log_data.append({'message': message})
        # Add new message to the log data
        
        # Write entire log data to file
        with open(self._filepath(), "w") as f:
            json.dump(self.log_data, f, indent=2)

    def info(self, message, *args, **kwargs):
        if args:
            try:
                message = message % args
            except (TypeError, ValueError):
                message = f"{message} {' '.join(str(a) for a in args)}"
        self.log("INFO", message, **kwargs)

    def error(self, message, *args, **kwargs):
        if args:
            try:
                message = message % args
            except (TypeError, ValueError):
                message = f"{message} {' '.join(str(a) for a in args)}"
        self.log("ERROR", message, **kwargs)

    def debug(self, message, *args, **kwargs):
        if args:
            try:
                message = message % args
            except (TypeError, ValueError):
                message = f"{message} {' '.join(str(a) for a in args)}"
        self.log("DEBUG", message, **kwargs)

    def exception(self, message, *args, **kwargs):
        if args:
            try:
                message = message % args
            except (TypeError, ValueError):
                message = f"{message} {' '.join(str(a) for a in args)}"
        kwargs["exception"] = True
        self.log("ERROR", message, **kwargs)

    def _filepath(self):
        return os.path.join("logs", self.filename)
    



def _structure_level(structure) -> int:
    if not structure:
        return 1
    return len(str(structure).split("."))


def classify_content_type(title: str, level: int = 1) -> str:
    t = (title or "").lower()
    if "glossary" in t:
        return "glossary"
    if "summary" in t or "chapter summary" in t:
        return "summary"
    if "appendix" in t or "preface" in t or "about this" in t:
        return "preface"
    if level <= 1:
        return "chapter"
    return "section"


def list_to_tree(data):
    def get_parent_structure(structure):
        if not structure:
            return None
        parts = str(structure).split(".")
        return ".".join(parts[:-1]) if len(parts) > 1 else None

    nodes = {}
    root_nodes = []

    for item in data:
        structure = item.get("structure")
        level = item.get("level") or _structure_level(structure)
        start = item.get("start_index")
        end = item.get("end_index")
        node = {
            "title": item.get("title"),
            "structure": structure,
            "level": level,
            "start_index": start,
            "end_index": end,
            "start_page": start,
            "end_page": end,
            "content_type": item.get("content_type") or classify_content_type(item.get("title", ""), level),
            "semantic_tags": item.get("semantic_tags") or [],
            "keywords": item.get("keywords") or [],
            "nodes": [],
        }
        nodes[structure] = node
        parent_structure = get_parent_structure(structure)
        if parent_structure:
            if parent_structure in nodes:
                nodes[parent_structure]["nodes"].append(node)
            else:
                root_nodes.append(node)
        else:
            root_nodes.append(node)

    def clean_node(node):
        if not node["nodes"]:
            del node["nodes"]
        else:
            for child in node["nodes"]:
                clean_node(child)
        return node

    return [clean_node(node) for node in root_nodes]


def assign_parent_ids(structure: list, parent_id=None) -> None:
    """Set parent_id on every node after write_node_id."""
    if isinstance(structure, dict):
        structure["parent_id"] = parent_id
        for ch in structure.get("nodes") or []:
            assign_parent_ids(ch, structure.get("node_id"))
    elif isinstance(structure, list):
        for item in structure:
            assign_parent_ids(item, parent_id)


def nodes_to_children_export(structure):
    """Rename nodes -> children for JSON artifacts; keep nodes in-memory."""
    if isinstance(structure, dict):
        out = {k: v for k, v in structure.items() if k != "nodes"}
        if structure.get("nodes"):
            out["children"] = [nodes_to_children_export(ch) for ch in structure["nodes"]]
        return out
    if isinstance(structure, list):
        return [nodes_to_children_export(n) for n in structure]
    return structure


def strip_page_list_banners(page_list: list, logger=None) -> list:
    """Remove repeated textbook header/footer lines from every page."""
    from collections import Counter
    from .heading_hints import _RE_WATERMARK

    line_counts: Counter = Counter()
    for text, _ in page_list:
        for line in (text or "").splitlines():
            s = line.strip()
            if 10 < len(s) <= 120:
                line_counts[s] += 1
    threshold = max(2, int(len(page_list) * 0.35))
    noise = {ln for ln, c in line_counts.items() if c >= threshold}
    noise.update({
        ln for ln in line_counts
        if re.search(r"CBSE\s+Grade|NCERT|Visual\s+AI\s+Teaching|Physics\s+for\s+Everyone", ln, re.I)
    })
    noise.update({
        ln for ln in line_counts
        if _RE_WATERMARK.search(ln)
    })
    cleaned = []
    for text, tok in page_list:
        lines = []
        for l in (text or "").splitlines():
            s = l.strip()
            if s in noise:
                continue
            if _RE_WATERMARK.search(s):
                continue
            lines.append(l)
        cleaned.append(("\n".join(lines), tok))
    if logger and noise:
        logger.info({"strip_page_list_banners": len(noise)})
    return cleaned


def clean_node_text(text: str) -> str:
    """Remove answer-key fragments, watermarks, and noise before summarization."""
    from . import extractive
    return extractive._clean_for_summary(text or "")

def add_preface_if_needed(data):
    if not isinstance(data, list) or not data:
        return data

    if data[0]['physical_index'] is not None and data[0]['physical_index'] > 1:
        preface_node = {
            "structure": "0",
            "title": "Front Matter",
            "physical_index": 1,
            "content_type": "preface",
        }
        data.insert(0, preface_node)
    return data



def get_page_tokens(pdf_path, model=None, pdf_parser="PyPDF2", use_api_tokenizer=False):
    """Extract page text and token estimates.

    Uses fast local estimation (len/4) by default to avoid per-page API calls on large PDFs.
    Pass use_api_tokenizer=True with a token_count_model only when exact counts are required.
    """
    if use_api_tokenizer and model and litellm is not None:
        model = _normalize_litellm_model(model)

    def _page_token_len(page_text: str) -> int:
        if use_api_tokenizer and model and litellm is not None:
            return litellm.token_counter(model=model, text=page_text)
        return count_tokens(page_text, model=None)

    if pdf_parser == "PyPDF2":
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_path)
            page_list = []
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                page_list.append((page_text, _page_token_len(page_text)))
            return page_list
        except Exception as exc:
            print(
                f"[PageIndex] PyPDF2 failed ({type(exc).__name__}); falling back to PyMuPDF",
                flush=True,
            )
            pdf_parser = "PyMuPDF"
    if pdf_parser == "PyMuPDF":
        if isinstance(pdf_path, BytesIO):
            pdf_stream = pdf_path
            doc = pymupdf.open(stream=pdf_stream, filetype="pdf")
        elif isinstance(pdf_path, str) and os.path.isfile(pdf_path) and pdf_path.lower().endswith(".pdf"):
            doc = pymupdf.open(pdf_path)
        page_list = []
        for page in doc:
            page_text = page.get_text()
            page_list.append((page_text, _page_token_len(page_text)))
        return page_list
    else:
        raise ValueError(f"Unsupported PDF parser: {pdf_parser}")

        

def get_text_of_pdf_pages(pdf_pages, start_page, end_page, *, clean: bool = True):
    text = ""
    for page_num in range(start_page - 1, end_page):
        text += pdf_pages[page_num][0]
    if clean and text:
        text = clean_node_text(text)
    return text

def get_text_of_pdf_pages_with_labels(pdf_pages, start_page, end_page):
    text = ""
    for page_num in range(start_page-1, end_page):
        text += f"<physical_index_{page_num+1}>\n{pdf_pages[page_num][0]}\n<physical_index_{page_num+1}>\n"
    return text

def get_number_of_pages(pdf_path):
    pdf_reader = PyPDF2.PdfReader(pdf_path)
    num = len(pdf_reader.pages)
    return num



def assign_page_spans(structure, end_physical_index):
    for i, item in enumerate(structure):
        item["start_index"] = item.get("physical_index")
        if i < len(structure) - 1:
            nxt = structure[i + 1]["physical_index"]
            if structure[i + 1].get("appear_start") == "yes":
                item["end_index"] = nxt - 1
            else:
                item["end_index"] = nxt
        else:
            item["end_index"] = end_physical_index
        level = item.get("level") or _structure_level(item.get("structure"))
        item["level"] = level
        item["content_type"] = item.get("content_type") or classify_content_type(
            item.get("title", ""), level
        )
        item.setdefault("semantic_tags", [])
        item["start_page"] = item["start_index"]
        item["end_page"] = item["end_index"]
        if item["end_index"] is not None and item["start_index"] is not None:
            item["end_index"] = max(item["start_index"], item["end_index"])
            item["end_page"] = item["end_index"]
    return structure


def post_processing(structure, end_physical_index, page_list=None, opt=None, logger=None):
    structure = assign_page_spans(structure, end_physical_index)
    if page_list is not None:
        from .hierarchy_repair import semantic_boundary_refiner
        structure = semantic_boundary_refiner(structure, page_list, opt=opt, logger=logger)
        for item in structure:
            item["start_page"] = item.get("start_index")
            item["end_page"] = item.get("end_index")
    tree = list_to_tree(structure)
    if len(tree) != 0:
        return tree
    for node in structure:
        node.pop("appear_start", None)
        node.pop("physical_index", None)
    return structure

def clean_structure_post(data):
    if isinstance(data, dict):
        data.pop('page_number', None)
        data.pop('start_index', None)
        data.pop('end_index', None)
        if 'nodes' in data:
            clean_structure_post(data['nodes'])
    elif isinstance(data, list):
        for section in data:
            clean_structure_post(section)
    return data

def remove_fields(data, fields=['text']):
    if isinstance(data, dict):
        return {k: remove_fields(v, fields)
            for k, v in data.items() if k not in fields}
    elif isinstance(data, list):
        return [remove_fields(item, fields) for item in data]
    return data

def print_toc(tree, indent=0):
    for node in tree:
        print('  ' * indent + node['title'])
        if node.get('nodes'):
            print_toc(node['nodes'], indent + 1)

def print_json(data, max_len=40, indent=2):
    def simplify_data(obj):
        if isinstance(obj, dict):
            return {k: simplify_data(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [simplify_data(item) for item in obj]
        elif isinstance(obj, str) and len(obj) > max_len:
            return obj[:max_len] + '...'
        else:
            return obj
    
    simplified = simplify_data(data)
    print(json.dumps(simplified, indent=indent, ensure_ascii=False))


def remove_structure_text(data):
    if isinstance(data, dict):
        data.pop('text', None)
        if 'nodes' in data:
            remove_structure_text(data['nodes'])
    elif isinstance(data, list):
        for item in data:
            remove_structure_text(item)
    return data


def check_token_limit(structure, limit=110000):
    list = structure_to_list(structure)
    for node in list:
        num_tokens = count_tokens(node['text'], model=None)
        if num_tokens > limit:
            print(f"Node ID: {node['node_id']} has {num_tokens} tokens")
            print("Start Index:", node['start_index'])
            print("End Index:", node['end_index'])
            print("Title:", node['title'])
            print("\n")


def convert_physical_index_to_int(data):
    if isinstance(data, list):
        for i in range(len(data)):
            # Check if item is a dictionary and has 'physical_index' key
            if isinstance(data[i], dict) and 'physical_index' in data[i]:
                if isinstance(data[i]['physical_index'], str):
                    if data[i]['physical_index'].startswith('<physical_index_'):
                        data[i]['physical_index'] = int(data[i]['physical_index'].split('_')[-1].rstrip('>').strip())
                    elif data[i]['physical_index'].startswith('physical_index_'):
                        data[i]['physical_index'] = int(data[i]['physical_index'].split('_')[-1].strip())
    elif isinstance(data, str):
        if data.startswith('<physical_index_'):
            data = int(data.split('_')[-1].rstrip('>').strip())
        elif data.startswith('physical_index_'):
            data = int(data.split('_')[-1].strip())
        # Check data is int
        if isinstance(data, int):
            return data
        else:
            return None
    return data


def convert_page_to_int(data):
    for item in data:
        if 'page' in item and isinstance(item['page'], str):
            try:
                item['page'] = int(item['page'])
            except ValueError:
                # Keep original value if conversion fails
                pass
    return data


def add_node_text(node, pdf_pages):
    if isinstance(node, dict):
        start_page = node.get('start_index')
        end_page = node.get('end_index')
        node['text'] = get_text_of_pdf_pages(pdf_pages, start_page, end_page)
        ch = _child_list(node)
        if ch:
            add_node_text(ch, pdf_pages)
    elif isinstance(node, list):
        for index in range(len(node)):
            add_node_text(node[index], pdf_pages)
    return


def add_node_text_with_labels(node, pdf_pages):
    if isinstance(node, dict):
        start_page = node.get('start_index')
        end_page = node.get('end_index')
        node['text'] = get_text_of_pdf_pages_with_labels(pdf_pages, start_page, end_page)
        if 'nodes' in node:
            add_node_text_with_labels(node['nodes'], pdf_pages)
    elif isinstance(node, list):
        for index in range(len(node)):
            add_node_text_with_labels(node[index], pdf_pages)
    return


async def generate_node_summary(node, model=None):
    prompt = f"""Summarize the following document excerpt in 2–4 sentences (main points only).

Partial document text:
{node['text']}
"""
    system_prompt = "Respond with ONLY valid JSON: an object with a single string field \"summary\"."
    out = await asyncio.to_thread(
        generate_structured, prompt, PlainSummary, system_prompt
    )
    return out.summary


def _build_summary_batches(nodes, max_nodes_per_batch=None, max_content_tokens=None, model=None):
    """Split nodes into batches that fit within token budget (max 1–2 nodes by default)."""
    max_nodes = max_nodes_per_batch or SUMMARY_BATCH_SIZE
    content_cap = max_content_tokens or (MAX_PROMPT_TOKENS_DEFAULT - PROMPT_OVERHEAD_TOKENS)
    batches = []
    current = []
    current_tokens = 0

    for node in nodes:
        section = (
            f"node_id: {node.get('node_id', '')}\n"
            f"title: {node.get('title', '')}\n"
            f"content:\n{node.get('text', '')}\n"
        )
        section_tokens = count_tokens(section, model)
        would_exceed = (
            len(current) >= max_nodes
            or (current and current_tokens + section_tokens > content_cap)
            or section_tokens > content_cap
        )
        if would_exceed and current:
            batches.append(current)
            current = []
            current_tokens = 0
        if section_tokens > content_cap and not current:
            truncated = node.get("text", "")[: content_cap * 3]
            node = {**node, "text": truncated + "\n...(truncated for token budget)"}
            section = (
                f"node_id: {node.get('node_id', '')}\n"
                f"title: {node.get('title', '')}\n"
                f"content:\n{node.get('text', '')}\n"
            )
            section_tokens = count_tokens(section, model)
        current.append(node)
        current_tokens += section_tokens
        if len(current) >= max_nodes:
            batches.append(current)
            current = []
            current_tokens = 0

    if current:
        batches.append(current)
    return batches


def reset_slm_summary_budget(total_nodes: int, ratio_max: float = None) -> None:
    global _slm_calls_budget
    ratio = ratio_max if ratio_max is not None else SLM_FALLBACK_RATIO_MAX
    _slm_calls_budget = {
        "used": 0,
        "max": max(1, int(total_nodes * ratio)) if total_nodes else 1,
    }


def _slm_budget_ok() -> bool:
    b = _slm_calls_budget
    if b.get("max") is None:
        return True
    return b.get("used", 0) < b["max"]


def _record_slm_call() -> None:
    _slm_calls_budget["used"] = _slm_calls_budget.get("used", 0) + 1


def _collect_child_summaries(node: dict) -> str:
    parts = []
    for ch in node.get("nodes") or []:
        s = (ch.get("summary") or "").strip()
        if s:
            parts.append(f"### {ch.get('title', '')}\n{s}")
        sub = _collect_child_summaries(ch)
        if sub:
            parts.append(sub)
    return "\n\n".join(parts)


def _clean_child_blob(blob: str) -> str:
    parts = []
    for line in blob.splitlines():
        line = re.sub(r"^#+\s*", "", line).strip()
        if line and not line.startswith("•"):
            parts.append(line)
    text = " ".join(parts)
    sents = re.split(r"(?<=[.!?])\s+", text)
    good = [s for s in sents if len(s.split()) >= 6][:4]
    return " ".join(good) if good else text[:800]


async def _summarize_chapter_node(node, model=None, opt=None):
    """Synthesize chapter summary from child section summaries (not raw body)."""
    from .quality_policy import prefer_llm_summaries

    child_blob = _collect_child_summaries(node)
    raw = (node.get("text") or "")[:1500]
    child_titles = [
        (ch.get("title") or "").strip()
        for ch in (node.get("nodes") or [])
        if ch.get("title")
    ]

    if _is_garbled_ocr(raw) and not child_blob:
        title = node.get("title", "") or "Chapter"
        node["summary"] = f"This chapter covers: {title}."
        node["keywords"] = node.get("keywords") or []
        node["_summary_source"] = "title_only_garbled"
        enrich_node_metadata(node, child_titles)
        return

    if child_blob and len(child_blob) >= 200 and not prefer_llm_summaries(opt):
        node["summary"] = _clean_child_blob(child_blob)
        node["_summary_source"] = "chapter_children_concat"
        enrich_node_metadata(node, child_titles)
        return

    if len(child_blob) >= 500:
        prompt_body = child_blob[:4000]
    else:
        prompt_body = (child_blob + "\n\n" + raw).strip()[:2500]
    if not prompt_body:
        prompt_body = raw[:1500] or node.get("title", "")

    use_quality = (getattr(opt, "quality", False) if opt else False) or prefer_llm_summaries(opt)
    chapter_timeout = getattr(opt, "chapter_summary_timeout_seconds", 45) if opt else 45
    num_predict = getattr(opt, "summary_num_predict", 384) if opt else 384

    if use_quality:
        user_prompt = (
            f"Chapter: {node.get('title', '')}\n\n"
            f"Section summaries:\n{prompt_body}\n\n"
            "Write an educational chapter summary (4-6 sentences)."
        )
        system_prompt = (
            "You summarize textbook chapters. Respond with ONLY valid JSON: "
            '{"summary": "..."}'
        )
        try:
            out = await asyncio.to_thread(
                generate_structured,
                user_prompt,
                PlainSummary,
                system_prompt,
                stage="chapter_summary",
                node_id=node.get("node_id"),
                inference_options={"num_predict": num_predict},
                timeout_seconds=chapter_timeout,
            )
            if out.summary and len(out.summary.strip()) >= 30:
                node["summary"] = out.summary.strip()
                node["_summary_source"] = "chapter_slm"
                from .quality_policy import record_path
                record_path("llm_summary")
                enrich_node_metadata(node, child_titles)
                return
        except Exception as exc:
            logging.warning("chapter_summary failed for %s: %s", node.get("title"), exc)

    if child_blob:
        node["summary"] = _clean_child_blob(child_blob)
        node["_summary_source"] = "chapter_children_concat"
    else:
        text = (node.get("text") or "")[:3000]
        if text:
            ext = extractive.summarize(text, max_sentences=3)
            if ext.get("summary") and len(ext["summary"]) >= 20:
                node["summary"] = ext["summary"]
                node["keywords"] = ext.get("keywords", [])
                node["_summary_source"] = "extractive_chapter_fallback"
                enrich_node_metadata(node, child_titles)
                return
        title = node.get("title", "") or "Chapter"
        node["summary"] = f"This chapter covers: {title}."
        node["_summary_source"] = "title_only"
    enrich_node_metadata(node, child_titles)


async def _run_summary_batch(batch, batch_index, model=None, checkpoints=None, opt=None):
    from .quality_policy import prefer_llm_summaries, record_path

    needs_slm = []
    max_chars = getattr(opt, "max_node_text_chars", None) if opt else None
    max_sentences = EXTRACTIVE_MAX_SENTENCES
    force_llm = prefer_llm_summaries(opt)

    for node in batch:
        if node.get("level") == 1 or node.get("content_type") == "chapter":
            continue
        text = node.get("text", "") or ""
        if max_chars and len(text) > max_chars:
            text = text[:max_chars] + "\n...(truncated)"
        if _is_garbled_ocr(text):
            title = node.get("title", "") or "Section"
            node["summary"] = f"This section covers: {title}."
            node["keywords"] = []
            node["_summary_source"] = "title_only_garbled"
            continue
        if force_llm:
            needs_slm.append((node, {}))
            continue
        ext = extractive.summarize(text, max_sentences=max_sentences)
        if ext["confidence"] >= EXTRACTIVE_MIN_CONFIDENCE and ext["summary"]:
            node["summary"] = ext["summary"]
            node["keywords"] = ext.get("keywords", [])
            node["_summary_source"] = "extractive"
            enrich_node_metadata(node)
            record_path("extractive_summary")
            try:
                from .telemetry import PipelineMetrics
                PipelineMetrics.record_extractive("summary_generation")
            except Exception:
                pass
        else:
            needs_slm.append((node, ext))

    if needs_slm and _slm_budget_ok():
        sections = []
        for node, ext in needs_slm:
            draft = ext.get("summary", "")
            sections.append(
                f"node_id: {node.get('node_id', '')}\n"
                f"title: {node.get('title', '')}\n"
                f"draft_summary: {draft}\n"
                f"content:\n{(node.get('text', '') or '')[:4000]}\n"
            )
        user_prompt = (
            "Improve each draft summary (2–5 sentences) and add 3–10 keywords.\n\n"
            + "\n---\n".join(sections)
        )
        system_prompt = (
            "You are a content summarization engine for educational documents. "
            "Include an entry for EVERY section provided. Respond with ONLY valid JSON."
        )
        node_ids = [n.get("node_id") for n, _ in needs_slm]
        logging.info(
            "stage=summary_generation batch=%s/%s action=run_slm nodes=%s est_tokens=unknown",
            batch_index,
            batch_index,
            node_ids,
        )
        try:
            _record_slm_call()
            batch_result = await asyncio.to_thread(
                generate_structured,
                user_prompt,
                SummaryBatch,
                system_prompt,
                stage="summary_generation",
                batch_index=batch_index,
                node_id=node_ids[0] if len(node_ids) == 1 else None,
            )
            by_id = {ns.node_id: ns for ns in batch_result.nodes}
            for node, ext in needs_slm:
                ns = by_id.get(node.get("node_id"))
                if ns:
                    node["summary"] = ns.summary
                    node["keywords"] = ns.keywords
                    node["semantic_tags"] = getattr(ns, "semantic_tags", None) or []
                    node["_summary_source"] = "slm"
                    record_path("llm_summary")
                elif ext.get("summary"):
                    node["summary"] = ext["summary"]
                    node["keywords"] = ext.get("keywords", [])
                    node["_summary_source"] = "extractive_low"
        except TokenBudgetExceeded:
            if len(needs_slm) > 1:
                mid = max(1, len(needs_slm) // 2)
                print(
                    f"[PageIndex] stage=summary_generation batch={batch_index} "
                    f"action=shrink nodes={len(needs_slm)}",
                    flush=True,
                )
                try:
                    from .telemetry import PipelineMetrics
                    PipelineMetrics.record_shrink("summary_generation")
                except Exception:
                    pass
                await _run_summary_batch(
                    [n for n, _ in needs_slm[:mid]], batch_index, model=model, checkpoints=checkpoints, opt=opt
                )
                await _run_summary_batch(
                    [n for n, _ in needs_slm[mid:]], batch_index + 1000, model=model, checkpoints=checkpoints, opt=opt
                )
                return True
        except (TimeoutError, PipelineStageFailure) as exc:
            logging.warning("summary_generation SLM failed batch=%s: %s", batch_index, exc)
            try:
                from .telemetry import PipelineMetrics
                PipelineMetrics.record_shrink("summary_generation")
            except Exception:
                pass
            if len(needs_slm) > 1:
                mid = max(1, len(needs_slm) // 2)
                await _run_summary_batch(
                    [n for n, _ in needs_slm[:mid]], batch_index, model=model, checkpoints=checkpoints, opt=opt
                )
                await _run_summary_batch(
                    [n for n, _ in needs_slm[mid:]], batch_index + 1000, model=model, checkpoints=checkpoints, opt=opt
                )
                return True
        except Exception as exc:
            logging.error("generate_summaries_for_structure batch failed: %s", exc)

    for node in batch:
        if not node.get("summary"):
            text = (node.get("text") or "")
            filled = False
            if text:
                ext = extractive.summarize(text[:3000], max_sentences=2)
                if ext.get("summary") and len(ext["summary"]) >= 20:
                    node["summary"] = ext["summary"]
                    node["keywords"] = ext.get("keywords", [])
                    node["_summary_source"] = "extractive_final_fallback"
                    filled = True
            if not filled:
                title = node.get("title", "") or "Section"
                node["summary"] = f"This section covers: {title}."
                node["keywords"] = node.get("keywords", [])
                node["_summary_source"] = "title_only"
            enrich_node_metadata(node)
            try:
                from .telemetry import PipelineMetrics
                PipelineMetrics.record_title_only("summary_generation")
            except Exception:
                pass

    if checkpoints:
        checkpoints.merge_summary_cache(
            {n.get("node_id"): {"summary": n.get("summary"), "keywords": n.get("keywords")} for n in batch}
        )
    return True


async def generate_summaries_for_structure(structure, model=None, max_nodes=None, checkpoints=None, opt=None):
    leaf_nodes = [
        n for n in structure_to_list(structure)
        if n.get("level", 1) >= 2 or n.get("content_type") not in ("chapter", None)
    ]
    chapter_nodes = [
        n for n in structure_to_list(structure)
        if n.get("level") == 1 or n.get("content_type") == "chapter"
    ]
    nodes = leaf_nodes + [c for c in chapter_nodes if c not in leaf_nodes]
    if max_nodes is not None:
        nodes = nodes[:max_nodes]
    reset_slm_summary_budget(len(nodes), getattr(opt, "slm_fallback_ratio_max", None) if opt else None)
    section_nodes = [n for n in nodes if n.get("level", 1) >= 2 or n.get("content_type") != "chapter"]
    batches = _build_summary_batches(section_nodes, max_nodes_per_batch=SUMMARY_BATCH_SIZE, model=model)
    total = len(batches)
    for batch_index, batch in enumerate(batches):
        print(
            f"[PageIndex] stage=summary_generation batch={batch_index + 1}/{total} action=run",
            flush=True,
        )
        await _run_summary_batch(batch, batch_index, model=model, checkpoints=checkpoints, opt=opt)

    for ch in chapter_nodes:
        if ch.get("nodes") or not ch.get("summary"):
            await _summarize_chapter_node(ch, model=model, opt=opt)

    from .quality_policy import prefer_llm_summaries

    for node in structure_to_list(structure):
        if not node.get("summary"):
            text = (node.get("text") or "")
            filled = False
            if text and not prefer_llm_summaries(opt):
                ext = extractive.summarize(text[:3000], max_sentences=2)
                if ext.get("summary") and len(ext["summary"]) >= 20:
                    node["summary"] = ext["summary"]
                    node["keywords"] = ext.get("keywords", [])
                    node["_summary_source"] = "extractive_final_fallback"
                    filled = True
            if not filled:
                title = node.get("title", "") or "Section"
                node["summary"] = f"This section covers: {title}."
                node["keywords"] = node.get("keywords", [])
                node["_summary_source"] = "title_only"
            enrich_node_metadata(node)

    if checkpoints:
        flat = [
            {
                "node_id": n.get("node_id"),
                "title": n.get("title"),
                "structure": n.get("structure"),
                "level": n.get("level"),
                "summary": n.get("summary", ""),
                "keywords": n.get("keywords", []),
                "semantic_tags": n.get("semantic_tags", []),
                "learning_objectives": n.get("learning_objectives", []),
                "visualizable_elements": n.get("visualizable_elements", []),
                "content_type": n.get("content_type"),
            }
            for n in structure_to_list(structure)
            if n.get("summary")
        ]
        checkpoints.save("summaries.json", flat)
    return structure


def create_clean_structure_for_description(structure):
    """
    Create a clean structure for document description generation,
    excluding unnecessary fields like 'text'.
    """
    if isinstance(structure, dict):
        clean_node = {}
        # Only include essential fields for description
        for key in ['title', 'node_id', 'summary', 'prefix_summary']:
            if key in structure:
                clean_node[key] = structure[key]
        
        # Recursively process child nodes
        if 'nodes' in structure and structure['nodes']:
            clean_node['nodes'] = create_clean_structure_for_description(structure['nodes'])
        
        return clean_node
    elif isinstance(structure, list):
        return [create_clean_structure_for_description(item) for item in structure]
    else:
        return structure


def generate_doc_description(structure, model=None):
    user_prompt = f"""You are given the hierarchical structure of a document (titles and summaries).

Document structure:
{json.dumps(structure, ensure_ascii=False, indent=2)}

Produce metadata and a high-level description for this document."""
    system_prompt = (
        "You are an expert at describing educational documents. "
        "Respond with ONLY valid JSON matching the required schema."
    )
    result = generate_structured(user_prompt, DocDescription, system_prompt=system_prompt)
    return result.model_dump()


def reorder_dict(data, key_order):
    if not key_order:
        return data
    return {key: data[key] for key in key_order if key in data}


def format_structure(structure, order=None):
    if not order:
        return structure
    if isinstance(structure, dict):
        if 'nodes' in structure:
            structure['nodes'] = format_structure(structure['nodes'], order)
        if not structure.get('nodes'):
            structure.pop('nodes', None)
        structure = reorder_dict(structure, order)
    elif isinstance(structure, list):
        structure = [format_structure(item, order) for item in structure]
    return structure


class ConfigLoader:
    def __init__(self, default_path: str = None):
        if default_path is None:
            default_path = Path(__file__).parent / "config.yaml"
        self._default_dict = self._load_yaml(default_path)

    @staticmethod
    def _load_yaml(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _validate_keys(self, user_dict):
        profile_keys = set()
        for block in ("cpu_mode", "gpu_mode", "demo_overrides", "max_quality_mode", "high_quality_mode"):
            if isinstance(self._default_dict.get(block), dict):
                profile_keys |= set(self._default_dict[block])
        known = (
            set(self._default_dict)
            | profile_keys
            | {
                "model", "test_mode", "enable_gemini_fallback", "mode", "demo",
                "resume", "benchmark", "no_summaries", "max_pages", "stage_models",
                "summary_num_predict", "boundary_extend_max_pages", "quality",
                "max_quality", "max_quality_mode", "high_quality_mode", "nvidia",
                "quality_level", "skip_deterministic_toc", "force_llm_summaries",
                "force_llm_subsections", "force_title_polish",
                "hybrid_nvidia_enabled", "nvidia_stages", "nvidia_route_after_timeouts",
                "nvidia_first", "local_fallback_model", "subsection_llm_timeout_seconds",
                "tree_max_depth", "recursive_depth", "min_heading_len", "junk_filter_strict",
                "chapter_summary_timeout_seconds", "pdf_parser",
            }
        )
        unknown_keys = set(user_dict) - known
        if unknown_keys:
            raise ValueError(f"Unknown config keys: {unknown_keys}")

    def load(self, user_opt=None) -> config:
        if user_opt is None:
            user_dict = {}
        elif isinstance(user_opt, config):
            user_dict = vars(user_opt)
        elif isinstance(user_opt, dict):
            user_dict = user_opt
        else:
            raise TypeError("user_opt must be dict, config(SimpleNamespace) or None")

        self._validate_keys(user_dict)
        merged = {**self._default_dict, **user_dict}
        mode = merged.get("mode", "cpu")
        profile = merged.get(f"{mode}_mode", {}) or {}
        if isinstance(profile, dict):
            for k, v in profile.items():
                if v is not None:
                    merged.setdefault(k, v)
        validation = merged.get("validation") or {}
        if isinstance(validation, dict):
            if validation.get("fragment_summary_max_fragment_ratio") is not None:
                merged["fragment_summary_max_fragment_ratio"] = float(
                    validation["fragment_summary_max_fragment_ratio"]
                )
        if merged.get("demo"):
            for k, v in (merged.get("demo_overrides") or {}).items():
                if v is not None:
                    merged[k] = v

        ql = str(merged.get("quality_level") or "fast").lower()
        if ql not in ("fast", "balanced", "high"):
            ql = "fast"
        if merged.get("max_quality") and ql == "fast":
            ql = "balanced"
        merged["quality_level"] = ql

        if ql == "high":
            merged["quality"] = True
            merged["max_quality"] = True
            for k, v in (merged.get("max_quality_mode") or {}).items():
                if v is not None:
                    merged[k] = v
            for k, v in (merged.get("high_quality_mode") or {}).items():
                if v is not None and k != "quality_level":
                    merged[k] = v
        elif merged.get("max_quality"):
            merged["quality"] = True
            for k, v in (merged.get("max_quality_mode") or {}).items():
                if v is not None:
                    merged[k] = v

        if "model" in user_dict:
            merged.setdefault("token_count_model", user_dict["model"])
        stage_models = merged.get("stage_models")
        if isinstance(stage_models, dict):
            merged["stage_models"] = stage_models
        opt = config(**merged)
        configure_from_opt(opt)
        global SUMMARY_BATCH_SIZE, EXTRACTIVE_MIN_CONFIDENCE, EXTRACTIVE_MAX_SENTENCES, SLM_FALLBACK_RATIO_MAX
        if merged.get("summary_nodes_per_batch"):
            SUMMARY_BATCH_SIZE = int(merged["summary_nodes_per_batch"])
        if merged.get("extractive_min_confidence") is not None:
            EXTRACTIVE_MIN_CONFIDENCE = float(merged["extractive_min_confidence"])
        if merged.get("extractive_max_sentences") is not None:
            EXTRACTIVE_MAX_SENTENCES = int(merged["extractive_max_sentences"])
        if merged.get("slm_fallback_ratio_max") is not None:
            SLM_FALLBACK_RATIO_MAX = float(merged["slm_fallback_ratio_max"])
        return opt


class PipelineCheckpoints:
    """Persist intermediate pipeline artifacts for resume/debugging."""

    def __init__(self, directory: str):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._summary_cache: dict = {}
        if (self.directory / "summary_cache.json").is_file():
            try:
                with open(self.directory / "summary_cache.json", encoding="utf-8") as f:
                    self._summary_cache = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._summary_cache = {}

    def load(self, filename: str):
        path = self.directory / filename
        if not path.is_file():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def is_done(self, filename: str, resume: bool = False) -> bool:
        if not resume:
            return False
        return (self.directory / filename).is_file()

    def save(self, filename: str, data) -> None:
        path = self.directory / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        logging.info("stage=checkpoint action=save file=%s", path.name)
        print(f"[PageIndex] checkpoint saved: {path.name}", flush=True)

    def merge_summary_cache(self, entries: dict) -> None:
        self._summary_cache.update(entries)
        self.save("summary_cache.json", self._summary_cache)

def create_node_mapping(tree):
    """Create a flat dict mapping node_id to node for quick lookup."""
    mapping = {}
    def _traverse(nodes):
        for node in nodes:
            if node.get('node_id'):
                mapping[node['node_id']] = node
            if node.get('nodes'):
                _traverse(node['nodes'])
    _traverse(tree)
    return mapping

def print_tree(tree, indent=0):
    for node in tree:
        summary = node.get('summary') or node.get('prefix_summary', '')
        summary_str = f"  —  {summary[:60]}..." if summary else ""
        print('  ' * indent + f"[{node.get('node_id', '?')}] {node.get('title', '')}{summary_str}")
        if node.get('nodes'):
            print_tree(node['nodes'], indent + 1)

def print_wrapped(text, width=100):
    for line in text.splitlines():
        print(textwrap.fill(line, width=width))


def validate_and_truncate_physical_indices(toc_with_page_number, page_list_length, start_index=1, logger=None):
    """
    Set physical_index to None for entries that reference pages beyond the document.
    This prevents index errors when the TOC cites pages not in the PDF.
    """
    if not toc_with_page_number:
        return toc_with_page_number

    max_allowed_page = page_list_length + start_index - 1
    truncated = []

    for item in toc_with_page_number:
        idx = item.get("physical_index")
        if idx is not None and idx > max_allowed_page:
            item["physical_index"] = None
            truncated.append({"title": item.get("title", "Unknown"), "original_index": idx})
            if logger:
                logger.info(
                    f"validate_and_truncate: removed physical_index for "
                    f"'{item.get('title', 'Unknown')}' (was {idx}, max={max_allowed_page})"
                )

    if truncated and logger:
        logger.info(f"validate_and_truncate: total removed={len(truncated)}")

    return toc_with_page_number


def page_list_to_group_text(page_contents, token_lengths, max_tokens=20000, overlap_page=1):
    """Split a list of page texts into groups that fit within max_tokens."""
    num_tokens = sum(token_lengths)
    if num_tokens <= max_tokens:
        return ["".join(page_contents)]

    subsets = []
    current_subset = []
    current_token_count = 0
    expected_parts_num = math.ceil(num_tokens / max_tokens)
    average_tokens_per_part = math.ceil(((num_tokens / expected_parts_num) + max_tokens) / 2)

    for i, (page_content, page_tokens) in enumerate(zip(page_contents, token_lengths)):
        if current_token_count + page_tokens > average_tokens_per_part:
            subsets.append("".join(current_subset))
            overlap_start = max(i - overlap_page, 0)
            current_subset = page_contents[overlap_start:i]
            current_token_count = sum(token_lengths[overlap_start:i])
        current_subset.append(page_content)
        current_token_count += page_tokens

    if current_subset:
        subsets.append("".join(current_subset))

    return subsets


# ── Deterministic TOC helpers ─────────────────────────────────────────────────

def _normalize_title(title: str) -> str:
    """Lowercase, collapse whitespace, strip leading numbering for fuzzy matching."""
    t = title.lower().strip()
    t = re.sub(r"^[\d\.]+\s*", "", t)  # strip leading section numbers like "1.2 "
    t = re.sub(r"\s+", " ", t)
    return t


def _fuzzy_score(title: str, page_text: str, window: int = 400) -> float:
    """Return 0-100 match score of title against the first `window` chars of page_text."""
    if not title or not page_text:
        return 0.0
    haystack = page_text[:window].lower()
    needle = _normalize_title(title)
    if not needle:
        return 0.0
    if _HAS_RAPIDFUZZ:
        return _fuzz.partial_ratio(needle, haystack)
    # Fallback: simple substring check
    return 80.0 if needle in haystack else 0.0


def deterministic_appear_start(title: str, page_text: str, threshold: float = 75.0) -> str:
    """
    Return 'yes' if `title` appears near the start of `page_text` (no LLM).
    Checks the first 400 characters with fuzzy matching.
    """
    score = _fuzzy_score(title, page_text, window=400)
    return "yes" if score >= threshold else "no"


def verify_page_anchors(toc_items: list, page_list: list, threshold: float = 70.0, logger=None) -> list:
    """Cross-check TOC anchors using fuzzy page-title matching."""
    for item in toc_items:
        idx = item.get("physical_index")
        if idx is None:
            continue
        list_idx = idx - 1
        if list_idx < 0 or list_idx >= len(page_list):
            item["physical_index"] = None
            continue
        best_idx = idx
        best_score = _fuzzy_score(item.get("title", ""), page_list[list_idx][0])
        for delta in (-2, -1, 1, 2):
            j = idx + delta
            if 1 <= j <= len(page_list):
                s = _fuzzy_score(item.get("title", ""), page_list[j - 1][0])
                if s > best_score + 5:
                    best_idx, best_score = j, s
        if best_score < threshold:
            if logger:
                logger.info(
                    "page_anchor_verify: kept '%s' at page %s (low score=%.1f)",
                    item.get("title", ""),
                    idx,
                    best_score,
                )
        elif best_idx != idx:
            item["physical_index"] = best_idx
            if logger:
                logger.info(
                    "page_anchor_verify: '%s' %d -> %d (score=%.1f)",
                    item.get("title", ""),
                    idx,
                    best_idx,
                    best_score,
                )
    return toc_items


def semantic_dedupe(structure: list, logger=None) -> list:
    """Merge duplicate/overlapping TOC nodes before summarization."""
    if not structure or not isinstance(structure, list):
        return structure

    def _overlap(a, b) -> float:
        sa, ea = a.get("start_index"), a.get("end_index")
        sb, eb = b.get("start_index"), b.get("end_index")
        if None in (sa, ea, sb, eb):
            return 0.0
        inter = max(0, min(ea, eb) - max(sa, sb) + 1)
        union = max(ea, eb) - min(sa, sb) + 1
        return inter / union if union else 0.0

    cleaned = []
    for node in structure:
        title_norm = _normalize_title(node.get("title", ""))
        merged = False
        for prev in cleaned:
            prev_norm = _normalize_title(prev.get("title", ""))
            if title_norm and title_norm == prev_norm:
                if node.get("nodes"):
                    prev.setdefault("nodes", []).extend(node.get("nodes", []))
                if node.get("end_index"):
                    prev["end_index"] = max(prev.get("end_index", 0), node["end_index"])
                merged = True
                if logger:
                    logger.info("semantic_dedupe: merged duplicate title '%s'", node.get("title"))
                break
            if _overlap(prev, node) >= 0.8:
                if (node.get("end_index", 0) - node.get("start_index", 0)) <= (
                    prev.get("end_index", 0) - prev.get("start_index", 0)
                ):
                    merged = True
                    if logger:
                        logger.info("semantic_dedupe: dropped overlapping '%s'", node.get("title"))
                    break
        cont_markers = ("(continued)", "cont.", "continued")
        if not merged and cleaned:
            t = (node.get("title") or "").lower()
            if any(m in t for m in cont_markers):
                prev = cleaned[-1]
                prev["end_index"] = max(prev.get("end_index", 0), node.get("end_index", 0))
                merged = True
                if logger:
                    logger.info("semantic_dedupe: folded continuation '%s'", node.get("title"))
        if not merged:
            cleaned.append(node)
    return cleaned


def deterministic_repair_missing_pages(
    toc_items: list,
    page_list: list,
    start_index: int = 1,
    fuzzy_threshold: float = 75.0,
    logger=None,
) -> list:
    """
    For TOC entries missing `physical_index`, attempt to fill by fuzzy-matching the
    title against pages between the previous and next known physical_index values.
    Then enforce monotonic non-decreasing order; drop entries that violate it.

    `page_list` is a list of (page_text, token_count) tuples (1-based via start_index).
    """
    n = len(toc_items)
    max_page = len(page_list) + start_index - 1

    # Pass 1: fuzzy fill missing physical_index values
    for i, item in enumerate(toc_items):
        if item.get("physical_index") is not None:
            continue

        # Determine search window from neighbors
        prev_idx = start_index
        for j in range(i - 1, -1, -1):
            if toc_items[j].get("physical_index") is not None:
                prev_idx = toc_items[j]["physical_index"]
                break

        next_idx = max_page
        for j in range(i + 1, n):
            if toc_items[j].get("physical_index") is not None:
                next_idx = toc_items[j]["physical_index"]
                break

        best_score = 0.0
        best_page = None
        title = item.get("title", "")
        for page_num in range(prev_idx, next_idx + 1):
            list_idx = page_num - start_index
            if list_idx < 0 or list_idx >= len(page_list):
                continue
            page_text = page_list[list_idx][0]
            score = _fuzzy_score(title, page_text)
            if score > best_score:
                best_score = score
                best_page = page_num

        if best_page is not None and best_score >= fuzzy_threshold:
            item["physical_index"] = best_page
            if logger:
                logger.info(f"deterministic_repair: filled '{title}' -> page {best_page} (score={best_score:.1f})")
        else:
            if logger:
                logger.info(f"deterministic_repair: could not fill '{title}' (best_score={best_score:.1f})")

    # Pass 2: enforce monotonic non-decreasing physical_index; drop violators
    cleaned = []
    last_valid = start_index - 1
    for item in toc_items:
        idx = item.get("physical_index")
        if idx is None:
            cleaned.append(item)  # keep; filtered later by caller
            continue
        if idx >= last_valid:
            cleaned.append(item)
            last_valid = idx
        else:
            if logger:
                logger.info(
                    f"deterministic_repair: dropped '{item.get('title', '')}' "
                    f"physical_index={idx} violates monotonic order (last={last_valid})"
                )

    return cleaned

