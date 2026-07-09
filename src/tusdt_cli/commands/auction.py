"""Auction CLI commands."""

import click

from tusdt_cli.client import TUSDTClient
from tusdt_cli.config import NETWORKS, load_config
from tusdt_cli.utils import (
    ModeAwareGroup,
    format_balance,
    parse_balance,
    print_dict,
    print_error,
    print_info,
    print_success,
    print_table,
    print_tx_result,
    print_warning,
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


_AUCTION_ADVANCED = {
    "list-all",
    "total-count",
    "vault-auction",
    "bids",
    "bid-info",
    "create",
    "set-admin",
    "update-governance",
    "transfer-winning-bid",
}
_AUCTION_BASIC_READS = {"controller", "governance", "admin-address"}


@click.group("auction", cls=ModeAwareGroup, advanced_commands=_AUCTION_ADVANCED)
def auction_group() -> None:
    """Liquidation auction operations."""


# ------------------------------------------------------------------
# list-active  (read-only – no --wallet-name needed)
# ------------------------------------------------------------------


@auction_group.command("list-active")
@click.option("--page", default=0, show_default=True, help="Page number (10 per page)")
@_network_option
@click.pass_context
def list_active(ctx: click.Context, page: int, network: str | None) -> None:
    """List active liquidation auctions.

    \b
    Examples:
      tusdt auction list-active --network testnet
      tusdt auction list-active --page 2 --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        total = client.get_active_auctions_count(keypair)
        auctions = client.list_active_auctions(keypair, page)
    except Exception as exc:
        print_error(str(exc))
        return

    if not auctions:
        print_info(f"No active auctions (page {page})")
        return

    rows = []
    for a in auctions:
        rows.append(
            [
                str(a.get("id", "?")),
                str(a.get("vault_id", "?")),
                format_balance(a.get("collateral_balance", 0), decimals),
                format_balance(a.get("debt_balance", 0), decimals),
                format_balance(a.get("highest_bid", 0), decimals),
                str(a.get("bid_count", 0)),
                str(a.get("ends_at", "?")),
            ]
        )

    print_info(f"Active auctions: {total}  |  Page: {page}")
    print_table(
        "Active Auctions",
        ["ID", "Vault", "Collateral", "Debt", "Highest Bid", "Bids", "Ends At"],
        rows,
    )


# ------------------------------------------------------------------
# info  (read-only – no --wallet-name needed)
# ------------------------------------------------------------------


@auction_group.command("info")
@click.argument("auction_id", type=int, metavar="<auction-id>")
@_network_option
@click.pass_context
def auction_info(ctx: click.Context, auction_id: int, network: str | None) -> None:
    """Show details for a specific auction.

    \b
    AUCTION_ID is the numeric ID of the auction to query.
    Examples:
      tusdt auction info 5 --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        data = client.get_auction(keypair, auction_id)
    except Exception as exc:
        print_error(str(exc))
        return

    if data is None:
        print_error(f"Auction {auction_id} not found")
        return

    print_dict(
        f"Auction #{auction_id}",
        {
            "ID": data.get("id", auction_id),
            "Vault Owner": data.get("vault_owner", "?"),
            "Vault ID": data.get("vault_id", "?"),
            "Collateral": format_balance(data.get("collateral_balance", 0), decimals),
            "Debt": format_balance(data.get("debt_balance", 0), decimals),
            "Starts at": data.get("starts_at", "?"),
            "Ends at": data.get("ends_at", "?"),
            "Highest bidder": data.get("highest_bidder") or "None",
            "Highest bid": format_balance(data.get("highest_bid", 0), decimals),
            "Bid count": data.get("bid_count", 0),
            "Finalized": data.get("is_finalized", False),
        },
    )


# ------------------------------------------------------------------
# bid  (has --wallet-hotkey for hotkey SS58 metadata)
# ------------------------------------------------------------------


@auction_group.command("bid")
@click.argument("auction_id", type=int, metavar="<auction-id>")
@click.argument("amount", type=str, metavar="<amount>")
@click.option(
    "--wallet-hotkey", default=None, help="Hotkey name to resolve its SS58 address for bid metadata"
)
@_wallet_option
@_network_option
@click.pass_context
def bid(
    ctx: click.Context,
    auction_id: int,
    amount: str,
    wallet_hotkey: str | None,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Place a bid on a liquidation auction.

    \b
    AUCTION_ID is the numeric ID of the auction.
    AMOUNT     is the human-readable token amount to bid (e.g. 500).
    Automatically checks token allowance and prompts for approval if
    the auction contract does not have sufficient spending permission.
    Examples:
      tusdt auction bid 5 500 --wallet-name MyWallet --network testnet
      tusdt auction bid 5 500 --wallet-name MyWallet --wallet-hotkey myhotkey
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))

    # Resolve hotkey SS58 address for bid metadata
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

    try:
        client = TUSDTClient(config)

        # Check and handle allowance
        auction_address = config.get("auction_address", "")
        if auction_address:
            current_allowance = client.allowance(keypair, keypair.ss58_address, auction_address)
            if current_allowance < raw_amount:
                print_warning(
                    f"Current allowance ({format_balance(current_allowance, decimals)}) "
                    f"is less than bid amount ({amount})."
                )
                if click.confirm("Approve the auction contract to spend your tokens?"):
                    max_approval = 2**64 - 1
                    approve_result = client.approve(keypair, auction_address, max_approval)
                    print_success(f"Approved! tx: {approve_result['extrinsic_hash']}")
                else:
                    print_info("Bid cancelled.")
                    return

        print_info(f"Placing bid of {amount} on auction {auction_id}...")
        result = client.place_bid(keypair, auction_id, raw_amount, hot_key_address)
        print_success("Bid placed!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# finalize
# ------------------------------------------------------------------


@auction_group.command("finalize")
@click.argument("auction_id", type=int, metavar="<auction-id>")
@_wallet_option
@_network_option
@click.pass_context
def finalize(ctx: click.Context, auction_id: int, wallet_name: str | None, network: str | None) -> None:
    """Finalize a completed auction.

    \b
    AUCTION_ID is the numeric ID of the auction to finalize.
    Examples:
      tusdt auction finalize 5 --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Finalizing auction {auction_id}...")

    try:
        client = TUSDTClient(config)
        result = client.finalize_auction(keypair, auction_id)
        print_success("Auction finalized!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# withdraw-refund
# ------------------------------------------------------------------


@auction_group.command("withdraw-refund")
@click.argument("auction_id", type=int, metavar="<auction-id>")
@click.argument("bid_id", type=int, metavar="<bid-id>")
@_wallet_option
@_network_option
@click.pass_context
def withdraw_refund(
    ctx: click.Context, auction_id: int, bid_id: int, wallet_name: str | None, network: str | None
) -> None:
    """Withdraw a refund for a non-winning bid after auction finalization.

    \b
    AUCTION_ID is the numeric ID of the auction.
    BID_ID     is the numeric ID of your bid to withdraw.
    Examples:
      tusdt auction withdraw-refund 5 1 --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Withdrawing refund for bid {bid_id} on auction {auction_id}...")

    try:
        client = TUSDTClient(config)
        result = client.withdraw_refund(keypair, auction_id, bid_id)
        print_success("Refund withdrawn!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# my-bid  (uses --wallet-name to determine bidder address)
# ------------------------------------------------------------------


@auction_group.command("my-bid")
@click.argument("auction_id", type=int, metavar="<auction-id>")
@_wallet_option
@_network_option
@click.pass_context
def my_bid(ctx: click.Context, auction_id: int, wallet_name: str | None, network: str | None) -> None:
    """Show your current bid in an auction.

    \b
    AUCTION_ID is the numeric ID of the auction.
    Examples:
      tusdt auction my-bid 5 --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 9)

    # Determine bidder address from wallet name (no password needed – reads coldkeypub.txt)
    wname = wallet_name or config.get("wallet_name")
    if not wname:
        print_error("Provide --wallet-name or configure wallet_name to identify your address.")
        return

    try:
        bidder = resolve_ss58(wname, config.get("wallet_path"))
    except Exception as exc:
        print_error(str(exc))
        return

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        data = client.get_my_bid(keypair, auction_id, bidder)
    except Exception as exc:
        print_error(str(exc))
        return

    if data is None:
        print_info(f"No bid found for {bidder} in auction {auction_id}")
        return

    print_dict(
        f"Your Bid – Auction #{auction_id}",
        {
            "Bid ID": data.get("id", "?"),
            "Auction ID": data.get("auction_id", auction_id),
            "Bidder": data.get("bidder", bidder),
            "Amount": format_balance(data.get("amount", 0), decimals),
            "Withdrawn": data.get("is_withdrawn", False),
        },
    )


# ------------------------------------------------------------------
# list-all  (read-only – all auctions including finalized)
# ------------------------------------------------------------------


@auction_group.command("list-all")
@click.option("--page", default=0, show_default=True, help="Page number (10 per page)")
@_network_option
@click.pass_context
def list_all(ctx: click.Context, page: int, network: str | None) -> None:
    """List all auctions (active + finalized, paginated).

    \b
    Examples:
      tusdt auction list-all --network testnet
      tusdt auction list-all --page 2 --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        total = client.get_total_auctions_count(keypair)
        auctions = client.list_all_auctions(keypair, page)
    except Exception as exc:
        print_error(str(exc))
        return

    if not auctions:
        print_info(f"No auctions found (page {page})")
        return

    rows = []
    for a in auctions:
        rows.append(
            [
                str(a.get("id", "?")),
                str(a.get("vault_id", "?")),
                format_balance(a.get("collateral_balance", 0), decimals),
                format_balance(a.get("debt_balance", 0), decimals),
                format_balance(a.get("highest_bid", 0), decimals),
                str(a.get("bid_count", 0)),
                str(a.get("is_finalized", "?")),
            ]
        )

    print_info(f"Total auctions: {total}  |  Page: {page}")
    print_table(
        "All Auctions",
        ["ID", "Vault", "Collateral", "Debt", "Highest Bid", "Bids", "Finalized"],
        rows,
    )


# ------------------------------------------------------------------
# total-count
# ------------------------------------------------------------------


@auction_group.command("total-count")
@_network_option
@click.pass_context
def total_count(ctx: click.Context, network: str | None) -> None:
    """Show total auction count.

    \b
    Examples:
      tusdt auction total-count --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        count = client.get_total_auctions_count(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Total Auctions", {"Count": count})


# ------------------------------------------------------------------
# vault-auction
# ------------------------------------------------------------------


@auction_group.command("vault-auction")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--owner", required=True, help="Vault owner SS58 address or wallet name")
@_network_option
@click.pass_context
def vault_auction(ctx: click.Context, vault_id: int, owner: str, network: str | None) -> None:
    """Show the active auction for a specific vault.

    \b
    VAULT_ID is the numeric ID of the vault.
    Examples:
      tusdt auction vault-auction 0 --owner 5GrwvaEF... --network testnet
    """
    config = load_config(network=network)

    try:
        owner = resolve_ss58(owner, config.get("wallet_path"))
    except Exception as exc:
        print_error(str(exc))
        return

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        auction_id = client.get_active_vault_auction(keypair, owner, vault_id)
    except Exception as exc:
        print_error(str(exc))
        return

    if auction_id is None:
        print_info(f"No active auction for vault {vault_id} (owner: {owner})")
    else:
        print_dict(
            f"Active Auction – Vault #{vault_id}",
            {
                "Owner": owner,
                "Auction ID": auction_id,
            },
        )


# ------------------------------------------------------------------
# bids  (list bids for an auction)
# ------------------------------------------------------------------


@auction_group.command("bids")
@click.argument("auction_id", type=int, metavar="<auction-id>")
@click.option("--page", default=0, show_default=True, help="Page number (10 per page)")
@_network_option
@click.pass_context
def list_bids(ctx: click.Context, auction_id: int, page: int, network: str | None) -> None:
    """List bids for an auction (paginated).

    \b
    AUCTION_ID is the numeric ID of the auction.
    Examples:
      tusdt auction bids 5 --network testnet
      tusdt auction bids 5 --page 1 --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        bids = client.list_bids(keypair, auction_id, page)
    except Exception as exc:
        print_error(str(exc))
        return

    if not bids:
        print_info(f"No bids for auction {auction_id} (page {page})")
        return

    rows = []
    for b in bids:
        rows.append(
            [
                str(b.get("id", "?")),
                str(b.get("bidder", "?")),
                format_balance(b.get("amount", 0), decimals),
                str(b.get("is_withdrawn", False)),
            ]
        )

    print_info(f"Bids for auction {auction_id}  |  Page: {page}")
    print_table(
        f"Bids – Auction #{auction_id}",
        ["Bid ID", "Bidder", "Amount", "Withdrawn"],
        rows,
    )


# ------------------------------------------------------------------
# bid-info  (single bid details)
# ------------------------------------------------------------------


@auction_group.command("bid-info")
@click.argument("auction_id", type=int, metavar="<auction-id>")
@click.argument("bid_id", type=int, metavar="<bid-id>")
@_network_option
@click.pass_context
def bid_info(ctx: click.Context, auction_id: int, bid_id: int, network: str | None) -> None:
    """Show details for a specific bid.

    \b
    AUCTION_ID is the numeric ID of the auction.
    BID_ID     is the numeric ID of the bid.
    Examples:
      tusdt auction bid-info 5 1 --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        data = client.get_bid(keypair, auction_id, bid_id)
    except Exception as exc:
        print_error(str(exc))
        return

    if data is None:
        print_error(f"Bid {bid_id} not found in auction {auction_id}")
        return

    metadata = data.get("metadata")
    hot_key = metadata.get("hot_key", "N/A") if isinstance(metadata, dict) else "N/A"

    print_dict(
        f"Bid #{bid_id} – Auction #{auction_id}",
        {
            "Bid ID": data.get("id", bid_id),
            "Auction ID": data.get("auction_id", auction_id),
            "Bidder": data.get("bidder", "?"),
            "Amount": format_balance(data.get("amount", 0), decimals),
            "Hotkey": hot_key,
            "Withdrawn": data.get("is_withdrawn", False),
        },
    )


# ------------------------------------------------------------------
# controller
# ------------------------------------------------------------------


@auction_group.command("controller")
@_network_option
@click.pass_context
def auction_controller_cmd(ctx: click.Context, network: str | None) -> None:
    """Show the controller address of the auction contract.

    \b
    Examples:
      tusdt auction controller
      tusdt auction controller --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.get_auction_controller(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Auction Controller", {"Address": addr})


# ------------------------------------------------------------------
# governance
# ------------------------------------------------------------------


@auction_group.command("governance")
@_network_option
@click.pass_context
def auction_governance_cmd(ctx: click.Context, network: str | None) -> None:
    """Show the governance address of the auction contract.

    \b
    Examples:
      tusdt auction governance
      tusdt auction governance --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.get_auction_governance(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Auction Governance", {"Address": addr})


# ------------------------------------------------------------------
# admin-address
# ------------------------------------------------------------------


@auction_group.command("admin-address")
@_network_option
@click.pass_context
def auction_admin_cmd(ctx: click.Context, network: str | None) -> None:
    """Show the admin address of the auction contract, if set.

    \b
    Examples:
      tusdt auction admin-address
      tusdt auction admin-address --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        admin = client.get_auction_admin(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    if admin is None:
        print_info("No admin set")
    else:
        print_dict("Auction Admin", {"Address": admin})


# ------------------------------------------------------------------
# create
# ------------------------------------------------------------------


@auction_group.command("create")
@click.argument("vault_owner", type=str, metavar="<ss58-address>")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option(
    "--collateral-balance",
    type=str,
    required=True,
    help="Collateral balance in human-readable units (e.g. 10.0)",
)
@click.option(
    "--debt-balance", type=str, required=True, help="Debt balance in human-readable units (e.g. 100.0)"
)
@click.option("--min-bid", type=str, required=True, help="Minimum bid in human-readable units (e.g. 10.0)")
@click.option(
    "--liquidation-price", type=int, required=True, help="Liquidation price as raw integer (10^18 scale)"
)
@click.option(
    "--duration-ms",
    type=int,
    default=None,
    help="Auction duration in milliseconds (uses contract default if omitted)",
)
@_wallet_option
@_network_option
@click.pass_context
def create_auction_cmd(
    ctx: click.Context,
    vault_owner: str,
    vault_id: int,
    collateral_balance: str,
    debt_balance: str,
    min_bid: str,
    liquidation_price: int,
    duration_ms: int | None,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Create a new liquidation auction (controller only).

    \b
    VAULT_OWNER is the SS58 address of the vault owner.
    VAULT_ID    is the numeric vault ID (integer).
    Examples:
      tusdt auction create 5GrwvaEF... 0 --collateral-balance 10 --debt-balance 100 --min-bid 10 --liquidation-price 1500000000000000000 --duration-ms 86400000 --wallet-name MyWallet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 9)

    raw_collateral = parse_balance(collateral_balance, decimals)
    raw_debt = parse_balance(debt_balance, decimals)
    raw_min_bid = parse_balance(min_bid, decimals)

    try:
        vault_owner = resolve_ss58(vault_owner, config.get("wallet_path"))
    except Exception as exc:
        print_error(str(exc))
        return

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Creating auction for vault {vault_id} (owner: {vault_owner})...")

    try:
        client = TUSDTClient(config)
        result = client.create_auction(
            keypair,
            vault_owner,
            vault_id,
            raw_collateral,
            raw_debt,
            raw_min_bid,
            liquidation_price,
            duration_ms,
        )
        print_success("Auction created!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# set-admin
# ------------------------------------------------------------------


@auction_group.command("set-admin")
@click.argument("address", type=str, metavar="<ss58-address>", required=False)
@click.option("--clear", is_flag=True, default=False, help="Clear the admin (set to None)")
@_wallet_option
@_network_option
@click.pass_context
def auction_set_admin_cmd(
    ctx: click.Context,
    address: str | None,
    clear: bool,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Set or clear the auction admin (governance only).

    \b
    ADDRESS is the SS58 address of the admin, or omit and use --clear to remove.
    Examples:
      tusdt auction set-admin 5GrwvaEF... --wallet-name MyWallet
      tusdt auction set-admin --clear --wallet-name MyWallet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    admin = None if clear else address
    if not clear and not address:
        print_error("Provide an SS58 address or use --clear to remove the admin")
        return

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    action = "Clearing" if clear else f"Setting to {address}"
    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"{action} auction admin...")

    try:
        client = TUSDTClient(config)
        result = client.auction_set_admin(keypair, admin)
        print_success("Auction admin updated!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# update-governance
# ------------------------------------------------------------------


@auction_group.command("update-governance")
@click.argument("address", type=str, metavar="<ss58-address>")
@_wallet_option
@_network_option
@click.pass_context
def auction_update_governance_cmd(
    ctx: click.Context,
    address: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Transfer auction governance to a new account (controller only).

    \b
    ADDRESS is the SS58 address of the new governance account.
    Examples:
      tusdt auction update-governance 5GrwvaEF... --wallet-name MyWallet
      tusdt auction update-governance 5GrwvaEF... --wallet-name MyWallet --network testnet
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
    print_info(f"Updating auction governance to {address}...")

    try:
        client = TUSDTClient(config)
        result = client.auction_update_governance(keypair, address)
        print_success("Auction governance updated!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# transfer-winning-bid
# ------------------------------------------------------------------


@auction_group.command("transfer-winning-bid")
@click.argument("auction_id", type=int, metavar="<auction-id>")
@click.argument("recipient", type=str, metavar="<ss58-address>")
@_wallet_option
@_network_option
@click.pass_context
def transfer_winning_bid_cmd(
    ctx: click.Context,
    auction_id: int,
    recipient: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Transfer the winning bid amount to a recipient (controller only).

    \b
    AUCTION_ID is the numeric auction ID (integer).
    RECIPIENT  is the SS58 address to receive the winning bid tokens.
    Examples:
      tusdt auction transfer-winning-bid 0 5GrwvaEF... --wallet-name MyWallet
      tusdt auction transfer-winning-bid 5 5GrwvaEF... --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        recipient = resolve_ss58(recipient, config.get("wallet_path"))
    except Exception as exc:
        print_error(str(exc))

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Transferring winning bid for auction {auction_id} to {recipient}...")

    try:
        client = TUSDTClient(config)
        result = client.auction_transfer_winning_bid(keypair, auction_id, recipient)
        print_success("Winning bid transferred!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))
