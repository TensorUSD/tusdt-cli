"""Vault CLI commands."""

import click

from tusdt_cli.context import CLIContext
from tusdt_cli.globals import network_option, wallet_option
from tusdt_cli.utils import (
    ModeAwareGroup,
    format_balance,
    parse_balance,
)
from tusdt_cli.wallet import get_reader_keypair, resolve_ss58

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
    "set-global-params",
    "execute-global-update",
    "cancel-global-update",
    "get-global-params",
    "set-approved-netuid",
    "is-approved-netuid",
    "claim-excess-alpha",
}


@click.group("vault", cls=ModeAwareGroup, advanced_commands=_VAULT_ADVANCED)
def vault_group() -> None:
    """Manage collateral vaults."""


# ------------------------------------------------------------------
# create
# ------------------------------------------------------------------


@vault_group.command("create")
@click.option("--amount", required=True, help="Alpha collateral amount in human-readable units (e.g. 1.5)")
@click.option("--netuid", required=True, type=int, help="Subnet netuid for the alpha collateral")
@wallet_option
@network_option
@click.pass_context
def create_vault(
    ctx: click.Context, amount: str, netuid: int, wallet_name: str | None, network: str | None
) -> None:
    """Create a new vault with subnet-alpha collateral via atomic pull deposit.

    The caller's alpha stake (held under the vault's hotkey) is pulled
    atomically via the caller_transfer_stake chain extension — no prior
    transfer step is needed.

    \b
    Examples:
      tusdt vault create --amount 1.5 --netuid 1 --wallet-name MyWallet
      tusdt vault create --amount 10 --netuid 42 --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    state.output.info(f"Pulling {amount} alpha (netuid {netuid}) as collateral...")
    state.submit(lambda c, kp: c.create_alpha_vault(kp, raw_amount, netuid))
    state.output.success("Vault created successfully!")


# ------------------------------------------------------------------
# add-collateral
# ------------------------------------------------------------------


@vault_group.command("add-collateral")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--amount", required=True, help="Collateral amount to add (e.g. 2.5)")
@wallet_option
@network_option
@click.pass_context
def add_collateral(
    ctx: click.Context, vault_id: int, amount: str, wallet_name: str | None, network: str | None
) -> None:
    """Add alpha collateral to an existing vault via atomic pull.

    \b
    VAULT_ID is the numeric ID of your vault.
    Examples:
      tusdt vault add-collateral 0 --amount 2.5 --wallet-name MyWallet
      tusdt vault add-collateral 3 --amount 1.0 --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    state.output.info(f"Pulling {amount} alpha collateral to vault {vault_id}...")
    state.submit(lambda c, kp: c.add_alpha_collateral(kp, vault_id, raw_amount))
    state.output.success("Collateral added!")


# ------------------------------------------------------------------
# borrow
# ------------------------------------------------------------------


@vault_group.command("borrow")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.argument("amount", type=str, metavar="<amount>")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    state.output.info(f"Borrowing {amount} from vault {vault_id}...")
    state.submit(lambda c, kp: c.borrow(kp, vault_id, raw_amount))
    state.output.success("Tokens borrowed!")


# ------------------------------------------------------------------
# repay
# ------------------------------------------------------------------


@vault_group.command("repay")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.argument("amount", type=str, metavar="<amount>")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    state.output.info(f"Repaying {amount} to vault {vault_id}...")
    state.submit(lambda c, kp: c.repay(kp, vault_id, raw_amount))
    state.output.success("Tokens repaid!")


# ------------------------------------------------------------------
# release-collateral
# ------------------------------------------------------------------


@vault_group.command("release-collateral")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.argument("amount", type=str, metavar="<amount>")
@click.option("--dest-coldkey", required=True, help="Destination coldkey SS58 address to receive the alpha")
@wallet_option
@network_option
@click.pass_context
def release_collateral(
    ctx: click.Context,
    vault_id: int,
    amount: str,
    dest_coldkey: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Release alpha collateral from a vault to a destination coldkey.

    \b
    VAULT_ID is the numeric ID of your vault.
    AMOUNT  is the human-readable collateral amount to release (e.g. 1.0).
    Examples:
      tusdt vault release-collateral 0 1.0 --dest-coldkey 5GrwvaEF... --wallet-name MyWallet
      tusdt vault release-collateral 2 0.5 --dest-coldkey 5GrwvaEF... --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)
    resolved_dest = resolve_ss58(dest_coldkey, cfg.get("wallet_path", ""))

    state.output.info(f"Releasing {amount} alpha collateral from vault {vault_id} to {resolved_dest}...")
    state.submit(lambda c, kp: c.release_alpha_collateral(kp, vault_id, raw_amount, resolved_dest))
    state.output.success("Collateral released!")


# ------------------------------------------------------------------
# info
# ------------------------------------------------------------------


@vault_group.command("info")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--owner", default=None, help="Owner SS58 address or wallet name (defaults to --wallet-name)")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)

    if owner:
        owner = resolve_ss58(owner, cfg.get("wallet_path"))
    elif state.wallet_name:
        owner = resolve_ss58(state.wallet_name, cfg.get("wallet_path"))
    else:
        state.output.error("Provide --owner (address or wallet name) or --wallet-name")
        return

    kp = get_reader_keypair(cfg)
    vault_data = state.run_read(lambda c: c.get_vault(kp, owner, vault_id))

    if vault_data is None:
        state.output.error(f"Vault {vault_id} not found for owner {owner}")
        return

    state.output.detail(
        f"Vault #{vault_id}",
        {
            "ID": vault_data.get("id", vault_id),
            "Owner": vault_data.get("owner", owner),
            "Netuid": vault_data.get("netuid", "?"),
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
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)

    if owner:
        owner = resolve_ss58(owner, cfg.get("wallet_path"))
    elif state.wallet_name:
        owner = resolve_ss58(state.wallet_name, cfg.get("wallet_path"))
    else:
        state.output.error("Provide --owner (address or wallet name) or --wallet-name")
        return

    kp = get_reader_keypair(cfg)
    total = state.run_read(lambda c: c.get_vaults_count(kp, owner))
    vaults = state.run_read(lambda c: c.list_vaults(kp, owner, page))

    if not vaults:
        state.output.info(f"No vaults found for {owner} (page {page})")
        return

    rows = []
    for v in vaults:
        rows.append(
            [
                str(v.get("id", "?")),
                str(v.get("netuid", "?")),
                format_balance(v.get("collateral_balance", 0), decimals),
                format_balance(v.get("borrowed_token_balance", 0), decimals),
                format_balance(v.get("debt_balance", 0), decimals),
                str(v.get("created_at", "?")),
            ]
        )

    state.output.info(f"Total vaults: {total}  |  Page: {page}")
    state.output.table(
        f"Vaults for {owner[:12]}...{owner[-6:]}",
        ["ID", "Netuid", "Collateral", "Borrowed", "Debt", "Created"],
        rows,
    )


# ------------------------------------------------------------------
# max-borrow
# ------------------------------------------------------------------


@vault_group.command("max-borrow")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--owner", default=None, help="Owner SS58 address or wallet name (defaults to --wallet-name)")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)

    if owner:
        owner = resolve_ss58(owner, cfg.get("wallet_path"))
    elif state.wallet_name:
        owner = resolve_ss58(state.wallet_name, cfg.get("wallet_path"))
    else:
        state.output.error("Provide --owner (address or wallet name) or --wallet-name")
        return

    kp = get_reader_keypair(cfg)
    value = state.run_read(lambda c: c.get_max_borrow(kp, owner, vault_id))

    state.output.detail(
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
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)

    if owner:
        owner = resolve_ss58(owner, cfg.get("wallet_path"))
    elif state.wallet_name:
        owner = resolve_ss58(state.wallet_name, cfg.get("wallet_path"))
    else:
        state.output.error("Provide --owner (address or wallet name) or --wallet-name")
        return

    kp = get_reader_keypair(cfg)
    value = state.run_read(lambda c: c.get_collateral_value(kp, owner, vault_id))

    state.output.detail(
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
@wallet_option
@network_option
@click.pass_context
def total_debt(ctx: click.Context, owner: str | None, wallet_name: str | None, network: str | None) -> None:
    """Show total debt for an owner across all vaults.

    \b
    Examples:
      tusdt vault total-debt --wallet-name MyWallet
      tusdt vault total-debt --owner 5GrwvaEF... --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)

    if owner:
        owner = resolve_ss58(owner, cfg.get("wallet_path"))
    elif state.wallet_name:
        owner = resolve_ss58(state.wallet_name, cfg.get("wallet_path"))
    else:
        state.output.error("Provide --owner (address or wallet name) or --wallet-name")
        return

    kp = get_reader_keypair(cfg)
    value = state.run_read(lambda c: c.get_total_debt(kp, owner))

    state.output.detail(
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
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()

    if owner:
        owner = resolve_ss58(owner, cfg.get("wallet_path"))
    elif state.wallet_name:
        owner = resolve_ss58(state.wallet_name, cfg.get("wallet_path"))
    else:
        state.output.error("Provide --owner (address or wallet name) or --wallet-name")
        return

    kp = get_reader_keypair(cfg)
    auction_id = state.run_read(lambda c: c.get_liquidation_auction_id(kp, owner, vault_id))

    if auction_id is None:
        state.output.info(f"No active liquidation auction for vault {vault_id} (owner: {owner})")
    else:
        state.output.detail(
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
@network_option
@click.pass_context
def list_all_vaults(ctx: click.Context, page: int, network: str | None) -> None:
    """List all vaults across all owners (paginated).

    \b
    Examples:
      tusdt vault list-all --network testnet
      tusdt vault list-all --page 2 --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)

    kp = get_reader_keypair(cfg)
    total = state.run_read(lambda c: c.get_total_vaults_count(kp))
    vaults = state.run_read(lambda c: c.get_all_vaults(kp, page))

    if not vaults:
        state.output.info(f"No vaults found (page {page})")
        return

    rows = []
    for v in vaults:
        rows.append(
            [
                str(v.get("id", "?")),
                str(v.get("netuid", "?")),
                str(v.get("owner", "?")),
                format_balance(v.get("collateral_balance", 0), decimals),
                format_balance(v.get("borrowed_token_balance", 0), decimals),
                format_balance(v.get("debt_balance", 0), decimals),
                str(v.get("created_at", "?")),
            ]
        )

    state.output.info(f"Total vaults: {total}  |  Page: {page}")
    state.output.table(
        "All Vaults",
        ["ID", "Netuid", "Owner", "Collateral", "Borrowed", "Debt", "Created"],
        rows,
    )


# ------------------------------------------------------------------
# params
# ------------------------------------------------------------------


@vault_group.command("params")
@click.option("--netuid", required=True, type=int, help="Subnet netuid")
@network_option
@click.pass_context
def vault_params(ctx: click.Context, netuid: int, network: str | None) -> None:
    """Show per-netuid vault contract parameters.

    \b
    Examples:
      tusdt vault params --netuid 1
      tusdt vault params --netuid 42 --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()

    kp = get_reader_keypair(cfg)
    params = state.run_read(lambda c: c.get_contract_params(kp, netuid))

    if isinstance(params, dict):
        display = {}
        for key, value in params.items():
            display[key] = value
        state.output.detail(f"Vault Contract Parameters (netuid {netuid})", display)
    else:
        state.output.detail(f"Vault Contract Parameters (netuid {netuid})", {"Raw": params})


# ------------------------------------------------------------------
# total-collateral
# ------------------------------------------------------------------


@vault_group.command("total-collateral")
@network_option
@click.pass_context
def total_collateral(ctx: click.Context, network: str | None) -> None:
    """Show total collateral balance across all vaults.

    \b
    Examples:
      tusdt vault total-collateral --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)

    kp = get_reader_keypair(cfg)
    value = state.run_read(lambda c: c.get_total_collateral_balance(kp))

    state.output.detail(
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
@network_option
@click.pass_context
def total_count(ctx: click.Context, network: str | None) -> None:
    """Show total vault count across all owners.

    \b
    Examples:
      tusdt vault total-count --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()

    kp = get_reader_keypair(cfg)
    count = state.run_read(lambda c: c.get_total_vaults_count(kp))

    state.output.detail("Total Vaults", {"Count": count})


# ------------------------------------------------------------------
# accrue-interest
# ------------------------------------------------------------------


@vault_group.command("accrue-interest")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--owner", required=True, help="Vault owner SS58 address or wallet name")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()

    owner = resolve_ss58(owner, cfg.get("wallet_path"))
    state.output.info(f"Accruing interest on vault {vault_id} (owner: {owner})...")
    state.submit(lambda c, kp: c.accrue_interest(kp, owner, vault_id))
    state.output.success("Interest accrued!")


# ------------------------------------------------------------------
# trigger-liquidation
# ------------------------------------------------------------------


@vault_group.command("trigger-liquidation")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--owner", required=True, help="Vault owner SS58 address or wallet name")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()

    owner = resolve_ss58(owner, cfg.get("wallet_path"))
    state.output.info(f"Triggering liquidation for vault {vault_id} (owner: {owner})...")
    state.submit(lambda c, kp: c.trigger_liquidation(kp, owner, vault_id))
    state.output.success("Liquidation auction triggered!")


# ------------------------------------------------------------------
# settle-liquidation
# ------------------------------------------------------------------


@vault_group.command("settle-liquidation")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--owner", required=True, help="Vault owner SS58 address or wallet name")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()

    owner = resolve_ss58(owner, cfg.get("wallet_path"))
    state.output.info(f"Settling liquidation for vault {vault_id} (owner: {owner})...")
    state.submit(lambda c, kp: c.settle_liquidation(kp, owner, vault_id))
    state.output.success("Liquidation settled!")


# ------------------------------------------------------------------
# governance
# ------------------------------------------------------------------


@vault_group.command("governance")
@network_option
@click.pass_context
def governance(ctx: click.Context, network: str | None) -> None:
    """Show the current governance address."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    addr = state.run_read(lambda c: c.get_governance(kp))
    state.output.detail("Governance", {"Address": addr})


# ------------------------------------------------------------------
# platform
# ------------------------------------------------------------------


@vault_group.command("platform")
@network_option
@click.pass_context
def platform(ctx: click.Context, network: str | None) -> None:
    """Show the current platform address."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    addr = state.run_read(lambda c: c.get_platform(kp))
    state.output.detail("Platform", {"Address": addr})


# ------------------------------------------------------------------
# paused
# ------------------------------------------------------------------


@vault_group.command("paused")
@network_option
@click.pass_context
def paused(ctx: click.Context, network: str | None) -> None:
    """Show whether the vault contract is paused."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    is_paused = state.run_read(lambda c: c.is_paused(kp))
    state.output.detail("Contract Status", {"Paused": is_paused})


# ------------------------------------------------------------------
# pending-update
# ------------------------------------------------------------------


@vault_group.command("pending-update")
@click.option("--netuid", required=True, type=int, help="Subnet netuid")
@network_option
@click.pass_context
def pending_update(ctx: click.Context, netuid: int, network: str | None) -> None:
    """Show pending per-netuid contract parameter update details."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    update = state.run_read(lambda c: c.get_pending_contract_params_update(kp, netuid))

    if update is None:
        state.output.info(f"No pending parameter update for netuid {netuid}")
    else:
        state.output.detail(f"Pending Parameter Update (netuid {netuid})", update)


# ------------------------------------------------------------------
# update-governance
# ------------------------------------------------------------------


@vault_group.command("update-governance")
@click.argument("address", type=str, metavar="<new-governance-address>")
@wallet_option
@network_option
@click.pass_context
def update_governance(ctx: click.Context, address: str, wallet_name: str | None, network: str | None) -> None:
    """Transfer governance to a new address.

    \b
    Examples:
      tusdt vault update-governance 5GrwvaEF... --wallet-name MyWallet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Updating governance to {address}...")
    state.submit(lambda c, kp: c.update_governance(kp, address))
    state.output.success("Governance updated!")


# ------------------------------------------------------------------
# update-platform
# ------------------------------------------------------------------


@vault_group.command("update-platform")
@click.argument("address", type=str, metavar="<new-platform-address>")
@wallet_option
@network_option
@click.pass_context
def update_platform(ctx: click.Context, address: str, wallet_name: str | None, network: str | None) -> None:
    """Update the platform address.

    \b
    Examples:
      tusdt vault update-platform 5GrwvaEF... --wallet-name MyWallet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Updating platform to {address}...")
    state.submit(lambda c, kp: c.update_platform(kp, address))
    state.output.success("Platform updated!")


# ------------------------------------------------------------------
# pause
# ------------------------------------------------------------------


@vault_group.command("pause")
@wallet_option
@network_option
@click.pass_context
def pause_contract(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Pause the vault contract (governance only).

    \b
    Examples:
      tusdt vault pause --wallet-name MyWallet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info("Pausing vault contract...")
    state.submit(lambda c, kp: c.pause_contract(kp))
    state.output.success("Contract paused!")


# ------------------------------------------------------------------
# unpause
# ------------------------------------------------------------------


@vault_group.command("unpause")
@wallet_option
@network_option
@click.pass_context
def unpause_contract(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Unpause the vault contract (governance only).

    \b
    Examples:
      tusdt vault unpause --wallet-name MyWallet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info("Unpausing vault contract...")
    state.submit(lambda c, kp: c.unpause_contract(kp))
    state.output.success("Contract unpaused!")


# ------------------------------------------------------------------
# set-params
# ------------------------------------------------------------------


@vault_group.command("set-params")
@click.option("--netuid", required=True, type=int, help="Subnet netuid")
@click.option("--collateral-ratio", type=int, default=None, help="Collateral ratio (e.g. 150 for 150%%)")
@click.option("--liquidation-ratio", type=int, default=None, help="Liquidation ratio (e.g. 120 for 120%%)")
@click.option(
    "--interest-rate", type=int, default=None, help="Interest rate in basis points (e.g. 1000 for 10%%)"
)
@click.option(
    "--liquidation-fee", type=int, default=None, help="Liquidation fee in basis points (e.g. 1100 for 11%%)"
)
@wallet_option
@network_option
@click.pass_context
def set_params(
    ctx: click.Context,
    netuid: int,
    collateral_ratio: int | None,
    liquidation_ratio: int | None,
    interest_rate: int | None,
    liquidation_fee: int | None,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Schedule a per-netuid contract parameter update (24h timelock).

    \b
    Per-netuid params: collateral_ratio, liquidation_ratio,
    interest_rate (bps), liquidation_fee (bps).
    Global params (transaction_fee, auction_duration_ms, max_oracle_age_ms)
    use the separate `set-global-params` command.

    \b
    Examples:
      tusdt vault set-params --netuid 1 --collateral-ratio 150 --liquidation-ratio 120 --wallet-name MyWallet
      tusdt vault set-params --netuid 42 --interest-rate 1000 --wallet-name MyWallet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    params: dict = {}
    if collateral_ratio is not None:
        params["collateral_ratio"] = collateral_ratio
    if liquidation_ratio is not None:
        params["liquidation_ratio"] = liquidation_ratio
    if interest_rate is not None:
        params["interest_rate"] = interest_rate
    if liquidation_fee is not None:
        params["liquidation_fee"] = liquidation_fee

    if not params:
        state.output.error("Provide at least one parameter to update")
        return

    state.output.info(f"Scheduling parameter update for netuid {netuid}: {params}")
    state.submit(lambda c, kp: c.set_contract_params(kp, netuid, params))
    state.output.success("Parameter update scheduled (24h timelock)!")


# ------------------------------------------------------------------
# execute-update
# ------------------------------------------------------------------


@vault_group.command("execute-update")
@click.option("--netuid", required=True, type=int, help="Subnet netuid")
@wallet_option
@network_option
@click.pass_context
def execute_update(ctx: click.Context, netuid: int, wallet_name: str | None, network: str | None) -> None:
    """Execute a pending per-netuid contract parameter update (after timelock expires).

    \b
    Examples:
      tusdt vault execute-update --netuid 1 --wallet-name MyWallet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Executing pending parameter update for netuid {netuid}...")
    state.submit(lambda c, kp: c.execute_contract_params_update(kp, netuid))
    state.output.success("Parameter update executed!")


# ------------------------------------------------------------------
# cancel-update
# ------------------------------------------------------------------


@vault_group.command("cancel-update")
@click.option("--netuid", required=True, type=int, help="Subnet netuid")
@wallet_option
@network_option
@click.pass_context
def cancel_update(ctx: click.Context, netuid: int, wallet_name: str | None, network: str | None) -> None:
    """Cancel a pending per-netuid contract parameter update.

    \b
    Examples:
      tusdt vault cancel-update --netuid 1 --wallet-name MyWallet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Cancelling pending parameter update for netuid {netuid}...")
    state.submit(lambda c, kp: c.cancel_contract_params_update(kp, netuid))
    state.output.success("Parameter update cancelled!")


# ------------------------------------------------------------------
# claim-surplus
# ------------------------------------------------------------------


@vault_group.command("claim-surplus")
@click.argument("amount", type=str, metavar="<amount>")
@wallet_option
@network_option
@click.pass_context
def claim_surplus(ctx: click.Context, amount: str, wallet_name: str | None, network: str | None) -> None:
    """Claim surplus TUSDT from the vault contract (permissionless — anyone may call).

    \b
    AMOUNT is the human-readable token amount to claim.
    Examples:
      tusdt vault claim-surplus 1000 --wallet-name MyWallet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    state.output.info(f"Claiming {amount} surplus TUSDT...")
    state.submit(lambda c, kp: c.claim_surplus_tusdt(kp, raw_amount))
    state.output.success("Surplus TUSDT claimed!")


# ------------------------------------------------------------------
# token-address
# ------------------------------------------------------------------


@vault_group.command("token-address")
@network_option
@click.pass_context
def token_address(ctx: click.Context, network: str | None) -> None:
    """Show the token contract address registered in the vault.

    \b
    Examples:
      tusdt vault token-address --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    addr = state.run_read(lambda c: c.get_token_address(kp))
    state.output.detail("Token Contract", {"Address": addr})


# ------------------------------------------------------------------
# auction-address
# ------------------------------------------------------------------


@vault_group.command("auction-address")
@network_option
@click.pass_context
def auction_address(ctx: click.Context, network: str | None) -> None:
    """Show the auction contract address registered in the vault.

    \b
    Examples:
      tusdt vault auction-address --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    addr = state.run_read(lambda c: c.get_auction_address(kp))
    state.output.detail("Auction Contract", {"Address": addr})


# ------------------------------------------------------------------
# oracle-address
# ------------------------------------------------------------------


@vault_group.command("oracle-address")
@network_option
@click.pass_context
def oracle_address(ctx: click.Context, network: str | None) -> None:
    """Show the oracle contract address registered in the vault.

    \b
    Examples:
      tusdt vault oracle-address --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    addr = state.run_read(lambda c: c.get_oracle_address(kp))
    state.output.detail("Oracle Contract", {"Address": addr})


# ------------------------------------------------------------------
# collateral-balance
# ------------------------------------------------------------------


@vault_group.command("collateral-balance")
@click.argument("vault_id", type=int, metavar="<vault-id>")
@click.option("--owner", default=None, help="Owner SS58 address or wallet name (defaults to --wallet-name)")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)

    if owner:
        owner = resolve_ss58(owner, cfg.get("wallet_path"))
    elif state.wallet_name:
        owner = resolve_ss58(state.wallet_name, cfg.get("wallet_path"))
    else:
        state.output.error("Provide --owner (address or wallet name) or --wallet-name")
        return

    kp = get_reader_keypair(cfg)
    value = state.run_read(lambda c: c.get_vault_collateral_balance(kp, owner, vault_id))

    if value is None:
        state.output.error(f"Vault {vault_id} not found for owner {owner}")
        return

    state.output.detail(
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
@network_option
@click.pass_context
def vault_treasury_address(ctx: click.Context, network: str | None) -> None:
    """Show the treasury address registered in the vault contract.

    \b
    Examples:
      tusdt vault treasury-address
      tusdt vault treasury-address --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    addr = state.run_read(lambda c: c.vault_get_treasury(kp))
    state.output.detail("Vault Treasury", {"Address": addr})


# ------------------------------------------------------------------
# update-treasury
# ------------------------------------------------------------------


@vault_group.command("update-treasury")
@click.argument("address", type=str, metavar="<ss58-address>")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Updating vault treasury address to {address}...")
    state.submit(lambda c, kp: c.vault_update_treasury(kp, address))
    state.output.success("Treasury address updated!")


# ------------------------------------------------------------------
# emergency-drain
# ------------------------------------------------------------------


@vault_group.command("emergency-drain")
@click.argument("recipient", type=str, metavar="<ss58-address>")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()

    # TESTNET-ONLY guard
    if cfg.get("network") != "testnet":
        state.output.error("emergency-drain is only available on testnet")
        return

    state.output.warning(
        "DESTRUCTIVE OPERATION: This drains the vault's native balance. Only use on testnet."
    )
    state.output.info(f"Emergency draining vault native balance to {recipient}...")
    state.submit(lambda c, kp: c.vault_emergency_drain(kp, recipient))
    state.output.success("Emergency drain completed!")


# ------------------------------------------------------------------
# set-global-params
# ------------------------------------------------------------------


@vault_group.command("set-global-params")
@click.option(
    "--transaction-fee", type=int, default=None, help="Transaction fee in basis points (e.g. 30 for 0.3%%)"
)
@click.option("--auction-duration-ms", type=int, default=None, help="Auction duration in milliseconds")
@click.option("--max-oracle-age-ms", type=int, default=None, help="Max oracle price age in milliseconds")
@wallet_option
@network_option
@click.pass_context
def set_global_params(
    ctx: click.Context,
    transaction_fee: int | None,
    auction_duration_ms: int | None,
    max_oracle_age_ms: int | None,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Schedule a global parameters update (24h timelock).

    Global params affect all subnets: transaction_fee (bps),
    auction_duration_ms, max_oracle_age_ms.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    config: dict = {}
    if transaction_fee is not None:
        config["transaction_fee"] = transaction_fee
    if auction_duration_ms is not None:
        config["auction_duration_ms"] = auction_duration_ms
    if max_oracle_age_ms is not None:
        config["max_oracle_age_ms"] = max_oracle_age_ms

    if not config:
        state.output.error("Provide at least one global parameter to update")
        return

    state.output.info(f"Scheduling global params update: {config}")
    state.submit(lambda c, kp: c.set_global_params(kp, config))
    state.output.success("Global params update scheduled (24h timelock)!")


# ------------------------------------------------------------------
# execute-global-update
# ------------------------------------------------------------------


@vault_group.command("execute-global-update")
@wallet_option
@network_option
@click.pass_context
def execute_global_update(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Execute the pending global params update (after timelock expires, permissionless)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info("Executing pending global params update...")
    state.submit(lambda c, kp: c.execute_global_params_update(kp))
    state.output.success("Global params update executed!")


# ------------------------------------------------------------------
# cancel-global-update
# ------------------------------------------------------------------


@vault_group.command("cancel-global-update")
@wallet_option
@network_option
@click.pass_context
def cancel_global_update(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Cancel the pending global params update."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info("Cancelling pending global params update...")
    state.submit(lambda c, kp: c.cancel_global_params_update(kp))
    state.output.success("Global params update cancelled!")


# ------------------------------------------------------------------
# get-global-params
# ------------------------------------------------------------------


@vault_group.command("get-global-params")
@network_option
@click.pass_context
def get_global_params(ctx: click.Context, network: str | None) -> None:
    """Show vault global parameters (transaction fee, auction duration, max oracle age)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    params = state.run_read(lambda c: c.get_global_params(kp))
    if isinstance(params, dict):
        state.output.detail("Vault Global Parameters", params)
    else:
        state.output.detail("Vault Global Parameters", {"Raw": params})


# ------------------------------------------------------------------
# set-approved-netuid
# ------------------------------------------------------------------


@vault_group.command("set-approved-netuid")
@click.argument("netuid", type=int, metavar="<netuid>")
@click.option("--approve/--revoke", default=True, help="Approve (default) or revoke the subnet")
@wallet_option
@network_option
@click.pass_context
def set_approved_netuid(
    ctx: click.Context,
    netuid: int,
    approve: bool,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Approve or revoke a subnet for vault collateral.

    \b
    Examples:
      tusdt vault set-approved-netuid 42 --approve --wallet-name MyWallet
      tusdt vault set-approved-netuid 42 --revoke --wallet-name MyWallet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    action = "Approving" if approve else "Revoking"
    state.output.info(f"{action} subnet {netuid}...")
    state.submit(lambda c, kp: c.set_approved_netuid(kp, netuid, approve))
    state.output.success(f"Subnet {netuid} {'approved' if approve else 'revoked'}!")


# ------------------------------------------------------------------
# is-approved-netuid
# ------------------------------------------------------------------


@vault_group.command("is-approved-netuid")
@click.argument("netuid", type=int, metavar="<netuid>")
@network_option
@click.pass_context
def is_approved_netuid(ctx: click.Context, netuid: int, network: str | None) -> None:
    """Check whether a subnet is approved for vault collateral."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    approved = state.run_read(lambda c: c.is_approved_netuid(kp, netuid))
    status = "approved" if approved else "NOT approved"
    state.output.detail(f"Subnet {netuid}", {"Approved": status})


# ------------------------------------------------------------------
# claim-excess-alpha
# ------------------------------------------------------------------


@vault_group.command("claim-excess-alpha")
@click.argument("netuid", type=int, metavar="<netuid>")
@wallet_option
@network_option
@click.pass_context
def claim_excess_alpha(ctx: click.Context, netuid: int, wallet_name: str | None, network: str | None) -> None:
    """Claim excess alpha staking rewards on a subnet (maintainer only).

    Excess = actual contract stake minus total collateral. The excess
    is unstaked to native TAO and transferred to the treasury.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Claiming excess alpha on netuid {netuid}...")
    state.submit(lambda c, kp: c.claim_excess_alpha(kp, netuid))
    state.output.success(f"Excess alpha claimed on netuid {netuid}!")
