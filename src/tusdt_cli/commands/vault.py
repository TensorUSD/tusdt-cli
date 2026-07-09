"""Vault CLI commands."""

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
from tusdt_cli.wallet import get_reader_keypair, get_signer_keypair, resolve_ss58

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


_VAULT_ADVANCED = {
    "total-debt",
    "liquidation-auction",
    "list-all",
    "params",
    "total-collateral",
    "total-count",
    "accrue-interest",
    "trigger-liquidation",
    "settle-liquidation",
    "governance",
    "platform",
    "paused",
    "pending-update",
    "update-governance",
    "update-platform",
    "pause",
    "unpause",
    "set-params",
    "execute-update",
    "cancel-update",
    "claim-surplus",
    "token-address",
    "auction-address",
    "oracle-address",
    "collateral-balance",
    "treasury-address",
    "update-treasury",
    "emergency-drain",
}


@click.group("vault", cls=ModeAwareGroup, advanced_commands=_VAULT_ADVANCED)
def vault_group() -> None:
    """Manage collateral vaults."""


# ------------------------------------------------------------------
# create
# ------------------------------------------------------------------


@vault_group.command("create")
@click.option("--amount", required=True, help="Collateral amount in human-readable units (e.g. 1.5)")
@_wallet_option
@_network_option
@click.pass_context
def create_vault(ctx: click.Context, amount: str, wallet_name: str | None, network: str | None) -> None:
    """Create a new vault with native-token collateral.

    \b
    Examples:
      tusdt vault create --amount 1.5 --wallet-name MyWallet
      tusdt vault create --amount 10 --wallet-name MyWallet --network testnet
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

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Depositing {amount} (raw {raw_amount}) as collateral...")

    try:
        client = TUSDTClient(config)
        result = client.create_vault(keypair, raw_amount)
        print_success("Vault created successfully!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# add-collateral
# ------------------------------------------------------------------


@vault_group.command("add-collateral")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--amount", required=True, help="Collateral amount to add (e.g. 2.5)")
@_wallet_option
@_network_option
@click.pass_context
def add_collateral(
    ctx: click.Context, vault_id: int, amount: str, wallet_name: str | None, network: str | None
) -> None:
    """Add collateral to an existing vault.

    \b
    VAULT_ID is the numeric ID of your vault.
    Examples:
      tusdt vault add-collateral 0 --amount 2.5 --wallet-name MyWallet
      tusdt vault add-collateral 3 --amount 1.0 --wallet-name MyWallet --network testnet
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

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Adding {amount} collateral to vault {vault_id}...")

    try:
        client = TUSDTClient(config)
        result = client.add_collateral(keypair, vault_id, raw_amount)
        print_success("Collateral added!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# borrow
# ------------------------------------------------------------------


@vault_group.command("borrow")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.argument("amount", type=str, metavar="<amount>")
@_wallet_option
@_network_option
@click.pass_context
def borrow(
    ctx: click.Context, vault_id: int, amount: str, wallet_name: str | None, network: str | None
) -> None:
    """Borrow TUSDT tokens against a vault's collateral.

    \b
    VAULT_ID is the numeric ID of your vault.
    AMOUNT  is the human-readable token amount to borrow (e.g. 100.5).
    Examples:
      tusdt vault borrow 0 100 --wallet-name MyWallet
      tusdt vault borrow 2 50.5 --wallet-name MyWallet --network testnet
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

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Borrowing {amount} from vault {vault_id}...")

    try:
        client = TUSDTClient(config)
        result = client.borrow(keypair, vault_id, raw_amount)
        print_success("Tokens borrowed!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# repay
# ------------------------------------------------------------------


@vault_group.command("repay")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.argument("amount", type=str, metavar="<amount>")
@_wallet_option
@_network_option
@click.pass_context
def repay(
    ctx: click.Context, vault_id: int, amount: str, wallet_name: str | None, network: str | None
) -> None:
    """Repay borrowed TUSDT tokens to a vault.

    \b
    VAULT_ID is the numeric ID of your vault.
    AMOUNT  is the human-readable token amount to repay (e.g. 50).
    Examples:
      tusdt vault repay 0 50 --wallet-name MyWallet
      tusdt vault repay 2 25.5 --wallet-name MyWallet --network testnet
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

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Repaying {amount} to vault {vault_id}...")

    try:
        client = TUSDTClient(config)
        result = client.repay(keypair, vault_id, raw_amount)
        print_success("Tokens repaid!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# release-collateral
# ------------------------------------------------------------------


@vault_group.command("release-collateral")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.argument("amount", type=str, metavar="<amount>")
@_wallet_option
@_network_option
@click.pass_context
def release_collateral(
    ctx: click.Context, vault_id: int, amount: str, wallet_name: str | None, network: str | None
) -> None:
    """Release collateral from a vault.

    \b
    VAULT_ID is the numeric ID of your vault.
    AMOUNT  is the human-readable collateral amount to release (e.g. 1.0).
    Examples:
      tusdt vault release-collateral 0 1.0 --wallet-name MyWallet
      tusdt vault release-collateral 2 0.5 --wallet-name MyWallet --network testnet
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

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Releasing {amount} collateral from vault {vault_id}...")

    try:
        client = TUSDTClient(config)
        result = client.release_collateral(keypair, vault_id, raw_amount)
        print_success("Collateral released!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# info
# ------------------------------------------------------------------


@vault_group.command("info")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--owner", default=None, help="Owner SS58 address or wallet name (defaults to --wallet-name)")
@_wallet_option
@_network_option
@click.pass_context
def vault_info(
    ctx: click.Context, vault_id: int, owner: str | None, wallet_name: str | None, network: str | None
) -> None:
    """Display detailed information for a single vault.

    \b
    VAULT_ID is the numeric ID of the vault to query.
    Owner is resolved from --wallet-name, or pass --owner explicitly.
    Examples:
      tusdt vault info 0 --wallet-name MyWallet
      tusdt vault info 3 --owner 5GrwvaEF... --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        if owner:
            owner = resolve_ss58(owner, config.get("wallet_path"))
        elif wallet_name:
            owner = resolve_ss58(wallet_name, config.get("wallet_path"))
        else:
            print_error("Provide --owner (address or wallet name) or --wallet-name")
            return
    except Exception as exc:
        print_error(str(exc))
        return

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        vault_data = client.get_vault(keypair, owner, vault_id)
    except Exception as exc:
        print_error(str(exc))
        return

    if vault_data is None:
        print_error(f"Vault {vault_id} not found for owner {owner}")
        return

    print_dict(
        f"Vault #{vault_id}",
        {
            "ID": vault_data.get("id", vault_id),
            "Owner": vault_data.get("owner", owner),
            "Collateral": format_balance(vault_data.get("collateral_balance", 0), decimals),
            "Borrowed (principal)": format_balance(vault_data.get("borrowed_token_balance", 0), decimals),
            "Debt (principal + interest)": format_balance(vault_data.get("debt_balance", 0), decimals),
            "Interest accrued": format_balance(vault_data.get("total_interest_accrued", 0), decimals),
            "Created at": vault_data.get("created_at", "?"),
            "Interest accrued at": vault_data.get("last_interest_accrued_at", "?"),
        },
    )


# ------------------------------------------------------------------
# list
# ------------------------------------------------------------------


@vault_group.command("list")
@click.option("--owner", default=None, help="Owner SS58 address or wallet name (defaults to --wallet-name)")
@click.option("--page", default=0, show_default=True, help="Page number (10 per page)")
@_wallet_option
@_network_option
@click.pass_context
def list_vaults(
    ctx: click.Context, owner: str | None, page: int, wallet_name: str | None, network: str | None
) -> None:
    """List vaults for an owner (paginated).

    \b
    Owner is resolved from --wallet-name, or pass --owner explicitly.
    Examples:
      tusdt vault list --wallet-name MyWallet
      tusdt vault list --owner 5GrwvaEF... --page 2 --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        if owner:
            owner = resolve_ss58(owner, config.get("wallet_path"))
        elif wallet_name:
            owner = resolve_ss58(wallet_name, config.get("wallet_path"))
        else:
            print_error("Provide --owner (address or wallet name) or --wallet-name")
            return
    except Exception as exc:
        print_error(str(exc))
        return

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        total = client.get_vaults_count(keypair, owner)
        vaults = client.list_vaults(keypair, owner, page)
    except Exception as exc:
        print_error(str(exc))
        return

    if not vaults:
        print_info(f"No vaults found for {owner} (page {page})")
        return

    rows = []
    for v in vaults:
        rows.append(
            [
                str(v.get("id", "?")),
                format_balance(v.get("collateral_balance", 0), decimals),
                format_balance(v.get("borrowed_token_balance", 0), decimals),
                format_balance(v.get("debt_balance", 0), decimals),
                str(v.get("created_at", "?")),
            ]
        )

    print_info(f"Total vaults: {total}  |  Page: {page}")
    print_table(
        f"Vaults for {owner[:12]}...{owner[-6:]}",
        ["ID", "Collateral", "Borrowed", "Debt", "Created"],
        rows,
    )


# ------------------------------------------------------------------
# max-borrow
# ------------------------------------------------------------------


@vault_group.command("max-borrow")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--owner", default=None, help="Owner SS58 address or wallet name (defaults to --wallet-name)")
@_wallet_option
@_network_option
@click.pass_context
def max_borrow(
    ctx: click.Context, vault_id: int, owner: str | None, wallet_name: str | None, network: str | None
) -> None:
    """Show the maximum additional borrowing capacity for a vault.

    \b
    VAULT_ID is the numeric ID of the vault to query.
    Owner is resolved from --wallet-name, or pass --owner explicitly.
    Examples:
      tusdt vault max-borrow 0 --wallet-name MyWallet
      tusdt vault max-borrow 3 --owner 5GrwvaEF... --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        if owner:
            owner = resolve_ss58(owner, config.get("wallet_path"))
        elif wallet_name:
            owner = resolve_ss58(wallet_name, config.get("wallet_path"))
        else:
            print_error("Provide --owner (address or wallet name) or --wallet-name")
            return
    except Exception as exc:
        print_error(str(exc))
        return

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        value = client.get_max_borrow(keypair, owner, vault_id)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict(
        f"Max Borrow – Vault #{vault_id}",
        {
            "Owner": owner,
            "Max additional borrow": format_balance(value, decimals),
        },
    )


# ------------------------------------------------------------------
# collateral-value
# ------------------------------------------------------------------


@vault_group.command("collateral-value")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--owner", default=None, help="Owner SS58 address or wallet name (defaults to --wallet-name)")
@_wallet_option
@_network_option
@click.pass_context
def collateral_value(
    ctx: click.Context, vault_id: int, owner: str | None, wallet_name: str | None, network: str | None
) -> None:
    """Show the collateral value (in borrowed-token terms) for a vault.

    \b
    VAULT_ID is the numeric ID of the vault to query.
    Owner is resolved from --wallet-name, or pass --owner explicitly.
    Examples:
      tusdt vault collateral-value 0 --wallet-name MyWallet
      tusdt vault collateral-value 3 --owner 5GrwvaEF... --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        if owner:
            owner = resolve_ss58(owner, config.get("wallet_path"))
        elif wallet_name:
            owner = resolve_ss58(wallet_name, config.get("wallet_path"))
        else:
            print_error("Provide --owner (address or wallet name) or --wallet-name")
            return
    except Exception as exc:
        print_error(str(exc))
        return

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        value = client.get_collateral_value(keypair, owner, vault_id)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict(
        f"Collateral Value – Vault #{vault_id}",
        {
            "Owner": owner,
            "Collateral value": format_balance(value, decimals),
        },
    )


# ------------------------------------------------------------------
# total-debt
# ------------------------------------------------------------------


@vault_group.command("total-debt")
@click.option("--owner", default=None, help="Owner SS58 address or wallet name (defaults to --wallet-name)")
@_wallet_option
@_network_option
@click.pass_context
def total_debt(ctx: click.Context, owner: str | None, wallet_name: str | None, network: str | None) -> None:
    """Show total debt for an owner across all vaults.

    \b
    Examples:
      tusdt vault total-debt --wallet-name MyWallet
      tusdt vault total-debt --owner 5GrwvaEF... --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        if owner:
            owner = resolve_ss58(owner, config.get("wallet_path"))
        elif wallet_name:
            owner = resolve_ss58(wallet_name, config.get("wallet_path"))
        else:
            print_error("Provide --owner (address or wallet name) or --wallet-name")
            return
    except Exception as exc:
        print_error(str(exc))
        return

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        value = client.get_total_debt(keypair, owner)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict(
        "Total Debt",
        {
            "Owner": owner,
            "Total debt": format_balance(value, decimals),
            "Raw": value,
        },
    )


# ------------------------------------------------------------------
# liquidation-auction
# ------------------------------------------------------------------


@vault_group.command("liquidation-auction")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--owner", default=None, help="Owner SS58 address or wallet name (defaults to --wallet-name)")
@_wallet_option
@_network_option
@click.pass_context
def liquidation_auction(
    ctx: click.Context, vault_id: int, owner: str | None, wallet_name: str | None, network: str | None
) -> None:
    """Show the active liquidation auction ID for a vault.

    \b
    VAULT_ID is the numeric ID of the vault to query.
    Examples:
      tusdt vault liquidation-auction 0 --wallet-name MyWallet
      tusdt vault liquidation-auction 3 --owner 5GrwvaEF... --network testnet
    """
    config = load_config(network=network)

    try:
        if owner:
            owner = resolve_ss58(owner, config.get("wallet_path"))
        elif wallet_name:
            owner = resolve_ss58(wallet_name, config.get("wallet_path"))
        else:
            print_error("Provide --owner (address or wallet name) or --wallet-name")
            return
    except Exception as exc:
        print_error(str(exc))
        return

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        auction_id = client.get_liquidation_auction_id(keypair, owner, vault_id)
    except Exception as exc:
        print_error(str(exc))
        return

    if auction_id is None:
        print_info(f"No active liquidation auction for vault {vault_id} (owner: {owner})")
    else:
        print_dict(
            f"Liquidation Auction – Vault #{vault_id}",
            {
                "Owner": owner,
                "Auction ID": auction_id,
            },
        )


# ------------------------------------------------------------------
# list-all
# ------------------------------------------------------------------


@vault_group.command("list-all")
@click.option("--page", default=0, show_default=True, help="Page number (10 per page)")
@_network_option
@click.pass_context
def list_all_vaults(ctx: click.Context, page: int, network: str | None) -> None:
    """List all vaults across all owners (paginated).

    \b
    Examples:
      tusdt vault list-all --network testnet
      tusdt vault list-all --page 2 --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        total = client.get_total_vaults_count(keypair)
        vaults = client.get_all_vaults(keypair, page)
    except Exception as exc:
        print_error(str(exc))
        return

    if not vaults:
        print_info(f"No vaults found (page {page})")
        return

    rows = []
    for v in vaults:
        rows.append(
            [
                str(v.get("id", "?")),
                str(v.get("owner", "?")),
                format_balance(v.get("collateral_balance", 0), decimals),
                format_balance(v.get("borrowed_token_balance", 0), decimals),
                format_balance(v.get("debt_balance", 0), decimals),
                str(v.get("created_at", "?")),
            ]
        )

    print_info(f"Total vaults: {total}  |  Page: {page}")
    print_table(
        "All Vaults",
        ["ID", "Owner", "Collateral", "Borrowed", "Debt", "Created"],
        rows,
    )


# ------------------------------------------------------------------
# params
# ------------------------------------------------------------------


@vault_group.command("params")
@_network_option
@click.pass_context
def vault_params(ctx: click.Context, network: str | None) -> None:
    """Show vault contract parameters.

    \b
    Examples:
      tusdt vault params --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        params = client.get_contract_params(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    if isinstance(params, dict):
        display = {}
        for key, value in params.items():
            display[key] = value
        print_dict("Vault Contract Parameters", display)
    else:
        print_dict("Vault Contract Parameters", {"Raw": params})


# ------------------------------------------------------------------
# total-collateral
# ------------------------------------------------------------------


@vault_group.command("total-collateral")
@_network_option
@click.pass_context
def total_collateral(ctx: click.Context, network: str | None) -> None:
    """Show total collateral balance across all vaults.

    \b
    Examples:
      tusdt vault total-collateral --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        value = client.get_total_collateral_balance(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict(
        "Total Collateral",
        {
            "Total collateral": format_balance(value, decimals),
            "Raw": value,
        },
    )


# ------------------------------------------------------------------
# total-count
# ------------------------------------------------------------------


@vault_group.command("total-count")
@_network_option
@click.pass_context
def total_count(ctx: click.Context, network: str | None) -> None:
    """Show total vault count across all owners.

    \b
    Examples:
      tusdt vault total-count --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        count = client.get_total_vaults_count(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Total Vaults", {"Count": count})


# ------------------------------------------------------------------
# accrue-interest
# ------------------------------------------------------------------


@vault_group.command("accrue-interest")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--owner", required=True, help="Vault owner SS58 address or wallet name")
@_wallet_option
@_network_option
@click.pass_context
def accrue_interest(
    ctx: click.Context, vault_id: int, owner: str, wallet_name: str | None, network: str | None
) -> None:
    """Accrue interest on a vault.

    \b
    VAULT_ID is the numeric ID of the vault.
    Examples:
      tusdt vault accrue-interest 0 --owner 5GrwvaEF... --wallet-name MyWallet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        owner = resolve_ss58(owner, config.get("wallet_path"))
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Accruing interest on vault {vault_id} (owner: {owner})...")

    try:
        client = TUSDTClient(config)
        result = client.accrue_interest(keypair, owner, vault_id)
        print_success("Interest accrued!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# trigger-liquidation
# ------------------------------------------------------------------


@vault_group.command("trigger-liquidation")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--owner", required=True, help="Vault owner SS58 address or wallet name")
@_wallet_option
@_network_option
@click.pass_context
def trigger_liquidation(
    ctx: click.Context, vault_id: int, owner: str, wallet_name: str | None, network: str | None
) -> None:
    """Trigger a liquidation auction for an undercollateralized vault.

    \b
    VAULT_ID is the numeric ID of the vault.
    Examples:
      tusdt vault trigger-liquidation 0 --owner 5GrwvaEF... --wallet-name MyWallet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        owner = resolve_ss58(owner, config.get("wallet_path"))
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Triggering liquidation for vault {vault_id} (owner: {owner})...")

    try:
        client = TUSDTClient(config)
        result = client.trigger_liquidation(keypair, owner, vault_id)
        print_success("Liquidation auction triggered!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# settle-liquidation
# ------------------------------------------------------------------


@vault_group.command("settle-liquidation")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--owner", required=True, help="Vault owner SS58 address or wallet name")
@_wallet_option
@_network_option
@click.pass_context
def settle_liquidation(
    ctx: click.Context, vault_id: int, owner: str, wallet_name: str | None, network: str | None
) -> None:
    """Settle a completed liquidation auction for a vault.

    \b
    VAULT_ID is the numeric ID of the vault.
    Examples:
      tusdt vault settle-liquidation 0 --owner 5GrwvaEF... --wallet-name MyWallet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        owner = resolve_ss58(owner, config.get("wallet_path"))
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Settling liquidation for vault {vault_id} (owner: {owner})...")

    try:
        client = TUSDTClient(config)
        result = client.settle_liquidation(keypair, owner, vault_id)
        print_success("Liquidation settled!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# governance
# ------------------------------------------------------------------


@vault_group.command("governance")
@_network_option
@click.pass_context
def governance(ctx: click.Context, network: str | None) -> None:
    """Show the current governance address."""
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.get_governance(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Governance", {"Address": addr})


# ------------------------------------------------------------------
# platform
# ------------------------------------------------------------------


@vault_group.command("platform")
@_network_option
@click.pass_context
def platform(ctx: click.Context, network: str | None) -> None:
    """Show the current platform address."""
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.get_platform(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Platform", {"Address": addr})


# ------------------------------------------------------------------
# paused
# ------------------------------------------------------------------


@vault_group.command("paused")
@_network_option
@click.pass_context
def paused(ctx: click.Context, network: str | None) -> None:
    """Show whether the vault contract is paused."""
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        is_paused = client.is_paused(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Contract Status", {"Paused": is_paused})


# ------------------------------------------------------------------
# pending-update
# ------------------------------------------------------------------


@vault_group.command("pending-update")
@_network_option
@click.pass_context
def pending_update(ctx: click.Context, network: str | None) -> None:
    """Show pending contract parameter update details."""
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        update = client.get_pending_params_update(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    if update is None:
        print_info("No pending parameter update")
    else:
        print_dict("Pending Parameter Update", update)


# ------------------------------------------------------------------
# update-governance
# ------------------------------------------------------------------


@vault_group.command("update-governance")
@click.argument("address", type=str, metavar="<new-governance-address>")
@_wallet_option
@_network_option
@click.pass_context
def update_governance(ctx: click.Context, address: str, wallet_name: str | None, network: str | None) -> None:
    """Transfer governance to a new address.

    \b
    Examples:
      tusdt vault update-governance 5GrwvaEF... --wallet-name MyWallet
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
    print_info(f"Updating governance to {address}...")

    try:
        client = TUSDTClient(config)
        result = client.update_governance(keypair, address)
        print_success("Governance updated!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# update-platform
# ------------------------------------------------------------------


@vault_group.command("update-platform")
@click.argument("address", type=str, metavar="<new-platform-address>")
@_wallet_option
@_network_option
@click.pass_context
def update_platform(ctx: click.Context, address: str, wallet_name: str | None, network: str | None) -> None:
    """Update the platform address.

    \b
    Examples:
      tusdt vault update-platform 5GrwvaEF... --wallet-name MyWallet
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
    print_info(f"Updating platform to {address}...")

    try:
        client = TUSDTClient(config)
        result = client.update_platform(keypair, address)
        print_success("Platform updated!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# pause
# ------------------------------------------------------------------


@vault_group.command("pause")
@_wallet_option
@_network_option
@click.pass_context
def pause_contract(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Pause the vault contract (governance only).

    \b
    Examples:
      tusdt vault pause --wallet-name MyWallet
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
    print_info("Pausing vault contract...")

    try:
        client = TUSDTClient(config)
        result = client.pause_contract(keypair)
        print_success("Contract paused!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# unpause
# ------------------------------------------------------------------


@vault_group.command("unpause")
@_wallet_option
@_network_option
@click.pass_context
def unpause_contract(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Unpause the vault contract (governance only).

    \b
    Examples:
      tusdt vault unpause --wallet-name MyWallet
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
    print_info("Unpausing vault contract...")

    try:
        client = TUSDTClient(config)
        result = client.unpause_contract(keypair)
        print_success("Contract unpaused!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# set-params
# ------------------------------------------------------------------


@vault_group.command("set-params")
@click.option("--collateral-ratio", type=int, default=None, help="Collateral ratio (e.g. 150 for 150%%)")
@click.option("--liquidation-ratio", type=int, default=None, help="Liquidation ratio (e.g. 120 for 120%%)")
@click.option("--interest-rate", type=int, default=None, help="Interest rate (e.g. 5 for 5%%)")
@click.option("--liquidation-fee", type=int, default=None, help="Liquidation fee (e.g. 10 for 10%%)")
@click.option("--borrow-cap", type=str, default=None, help="Borrow cap in human-readable units")
@click.option("--auction-duration-ms", type=int, default=None, help="Auction duration in milliseconds")
@click.option("--max-oracle-age-ms", type=int, default=None, help="Max oracle age in milliseconds")
@click.option(
    "--transaction-fee", type=int, default=None, help="Transaction fee in basis points (e.g. 3 for 0.03%%)"
)
@click.option(
    "--min-vault-collateral", type=str, default=None, help="Minimum vault collateral in human-readable units"
)
@click.option(
    "--max-vault-collateral",
    type=str,
    default=None,
    help="Maximum per-vault collateral in human-readable units",
)
@click.option(
    "--max-total-collateral",
    type=str,
    default=None,
    help="Maximum total collateral across all vaults in human-readable units",
)
@_wallet_option
@_network_option
@click.pass_context
def set_params(
    ctx: click.Context,
    collateral_ratio: int | None,
    liquidation_ratio: int | None,
    interest_rate: int | None,
    liquidation_fee: int | None,
    borrow_cap: str | None,
    auction_duration_ms: int | None,
    max_oracle_age_ms: int | None,
    transaction_fee: int | None,
    min_vault_collateral: str | None,
    max_vault_collateral: str | None,
    max_total_collateral: str | None,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Schedule a contract parameter update (24h timelock).

    \b
    All parameters are optional; only supplied values will be updated.
    Examples:
      tusdt vault set-params --collateral-ratio 150 --liquidation-ratio 120 --wallet-name MyWallet
      tusdt vault set-params --interest-rate 5 --borrow-cap 1000000 --wallet-name MyWallet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 9)

    params: dict = {}
    if collateral_ratio is not None:
        params["collateral_ratio"] = collateral_ratio
    if liquidation_ratio is not None:
        params["liquidation_ratio"] = liquidation_ratio
    if interest_rate is not None:
        params["interest_rate"] = interest_rate
    if liquidation_fee is not None:
        params["liquidation_fee"] = liquidation_fee
    if borrow_cap is not None:
        params["borrow_cap"] = parse_balance(borrow_cap, decimals)
    if auction_duration_ms is not None:
        params["auction_duration_ms"] = auction_duration_ms
    if max_oracle_age_ms is not None:
        params["max_oracle_age_ms"] = max_oracle_age_ms
    if transaction_fee is not None:
        params["transaction_fee"] = transaction_fee
    if min_vault_collateral is not None:
        params["min_vault_collateral"] = parse_balance(min_vault_collateral, decimals)
    if max_vault_collateral is not None:
        params["max_vault_collateral"] = parse_balance(max_vault_collateral, decimals)
    if max_total_collateral is not None:
        params["max_total_collateral"] = parse_balance(max_total_collateral, decimals)

    if not params:
        print_error("Provide at least one parameter to update")
        return

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Scheduling parameter update: {params}")

    try:
        client = TUSDTClient(config)
        result = client.set_contract_params(keypair, params)
        print_success("Parameter update scheduled (24h timelock)!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# execute-update
# ------------------------------------------------------------------


@vault_group.command("execute-update")
@_wallet_option
@_network_option
@click.pass_context
def execute_update(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Execute a pending contract parameter update (after timelock expires).

    \b
    Examples:
      tusdt vault execute-update --wallet-name MyWallet
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
    print_info("Executing pending parameter update...")

    try:
        client = TUSDTClient(config)
        result = client.execute_params_update(keypair)
        print_success("Parameter update executed!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# cancel-update
# ------------------------------------------------------------------


@vault_group.command("cancel-update")
@_wallet_option
@_network_option
@click.pass_context
def cancel_update(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Cancel a pending contract parameter update.

    \b
    Examples:
      tusdt vault cancel-update --wallet-name MyWallet
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
    print_info("Cancelling pending parameter update...")

    try:
        client = TUSDTClient(config)
        result = client.cancel_params_update(keypair)
        print_success("Parameter update cancelled!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# claim-surplus
# ------------------------------------------------------------------


@vault_group.command("claim-surplus")
@click.argument("amount", type=str, metavar="<amount>")
@_wallet_option
@_network_option
@click.pass_context
def claim_surplus(ctx: click.Context, amount: str, wallet_name: str | None, network: str | None) -> None:
    """Claim surplus TUSDT from the vault contract (permissionless — anyone may call).

    \b
    AMOUNT is the human-readable token amount to claim.
    Examples:
      tusdt vault claim-surplus 1000 --wallet-name MyWallet
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
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Claiming {amount} surplus TUSDT...")

    try:
        client = TUSDTClient(config)
        result = client.claim_surplus_tusdt(keypair, raw_amount)
        print_success("Surplus TUSDT claimed!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# token-address
# ------------------------------------------------------------------


@vault_group.command("token-address")
@_network_option
@click.pass_context
def token_address(ctx: click.Context, network: str | None) -> None:
    """Show the token contract address registered in the vault.

    \b
    Examples:
      tusdt vault token-address --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.get_token_address(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Token Contract", {"Address": addr})


# ------------------------------------------------------------------
# auction-address
# ------------------------------------------------------------------


@vault_group.command("auction-address")
@_network_option
@click.pass_context
def auction_address(ctx: click.Context, network: str | None) -> None:
    """Show the auction contract address registered in the vault.

    \b
    Examples:
      tusdt vault auction-address --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.get_auction_address(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Auction Contract", {"Address": addr})


# ------------------------------------------------------------------
# oracle-address
# ------------------------------------------------------------------


@vault_group.command("oracle-address")
@_network_option
@click.pass_context
def oracle_address(ctx: click.Context, network: str | None) -> None:
    """Show the oracle contract address registered in the vault.

    \b
    Examples:
      tusdt vault oracle-address --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.get_oracle_address(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Oracle Contract", {"Address": addr})


# ------------------------------------------------------------------
# collateral-balance
# ------------------------------------------------------------------


@vault_group.command("collateral-balance")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--owner", default=None, help="Owner SS58 address or wallet name (defaults to --wallet-name)")
@_wallet_option
@_network_option
@click.pass_context
def collateral_balance(
    ctx: click.Context,
    vault_id: int,
    owner: str | None,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Show the raw collateral balance for a specific vault.

    \b
    VAULT_ID is the numeric ID of the vault.
    Owner is resolved from --wallet-name, or pass --owner explicitly.
    Examples:
      tusdt vault collateral-balance 0 --wallet-name MyWallet
      tusdt vault collateral-balance 3 --owner 5GrwvaEF... --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        if owner:
            owner = resolve_ss58(owner, config.get("wallet_path"))
        elif wallet_name:
            owner = resolve_ss58(wallet_name, config.get("wallet_path"))
        else:
            print_error("Provide --owner (address or wallet name) or --wallet-name")
            return
    except Exception as exc:
        print_error(str(exc))
        return

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        value = client.get_vault_collateral_balance(keypair, owner, vault_id)
    except Exception as exc:
        print_error(str(exc))
        return

    if value is None:
        print_error(f"Vault {vault_id} not found for owner {owner}")
        return

    print_dict(
        f"Collateral Balance – Vault #{vault_id}",
        {
            "Owner": owner,
            "Collateral balance": format_balance(value, decimals),
            "Raw": value,
        },
    )


# ------------------------------------------------------------------
# treasury-address
# ------------------------------------------------------------------


@vault_group.command("treasury-address")
@_network_option
@click.pass_context
def vault_treasury_address(ctx: click.Context, network: str | None) -> None:
    """Show the treasury address registered in the vault contract.

    \b
    Examples:
      tusdt vault treasury-address
      tusdt vault treasury-address --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.vault_get_treasury(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Vault Treasury", {"Address": addr})


# ------------------------------------------------------------------
# update-treasury
# ------------------------------------------------------------------


@vault_group.command("update-treasury")
@click.argument("address", type=str, metavar="<ss58-address>")
@_wallet_option
@_network_option
@click.pass_context
def vault_update_treasury_cmd(
    ctx: click.Context,
    address: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Update the treasury address in the vault contract (governance only).

    \b
    ADDRESS is the SS58 address of the new treasury contract.
    Examples:
      tusdt vault update-treasury 5GrwvaEF... --wallet-name MyWallet
      tusdt vault update-treasury 5GrwvaEF... --wallet-name MyWallet --network testnet
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
    print_info(f"Updating vault treasury address to {address}...")

    try:
        client = TUSDTClient(config)
        result = client.vault_update_treasury(keypair, address)
        print_success("Treasury address updated!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# emergency-drain
# ------------------------------------------------------------------


@vault_group.command("emergency-drain")
@click.argument("recipient", type=str, metavar="<ss58-address>")
@_wallet_option
@_network_option
@click.pass_context
def vault_emergency_drain_cmd(
    ctx: click.Context,
    recipient: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Emergency drain the vault's native balance to a recipient (TESTNET ONLY, governance).

    \b
    RECIPIENT is the SS58 address to receive the drained native balance.
    This command is ONLY available on testnet and will refuse to run on finney.
    Examples:
      tusdt vault emergency-drain 5GrwvaEF... --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)

    # TESTNET-ONLY guard
    if config.get("network") != "testnet":
        print_error("emergency-drain is only available on testnet")
        return

    print_warning("DESTRUCTIVE OPERATION: This drains the vault's native balance. Only use on testnet.")

    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Emergency draining vault native balance to {recipient}...")

    try:
        client = TUSDTClient(config)
        result = client.vault_emergency_drain(keypair, recipient)
        print_success("Emergency drain completed!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))
