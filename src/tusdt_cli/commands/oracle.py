"""Oracle CLI commands."""

import click

from tusdt_cli.client import TUSDTClient
from tusdt_cli.config import load_config, NETWORKS
from tusdt_cli.utils import (
    HelpfulGroup,
    ModeAwareGroup,
    format_balance,
    print_dict,
    print_error,
    print_info,
    print_success,
    print_table,
    print_tx_result,
)
from tusdt_cli.wallet import get_reader_keypair, get_signer_keypair, load_hotkey, resolve_ss58

_network_option = click.option(
    "--network",
    type=click.Choice(list(NETWORKS.keys()), case_sensitive=False),
    default=None,
    help="Network preset (overrides rpc & contract addresses)",
)

_wallet_option = click.option(
    "--wallet-name", default=None,
    help="Bittensor wallet name for signing (prompts for coldkey password)",
)


_ORACLE_ADVANCED = {
    "submit-price", "commit-round", "round-price", "history",
    "history-count", "submissions", "summary", "is-reporter",
}


@click.group("oracle", cls=ModeAwareGroup, advanced_commands=_ORACLE_ADVANCED)
def oracle_group() -> None:
    """Oracle price-feed operations."""


@oracle_group.command("price")
@_network_option
@click.pass_context
def price(ctx: click.Context, network: str | None) -> None:
    """Show the latest committed oracle price.

    \b
    Examples:
      tusdt oracle price --network testnet
    """
    config = load_config(network=network)

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

    raw_price = data.get("price", 0)
    raw_median = data.get("median_price", 0)
    price_val = int(raw_price) / 10**18 if raw_price else 0
    median_val = int(raw_median) / 10**18 if raw_median else 0

    print_dict("Oracle Price", {
        "Round ID": data.get("round_id", "?"),
        "Price": price_val,
        "Median price": median_val,
        "Reporter count": data.get("reporter_count", "?"),
        "Committed at": data.get("committed_at", "?"),
        "Was overridden": data.get("was_overridden", "?"),
    })


@oracle_group.command("round")
@_network_option
@click.pass_context
def round_info(ctx: click.Context, network: str | None) -> None:
    """Show the current oracle round ID.

    \b
    Examples:
      tusdt oracle round --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        round_id = client.get_current_round(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Oracle Round", {"Current round ID": round_id})


# ------------------------------------------------------------------
# submit-price
# ------------------------------------------------------------------

@oracle_group.command("submit-price")
@click.argument("price_value", type=str, metavar="<price>")
@click.option("--wallet-hotkey", default=None,
              help="Hotkey name to resolve its SS58 address for submission metadata")
@_wallet_option
@_network_option
@click.pass_context
def submit_price(
    ctx: click.Context,
    price_value: str,
    wallet_hotkey: str | None,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Submit a price to the oracle as a reporter.

    \b
    PRICE is a decimal value (e.g. 245.50) which will be scaled by 10^18.
    Examples:
      tusdt oracle submit-price 245.50 --wallet-name MyWallet --network testnet
      tusdt oracle submit-price 245.50 --wallet-name MyWallet --wallet-hotkey myhotkey
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    # Convert human-readable price to Ratio (10^18 scale)
    try:
        price_float = float(price_value)
        raw_price = int(price_float * 10**18)
    except ValueError:
        print_error(f"Invalid price value: {price_value}")
        return

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))

    # Resolve hotkey SS58 address for metadata
    hot_key_address: str | None = None
    if wallet_hotkey:
        wname = wallet_name or config.get("wallet_name")
        if not wname:
            print_error("--wallet-hotkey requires --wallet-name (or wallet_name in config)")
            return
        try:
            hk_keypair = load_hotkey(wname, wallet_hotkey, config.get("wallet_path"))
            hot_key_address = hk_keypair.ss58_address
            print_info(f"Hotkey: {hot_key_address}")
        except Exception as exc:
            print_error(f"Failed to load hotkey '{wallet_hotkey}': {exc}")
            return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Submitting price {price_value} (raw: {raw_price})...")

    try:
        client = TUSDTClient(config)
        result = client.submit_price(keypair, raw_price, hot_key_address)
        print_success("Price submitted!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# commit-round
# ------------------------------------------------------------------

@oracle_group.command("commit-round")
@click.option("--override-price", default=None, type=str,
              help="Override price (decimal, e.g. 245.50). If omitted, uses median.")
@_wallet_option
@_network_option
@click.pass_context
def commit_round(ctx: click.Context, override_price: str | None, wallet_name: str | None, network: str | None) -> None:
    """Commit the current oracle round (validator only).

    \b
    If --override-price is provided, the median price is overridden.
    Examples:
      tusdt oracle commit-round --wallet-name MyWallet --network testnet
      tusdt oracle commit-round --override-price 245.50 --wallet-name MyWallet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    raw_override: int | None = None
    if override_price is not None:
        try:
            price_float = float(override_price)
            raw_override = int(price_float * 10**18)
        except ValueError:
            print_error(f"Invalid override price: {override_price}")
            return

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))

    print_info(f"Signer: {keypair.ss58_address}")
    if raw_override is not None:
        print_info(f"Committing round with override price {override_price} (raw: {raw_override})...")
    else:
        print_info("Committing round (using median price)...")

    try:
        client = TUSDTClient(config)
        result = client.commit_round(keypair, raw_override)
        print_success("Round committed!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# round-price
# ------------------------------------------------------------------

@oracle_group.command("round-price")
@click.argument("round_id", type=int, metavar="<round-id>")
@_network_option
@click.pass_context
def round_price(ctx: click.Context, round_id: int, network: str | None) -> None:
    """Show the price data for a specific round.

    \b
    ROUND_ID is the numeric round identifier.
    Examples:
      tusdt oracle round-price 42 --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        data = client.get_round_price(keypair, round_id)
    except Exception as exc:
        print_error(str(exc))
        return

    if data is None:
        print_info(f"No price data for round {round_id}")
        return

    raw_price = data.get("price", 0)
    raw_median = data.get("median_price", 0)
    price_val = int(raw_price) / 10**18 if raw_price else 0
    median_val = int(raw_median) / 10**18 if raw_median else 0

    print_dict(f"Round #{round_id} Price", {
        "Round ID": data.get("round_id", round_id),
        "Price": price_val,
        "Median price": median_val,
        "Reporter count": data.get("reporter_count", "?"),
        "Committed at": data.get("committed_at", "?"),
        "Was overridden": data.get("was_overridden", "?"),
    })


# ------------------------------------------------------------------
# history
# ------------------------------------------------------------------

@oracle_group.command("history")
@click.option("--page", default=0, show_default=True, help="Page number (10 per page)")
@_network_option
@click.pass_context
def history(ctx: click.Context, page: int, network: str | None) -> None:
    """Show oracle price history (paginated).

    \b
    Examples:
      tusdt oracle history --network testnet
      tusdt oracle history --page 2 --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        total = client.get_price_history_count(keypair)
        entries = client.get_price_history(keypair, page)
    except Exception as exc:
        print_error(str(exc))
        return

    if not entries:
        print_info(f"No price history (page {page})")
        return

    rows = []
    for e in entries:
        raw_price = e.get("price", 0)
        price_val = int(raw_price) / 10**18 if raw_price else 0
        rows.append([
            str(e.get("round_id", "?")),
            f"{price_val:.6f}",
            str(e.get("reporter_count", "?")),
            str(e.get("was_overridden", "?")),
            str(e.get("committed_at", "?")),
        ])

    print_info(f"Total entries: {total}  |  Page: {page}")
    print_table(
        "Price History",
        ["Round", "Price", "Reporters", "Overridden", "Committed At"],
        rows,
    )


# ------------------------------------------------------------------
# history-count
# ------------------------------------------------------------------

@oracle_group.command("history-count")
@_network_option
@click.pass_context
def history_count(ctx: click.Context, network: str | None) -> None:
    """Show total number of price history entries.

    \b
    Examples:
      tusdt oracle history-count --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        count = client.get_price_history_count(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Price History", {"Total entries": count})


# ------------------------------------------------------------------
# submissions
# ------------------------------------------------------------------

@oracle_group.command("submissions")
@click.argument("round_id", type=int, metavar="<round-id>")
@_network_option
@click.pass_context
def submissions(ctx: click.Context, round_id: int, network: str | None) -> None:
    """Show all submissions for a specific oracle round.

    \b
    ROUND_ID is the numeric round identifier.
    Examples:
      tusdt oracle submissions 42 --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        subs = client.get_round_submissions(keypair, round_id)
    except Exception as exc:
        print_error(str(exc))
        return

    if not subs:
        print_info(f"No submissions for round {round_id}")
        return

    rows = []
    for s in subs:
        raw_price = s.get("price", 0)
        price_val = int(raw_price) / 10**18 if raw_price else 0
        metadata = s.get("metadata")
        hot_key = metadata.get("hot_key", "N/A") if isinstance(metadata, dict) else "N/A"
        rows.append([
            str(s.get("reporter", "?")),
            f"{price_val:.6f}",
            hot_key,
        ])

    print_info(f"Submissions for round {round_id}: {len(subs)}")
    print_table(
        f"Round #{round_id} Submissions",
        ["Reporter", "Price", "Hotkey"],
        rows,
    )


# ------------------------------------------------------------------
# summary
# ------------------------------------------------------------------

@oracle_group.command("summary")
@_network_option
@click.pass_context
def summary(ctx: click.Context, network: str | None) -> None:
    """Show a summary of the current oracle round.

    \b
    Examples:
      tusdt oracle summary --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        data = client.get_current_round_summary(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    if not isinstance(data, dict):
        print_info("No round summary available.")
        return

    raw_median = data.get("median_price")
    median_val = "N/A"
    if raw_median is not None:
        median_val = f"{int(raw_median) / 10**18:.6f}"

    print_dict("Current Round Summary", {
        "Round ID": data.get("round_id", "?"),
        "Reporter count": data.get("reporter_count", "?"),
        "Median price": median_val,
    })


# ------------------------------------------------------------------
# is-reporter
# ------------------------------------------------------------------

@oracle_group.command("is-reporter")
@click.argument("account", type=str, metavar="<account>")
@_network_option
@click.pass_context
def is_reporter(ctx: click.Context, account: str, network: str | None) -> None:
    """Check if an account is a registered oracle reporter.

    \b
    ACCOUNT is an SS58 address or wallet name.
    Examples:
      tusdt oracle is-reporter 5GrwvaEF... --network testnet
    """
    config = load_config(network=network)

    try:
        account = resolve_ss58(account, config.get("wallet_path"))
    except Exception as exc:
        print_error(str(exc))
        return

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        result = client.is_reporter(keypair, account)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Reporter Status", {
        "Account": account,
        "Is reporter": result,
    })
