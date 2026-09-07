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


def run_translate(args: argparse.Namespace) -> int:
    """Execute document translation."""
    config = load_config()
    logger = setup_logger(logs_dir=config.logs_dir, name="translator")

    input_file = Path(args.input_file).resolve()
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}", file=sys.stderr)
        return 1

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

    pipeline = TranslationPipeline(
        config=config,
        ollama_client=client,
        logger=logger
    )

    try:
        summary = pipeline.run(
            input_path=input_file,
            output_path=Path(args.output) if args.output else None,
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="local-translator",
        description="Local Japanese to Vietnamese Document Translation Pipeline using Ollama + TranslateGemma 4B"
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # check subcommand
    subparsers.add_parser("check", help="Run system diagnostics (Ollama, models, configuration)")

    # translate subcommand
    translate_parser = subparsers.add_parser("translate", help="Translate a document")
    translate_parser.add_argument("input_file", help="Path to input document (e.g. input/book.txt)")
    translate_parser.add_argument("-o", "--output", help="Path to output document (default: output/<filename>_vi.txt)")
    translate_parser.add_argument("--chunk-size", type=int, help="Target Japanese chunk size in characters (default: 1800)")
    translate_parser.add_argument("--context-size", type=int, help="Previous chunk context length in characters (default: 600)")
    translate_parser.add_argument("--force", action="store_true", help="Force retranslation of all chunks (ignore cache)")
    translate_parser.add_argument("--continue-on-error", action="store_true", help="Continue job even if a chunk fails")
    translate_parser.add_argument("--model", help="Override Ollama model name (default: translategemma:4b)")
    translate_parser.add_argument("--temperature", type=float, help="Override sampling temperature (default: 0.1)")
    translate_parser.add_argument("--host", help="Override Ollama host URL (default: http://localhost:11434)")

    return parser


def main() -> None:
    parser = build_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    if args.command == "check":
        sys.exit(run_check(args))
    elif args.command == "translate":
        sys.exit(run_translate(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
