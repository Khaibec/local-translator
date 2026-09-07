"""CLI entrypoint for local Japanese to Vietnamese translation pipeline."""

import argparse
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.config import load_config
from src.utils.logger import setup_logger
from src.translation.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaModelNotFoundError
)
from src.pipeline.translation_pipeline import TranslationPipeline, PipelineExecutionError
from src.pipeline.novel_pipeline import NovelTranslationPipeline
from src.crawler import get_crawler_for_url, CrawlerError


def run_check(args: argparse.Namespace) -> int:
    """Run environment, configuration, and Ollama health diagnostics."""
    config = load_config()
    print("=" * 60)
    print("  Local Japanese -> Vietnamese Translator: System Diagnostics")
    print("=" * 60)

    # 1. Python Environment
    py_ver = sys.version.split()[0]
    print(f"\n[1] Python Environment: {py_ver} ({sys.platform})")
    if sys.version_info >= (3, 10):
        print("    -> OK (Python 3.10+ requirement satisfied)")
    else:
        print("    -> WARNING: Python 3.11+ is recommended.")

    # 2. Dependencies
    print("\n[2] Required Python Packages:")
    packages = [
        ("requests", "requests"),
        ("yaml", "pyyaml"),
        ("tqdm", "tqdm"),
        ("docx", "python-docx"),
        ("bs4", "beautifulsoup4"),
    ]
    all_packages_ok = True
    for module_name, pip_name in packages:
        try:
            __import__(module_name)
            print(f"    - {pip_name}: OK")
        except ImportError:
            print(f"    - {pip_name}: MISSING (install with: pip install {pip_name})")
            all_packages_ok = False

    # 3. Project Configuration & Files
    print("\n[3] Configuration Files:")
    files = [
        ("Settings", config.settings_path),
        ("Prompt Template", config.prompt_path),
        ("Glossary", config.glossary_path),
    ]
    for label, path in files:
        if path.exists():
            print(f"    - {label}: OK ({path})")
        else:
            print(f"    - {label}: MISSING at {path}")

    # 4. Ollama Service & Model Check
    print(f"\n[4] Ollama Service & Model Diagnostics:")
    print(f"    - Ollama Host: {config.ollama_host}")
    print(f"    - Target Model: {config.ollama_model}")

    client = OllamaClient(
        host=config.ollama_host,
        model=config.ollama_model,
        timeout=config.ollama_timeout
    )

    ollama_ok = False
    model_ok = False

    if client.is_reachable():
        print("    - Ollama Connectivity: REACHABLE")
        ollama_ok = True
        try:
            installed_models = client.list_installed_models()
            print(f"    - Installed models ({len(installed_models)}): {', '.join(installed_models) or 'None'}")
            if client.is_model_installed(config.ollama_model):
                print(f"    - Target model '{config.ollama_model}': INSTALLED (Ready to use)")
                model_ok = True
            else:
                print(f"    - Target model '{config.ollama_model}': NOT FOUND")
                print(f"\n      -> Action required: Run the following command in PowerShell/CMD:")
                print(f"         ollama pull {config.ollama_model}\n")
        except Exception as e:
            print(f"    - Error listing models: {e}")
    else:
        print("    - Ollama Connectivity: UNREACHABLE (Service not running or endpoint incorrect)")
        print("\n      -> Action required: Start Ollama service on your Windows machine.")
        print("         Make sure the Ollama desktop application is started, or test in terminal:")
        print("         ollama list\n")

    print("=" * 60)
    if all_packages_ok and ollama_ok and model_ok:
        print("  STATUS: ALL CHECKS PASSED. Ready to translate documents!")
        print("=" * 60)
        return 0
    else:
        print("  STATUS: ACTION REQUIRED BEFORE TRANSLATING.")
        print("=" * 60)
        return 1


def run_crawl(args: argparse.Namespace) -> int:
    """Crawl a Japanese web novel."""
    config = load_config()
    logger = setup_logger(logs_dir=config.logs_dir, name="crawler")

    timeout = args.timeout or config.crawler_timeout
    delay = args.delay if args.delay is not None else config.crawler_delay

    crawler = get_crawler_for_url(
        url=args.url,
        timeout_seconds=timeout,
        delay_seconds=delay,
        user_agent=config.crawler_user_agent,
        logger=logger
    )

    print("\n" + "=" * 60)
    print("  WEB NOVEL CRAWLER")
    print("=" * 60)
    print(f"Target URL: {args.url}")
    print(f"Polite Delay: {delay}s | Timeout: {timeout}s")
    print("=" * 60 + "\n")

    try:
        metadata = crawler.crawl(
            novel_url=args.url,
            input_base_dir=config.input_dir,
            cache_base_dir=config.cache_dir,
            force=args.force
        )
        print("\n" + "=" * 60)
        print("  CRAWL COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"Title:         {metadata.title}")
        print(f"Ncode:         {metadata.ncode}")
        print(f"Chapters:      {metadata.chapter_count}")
        print(f"Location:      {config.input_dir / metadata.ncode}")
        print("=" * 60)
        print(f"\nTo translate this novel, run:")
        print(f"    python -m src.main translate {metadata.ncode}\n")
        return 0
    except CrawlerError as e:
        print(f"\n[Crawler Error] {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"\n[Unexpected Error] {e}", file=sys.stderr)
        logger.exception("Unexpected error during crawl.")
        return 3


def run_translate(args: argparse.Namespace) -> int:
    """Execute document or novel translation."""
    config = load_config()
    logger = setup_logger(logs_dir=config.logs_dir, name="translator")

    input_str = args.input_path
    input_path = Path(input_str).resolve()

    # Check if input points to a crawled novel directory or ncode
    is_novel = False
    novel_identifier = None

    if input_path.is_dir() and (input_path / "novel.json").exists():
        is_novel = True
        novel_identifier = str(input_path)
    elif (config.input_dir / input_str).is_dir() and (config.input_dir / input_str / "novel.json").exists():
        is_novel = True
        novel_identifier = str(config.input_dir / input_str)
    elif not input_path.exists() and (config.input_dir / input_str.lower()).is_dir():
        is_novel = True
        novel_identifier = str(config.input_dir / input_str.lower())

    # Overrides
    if args.model:
        config.ollama_model = args.model
    if args.host:
        config.ollama_host = args.host
    if args.temperature is not None:
        config.temperature = args.temperature
    if args.chunk_size:
        config.chunk_size = args.chunk_size
    if args.context_size:
        config.context_size = args.context_size
    if args.continue_on_error:
        config.continue_on_error = True

    client = OllamaClient(
        host=config.ollama_host,
        model=config.ollama_model,
        timeout=config.ollama_timeout,
        max_retries=config.max_retries,
        retry_backoff=config.retry_backoff,
        logger=logger
    )

    if is_novel:
        # Novel translation workflow
        pipeline = NovelTranslationPipeline(
            config=config,
            ollama_client=client,
            logger=logger
        )
        try:
            start_ch = getattr(args, "start_chapter", None)
            end_ch = getattr(args, "end_chapter", None)
            summary = pipeline.run(
                ncode_or_dir=novel_identifier,
                start_chapter=start_ch,
                end_chapter=end_ch,
                force=args.force,
                continue_on_error=args.continue_on_error,
                chunk_size=args.chunk_size,
                context_size=args.context_size,
                temperature=args.temperature
            )

            print("\n" + "=" * 60)
            print("  NOVEL TRANSLATION COMPLETED SUCCESSFULLY")
            print("=" * 60)
            print(f"Novel Title:       {summary['title']}")
            print(f"Ncode:             {summary['ncode']}")
            print(f"Total Chapters:    {summary['total_chapters']}")
            print(f"Translated:        {summary['translated_chapters']}")
            print(f"Chunks Translated: {summary['translated_chunks_session']}")
            print(f"Characters:        {summary['translated_chars_session']:,}")
            print(f"Output Directory:  {summary['output_dir']}")
            print(f"Elapsed Time:      {summary['elapsed_seconds']}s")
            print("=" * 60)
            return 0

        except (OllamaConnectionError, OllamaModelNotFoundError) as e:
            print(f"\n[Ollama Configuration Error]\n{e}", file=sys.stderr)
            return 2
        except PipelineExecutionError as e:
            print(f"\n[Translation Error]\n{e}", file=sys.stderr)
            return 3
        except Exception as e:
            print(f"\n[Unexpected Error] {e}", file=sys.stderr)
            logger.exception("Unexpected exception occurred during novel translation run.")
            return 4

    else:
        # Single document translation workflow (Phase 1)
        if not input_path.exists():
            print(f"Error: Input file or novel directory not found: {input_str}", file=sys.stderr)
            return 1

        pipeline = TranslationPipeline(
            config=config,
            ollama_client=client,
            logger=logger
        )

        try:
            summary = pipeline.run(
                input_path=input_path,
                output_path=Path(args.output) if getattr(args, "output", None) else None,
                force=args.force,
                continue_on_error=args.continue_on_error,
                chunk_size=args.chunk_size,
                context_size=args.context_size,
                temperature=args.temperature
            )

            print("\n" + "=" * 60)
            print("  TRANSLATION COMPLETED SUCCESSFULLY")
            print("=" * 60)
            print(f"Input:             {summary['input_file']}")
            print(f"Output:            {summary['output_file']}")
            print(f"Model:             {summary['model']}")
            print(f"Total Chunks:      {summary['total_chunks']}")
            print(f"Completed:         {summary['completed_chunks']}")
            print(f"Failed:            {summary['failed_chunks']}")
            print(f"Source Characters: {summary['source_characters']:,}")
            print(f"Elapsed Time:      {summary['elapsed_seconds']}s")
            print("=" * 60)
            return 0

        except (OllamaConnectionError, OllamaModelNotFoundError) as e:
            print(f"\n[Ollama Configuration Error]\n{e}", file=sys.stderr)
            return 2
        except PipelineExecutionError as e:
            print(f"\n[Translation Error]\n{e}", file=sys.stderr)
            return 3
        except Exception as e:
            print(f"\n[Unexpected Error] {e}", file=sys.stderr)
            logger.exception("Unexpected exception occurred during translation run.")
            return 4


def run_crawl_translate(args: argparse.Namespace) -> int:
    """Crawl and translate a novel in a single command."""
    print("\n>>> STEP 1: Crawling web novel...")
    crawl_rc = run_crawl(args)
    if crawl_rc != 0:
        return crawl_rc

    config = load_config()
    crawler = get_crawler_for_url(args.url)
    ncode = crawler.extract_novel_id(args.url)

    # Set input_path to crawled novel directory
    args.input_path = str(config.input_dir / ncode)
    args.output = None

    print("\n>>> STEP 2: Translating novel chapters...")
    return run_translate(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="local-translator",
        description="Local Japanese to Vietnamese Document & Novel Translation Pipeline using Ollama + TranslateGemma 4B"
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # check subcommand
    subparsers.add_parser("check", help="Run system diagnostics (Ollama, models, configuration)")

    # crawl subcommand
    crawl_parser = subparsers.add_parser("crawl", help="Crawl a Japanese web novel from URL")
    crawl_parser.add_argument("url", help="Novel URL (e.g. https://ncode.syosetu.com/n1234ab/)")
    crawl_parser.add_argument("--delay", type=float, help="Polite delay between requests in seconds (default: 1.0)")
    crawl_parser.add_argument("--timeout", type=int, help="Request timeout in seconds (default: 30)")
    crawl_parser.add_argument("--force", action="store_true", help="Force re-download of already crawled chapters")

    # translate subcommand
    translate_parser = subparsers.add_parser("translate", help="Translate a document or a crawled novel")
    translate_parser.add_argument("input_path", help="Path to input document (e.g. input/book.txt) or novel (e.g. input/n1234ab or n1234ab)")
    translate_parser.add_argument("-o", "--output", help="Path to output document (applicable to single files)")
    translate_parser.add_argument("--start-chapter", type=int, help="Start chapter index for novel translation (e.g. 1)")
    translate_parser.add_argument("--end-chapter", type=int, help="End chapter index for novel translation (e.g. 10)")
    translate_parser.add_argument("--chunk-size", type=int, help="Target Japanese chunk size in characters (default: 1800)")
    translate_parser.add_argument("--context-size", type=int, help="Previous chunk context length in characters (default: 600)")
    translate_parser.add_argument("--force", action="store_true", help="Force retranslation of all chunks (ignore cache)")
    translate_parser.add_argument("--continue-on-error", action="store_true", help="Continue job even if a chunk fails")
    translate_parser.add_argument("--model", help="Override Ollama model name (default: translategemma:4b)")
    translate_parser.add_argument("--temperature", type=float, help="Override sampling temperature (default: 0.1)")
    translate_parser.add_argument("--host", help="Override Ollama host URL (default: http://localhost:11434)")

    # crawl-translate subcommand
    ct_parser = subparsers.add_parser("crawl-translate", help="Crawl and translate a web novel in one command")
    ct_parser.add_argument("url", help="Novel URL (e.g. https://ncode.syosetu.com/n1234ab/)")
    ct_parser.add_argument("--delay", type=float, help="Polite delay between requests in seconds (default: 1.0)")
    ct_parser.add_argument("--timeout", type=int, help="Request timeout in seconds (default: 30)")
    ct_parser.add_argument("--start-chapter", type=int, help="Start chapter index (e.g. 1)")
    ct_parser.add_argument("--end-chapter", type=int, help="End chapter index (e.g. 10)")
    ct_parser.add_argument("--chunk-size", type=int, help="Target Japanese chunk size in characters (default: 1800)")
    ct_parser.add_argument("--context-size", type=int, help="Previous chunk context length in characters (default: 600)")
    ct_parser.add_argument("--force", action="store_true", help="Force retranslation/recrawl (ignore cache)")
    ct_parser.add_argument("--continue-on-error", action="store_true", help="Continue job even if a chunk fails")
    ct_parser.add_argument("--model", help="Override Ollama model name (default: translategemma:4b)")
    ct_parser.add_argument("--temperature", type=float, help="Override sampling temperature (default: 0.1)")
    ct_parser.add_argument("--host", help="Override Ollama host URL (default: http://localhost:11434)")

    return parser


def main() -> None:
    parser = build_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    if args.command == "check":
        sys.exit(run_check(args))
    elif args.command == "crawl":
        sys.exit(run_crawl(args))
    elif args.command == "translate":
        sys.exit(run_translate(args))
    elif args.command == "crawl-translate":
        sys.exit(run_crawl_translate(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
