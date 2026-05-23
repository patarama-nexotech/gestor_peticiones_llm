#!/usr/bin/env python3
"""Minimal file-driven request runner for OpenAI Responses API."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from agents import apply_diff
from openai import OpenAI


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def build_files_user_message(file_paths: list[Path]) -> str:
    lines: list[str] = ["<BEGIN_FILES>"]

    for file_path in file_paths:
        content = file_path.read_text(encoding="utf-8")
        lines.append("=====")
        lines.append(str(file_path))
        lines.append(content)

    lines.append("<END_FILES>")
    return "\n".join(lines)


def get_value(obj: object, key: str, default: object = None) -> object:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def resolve_allowed_path(path_value: str, base_dir: Path) -> Path:
    candidate = Path(path_value)
    target = candidate if candidate.is_absolute() else (base_dir / candidate)
    target = target.resolve()
    try:
        target.relative_to(base_dir)
    except ValueError:
        raise RuntimeError(f"Operation outside workspace: {target}") from None
    return target


def apply_patch_calls(response: object, base_dir: Path) -> list[dict[str, str]]:
    outputs: list[dict[str, str]] = []
    response_output = get_value(response, "output", [])

    for item in response_output:
        if get_value(item, "type") != "apply_patch_call":
            continue

        call_id = str(get_value(item, "call_id", ""))
        operation = get_value(item, "operation", {})
        op_type = str(get_value(operation, "type", ""))
        op_path = str(get_value(operation, "path", ""))
        op_diff = str(get_value(operation, "diff", "") or "")

        try:
            target = resolve_allowed_path(op_path, base_dir)

            if op_type == "create_file":
                content = apply_diff("", op_diff, mode="create")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                message = f"Created {target}"
            elif op_type == "update_file":
                original = target.read_text(encoding="utf-8")
                patched = apply_diff(original, op_diff)
                target.write_text(patched, encoding="utf-8")
                message = f"Updated {target}"
            elif op_type == "delete_file":
                target.unlink(missing_ok=True)
                message = f"Deleted {target}"
            else:
                raise RuntimeError(f"Unsupported operation type: {op_type}")

            outputs.append(
                {
                    "type": "apply_patch_call_output",
                    "call_id": call_id,
                    "status": "completed",
                    "output": message,
                }
            )
        except Exception as exc:
            outputs.append(
                {
                    "type": "apply_patch_call_output",
                    "call_id": call_id,
                    "status": "failed",
                    "output": str(exc),
                }
            )

    return outputs


def run(spec_path: Path) -> None:
    load_env(Path(__file__).with_name(".env"))
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY in .env")

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    base_dir = spec_path.parent.resolve()

    developer_path = (base_dir / spec["developer_file"]).resolve()
    user_file_paths = [(base_dir / p).resolve() for p in spec["user_files"]]
    prompt_path = (base_dir / spec["prompt_file"]).resolve()
    output_path = (base_dir / spec.get("output_file", "response_output.txt")).resolve()

    model = spec.get("model", "gpt-5.4-mini")
    effort = spec.get("effort", "low")
    tools = [
        {
            "type": "web_search",
            "user_location": {"type": "approximate", "country": "PE"},
            "search_context_size": "medium",
        },
        {"type": "apply_patch"},
    ]

    developer_content = developer_path.read_text(encoding="utf-8")
    files_user_content = build_files_user_message(user_file_paths)
    prompt_content = prompt_path.read_text(encoding="utf-8")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        text={"format": {"type": "text"}, "verbosity": "medium"},
        reasoning={"effort": effort, "summary": "auto"},
        tools=tools,
        store=True,
        include=["reasoning.encrypted_content", "web_search_call.action.sources"],
        input=[
            {"role": "developer", "content": developer_content},
            {"role": "user", "content": files_user_content},
            {"role": "user", "content": prompt_content},
        ],
    )

    while True:
        patch_results = apply_patch_calls(response, base_dir)
        if not patch_results:
            break
        response = client.responses.create(
            model=model,
            text={"format": {"type": "text"}, "verbosity": "medium"},
            reasoning={"effort": effort, "summary": "auto"},
            tools=tools,
            store=True,
            include=["reasoning.encrypted_content", "web_search_call.action.sources"],
            previous_response_id=getattr(response, "id"),
            input=patch_results,
        )

    output_text = response.output_text or ""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output_text, encoding="utf-8")

    print(f"Request completed. Output saved to: {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute a Responses API request from a JSON spec file."
    )
    parser.add_argument(
        "--spec",
        required=True,
        type=Path,
        help="Path to the JSON spec file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(args.spec.resolve())


if __name__ == "__main__":
    main()
