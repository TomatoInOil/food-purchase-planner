"""Management command to run the MCP server."""

from django.core.management.base import BaseCommand

from planner.mcp_server import run_server


class Command(BaseCommand):
    help = "Run MCP server with Streamable HTTP transport"

    def add_arguments(self, parser):
        parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
        parser.add_argument("--port", type=int, default=8001, help="Port to listen on")

    def handle(self, *args, **options):
        run_server(host=options["host"], port=options["port"])
