"""Governance CLI commands."""

import click

from tusdt_cli.context import CLIContext
from tusdt_cli.globals import network_option, wallet_option
from tusdt_cli.utils import (
    HelpfulCommand,
    ModeAwareGroup,
    format_balance,
    parse_balance,
)
from tusdt_cli.wallet import get_reader_keypair

_GOVERNANCE_ADVANCED = {
    "set-council",
    "vault-set-params",
    "vault-cancel-update",
    "vault-update-treasury",
    "vault-update-platform",
    "vault-set-token-controller",
    "vault-update-auction-address",
    "vault-update-oracle-address",
    "vault-unpause",
    "vault-pause",
    "vault-claim-excess-alpha",
    "vault-set-approved-netuid",
    "vault-set-global-params",
    "vault-cancel-global-update",
    "oracle-set-validator",
    "oracle-set-deviation",
    "oracle-commit-round",
    "oracle-set-netuid",
    "oracle-set-min-submitter-stake",
    "auction-set-admin",
    "update-params",
    "update-vault-address",
    "update-auction-address",
    "update-oracle-address",
    "update-treasury-address",
    "submit-proposal",
    "vote",
    "finalize-proposal",
    "execute-proposal",
    "submit-snapshot",
    "elect-maintainer",
    "election-set-netuid",
}


@click.group("governance", cls=ModeAwareGroup, advanced_commands=_GOVERNANCE_ADVANCED)
def governance_group() -> None:
    """Governance operations for the TUSDT system."""


# ======================================================================
# Basic (read) commands
# ======================================================================

# ------------------------------------------------------------------
# maintainer
# ------------------------------------------------------------------


@governance_group.command("maintainer")
@network_option
@click.pass_context
def maintainer(ctx: click.Context, network: str | None) -> None:
    """Show the current maintainer account address.

    \b
    Examples:
      tusdt governance maintainer
      tusdt governance maintainer --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    addr = state.run_read(lambda c: c.get_maintainer(kp))
    state.output.detail("Maintainer", {"Address": addr})


# ------------------------------------------------------------------
# council
# ------------------------------------------------------------------


@governance_group.command("council")
@network_option
@click.pass_context
def council(ctx: click.Context, network: str | None) -> None:
    """List all council members.

    \b
    Examples:
      tusdt governance council
      tusdt governance council --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    members = state.run_read(lambda c: c.get_council(kp))

    if not members:
        state.output.info("No council members")
        return

    rows = [[str(i), addr] for i, addr in enumerate(members)]
    state.output.table("Council Members", ["#", "Address"], rows)


# ------------------------------------------------------------------
# is-council
# ------------------------------------------------------------------


@governance_group.command("is-council")
@click.argument("account", type=str, metavar="<ss58-address>")
@network_option
@click.pass_context
def is_council_cmd(ctx: click.Context, account: str, network: str | None) -> None:
    """Check whether an account is a council member.

    \b
    ACCOUNT is the SS58 address to check.
    Examples:
      tusdt governance is-council 5GrwvaEF...
      tusdt governance is-council 5GrwvaEF... --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.is_council(kp, account))

    state.output.detail("Council Status", {"Account": account, "Is council member": result})


# ------------------------------------------------------------------
# treasury
# ------------------------------------------------------------------


@governance_group.command("treasury")
@network_option
@click.pass_context
def governance_treasury(ctx: click.Context, network: str | None) -> None:
    """Show the treasury address registered in the governance contract.

    \b
    Examples:
      tusdt governance treasury
      tusdt governance treasury --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    addr = state.run_read(lambda c: c.get_governance_treasury(kp))
    state.output.detail("Treasury", {"Address": addr})


# ------------------------------------------------------------------
# params
# ------------------------------------------------------------------


@governance_group.command("params")
@network_option
@click.pass_context
def governance_params(ctx: click.Context, network: str | None) -> None:
    """Show governance contract parameters.

    \b
    Examples:
      tusdt governance params
      tusdt governance params --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    params = state.run_read(lambda c: c.get_governance_params(kp))

    if isinstance(params, dict):
        state.output.detail("Governance Parameters", params)
    else:
        state.output.detail("Governance Parameters", {"Raw": params})


# ------------------------------------------------------------------
# current-epoch
# ------------------------------------------------------------------


@governance_group.command("current-epoch")
@network_option
@click.pass_context
def current_epoch(ctx: click.Context, network: str | None) -> None:
    """Show the current epoch number.

    \b
    Examples:
      tusdt governance current-epoch
      tusdt governance current-epoch --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    epoch = state.run_read(lambda c: c.get_current_epoch(kp))
    state.output.detail("Current Epoch", {"Epoch": epoch})


# ------------------------------------------------------------------
# get-snapshot
# ------------------------------------------------------------------


@governance_group.command("get-snapshot")
@click.argument("epoch", type=int, metavar="<epoch>")
@network_option
@click.pass_context
def get_snapshot(ctx: click.Context, epoch: int, network: str | None) -> None:
    """Show the Merkle snapshot for a given epoch.

    \b
    EPOCH is the epoch number to query (integer).
    Returns None if no snapshot exists for that epoch.
    Examples:
      tusdt governance get-snapshot 42
      tusdt governance get-snapshot 42 --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    snapshot = state.run_read(lambda c: c.get_snapshot(kp, epoch))

    if snapshot is None:
        state.output.info(f"No snapshot for epoch {epoch}")
    else:
        state.output.detail(f"Snapshot – Epoch {epoch}", snapshot)


# ------------------------------------------------------------------
# quorum
# ------------------------------------------------------------------


@governance_group.command("quorum")
@click.argument("epoch", type=int, metavar="<epoch>")
@network_option
@click.pass_context
def quorum(ctx: click.Context, epoch: int, network: str | None) -> None:
    """Show the absolute quorum threshold for a given epoch.

    \b
    EPOCH is the epoch number to query (integer).
    Returns the minimum yes-vote balance required for a proposal to pass.
    Examples:
      tusdt governance quorum 42
      tusdt governance quorum 42 --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.get_quorum(kp, epoch))

    state.output.detail(
        f"Quorum – Epoch {epoch}",
        {
            "Quorum (raw)": result,
            "Quorum": format_balance(result, decimals),  # ty: ignore
        },
    )


# ------------------------------------------------------------------
# proposal-count
# ------------------------------------------------------------------


@governance_group.command("proposal-count")
@network_option
@click.pass_context
def proposal_count(ctx: click.Context, network: str | None) -> None:
    """Show the total number of proposals.

    \b
    Examples:
      tusdt governance proposal-count
      tusdt governance proposal-count --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    count = state.run_read(lambda c: c.get_proposal_count(kp))
    state.output.detail("Proposals", {"Count": count})


# ------------------------------------------------------------------
# get-proposal
# ------------------------------------------------------------------


@governance_group.command("get-proposal")
@click.argument("proposal_id", type=int, metavar="<proposal-id>")
@network_option
@click.pass_context
def get_proposal(ctx: click.Context, proposal_id: int, network: str | None) -> None:
    """Show details for a specific proposal.

    \b
    PROPOSAL_ID is the numeric proposal ID (integer).
    Examples:
      tusdt governance get-proposal 0
      tusdt governance get-proposal 5 --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    proposal = state.run_read(lambda c: c.get_proposal(kp, proposal_id))

    if proposal is None:
        state.output.error(f"Proposal {proposal_id} not found")
        return

    state.output.detail(f"Proposal #{proposal_id}", proposal)


# ------------------------------------------------------------------
# has-voted
# ------------------------------------------------------------------


@governance_group.command("has-voted")
@click.argument("proposal_id", type=int, metavar="<proposal-id>")
@click.option("--coldkey", required=True, help="Coldkey SS58 address (e.g. 5GrwvaEF...)")
@click.option("--hotkey", required=True, help="Hotkey SS58 address (e.g. 5GrwvaEF...)")
@network_option
@click.pass_context
def has_voted_cmd(
    ctx: click.Context,
    proposal_id: int,
    coldkey: str,
    hotkey: str,
    network: str | None,
) -> None:
    """Check whether a (coldkey, hotkey) pair has voted on a proposal.

    \b
    PROPOSAL_ID is the numeric proposal ID (integer).
    Examples:
      tusdt governance has-voted 0 --coldkey 5GrwvaEF... --hotkey 5GrwvaEF...
      tusdt governance has-voted 5 --coldkey 5GrwvaEF... --hotkey 5FHneW... --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.has_voted(kp, proposal_id, coldkey, hotkey))

    state.output.detail(
        "Vote Status",
        {
            "Proposal ID": proposal_id,
            "Coldkey": coldkey,
            "Hotkey": hotkey,
            "Has voted": result,
        },
    )


# ------------------------------------------------------------------
# netuid
# ------------------------------------------------------------------


@governance_group.command("netuid")
@network_option
@click.pass_context
def governance_netuid(ctx: click.Context, network: str | None) -> None:
    """Show the governing subnet netuid.

    \b
    Examples:
      tusdt governance netuid
      tusdt governance netuid --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    netuid = state.run_read(lambda c: c.get_netuid(kp))
    state.output.detail("Governing Netuid", {"Netuid": netuid})


# ------------------------------------------------------------------
# election
# ------------------------------------------------------------------


@governance_group.command("election")
@network_option
@click.pass_context
def governance_election(ctx: click.Context, network: str | None) -> None:
    """Show the election contract address registered in governance.

    \b
    Examples:
      tusdt governance election
      tusdt governance election --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    addr = state.run_read(lambda c: c.get_election_address(kp))
    state.output.detail("Election Contract", {"Address": addr})


# ------------------------------------------------------------------
# election-snapshot
# ------------------------------------------------------------------


@governance_group.command("election-snapshot")
@network_option
@click.pass_context
def governance_election_snapshot(ctx: click.Context, network: str | None) -> None:
    """Show the latest election snapshot used by the election contract.

    \b
    Examples:
      tusdt governance election-snapshot
      tusdt governance election-snapshot --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    snapshot = state.run_read(lambda c: c.get_election_snapshot(kp))

    if snapshot is None:
        state.output.info("No election snapshot available")
        return

    if isinstance(snapshot, (list, tuple)) and len(snapshot) >= 4:
        merkle_root = snapshot[0]
        root_hex = "0x" + bytes(merkle_root).hex() if merkle_root else "N/A"
        state.output.detail(
            "Election Snapshot",
            {
                "Merkle Root": root_hex,
                "Circulating Supply": snapshot[1],
                "Netuid": snapshot[2],
                "Snapshot Block": snapshot[3],
            },
        )
    else:
        state.output.detail("Election Snapshot", {"Raw": snapshot})


# ======================================================================
# Advanced (write) commands
# ======================================================================

# ------------------------------------------------------------------
# set-council
# ------------------------------------------------------------------


@governance_group.command("set-council")
@click.option(
    "--members",
    multiple=True,
    required=True,
    help="Council member SS58 address (repeatable, e.g. --members A --members B)",
)
@wallet_option
@network_option
@click.pass_context
def set_council_cmd(
    ctx: click.Context,
    members: tuple,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Set the council member list (maintainer only).

    \b
    Replaces the entire council with the provided list of SS58 addresses.
    Examples:
      tusdt governance set-council --members 5GrwvaEF... --members 5FHneW... --wallet-name MyWallet
      tusdt governance set-council --members 5GrwvaEF... --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    members_list = list(members)
    state.output.info(f"Setting council to {len(members_list)} member(s)...")
    state.submit(lambda c, kp: c.set_council(kp, members_list))
    state.output.success("Council updated!")


# ------------------------------------------------------------------
# vault-set-params
# ------------------------------------------------------------------


@governance_group.command("vault-set-params")
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
def gov_vault_set_params_cmd(
    ctx: click.Context,
    netuid: int,
    collateral_ratio: int | None,
    liquidation_ratio: int | None,
    interest_rate: int | None,
    liquidation_fee: int | None,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Schedule a per-netuid vault contract parameter update via governance (maintainer only).

    \b
    Per-netuid params: collateral_ratio, liquidation_ratio,
    interest_rate (bps), liquidation_fee (bps).
    Global params use `vault-set-global-params`.

    \b
    Examples:
      tusdt governance vault-set-params --netuid 1 --collateral-ratio 150 --wallet-name MyWallet
      tusdt governance vault-set-params --netuid 42 --interest-rate 1000 --wallet-name MyWallet
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

    state.output.info(f"Scheduling vault parameter update via governance for netuid {netuid}: {params}")
    state.submit(lambda c, kp: c.gov_vault_set_contract_params(kp, netuid, params))
    state.output.success("Vault parameter update scheduled via governance!")


# ------------------------------------------------------------------
# vault-cancel-update
# ------------------------------------------------------------------


@governance_group.command("vault-cancel-update")
@click.option("--netuid", required=True, type=int, help="Subnet netuid")
@wallet_option
@network_option
@click.pass_context
def gov_vault_cancel_update_cmd(
    ctx: click.Context,
    netuid: int,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Cancel a pending per-netuid vault contract parameter update via governance.

    \b
    Examples:
      tusdt governance vault-cancel-update --netuid 1 --wallet-name MyWallet
      tusdt governance vault-cancel-update --netuid 42 --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Cancelling pending vault parameter update via governance for netuid {netuid}...")
    state.submit(lambda c, kp: c.gov_vault_cancel_update(kp, netuid))
    state.output.success("Vault parameter update cancelled via governance!")


# ------------------------------------------------------------------
# vault-update-treasury
# ------------------------------------------------------------------


@governance_group.command("vault-update-treasury")
@click.argument("address", type=str, metavar="<ss58-address>")
@wallet_option
@network_option
@click.pass_context
def gov_vault_update_treasury_cmd(
    ctx: click.Context,
    address: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Update the vault treasury address via governance.

    \b
    ADDRESS is the SS58 address of the new treasury contract.
    Examples:
      tusdt governance vault-update-treasury 5GrwvaEF... --wallet-name MyWallet
      tusdt governance vault-update-treasury 5GrwvaEF... --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Updating vault treasury to {address} via governance...")
    state.submit(lambda c, kp: c.gov_vault_update_treasury(kp, address))
    state.output.success("Vault treasury updated via governance!")


# ------------------------------------------------------------------
# vault-update-platform
# ------------------------------------------------------------------


@governance_group.command("vault-update-platform")
@click.argument("address", type=str, metavar="<ss58-address>")
@wallet_option
@network_option
@click.pass_context
def gov_vault_update_platform_cmd(
    ctx: click.Context,
    address: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Update the vault platform address via governance.

    \b
    ADDRESS is the SS58 address of the new platform account.
    Examples:
      tusdt governance vault-update-platform 5GrwvaEF... --wallet-name MyWallet
      tusdt governance vault-update-platform 5GrwvaEF... --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Updating vault platform to {address} via governance...")
    state.submit(lambda c, kp: c.gov_vault_update_platform(kp, address))
    state.output.success("Vault platform updated via governance!")


# ------------------------------------------------------------------
# vault-unpause
# ------------------------------------------------------------------


@governance_group.command("vault-unpause")
@wallet_option
@network_option
@click.pass_context
def gov_vault_unpause_cmd(
    ctx: click.Context,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Unpause the vault contract via governance.

    \b
    Examples:
      tusdt governance vault-unpause --wallet-name MyWallet
      tusdt governance vault-unpause --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info("Unpausing vault contract via governance...")
    state.submit(lambda c, kp: c.gov_vault_unpause(kp))
    state.output.success("Vault unpaused via governance!")


# ------------------------------------------------------------------
# vault-pause
# ------------------------------------------------------------------


@governance_group.command("vault-pause")
@wallet_option
@network_option
@click.pass_context
def gov_vault_pause_cmd(
    ctx: click.Context,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Pause the vault contract via governance (council only).

    \b
    Examples:
      tusdt governance vault-pause --wallet-name MyWallet
      tusdt governance vault-pause --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info("Pausing vault contract via governance...")
    state.submit(lambda c, kp: c.gov_vault_pause(kp))
    state.output.success("Vault paused via governance!")


# ------------------------------------------------------------------
# oracle-set-validator
# ------------------------------------------------------------------


@governance_group.command("oracle-set-validator")
@click.argument("address", type=str, metavar="<ss58-address>", required=False)
@click.option("--clear", is_flag=True, default=False, help="Clear the validator (set to None)")
@wallet_option
@network_option
@click.pass_context
def gov_oracle_set_validator_cmd(
    ctx: click.Context,
    address: str | None,
    clear: bool,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Set or clear the oracle validator via governance.

    \b
    ADDRESS is the SS58 address of the validator, or omit and use --clear to remove.
    Examples:
      tusdt governance oracle-set-validator 5GrwvaEF... --wallet-name MyWallet
      tusdt governance oracle-set-validator --clear --wallet-name MyWallet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    validator = None if clear else address
    if not clear and not address:
        state.output.error("Provide an SS58 address or use --clear to remove the validator")
        return

    action = "Clearing" if clear else f"Setting to {address}"
    state.output.info(f"{action} oracle validator via governance...")
    state.submit(lambda c, kp: c.gov_oracle_set_validator(kp, validator))
    state.output.success("Oracle validator updated via governance!")


# ------------------------------------------------------------------
# oracle-set-deviation
# ------------------------------------------------------------------


@governance_group.command("oracle-set-deviation")
@click.argument("deviation", type=int, metavar="<deviation>")
@wallet_option
@network_option
@click.pass_context
def gov_oracle_set_deviation_cmd(
    ctx: click.Context,
    deviation: int,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Set the oracle max price deviation via governance.

    \b
    DEVIATION is the max price deviation ratio on 10^18 scale (integer).
    Examples:
      tusdt governance oracle-set-deviation 500000000000000000 --wallet-name MyWallet
      tusdt governance oracle-set-deviation 500000000000000000 --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Setting oracle max price deviation to {deviation} via governance...")
    state.submit(lambda c, kp: c.gov_oracle_set_max_price_deviation(kp, deviation))
    state.output.success("Oracle max price deviation updated via governance!")


# ------------------------------------------------------------------
# oracle-commit-round
# ------------------------------------------------------------------


@governance_group.command("oracle-commit-round")
@click.argument("price", type=int, metavar="<price>")
@wallet_option
@network_option
@click.pass_context
def gov_oracle_commit_round_cmd(
    ctx: click.Context,
    price: int,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Commit the current oracle round with an explicit price via governance.

    \b
    PRICE is the price value on 10^18 scale (integer).
    Examples:
      tusdt governance oracle-commit-round 1500000000000000000 --wallet-name MyWallet
      tusdt governance oracle-commit-round 1500000000000000000 --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Committing oracle round with price {price} via governance...")
    state.submit(lambda c, kp: c.gov_oracle_commit_round(kp, price))
    state.output.success("Oracle round committed via governance!")


# ------------------------------------------------------------------
# oracle-set-netuid
# ------------------------------------------------------------------


@governance_group.command("oracle-set-netuid")
@click.argument("netuid", type=int, metavar="<netuid>")
@wallet_option
@network_option
@click.pass_context
def oracle_set_netuid(ctx: click.Context, netuid: int, wallet_name: str | None, network: str | None) -> None:
    """Set the oracle's governing subnet netuid via governance (maintainer only)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Setting oracle netuid to {netuid}...")
    state.submit(lambda c, kp: c.gov_oracle_set_netuid(kp, netuid))
    state.output.success("Oracle netuid updated!")


# ------------------------------------------------------------------
# oracle-set-min-submitter-stake
# ------------------------------------------------------------------


@governance_group.command("oracle-set-min-submitter-stake")
@click.argument("amount", type=str, metavar="<amount>")
@wallet_option
@network_option
@click.pass_context
def oracle_set_min_submitter_stake(
    ctx: click.Context, amount: str, wallet_name: str | None, network: str | None
) -> None:
    """Set the oracle's minimum submitter stake via governance (maintainer only)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)

    try:
        raw_amount = parse_balance(amount, decimals)
    except ValueError:
        state.output.error(f"Invalid amount: {amount}")
        return

    state.output.info(f"Setting oracle min submitter stake to {amount} (raw: {raw_amount})...")
    state.submit(lambda c, kp: c.gov_oracle_set_min_submitter_stake(kp, raw_amount))
    state.output.success("Oracle min submitter stake updated!")


# ------------------------------------------------------------------
# auction-set-admin
# ------------------------------------------------------------------


@governance_group.command("auction-set-admin")
@click.argument("address", type=str, metavar="<ss58-address>", required=False)
@click.option("--clear", is_flag=True, default=False, help="Clear the admin (set to None)")
@wallet_option
@network_option
@click.pass_context
def gov_auction_set_admin_cmd(
    ctx: click.Context,
    address: str | None,
    clear: bool,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Set or clear the auction admin via governance.

    \b
    ADDRESS is the SS58 address of the admin, or omit and use --clear to remove.
    Examples:
      tusdt governance auction-set-admin 5GrwvaEF... --wallet-name MyWallet
      tusdt governance auction-set-admin --clear --wallet-name MyWallet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    admin = None if clear else address
    if not clear and not address:
        state.output.error("Provide an SS58 address or use --clear to remove the admin")
        return

    action = "Clearing" if clear else f"Setting to {address}"
    state.output.info(f"{action} auction admin via governance...")
    state.submit(lambda c, kp: c.gov_auction_set_admin(kp, admin))
    state.output.success("Auction admin updated via governance!")


# ------------------------------------------------------------------
# update-params
# ------------------------------------------------------------------


@governance_group.command("update-params", cls=HelpfulCommand)
@wallet_option
@network_option
@click.option(
    "--voting-period-ms",
    type=int,
    required=True,
    help="Voting period in milliseconds (e.g., 172800000 for 48h)",
)
@click.option(
    "--quorum-bps", type=int, required=True, help="Quorum threshold in basis points (e.g., 2000 for 20%)"
)
@click.option(
    "--approval-bps", type=int, required=True, help="Approval threshold in basis points (e.g., 5001 for >50%)"
)
@click.option(
    "--min-proposer-stake",
    type=str,
    required=True,
    help="Minimum subnet alpha stake in human-readable units (e.g. 1000.0)",
)
@click.option(
    "--submission-open-day", type=int, required=True, help="First day of month proposals are accepted (1-28)"
)
@click.option(
    "--submission-close-day",
    type=int,
    required=True,
    help="Last day of month proposals are accepted (1-28, >= open day)",
)
@click.pass_context
def update_params_cmd(
    ctx: click.Context,
    wallet_name: str | None,
    network: str | None,
    voting_period_ms: int,
    quorum_bps: int,
    approval_bps: int,
    min_proposer_stake: str,
    submission_open_day: int,
    submission_close_day: int,
) -> None:
    """Update governance parameters (maintainer only).

    \b
    All six parameters are required.
    Examples:
      tusdt governance update-params --voting-period-ms 172800000 --quorum-bps 2000 --approval-bps 5001 --min-proposer-stake 1000.0 --submission-open-day 1 --submission-close-day 7 --wallet-name MyWallet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)

    raw_min_stake = parse_balance(min_proposer_stake, decimals)

    state.output.info(
        f"Updating governance parameters: voting_period_ms={voting_period_ms}, quorum_bps={quorum_bps}, approval_bps={approval_bps}, min_proposer_stake={raw_min_stake}, submission_open_day={submission_open_day}, submission_close_day={submission_close_day}"
    )
    state.submit(
        lambda c, kp: c.update_governance_params(
            kp,
            voting_period_ms,
            quorum_bps,
            approval_bps,
            raw_min_stake,
            submission_open_day,
            submission_close_day,
        )
    )
    state.output.success("Governance parameters updated!")


# ------------------------------------------------------------------
# submit-proposal
# ------------------------------------------------------------------


@governance_group.command("submit-proposal")
@click.option("--cid", required=True, help="Content identifier string (e.g. Qm... or proposal description)")
@click.option(
    "--kind",
    required=True,
    type=click.Choice(["non-funding", "funding"], case_sensitive=False),
    help="Proposal kind: non-funding (no fund allocation) or funding (allocates funds)",
)
@click.option(
    "--fund",
    default=None,
    type=click.Choice(
        ["emergency", "operation", "insurance", "dividend", "buyback", "voting"], case_sensitive=False
    ),
    help="Fund variant (required if kind=funding)",
)
@click.option(
    "--token-kind",
    "token_kind_opt",
    default=None,
    type=click.Choice(["tusdt", "native"], case_sensitive=False),
    help="Token kind for funding (required if kind=funding)",
)
@click.option(
    "--funding-amount",
    type=str,
    default=None,
    help="Funding amount in human-readable units (required if kind=funding, e.g. 1000.0)",
)
@click.option(
    "--funding-recipient",
    type=str,
    default=None,
    metavar="<ss58-address>",
    help="Recipient SS58 address (required if kind=funding)",
)
@wallet_option
@network_option
@click.pass_context
def submit_proposal_cmd(
    ctx: click.Context,
    cid: str,
    kind: str,
    fund: str | None,
    token_kind_opt: str | None,
    funding_amount: str | None,
    funding_recipient: str | None,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Submit a new governance proposal (council only).

    \b
    For non-funding proposals, only --cid and --kind non-funding are required.
    For funding proposals, also provide --fund, --token-kind, --funding-amount, and --funding-recipient.
    Examples:
      tusdt governance submit-proposal --cid "QmXyz..." --kind non-funding --wallet-name MyWallet
      tusdt governance submit-proposal --cid "QmXyz..." --kind funding --fund emergency --token-kind tusdt --funding-amount 5000 --funding-recipient 5GrwvaEF... --wallet-name MyWallet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)

    # Build ProposalKind
    if kind.lower() == "funding":
        if not all([fund, token_kind_opt, funding_amount, funding_recipient]):
            state.output.error(
                "Funding proposals require: --fund, --token-kind, --funding-amount, --funding-recipient"
            )
            return
        assert funding_amount is not None
        assert fund is not None
        assert token_kind_opt is not None
        raw_amount = parse_balance(funding_amount, decimals)
        # Fund variant: {"Emergency": null}, {"Operation": null}, etc.
        fund_dict = {fund.capitalize(): None}
        # TokenKind variant: {"Tusdt": null} or {"Native": null}
        token_kind_dict = {"Tusdt": None} if token_kind_opt.lower() == "tusdt" else {"Native": None}
        kind_dict = {
            "Funding": {
                "fund": fund_dict,
                "token_kind": token_kind_dict,
                "amount": raw_amount,
                "recipient": funding_recipient,
            }
        }
    else:
        kind_dict = {"NonFunding": None}

    state.output.info(f"Submitting proposal (cid={cid}, kind={kind})...")
    state.submit(lambda c, kp: c.submit_proposal(kp, cid, kind_dict))
    state.output.success("Proposal submitted!")


# ------------------------------------------------------------------
# vote
# ------------------------------------------------------------------


@governance_group.command("vote")
@click.argument("proposal_id", type=int, metavar="<proposal-id>")
@click.option("--hotkey", required=True, help="Hotkey SS58 address of the voter (e.g. 5GrwvaEF...)")
@click.option(
    "--support/--oppose", default=True, help="Vote in support (default) or opposition of the proposal"
)
@click.option(
    "--balance", type=str, required=True, help="Voting balance in human-readable units (e.g. 1000.0)"
)
@click.option(
    "--multiplier-bps", type=int, required=True, help="Multiplier in basis points (e.g. 10000 for 1x)"
)
@click.option(
    "--proof",
    "proofs",
    multiple=True,
    required=True,
    metavar="<hex-string>",
    help="Merkle proof hash as hex-encoded 32 bytes (repeatable, e.g. --proof 0xabc... --proof 0xdef...)",
)
@wallet_option
@network_option
@click.pass_context
def vote_cmd(
    ctx: click.Context,
    proposal_id: int,
    hotkey: str,
    support: bool,
    balance: str,
    multiplier_bps: int,
    proofs: tuple[str, ...],
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Cast a vote on a governance proposal.

    \b
    PROPOSAL_ID is the numeric proposal ID (integer).
    Each --proof is a hex-encoded 32-byte Merkle proof hash; repeat for multiple proof nodes.
    Examples:
      tusdt governance vote 0 --hotkey 5GrwvaEF... --support --balance 1000 --multiplier-bps 10000 --proof 0x5637... --wallet-name MyWallet
      tusdt governance vote 0 --hotkey 5GrwvaEF... --oppose --balance 500 --multiplier-bps 10000 --proof 0x5637... --proof 0x8087... --wallet-name MyWallet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_balance = parse_balance(balance, decimals)

    # Convert each hex proof hash to a list of 32 bytes (MerkleHash = [u8; 32])
    proof_list = []
    for proof_hex in proofs:
        ph = proof_hex.strip()
        if ph.startswith("0x"):
            ph = ph[2:]
        proof_bytes = bytes.fromhex(ph)
        if len(proof_bytes) != 32:
            state.output.error(
                f"Each --proof must be exactly 32 bytes (64 hex chars), got {len(proof_bytes)} bytes"
            )
            return
        proof_list.append(list(proof_bytes))

    vote_dir = "Support" if support else "Oppose"
    state.output.info(f"Casting {vote_dir} vote on proposal {proposal_id} with balance {balance}...")
    state.submit(
        lambda c, kp: c.vote(kp, proposal_id, hotkey, support, raw_balance, multiplier_bps, proof_list)
    )
    state.output.success("Vote cast!")


# ------------------------------------------------------------------
# finalize-proposal
# ------------------------------------------------------------------


@governance_group.command("finalize-proposal")
@click.argument("proposal_id", type=int, metavar="<proposal-id>")
@wallet_option
@network_option
@click.pass_context
def finalize_proposal_cmd(
    ctx: click.Context,
    proposal_id: int,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Finalize a governance proposal after the voting period ends.

    \b
    PROPOSAL_ID is the numeric proposal ID (integer).
    Examples:
      tusdt governance finalize-proposal 0 --wallet-name MyWallet
      tusdt governance finalize-proposal 5 --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Finalizing proposal {proposal_id}...")
    state.submit(lambda c, kp: c.finalize_proposal(kp, proposal_id))
    state.output.success("Proposal finalized!")


# ------------------------------------------------------------------
# execute-proposal
# ------------------------------------------------------------------


@governance_group.command("execute-proposal")
@click.argument("proposal_id", type=int, metavar="<proposal-id>")
@wallet_option
@network_option
@click.pass_context
def execute_proposal_cmd(
    ctx: click.Context,
    proposal_id: int,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Execute a finalized governance proposal after the execution delay.

    \b
    PROPOSAL_ID is the numeric proposal ID (integer).
    Examples:
      tusdt governance execute-proposal 0 --wallet-name MyWallet
      tusdt governance execute-proposal 5 --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Executing proposal {proposal_id}...")
    state.submit(lambda c, kp: c.execute_proposal(kp, proposal_id))
    state.output.success("Proposal executed!")


# ------------------------------------------------------------------
# submit-snapshot
# ------------------------------------------------------------------


@governance_group.command("submit-snapshot")
@click.option(
    "--root", required=True, metavar="<hex-string>", help="Merkle root as hex-encoded 32 bytes (e.g. 0x...)"
)
@click.option("--circulating-supply", type=int, required=True, help="Circulating supply as raw u128 integer")
@click.option("--snapshot-block", type=int, required=True, help="Snapshot block number as u32 integer")
@wallet_option
@network_option
@click.pass_context
def submit_snapshot_cmd(
    ctx: click.Context,
    root: str,
    circulating_supply: int,
    snapshot_block: int,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Submit a Merkle snapshot for circulating supply verification (council only).

    \b
    Examples:
      tusdt governance submit-snapshot --root 0xabcdef... --circulating-supply 1000000000000 --snapshot-block 5000000 --wallet-name MyWallet
      tusdt governance submit-snapshot --root 0xabcdef... --circulating-supply 1000000000000 --snapshot-block 5000000 --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    # Convert hex root to list of ints (32 bytes)
    root_hex = root.strip()
    if root_hex.startswith("0x"):
        root_hex = root_hex[2:]
    root_bytes = bytes.fromhex(root_hex.zfill(64))
    root_list = list(root_bytes)

    state.output.info(f"Submitting snapshot for block {snapshot_block} (supply={circulating_supply})...")
    state.submit(lambda c, kp: c.submit_snapshot(kp, root_list, circulating_supply, snapshot_block))
    state.output.success("Snapshot submitted!")


# ------------------------------------------------------------------
# vault-claim-excess-alpha
# ------------------------------------------------------------------


@governance_group.command("vault-claim-excess-alpha")
@click.argument("netuid", type=int, metavar="<netuid>")
@wallet_option
@network_option
@click.pass_context
def gov_vault_claim_excess_alpha(
    ctx: click.Context, netuid: int, wallet_name: str | None, network: str | None
) -> None:
    """Claim excess alpha staking rewards on a subnet via governance (maintainer only)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Claiming excess alpha via governance for netuid {netuid}...")
    state.submit(lambda c, kp: c.gov_vault_claim_excess_alpha(kp, netuid))
    state.output.success(f"Excess alpha claimed via governance for netuid {netuid}!")


# ------------------------------------------------------------------
# vault-set-approved-netuid
# ------------------------------------------------------------------


@governance_group.command("vault-set-approved-netuid")
@click.argument("netuid", type=int, metavar="<netuid>")
@click.option("--approve/--revoke", default=True, help="Approve (default) or revoke the subnet")
@wallet_option
@network_option
@click.pass_context
def gov_vault_set_approved_netuid(
    ctx: click.Context,
    netuid: int,
    approve: bool,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Approve or revoke a subnet for vault collateral via governance (maintainer only)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    action = "Approving" if approve else "Revoking"
    state.output.info(f"{action} subnet {netuid} via governance...")
    state.submit(lambda c, kp: c.gov_vault_set_approved_netuid(kp, netuid, approve))
    state.output.success(f"Subnet {netuid} {'approved' if approve else 'revoked'} via governance!")


# ------------------------------------------------------------------
# vault-set-global-params
# ------------------------------------------------------------------


@governance_group.command("vault-set-global-params")
@click.option("--transaction-fee", type=int, default=None, help="Transaction fee in basis points")
@click.option("--auction-duration-ms", type=int, default=None, help="Auction duration in milliseconds")
@click.option("--max-oracle-age-ms", type=int, default=None, help="Max oracle price age in milliseconds")
@wallet_option
@network_option
@click.pass_context
def gov_vault_set_global_params(
    ctx: click.Context,
    transaction_fee: int | None,
    auction_duration_ms: int | None,
    max_oracle_age_ms: int | None,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Schedule a vault global params update via governance (maintainer only)."""
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

    state.output.info(f"Scheduling global params update via governance: {config}")
    state.submit(lambda c, kp: c.gov_vault_set_global_params(kp, config))
    state.output.success("Global params update scheduled via governance!")


# ------------------------------------------------------------------
# vault-cancel-global-update
# ------------------------------------------------------------------


@governance_group.command("vault-cancel-global-update")
@wallet_option
@network_option
@click.pass_context
def gov_vault_cancel_global_update(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Cancel the pending vault global params update via governance (maintainer only)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info("Cancelling pending global params update via governance...")
    state.submit(lambda c, kp: c.gov_vault_cancel_global_params_update(kp))
    state.output.success("Global params update cancelled via governance!")


# ------------------------------------------------------------------
# elect-maintainer
# ------------------------------------------------------------------


@governance_group.command("elect-maintainer")
@click.argument("address", type=str, metavar="<new-maintainer-address>")
@wallet_option
@network_option
@click.pass_context
def gov_elect_maintainer(
    ctx: click.Context, address: str, wallet_name: str | None, network: str | None
) -> None:
    """Set the maintainer directly on the governance contract (election-only).

    This uses a raw selector (0xE1EC7000) that the election contract
    cross-calls to install the winning candidate.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Setting maintainer to {address}...")
    state.submit(lambda c, kp: c.elect_maintainer(kp, address))
    state.output.success(f"Maintainer set to {address}!")


# ------------------------------------------------------------------
# election-set-netuid
# ------------------------------------------------------------------


@governance_group.command("election-set-netuid")
@click.argument("netuid", type=int, metavar="<netuid>")
@wallet_option
@network_option
@click.pass_context
def gov_election_set_netuid(
    ctx: click.Context, netuid: int, wallet_name: str | None, network: str | None
) -> None:
    """Set the election contract netuid via governance (election-only).

    Uses raw selector 0xE1EC7001.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Setting election netuid to {netuid}...")
    state.submit(lambda c, kp: c.election_set_netuid(kp, netuid))
    state.output.success(f"Election netuid set to {netuid}!")


# ------------------------------------------------------------------
# vault-set-token-controller
# ------------------------------------------------------------------


@governance_group.command("vault-set-token-controller")
@click.argument("address", type=str, metavar="<new-controller-address>")
@wallet_option
@network_option
@click.pass_context
def gov_vault_set_token_controller(
    ctx: click.Context, address: str, wallet_name: str | None, network: str | None
) -> None:
    """Transfer the ERC20 token controller via governance (maintainer only).

    Calls through to the vault's set_token_controller, which cross-calls
    the ERC20 contract to update the controller and minter set.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Transferring token controller to {address}...")
    state.submit(lambda c, kp: c.gov_vault_set_token_controller(kp, address))
    state.output.success(f"Token controller transferred to {address}!")


# ------------------------------------------------------------------
# vault-update-auction-address
# ------------------------------------------------------------------


@governance_group.command("vault-update-auction-address")
@click.argument("address", type=str, metavar="<new-auction-address>")
@wallet_option
@network_option
@click.pass_context
def gov_vault_update_auction_address(
    ctx: click.Context, address: str, wallet_name: str | None, network: str | None
) -> None:
    """Update the vault's stored auction contract address via governance (maintainer only)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Updating vault auction address to {address}...")
    state.submit(lambda c, kp: c.gov_vault_update_auction_address(kp, address))
    state.output.success(f"Vault auction address updated to {address}!")


# ------------------------------------------------------------------
# vault-update-oracle-address
# ------------------------------------------------------------------


@governance_group.command("vault-update-oracle-address")
@click.argument("address", type=str, metavar="<new-oracle-address>")
@wallet_option
@network_option
@click.pass_context
def gov_vault_update_oracle_address(
    ctx: click.Context, address: str, wallet_name: str | None, network: str | None
) -> None:
    """Update the vault's stored oracle contract address via governance (maintainer only)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Updating vault oracle address to {address}...")
    state.submit(lambda c, kp: c.gov_vault_update_oracle_address(kp, address))
    state.output.success(f"Vault oracle address updated to {address}!")


# ------------------------------------------------------------------
# update-vault-address
# ------------------------------------------------------------------


@governance_group.command("update-vault-address")
@click.argument("address", type=str, metavar="<new-vault-address>")
@wallet_option
@network_option
@click.pass_context
def gov_update_vault_address(
    ctx: click.Context, address: str, wallet_name: str | None, network: str | None
) -> None:
    """Update the stored vault contract address in governance (maintainer only).

    Used after a vault upgrade to point governance at the new vault instance.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Updating governance vault address to {address}...")
    state.submit(lambda c, kp: c.gov_update_vault_address(kp, address))
    state.output.success(f"Governance vault address updated to {address}!")


# ------------------------------------------------------------------
# update-auction-address
# ------------------------------------------------------------------


@governance_group.command("update-auction-address")
@click.argument("address", type=str, metavar="<new-auction-address>")
@wallet_option
@network_option
@click.pass_context
def gov_update_auction_address(
    ctx: click.Context, address: str, wallet_name: str | None, network: str | None
) -> None:
    """Update the stored auction contract address in governance (maintainer only)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Updating governance auction address to {address}...")
    state.submit(lambda c, kp: c.gov_update_auction_address(kp, address))
    state.output.success(f"Governance auction address updated to {address}!")


# ------------------------------------------------------------------
# update-oracle-address
# ------------------------------------------------------------------


@governance_group.command("update-oracle-address")
@click.argument("address", type=str, metavar="<new-oracle-address>")
@wallet_option
@network_option
@click.pass_context
def gov_update_oracle_address(
    ctx: click.Context, address: str, wallet_name: str | None, network: str | None
) -> None:
    """Update the stored oracle contract address in governance (maintainer only)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Updating governance oracle address to {address}...")
    state.submit(lambda c, kp: c.gov_update_oracle_address(kp, address))
    state.output.success(f"Governance oracle address updated to {address}!")


# ------------------------------------------------------------------
# update-treasury-address
# ------------------------------------------------------------------


@governance_group.command("update-treasury-address")
@click.argument("address", type=str, metavar="<new-treasury-address>")
@wallet_option
@network_option
@click.pass_context
def gov_update_treasury_address(
    ctx: click.Context, address: str, wallet_name: str | None, network: str | None
) -> None:
    """Update the stored treasury contract address in governance (maintainer only)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Updating governance treasury address to {address}...")
    state.submit(lambda c, kp: c.gov_update_treasury_address(kp, address))
    state.output.success(f"Governance treasury address updated to {address}!")


# ------------------------------------------------------------------
# vault-address (read)
# ------------------------------------------------------------------


@governance_group.command("vault-address")
@wallet_option
@network_option
@click.pass_context
def gov_vault_address(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Show the vault contract address from the governance contract."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    kp = state.get_reader_keypair()
    state.make_config()
    result = state.run_read(lambda c: c.get_vault_address(kp))
    state.output.detail("Vault Address", {"Address": result})


# ------------------------------------------------------------------
# auction-address (read)
# ------------------------------------------------------------------


@governance_group.command("auction-address")
@wallet_option
@network_option
@click.pass_context
def gov_auction_address(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Show the auction contract address from the governance contract."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    kp = state.get_reader_keypair()
    state.make_config()
    result = state.run_read(lambda c: c.get_governance_auction_address(kp))
    state.output.detail("Auction Address", {"Address": result})


# ------------------------------------------------------------------
# oracle-address (read)
# ------------------------------------------------------------------


@governance_group.command("oracle-address")
@wallet_option
@network_option
@click.pass_context
def gov_oracle_address(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Show the oracle contract address from the governance contract."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    kp = state.get_reader_keypair()
    state.make_config()
    result = state.run_read(lambda c: c.get_governance_oracle_address(kp))
    state.output.detail("Oracle Address", {"Address": result})
