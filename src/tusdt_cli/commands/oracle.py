"""Oracle CLI commands."""

import click

from tusdt_cli.client import TUSDTClient
from tusdt_cli.config import load_config, NETWORKS
from tusdt_cli.utils import (
    ContractError,
    print_dict,
    print_error,
    print_info,
)
from tusdt_cli.wallet import get_reader_keypair

_network_option = click.option(
    "--network",
    type=click.Choice(list(NETWORKS.keys()), case_sensitive=False),
    default=None,
    help="Network preset (overrides rpc & contract addresses)",
)


@click.group("oracle")
def oracle_group() -> None:
    """Oracle price-feed operations (read-only)."""


@oracle_group.command("price")
@_network_option
@click.pass_context
def price(ctx: click.Context, network: str | None) -> None:
    """Show the latest committed oracle price."""
    config = load_config(network=network or ctx.obj.get("network_override"))

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        data = client.get_latest_price(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    if data is None:
        print_info("No price data available yet.")
        return

    print_dict("Oracle Price", {
        "Round ID": data.get("round_id", "?"),
        "Price": data.get("price", "?"),
        "Median price": data.get("median_price", "?"),
        "Reporter count": data.get("reporter_count", "?"),
        "Committed at": data.get("committed_at", "?"),
        "Was overridden": data.get("was_overridden", "?"),
    })


@oracle_group.command("round")
@_network_option
@click.pass_context
def round_info(ctx: click.Context, network: str | None) -> None:
    """Show the current oracle round ID."""
    config = load_config(network=network or ctx.obj.get("network_override"))

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        round_id = client.get_current_round(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Oracle Round", {"Current round ID": round_id})
