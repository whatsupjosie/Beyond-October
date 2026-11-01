"""
Command-line interface for PubPartner.

    pubpartner init <dir> --name NAME --summary SUMMARY --cadence C --vocabulary V
    pubpartner add-memory <cartridge> --type TYPE --text TEXT [--importance 0.0-1.0]
    pubpartner memories <cartridge> [--type TYPE]
    pubpartner prompt <cartridge> [--query TEXT] [--budget N]
    pubpartner chat <cartridge>          # interactive session against Claude
"""

from __future__ import annotations

import argparse
import os
import sys

from .cartridge import Cartridge, CartridgeValidationError, init_cartridge, load_cartridge
from .memory_store import MEMORY_TYPES, MemoryStoreError
from .prompt_assembler import DEFAULT_TOKEN_BUDGET, assemble_prompt
from .portable_runtime import PortableRuntime


def _cmd_init(args: argparse.Namespace) -> int:
    try:
        path = init_cartridge(
            args.directory,
            name=args.name,
            summary=args.summary,
            cadence=args.cadence,
            vocabulary=args.vocabulary,
        )
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Created cartridge at {path}")
    print("Edit character.yaml, voice_profile.yaml, and appearance.yaml, then add memories.")
    return 0


def _open(cartridge_path: str) -> Cartridge | None:
    try:
        return load_cartridge(cartridge_path)
    except (FileNotFoundError, CartridgeValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None


def _cmd_add_memory(args: argparse.Namespace) -> int:
    cartridge = _open(args.cartridge)
    if cartridge is None:
        return 1
    try:
        memory_id = cartridge.memory.add(args.text, args.type, importance=args.importance)
    except MemoryStoreError as exc:
        print(f"error: {exc}", file=sys.stderr)
        cartridge.close()
        return 1
    print(f"Added memory #{memory_id} ({args.type})")
    cartridge.close()
    return 0


def _cmd_memories(args: argparse.Namespace) -> int:
    cartridge = _open(args.cartridge)
    if cartridge is None:
        return 1
    for m in cartridge.memory.all(memory_type=args.type):
        print(f"[{m.id}] ({m.memory_type}, importance={m.importance:.2f}, {m.created_at}) {m.text}")
    cartridge.close()
    return 0


def _cmd_prompt(args: argparse.Namespace) -> int:
    cartridge = _open(args.cartridge)
    if cartridge is None:
        return 1
    result = assemble_prompt(cartridge, query=args.query or "", token_budget=args.budget)
    print(result.text)
    print("---", file=sys.stderr)
    print(
        f"tokens={result.token_count} memories={result.memories_included}/{result.memories_available} "
        f"truncated={result.truncated}",
        file=sys.stderr,
    )
    cartridge.close()
    return 0


def _cmd_chat(args: argparse.Namespace) -> int:
    cartridge = _open(args.cartridge)
    if cartridge is None:
        return 1

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "error: ANTHROPIC_API_KEY is not set. Export it to use `chat`; "
            "`prompt` works without an API key.",
            file=sys.stderr,
        )
        cartridge.close()
        return 1

    try:
        import anthropic
    except ImportError:
        print("error: the `anthropic` package is not installed. Run: pip install anthropic", file=sys.stderr)
        cartridge.close()
        return 1

    client = anthropic.Anthropic(api_key=api_key)
    runtime = PortableRuntime(cartridge, llm_client=client, model=args.model,
        max_tokens=args.max_tokens, token_budget=args.budget)
    print(f"Chatting with {cartridge.name}. Ctrl-D to exit.")

    try:
        while True:
            try:
                user_input = input("you> ")
            except EOFError:
                print()
                break
            if not user_input.strip():
                continue

            runtime.submit_input(user_input)
            result = runtime.run_turn()
            print(f"{cartridge.name}> {result.reply_text}")
    finally:
        runtime.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pubpartner", description="Persistent character cartridges.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Scaffold a new cartridge")
    p_init.add_argument("directory")
    p_init.add_argument("--name", required=True)
    p_init.add_argument("--summary", required=True)
    p_init.add_argument("--cadence", required=True)
    p_init.add_argument("--vocabulary", required=True)
    p_init.set_defaults(func=_cmd_init)

    p_add = sub.add_parser("add-memory", help="Add a memory to a cartridge")
    p_add.add_argument("cartridge")
    p_add.add_argument("--type", required=True, choices=MEMORY_TYPES)
    p_add.add_argument("--text", required=True)
    p_add.add_argument("--importance", type=float, default=0.5)
    p_add.set_defaults(func=_cmd_add_memory)

    p_list = sub.add_parser("memories", help="List memories in a cartridge")
    p_list.add_argument("cartridge")
    p_list.add_argument("--type", choices=MEMORY_TYPES, default=None)
    p_list.set_defaults(func=_cmd_memories)

    p_prompt = sub.add_parser("prompt", help="Build and print the assembled system prompt")
    p_prompt.add_argument("cartridge")
    p_prompt.add_argument("--query", default="")
    p_prompt.add_argument("--budget", type=int, default=DEFAULT_TOKEN_BUDGET)
    p_prompt.set_defaults(func=_cmd_prompt)

    p_chat = sub.add_parser("chat", help="Interactive chat session using this cartridge")
    p_chat.add_argument("cartridge")
    p_chat.add_argument("--budget", type=int, default=DEFAULT_TOKEN_BUDGET)
    p_chat.add_argument("--model", default="claude-sonnet-4-6")
    p_chat.add_argument("--max-tokens", type=int, default=1024)
    p_chat.set_defaults(func=_cmd_chat)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
