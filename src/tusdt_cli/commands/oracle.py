"""Oracle CLI commands."""

import click

from tusdt_cli.context import CLIContext
from tusdt_cli.globals import network_option, wallet_option
from tusdt_cli.utils import (
    HelpfulCommand,
    ModeAwareGroup,
    format_balance,
    parse_balance,
)
from tusdt_cli.wallet import get_reader_keypair, load_hotkey, resolve_ss58

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
@network_option
@click.pass_context
def price(ctx: click.Context, network: str | None) -> None:
    """Show the latest committed oracle price.

    \b
    Examples:
      tusdt oracle price --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network

    kp = get_reader_keypair(state.make_config())
    data = state.run_read(lambda c: c.get_latest_price(kp))

    if data is None:
        state.output.info("No price data available yet.")
        return

    raw_price = data.get("price", 0)
    raw_median = data.get("median_price", 0)
    price_val = int(raw_price) / 10**18 if raw_price else 0
    median_val = int(raw_median) / 10**18 if raw_median else 0

    state.output.detail(
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
@network_option
@click.pass_context
def round_info(ctx: click.Context, network: str | None) -> None:
    """Show the current oracle round ID.

    \b
    Examples:
      tusdt oracle round --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network

    kp = get_reader_keypair(state.make_config())
    round_id = state.run_read(lambda c: c.get_current_round(kp))

    state.output.detail("Oracle Round", {"Current round ID": round_id})


# ------------------------------------------------------------------
# submit-price
# ------------------------------------------------------------------


@oracle_group.command("submit-price")
@click.argument("price_value", type=str, metavar="<price>")
@click.option("--wallet-hotkey", required=True, help="Hotkey name to resolve its SS58 address (required)")
@click.option("--provider", default=None, help="Data provider name (e.g. coinmarketcap, coingecko)")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()

    # Convert human-readable price to Ratio (10^18 scale)
    try:
        price_float = float(price_value)
        raw_price = int(price_float * 10**18)
    except ValueError:
        state.output.error(f"Invalid price value: {price_value}")
        return

    # Resolve hotkey SS58 address for metadata (required)
    wname = state.wallet_name or cfg.get("wallet_name")
    if not wname:
        state.output.error("--wallet-name (or wallet_name in config) is required")
        return
    try:
        hk_keypair = load_hotkey(wname, wallet_hotkey, cfg.get("wallet_path"))
        hot_key_address = hk_keypair.ss58_address
        state.output.info(f"Hotkey: {hot_key_address}")
    except Exception as exc:
        state.output.error(f"Failed to load hotkey '{wallet_hotkey}': {exc}")
        return

    if provider:
        state.output.info(f"Provider: {provider}")

    state.output.info(f"Submitting price {price_value} (raw: {raw_price})...")
    state.submit(lambda c, kp: c.submit_price(kp, raw_price, hot_key_address, provider))
    state.output.success("Price submitted!")


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
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    raw_override: int | None = None
    if override_price is not None:
        try:
            price_float = float(override_price)
            raw_override = int(price_float * 10**18)
        except ValueError:
            state.output.error(f"Invalid override price: {override_price}")
            return

    if raw_override is not None:
        state.output.info(f"Committing round with override price {override_price} (raw: {raw_override})...")
    else:
        state.output.info("Committing round (using median price)...")

    state.submit(lambda c, kp: c.commit_round(kp, raw_override))
    state.output.success("Round committed!")


# ------------------------------------------------------------------
# round-price
# ------------------------------------------------------------------


@oracle_group.command("round-price")
@click.argument("round_id", type=int, metavar="<round-id>")
@network_option
@click.pass_context
def round_price(ctx: click.Context, round_id: int, network: str | None) -> None:
    """Show the price data for a specific round.

    \b
    ROUND_ID is the numeric round identifier.
    Examples:
      tusdt oracle round-price 42 --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network

    kp = get_reader_keypair(state.make_config())
    data = state.run_read(lambda c: c.get_round_price(kp, round_id))

    if data is None:
        state.output.info(f"No price data for round {round_id}")
        return

    raw_price = data.get("price", 0)
    raw_median = data.get("median_price", 0)
    price_val = int(raw_price) / 10**18 if raw_price else 0
    median_val = int(raw_median) / 10**18 if raw_median else 0

    state.output.detail(
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
@network_option
@click.pass_context
def history(ctx: click.Context, page: int, network: str | None) -> None:
    """Show oracle price history (paginated).

    \b
    Examples:
      tusdt oracle history --network testnet
      tusdt oracle history --page 2 --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network

    kp = get_reader_keypair(state.make_config())
    total = state.run_read(lambda c: c.get_price_history_count(kp))
    entries = state.run_read(lambda c: c.get_price_history(kp, page))

    if not entries:
        state.output.info(f"No price history (page {page})")
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

    state.output.info(f"Total entries: {total}  |  Page: {page}")
    state.output.table(
        "Price History",
        ["Round", "Price", "Reporters", "Overridden", "Committed At"],
        rows,
    )


# ------------------------------------------------------------------
# history-count
# ------------------------------------------------------------------


@oracle_group.command("history-count")
@network_option
@click.pass_context
def history_count(ctx: click.Context, network: str | None) -> None:
    """Show total number of price history entries.

    \b
    Examples:
      tusdt oracle history-count --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network

    kp = get_reader_keypair(state.make_config())
    count = state.run_read(lambda c: c.get_price_history_count(kp))

    state.output.detail("Price History", {"Total entries": count})


# ------------------------------------------------------------------
# submissions
# ------------------------------------------------------------------


@oracle_group.command("submissions")
@click.argument("round_id", type=int, metavar="<round-id>")
@network_option
@click.pass_context
def submissions(ctx: click.Context, round_id: int, network: str | None) -> None:
    """Show all submissions for a specific oracle round.

    \b
    ROUND_ID is the numeric round identifier.
    Examples:
      tusdt oracle submissions 42 --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network

    kp = get_reader_keypair(state.make_config())
    subs = state.run_read(lambda c: c.get_round_submissions(kp, round_id))

    if not subs:
        state.output.info(f"No submissions for round {round_id}")
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

    state.output.info(f"Submissions for round {round_id}: {len(subs)}")
    state.output.table(
        f"Round #{round_id} Submissions",
        ["Reporter", "Price", "Hotkey"],
        rows,
    )


# ------------------------------------------------------------------
# summary
# ------------------------------------------------------------------


@oracle_group.command("summary")
@network_option
@click.pass_context
def summary(ctx: click.Context, network: str | None) -> None:
    """Show a summary of the current oracle round.

    \b
    Examples:
      tusdt oracle summary --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network

    kp = get_reader_keypair(state.make_config())
    data = state.run_read(lambda c: c.get_current_round_summary(kp))

    if not isinstance(data, dict):
        state.output.info("No round summary available.")
        return

    raw_median = data.get("median_price")
    median_val = "N/A"
    if raw_median is not None:
        median_val = f"{int(raw_median) / 10**18:.6f}"

    state.output.detail(
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
@network_option
@click.pass_context
def get_netuid(ctx: click.Context, network: str | None) -> None:
    """Return the oracle's governing subnet netuid."""
    state: CLIContext = ctx.obj
    state.network = network or state.network

    kp = get_reader_keypair(state.make_config())
    result = state.run_read(lambda c: c.oracle_get_netuid(kp))

    state.output.detail("Oracle Netuid", {"Netuid": result})


@oracle_group.command("get-min-submitter-stake")
@network_option
@click.pass_context
def get_min_submitter_stake(ctx: click.Context, network: str | None) -> None:
    """Return the oracle's minimum required submitter stake."""
    state: CLIContext = ctx.obj
    state.network = network or state.network

    kp = get_reader_keypair(state.make_config())
    result = state.run_read(lambda c: c.oracle_get_min_submitter_stake(kp))

    state.output.detail("Min Submitter Stake", {"Raw": result, "Human": format_balance(result, 9)})


# ------------------------------------------------------------------
# controller
# ------------------------------------------------------------------


@oracle_group.command("controller")
@network_option
@click.pass_context
def controller(ctx: click.Context, network: str | None) -> None:
    """Show the oracle controller address.

    \b
    Examples:
      tusdt oracle controller --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network

    kp = get_reader_keypair(state.make_config())
    addr = state.run_read(lambda c: c.get_oracle_controller(kp))

    state.output.detail("Oracle Controller", {"Address": addr})


# ------------------------------------------------------------------
# governance
# ------------------------------------------------------------------


@oracle_group.command("governance", cls=HelpfulCommand)
@network_option
@click.pass_context
def oracle_governance(ctx: click.Context, network: str | None) -> None:
    """View the oracle contract's governance address.

    \b
    Examples:
      tusdt oracle governance --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network

    kp = get_reader_keypair(state.make_config())
    governance_addr = state.run_read(lambda c: c.get_oracle_governance(kp))

    state.output.detail("Oracle Governance", {"governance": governance_addr})


# ------------------------------------------------------------------
# validator
# ------------------------------------------------------------------


@oracle_group.command("validator")
@network_option
@click.pass_context
def validator(ctx: click.Context, network: str | None) -> None:
    """Show the oracle validator address.

    \b
    Examples:
      tusdt oracle validator --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network

    kp = get_reader_keypair(state.make_config())
    addr = state.run_read(lambda c: c.get_oracle_validator(kp))

    state.output.detail("Oracle Validator", {"Address": addr if addr is not None else "Not set"})


# ------------------------------------------------------------------
# max-deviation
# ------------------------------------------------------------------


@oracle_group.command("max-deviation")
@network_option
@click.pass_context
def max_deviation(ctx: click.Context, network: str | None) -> None:
    """Show the maximum allowed price deviation between rounds.

    \b
    Examples:
      tusdt oracle max-deviation --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network

    kp = get_reader_keypair(state.make_config())
    raw = state.run_read(lambda c: c.get_max_price_deviation(kp))

    val = int(raw) / 10**18 if raw else 0
    state.output.detail(
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
@network_option
@click.pass_context
def max_submissions(ctx: click.Context, network: str | None) -> None:
    """Show the maximum number of price submissions allowed per round.

    \b
    Examples:
      tusdt oracle max-submissions --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network

    kp = get_reader_keypair(state.make_config())
    count = state.run_read(lambda c: c.get_max_round_submissions(kp))

    state.output.detail("Max Round Submissions", {"Max submissions": count})


# ------------------------------------------------------------------
# commit-round-gov
# ------------------------------------------------------------------


@oracle_group.command("commit-round-gov")
@click.argument("price_value", type=str, metavar="<price>")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    try:
        price_float = float(price_value)
        raw_price = int(price_float * 10**18)
    except ValueError:
        state.output.error(f"Invalid price value: {price_value}")
        return

    state.output.info(f"Committing round with governance price {price_value} (raw: {raw_price})...")

    state.submit(lambda c, kp: c.commit_round_governance(kp, raw_price))
    state.output.success("Round committed (governance)!")


# ------------------------------------------------------------------
# set-netuid
# ------------------------------------------------------------------


@oracle_group.command("set-netuid")
@click.argument("netuid", type=click.IntRange(min=0, max=65535), metavar="<netuid>")
@wallet_option
@network_option
@click.pass_context
def set_netuid(ctx: click.Context, netuid: int, wallet_name: str | None, network: str | None) -> None:
    """Set the oracle's governing subnet netuid (governance only)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    state.output.info(f"Setting netuid to {netuid}...")
    state.submit(lambda c, kp: c.oracle_set_netuid(kp, netuid))
    state.output.success("Netuid updated!")


@oracle_group.command("set-min-submitter-stake")
@click.argument("amount", type=str, metavar="<amount>")
@wallet_option
@network_option
@click.pass_context
def set_min_submitter_stake(
    ctx: click.Context, amount: str, wallet_name: str | None, network: str | None
) -> None:
    """Set the oracle's minimum required submitter stake (governance only)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()

    try:
        raw_amount = parse_balance(amount, cfg.get("decimals", 9))
    except ValueError:
        state.output.error(f"Invalid amount: {amount}")
        return

    state.output.info(f"Setting min submitter stake to {amount} (raw: {raw_amount})...")
    state.submit(lambda c, kp: c.oracle_set_min_submitter_stake(kp, raw_amount))
    state.output.success("Min submitter stake updated!")


# ------------------------------------------------------------------
# set-validator
# ------------------------------------------------------------------


@oracle_group.command("set-validator")
@click.argument("account", type=str, metavar="<account>", required=False, default=None)
@click.option("--clear", is_flag=True, default=False, help="Clear the validator (set to None)")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    if not clear and account is None:
        state.output.error("Provide <account> or --clear")
        return
    if clear and account is not None:
        state.output.error("--clear and <account> are mutually exclusive")
        return

    cfg = state.make_config()

    resolved: str | None = None
    if not clear:
        assert account is not None
        try:
            resolved = resolve_ss58(account, cfg.get("wallet_path"))
        except Exception as exc:
            state.output.error(str(exc))
            return

    state.output.info(f"Setting validator to {'None' if clear else resolved}...")

    state.submit(lambda c, kp: c.set_validator(kp, resolved))
    state.output.success("Validator updated!")


# ------------------------------------------------------------------
# set-max-deviation
# ------------------------------------------------------------------


@oracle_group.command("set-max-deviation")
@click.argument("deviation", type=str, metavar="<deviation>")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    try:
        deviation_float = float(deviation)
        raw_deviation = int(deviation_float * 10**18)
    except ValueError:
        state.output.error(f"Invalid deviation value: {deviation}")
        return

    state.output.info(f"Setting max price deviation to {deviation}% (raw: {raw_deviation})...")

    state.submit(lambda c, kp: c.set_max_price_deviation(kp, raw_deviation))
    state.output.success("Max price deviation updated!")


# ------------------------------------------------------------------
# update-governance
# ------------------------------------------------------------------


@oracle_group.command("update-governance")
@click.argument("address", type=str, metavar="<new-governance-address>")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    state.output.info(f"Updating oracle governance to {address}...")
    state.submit(lambda c, kp: c.oracle_update_governance(kp, address))
    state.output.success("Oracle governance updated!")
