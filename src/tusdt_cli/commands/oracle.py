"""Oracle CLI commands."""

import click

from tusdt_cli.client import TUSDTClient
from tusdt_cli.config import NETWORKS, load_config
from tusdt_cli.utils import (
    HelpfulCommand,
    ModeAwareGroup,
    format_balance,
    parse_balance,
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
    "--wallet-name",
    default=None,
    help="Bittensor wallet name for signing (prompts for coldkey password)",
)


_ORACLE_ADVANCED = {
    "submit-price",
    "commit-round",
    "commit-round-gov",
    "round-price",
    "history",
    "history-count",
    "submissions",
    "summary",
    "get-netuid",
    "get-min-submitter-stake",
    "controller",
    "governance",
    "validator",
    "max-deviation",
    "max-submissions",
    "set-netuid",
    "set-min-submitter-stake",
    "set-validator",
    "set-max-deviation",
    "update-governance",
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

    print_dict(
        "Oracle Price",
        {
            "Round ID": data.get("round_id", "?"),
            "Price": price_val,
            "Median price": median_val,
            "Reporter count": data.get("reporter_count", "?"),
            "Committed at": data.get("committed_at", "?"),
            "Was overridden": data.get("was_overridden", "?"),
        },
    )


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
@click.option("--wallet-hotkey", required=True, help="Hotkey name to resolve its SS58 address (required)")
@click.option("--provider", default=None, help="Data provider name (e.g. coinmarketcap, coingecko)")
@_wallet_option
@_network_option
@click.pass_context
def submit_price(
    ctx: click.Context,
    price_value: str,
    wallet_hotkey: str,
    wallet_name: str | None,
    provider: str | None,
    network: str | None,
) -> None:
    """Submit a price to the oracle. Caller must be a registered subnet neuron.

    \b
    PRICE is a decimal value (e.g. 245.50) which will be scaled by 10^18.
    Examples:
      tusdt oracle submit-price 245.50 --wallet-name MyWallet --wallet-hotkey myhotkey
      tusdt oracle submit-price 245.50 --wallet-name MyWallet --wallet-hotkey myhotkey --provider coingecko
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
        return

    # Resolve hotkey SS58 address for metadata (required)
    wname = wallet_name or config.get("wallet_name")
    if not wname:
        print_error("--wallet-name (or wallet_name in config) is required")
        return
    try:
        hk_keypair = load_hotkey(wname, wallet_hotkey, config.get("wallet_path"))
        hot_key_address = hk_keypair.ss58_address
        print_info(f"Hotkey: {hot_key_address}")
    except Exception as exc:
        print_error(f"Failed to load hotkey '{wallet_hotkey}': {exc}")
        return

    if provider:
        print_info(f"Provider: {provider}")

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Submitting price {price_value} (raw: {raw_price})...")

    try:
        client = TUSDTClient(config)
        result = client.submit_price(keypair, raw_price, hot_key_address, provider)
        print_success("Price submitted!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# commit-round
# ------------------------------------------------------------------


@oracle_group.command("commit-round")
@click.option(
    "--override-price",
    default=None,
    type=str,
    help="Override price (decimal, e.g. 245.50). If omitted, uses median.",
)
@_wallet_option
@_network_option
@click.pass_context
def commit_round(
    ctx: click.Context, override_price: str | None, wallet_name: str | None, network: str | None
) -> None:
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
        return

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

    print_dict(
        f"Round #{round_id} Price",
        {
            "Round ID": data.get("round_id", round_id),
            "Price": price_val,
            "Median price": median_val,
            "Reporter count": data.get("reporter_count", "?"),
            "Committed at": data.get("committed_at", "?"),
            "Was overridden": data.get("was_overridden", "?"),
        },
    )


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
        rows.append(
            [
                str(e.get("round_id", "?")),
                f"{price_val:.6f}",
                str(e.get("reporter_count", "?")),
                str(e.get("was_overridden", "?")),
                str(e.get("committed_at", "?")),
            ]
        )

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
        rows.append(
            [
                str(s.get("reporter", "?")),
                f"{price_val:.6f}",
                hot_key,
            ]
        )

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

    print_dict(
        "Current Round Summary",
        {
            "Round ID": data.get("round_id", "?"),
            "Reporter count": data.get("reporter_count", "?"),
            "Median price": median_val,
        },
    )


# ------------------------------------------------------------------
# get-netuid
# ------------------------------------------------------------------


@oracle_group.command("get-netuid")
@_network_option
@click.pass_context
def get_netuid(ctx: click.Context, network: str | None) -> None:
    """Return the oracle's governing subnet netuid."""
    config = load_config(network=network)
    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        result = client.oracle_get_netuid(keypair)
    except Exception as exc:
        print_error(str(exc))
        return
    print_dict("Oracle Netuid", {"Netuid": result})


@oracle_group.command("get-min-submitter-stake")
@_network_option
@click.pass_context
def get_min_submitter_stake(ctx: click.Context, network: str | None) -> None:
    """Return the oracle's minimum required submitter stake."""
    config = load_config(network=network)
    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        result = client.oracle_get_min_submitter_stake(keypair)
    except Exception as exc:
        print_error(str(exc))
        return
    print_dict("Min Submitter Stake", {"Raw": result, "Human": format_balance(result, 9)})


# ------------------------------------------------------------------
# controller
# ------------------------------------------------------------------


@oracle_group.command("controller")
@_network_option
@click.pass_context
def controller(ctx: click.Context, network: str | None) -> None:
    """Show the oracle controller address.

    \b
    Examples:
      tusdt oracle controller --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.get_oracle_controller(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Oracle Controller", {"Address": addr})


# ------------------------------------------------------------------
# governance
# ------------------------------------------------------------------


@oracle_group.command("governance", cls=HelpfulCommand)
@_network_option
@click.pass_context
def oracle_governance(ctx: click.Context, network: str | None) -> None:
    """View the oracle contract's governance address.

    \b
    Examples:
      tusdt oracle governance --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        governance_addr = client.get_oracle_governance(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Oracle Governance", {"governance": governance_addr})


# ------------------------------------------------------------------
# validator
# ------------------------------------------------------------------


@oracle_group.command("validator")
@_network_option
@click.pass_context
def validator(ctx: click.Context, network: str | None) -> None:
    """Show the oracle validator address.

    \b
    Examples:
      tusdt oracle validator --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.get_oracle_validator(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Oracle Validator", {"Address": addr if addr is not None else "Not set"})


# ------------------------------------------------------------------
# max-deviation
# ------------------------------------------------------------------


@oracle_group.command("max-deviation")
@_network_option
@click.pass_context
def max_deviation(ctx: click.Context, network: str | None) -> None:
    """Show the maximum allowed price deviation between rounds.

    \b
    Examples:
      tusdt oracle max-deviation --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        raw = client.get_max_price_deviation(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    val = int(raw) / 10**18 if raw else 0
    print_dict(
        "Max Price Deviation",
        {
            "Deviation": f"{val:.6f}",
            "Raw": raw,
        },
    )


# ------------------------------------------------------------------
# max-submissions
# ------------------------------------------------------------------


@oracle_group.command("max-submissions")
@_network_option
@click.pass_context
def max_submissions(ctx: click.Context, network: str | None) -> None:
    """Show the maximum number of price submissions allowed per round.

    \b
    Examples:
      tusdt oracle max-submissions --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        count = client.get_max_round_submissions(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Max Round Submissions", {"Max submissions": count})


# ------------------------------------------------------------------
# commit-round-gov
# ------------------------------------------------------------------


@oracle_group.command("commit-round-gov")
@click.argument("price_value", type=str, metavar="<price>")
@_wallet_option
@_network_option
@click.pass_context
def commit_round_gov(
    ctx: click.Context,
    price_value: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Commit the current oracle round with an explicit price (governance only).

    \b
    Bypasses the minimum-reporter requirement; use only as a governance override.
    PRICE is a decimal value (e.g. 245.50) scaled by 10^18.
    Examples:
      tusdt oracle commit-round-gov 245.50 --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

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
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Committing round with governance price {price_value} (raw: {raw_price})...")

    try:
        client = TUSDTClient(config)
        result = client.commit_round_governance(keypair, raw_price)
        print_success("Round committed (governance)!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# set-reporter
# ------------------------------------------------------------------


@oracle_group.command("set-netuid")
@click.argument("netuid", type=click.IntRange(min=0, max=65535), metavar="<netuid>")
@_wallet_option
@_network_option
@click.pass_context
def set_netuid(ctx: click.Context, netuid: int, wallet_name: str | None, network: str | None) -> None:
    """Set the oracle's governing subnet netuid (governance only)."""
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return
    print_info(f"Setting netuid to {netuid}...")
    try:
        client = TUSDTClient(config)
        result = client.oracle_set_netuid(keypair, netuid)
        print_success("Netuid updated!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


@oracle_group.command("set-min-submitter-stake")
@click.argument("amount", type=str, metavar="<amount>")
@_wallet_option
@_network_option
@click.pass_context
def set_min_submitter_stake(
    ctx: click.Context, amount: str, wallet_name: str | None, network: str | None
) -> None:
    """Set the oracle's minimum required submitter stake (governance only)."""
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    try:
        raw_amount = parse_balance(amount, config.get("decimals", 9))
    except ValueError:
        print_error(f"Invalid amount: {amount}")
        return
    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return
    print_info(f"Setting min submitter stake to {amount} (raw: {raw_amount})...")
    try:
        client = TUSDTClient(config)
        result = client.oracle_set_min_submitter_stake(keypair, raw_amount)
        print_success("Min submitter stake updated!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# set-validator
# ------------------------------------------------------------------


@oracle_group.command("set-validator")
@click.argument("account", type=str, metavar="<account>", required=False, default=None)
@click.option("--clear", is_flag=True, default=False, help="Clear the validator (set to None)")
@_wallet_option
@_network_option
@click.pass_context
def set_validator_cmd(
    ctx: click.Context,
    account: str | None,
    clear: bool,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Set the oracle validator account (governance only).

    \b
    ACCOUNT is an SS58 address or wallet name.  Use --clear to unset.
    Examples:
      tusdt oracle set-validator 5GrwvaEF... --wallet-name MyWallet
      tusdt oracle set-validator --clear --wallet-name MyWallet
    """
    if not clear and account is None:
        print_error("Provide <account> or --clear")
        return
    if clear and account is not None:
        print_error("--clear and <account> are mutually exclusive")
        return

    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    resolved: str | None = None
    if not clear:
        try:
            resolved = resolve_ss58(account, config.get("wallet_path"))
        except Exception as exc:
            print_error(str(exc))
            return

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Setting validator to {'None' if clear else resolved}...")

    try:
        client = TUSDTClient(config)
        result = client.set_validator(keypair, resolved)
        print_success("Validator updated!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# set-max-deviation
# ------------------------------------------------------------------


@oracle_group.command("set-max-deviation")
@click.argument("deviation", type=str, metavar="<deviation>")
@_wallet_option
@_network_option
@click.pass_context
def set_max_deviation(
    ctx: click.Context,
    deviation: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Set the maximum allowed price deviation between rounds (governance only).

    \b
    DEVIATION is a decimal value (e.g. 20.0 for 20%) scaled by 10^18.
    Examples:
      tusdt oracle set-max-deviation 20.0 --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        deviation_float = float(deviation)
        raw_deviation = int(deviation_float * 10**18)
    except ValueError:
        print_error(f"Invalid deviation value: {deviation}")
        return

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Setting max price deviation to {deviation}% (raw: {raw_deviation})...")

    try:
        client = TUSDTClient(config)
        result = client.set_max_price_deviation(keypair, raw_deviation)
        print_success("Max price deviation updated!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# update-governance
# ------------------------------------------------------------------


@oracle_group.command("update-governance")
@click.argument("address", type=str, metavar="<new-governance-address>")
@_wallet_option
@_network_option
@click.pass_context
def update_governance(
    ctx: click.Context,
    address: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Transfer oracle governance to a new address (controller only).

    \b
    Examples:
      tusdt oracle update-governance 5GrwvaEF... --wallet-name MyWallet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Updating oracle governance to {address}...")

    try:
        client = TUSDTClient(config)
        result = client.oracle_update_governance(keypair, address)
        print_success("Oracle governance updated!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))
