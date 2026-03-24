"""Rigorously MCP Server — Model Context Protocol integration.

Exposes research integrity tools via the MCP protocol for integration
with compatible platforms.

Usage:
    python -m rigorous.mcp_server
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path


def create_server():
    """Create and configure the MCP server."""
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import TextContent, Tool
    except ImportError:
        raise ImportError(
            "MCP package not installed. Install with: pip install \"rigorously[mcp]\""
        )

    server = Server("rigorously")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="check_paper",
                description="Run all integrity checks on a manuscript (.tex or .md) and optional .bib file.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tex_path": {
                            "type": "string",
                            "description": "Path to .tex or .md manuscript file.",
                        },
                        "bib_path": {
                            "type": "string",
                            "description": "Path to .bib bibliography file (optional).",
                        },
                        "code_directory": {
                            "type": "string",
                            "description": "Directory containing Python code (optional).",
                        },
                    },
                    "required": ["tex_path"],
                },
            ),
            Tool(
                name="verify_citation",
                description="Verify a single DOI against the CrossRef API.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "doi": {
                            "type": "string",
                            "description": "The DOI to verify (e.g., '10.1038/s41586-020-2649-2').",
                        },
                    },
                    "required": ["doi"],
                },
            ),
            Tool(
                name="check_overclaims",
                description="Scan a manuscript file for overclaimed results and language issues.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tex_path": {
                            "type": "string",
                            "description": "Path to .tex or .md file.",
                        },
                    },
                    "required": ["tex_path"],
                },
            ),
            Tool(
                name="audit_parameters",
                description="Check ODE parameter consistency in a Python file (comments vs code values).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "python_path": {
                            "type": "string",
                            "description": "Path to a Python file containing ODE model parameters.",
                        },
                    },
                    "required": ["python_path"],
                },
            ),
            Tool(
                name="generate_report",
                description="Generate a full Markdown integrity report for a manuscript.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tex_path": {
                            "type": "string",
                            "description": "Path to .tex or .md manuscript file.",
                        },
                        "bib_path": {
                            "type": "string",
                            "description": "Path to .bib file (optional).",
                        },
                        "code_directory": {
                            "type": "string",
                            "description": "Code directory (optional).",
                        },
                    },
                    "required": ["tex_path"],
                },
            ),
            Tool(
                name="audit_time_units",
                description=(
                    "Audit time unit consistency across ODE model files. "
                    "Detects mismatched time units (hours vs minutes) and "
                    "verifies coupling/solver code has proper conversions."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "code_directory": {
                            "type": "string",
                            "description": "Directory containing ODE model Python files.",
                        },
                        "solver_directories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Additional directories to scan for solver/coupling files (optional).",
                        },
                    },
                    "required": ["code_directory"],
                },
            ),
            Tool(
                name="verify_numbers",
                description=(
                    "Verify that numbers in LaTeX tables match Python script output. "
                    "Extracts numbers from tabular environments, runs the script, "
                    "and flags discrepancies >5% (warning) or >20% (critical)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tex_path": {
                            "type": "string",
                            "description": "Path to .tex manuscript file.",
                        },
                        "script_path": {
                            "type": "string",
                            "description": "Path to Python script that produces the paper's results.",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Max seconds to run the script (default 120).",
                        },
                        "warning_threshold": {
                            "type": "number",
                            "description": "Relative difference for warnings (default 0.05 = 5%).",
                        },
                        "critical_threshold": {
                            "type": "number",
                            "description": "Relative difference for critical findings (default 0.20 = 20%).",
                        },
                    },
                    "required": ["tex_path", "script_path"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "check_paper":
            return await _handle_check_paper(arguments)
        elif name == "verify_citation":
            return await _handle_verify_citation(arguments)
        elif name == "check_overclaims":
            return await _handle_check_overclaims(arguments)
        elif name == "audit_parameters":
            return await _handle_audit_parameters(arguments)
        elif name == "generate_report":
            return await _handle_generate_report(arguments)
        elif name == "audit_time_units":
            return await _handle_audit_time_units(arguments)
        elif name == "verify_numbers":
            return await _handle_verify_numbers(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    async def _handle_check_paper(args: dict) -> list[TextContent]:
        from .core.review import generate_review

        tex_path = args["tex_path"]
        bib_path = args.get("bib_path")
        code_dir = args.get("code_directory")

        review = generate_review(
            tex_filepath=tex_path,
            bib_filepath=bib_path,
            code_directory=code_dir,
            skip_citations=bib_path is None,
            skip_reproducibility=True,
        )

        result = {
            "overall_rating": review.overall_rating,
            "summary": review.summary,
            "finding_counts": review.finding_counts,
            "major_issues": review.major_issues[:20],
            "minor_issues": review.minor_issues[:20],
            "suggestions": review.suggestions[:10],
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _handle_verify_citation(args: dict) -> list[TextContent]:
        from .core.citations import verify_doi

        doi = args["doi"]
        result = await verify_doi(doi)
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    async def _handle_check_overclaims(args: dict) -> list[TextContent]:
        from .core.overclaim import check_overclaims

        findings = check_overclaims(args["tex_path"])
        result = [
            {
                "file": f.file,
                "line": f.line,
                "matched_text": f.matched_text,
                "pattern_name": f.pattern_name,
                "severity": f.severity,
                "suggestion": f.suggestion,
            }
            for f in findings
        ]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _handle_audit_parameters(args: dict) -> list[TextContent]:
        from .core.parameters import check_parameters

        findings = check_parameters(args["python_path"])
        result = [
            {
                "file": f.file,
                "line": f.line,
                "severity": f.severity,
                "issue": f.issue,
                "details": f.details,
            }
            for f in findings
        ]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _handle_generate_report(args: dict) -> list[TextContent]:
        from .core.consistency import check_consistency
        from .core.overclaim import check_overclaims
        from .core.statistics import check_statistics
        from .report import generate_markdown_report

        tex_path = args["tex_path"]
        findings_by_check: dict[str, list] = {}

        try:
            findings_by_check["Overclaim Detection"] = check_overclaims(tex_path)
        except Exception as e:
            findings_by_check["Overclaim Detection"] = []

        try:
            findings_by_check["Number Consistency"] = check_consistency(tex_path)
        except Exception as e:
            findings_by_check["Number Consistency"] = []

        try:
            findings_by_check["Statistical Auditing"] = check_statistics(tex_path)
        except Exception as e:
            findings_by_check["Statistical Auditing"] = []

        if args.get("bib_path"):
            try:
                from .core.citations import verify_bib_file
                findings_by_check["Citation Verification"] = verify_bib_file(args["bib_path"])
            except Exception:
                pass

        md = generate_markdown_report(findings_by_check)
        return [TextContent(type="text", text=md)]

    async def _handle_audit_time_units(args: dict) -> list[TextContent]:
        from .core.time_units import audit_time_units

        findings = audit_time_units(
            args["code_directory"],
            solver_directories=args.get("solver_directories"),
        )
        result = [
            {
                "file": f.file,
                "line": f.line,
                "severity": f.severity,
                "issue": f.issue,
                "details": f.details,
            }
            for f in findings
        ]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _handle_verify_numbers(args: dict) -> list[TextContent]:
        from .core.verify_numbers import verify_numbers

        findings = verify_numbers(
            tex_path=args["tex_path"],
            script_path=args["script_path"],
            timeout=args.get("timeout", 120),
            warning_threshold=args.get("warning_threshold", 0.05),
            critical_threshold=args.get("critical_threshold", 0.20),
        )
        result = [
            {
                "file": f.file,
                "line": f.line,
                "severity": f.severity,
                "issue": f.issue,
                "details": f.details,
                "script": f.script,
                "expected": f.expected,
                "actual": f.actual,
            }
            for f in findings
        ]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    return server


async def main():
    """Run the MCP server."""
    try:
        from mcp.server.stdio import stdio_server
    except ImportError:
        print("Error: MCP package not installed. Install with: pip install 'rigorously[mcp]'")
        return

    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        from mcp.server import InitializationOptions
        from mcp.types import ServerCapabilities, ToolsCapability
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="rigorously",
                server_version="0.1.0",
                capabilities=ServerCapabilities(
                    tools=ToolsCapability(),
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
