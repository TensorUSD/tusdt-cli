"""Governance CLI commands."""

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
)
from tusdt_cli.wallet import get_reader_keypair, get_signer_keypair

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

_GOVERNANCE_ADVANCED = {
    "set-maintainer",
    "set-council",
    "vault-set-params",
    "vault-cancel-update",
    "vault-update-treasury",
    "vault-update-platform",
    "vault-unpause",
    "vault-pause",
    "oracle-set-validator",
    "oracle-set-deviation",
    "oracle-commit-round",
    "auction-set-admin",
    "update-params",
    "submit-proposal",
    "vote",
    "finalize-proposal",
    "execute-proposal",
    "submit-snapshot",
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
@_network_option
@click.pass_context
def maintainer(ctx: click.Context, network: str | None) -> None:
    """Show the current maintainer account address.

    \b
    Examples:
      tusdt governance maintainer
      tusdt governance maintainer --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.get_maintainer(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Maintainer", {"Address": addr})


# ------------------------------------------------------------------
# council
# ------------------------------------------------------------------


@governance_group.command("council")
@_network_option
@click.pass_context
def council(ctx: click.Context, network: str | None) -> None:
    """List all council members.

    \b
    Examples:
      tusdt governance council
      tusdt governance council --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        members = client.get_council(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    if not members:
        print_info("No council members")
        return

    rows = [[str(i), addr] for i, addr in enumerate(members)]
    print_table("Council Members", ["#", "Address"], rows)


# ------------------------------------------------------------------
# is-council
# ------------------------------------------------------------------


@governance_group.command("is-council")
@click.argument("account", type=str, metavar="<ss58-address>")
@_network_option
@click.pass_context
def is_council_cmd(ctx: click.Context, account: str, network: str | None) -> None:
    """Check whether an account is a council member.

    \b
    ACCOUNT is the SS58 address to check.
    Examples:
      tusdt governance is-council 5GrwvaEF...
      tusdt governance is-council 5GrwvaEF... --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        result = client.is_council(keypair, account)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Council Status", {"Account": account, "Is council member": result})


# ------------------------------------------------------------------
# treasury
# ------------------------------------------------------------------


@governance_group.command("treasury")
@_network_option
@click.pass_context
def governance_treasury(ctx: click.Context, network: str | None) -> None:
    """Show the treasury address registered in the governance contract.

    \b
    Examples:
      tusdt governance treasury
      tusdt governance treasury --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.get_governance_treasury(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Treasury", {"Address": addr})


# ------------------------------------------------------------------
# params
# ------------------------------------------------------------------


@governance_group.command("params")
@_network_option
@click.pass_context
def governance_params(ctx: click.Context, network: str | None) -> None:
    """Show governance contract parameters.

    \b
    Examples:
      tusdt governance params
      tusdt governance params --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        params = client.get_governance_params(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    if isinstance(params, dict):
        print_dict("Governance Parameters", params)
    else:
        print_dict("Governance Parameters", {"Raw": params})


# ------------------------------------------------------------------
# current-epoch
# ------------------------------------------------------------------


@governance_group.command("current-epoch")
@_network_option
@click.pass_context
def current_epoch(ctx: click.Context, network: str | None) -> None:
    """Show the current epoch number.

    \b
    Examples:
      tusdt governance current-epoch
      tusdt governance current-epoch --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        epoch = client.get_current_epoch(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Current Epoch", {"Epoch": epoch})


# ------------------------------------------------------------------
# get-snapshot
# ------------------------------------------------------------------


@governance_group.command("get-snapshot")
@click.argument("epoch", type=int, metavar="<epoch>")
@_network_option
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
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        snapshot = client.get_snapshot(keypair, epoch)
    except Exception as exc:
        print_error(str(exc))
        return

    if snapshot is None:
        print_info(f"No snapshot for epoch {epoch}")
    else:
        print_dict(f"Snapshot – Epoch {epoch}", snapshot)


# ------------------------------------------------------------------
# quorum
# ------------------------------------------------------------------


@governance_group.command("quorum")
@click.argument("epoch", type=int, metavar="<epoch>")
@_network_option
@click.pass_context
def quorum(ctx: click.Context, epoch: int, network: str | None) -> None:
    """Show quorum voting data for a given epoch.

    \b
    EPOCH is the epoch number to query (integer).
    Returns (yes_balance, no_balance) tuple.
    Examples:
      tusdt governance quorum 42
      tusdt governance quorum 42 --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        result = client.get_quorum(keypair, epoch)
    except Exception as exc:
        print_error(str(exc))
        return

    if isinstance(result, (list, tuple)) and len(result) >= 2:
        print_dict(
            f"Quorum – Epoch {epoch}",
            {
                "Yes (raw)": result[0],
                "No (raw)": result[1],
                "Yes": format_balance(result[0], decimals),
                "No": format_balance(result[1], decimals),
            },
        )
    else:
        print_dict(f"Quorum – Epoch {epoch}", {"Raw": result})


# ------------------------------------------------------------------
# proposal-count
# ------------------------------------------------------------------


@governance_group.command("proposal-count")
@_network_option
@click.pass_context
def proposal_count(ctx: click.Context, network: str | None) -> None:
    """Show the total number of proposals.

    \b
    Examples:
      tusdt governance proposal-count
      tusdt governance proposal-count --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        count = client.get_proposal_count(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Proposals", {"Count": count})


# ------------------------------------------------------------------
# get-proposal
# ------------------------------------------------------------------


@governance_group.command("get-proposal")
@click.argument("proposal_id", type=int, metavar="<proposal-id>")
@_network_option
@click.pass_context
def get_proposal(ctx: click.Context, proposal_id: int, network: str | None) -> None:
    """Show details for a specific proposal.

    \b
    PROPOSAL_ID is the numeric proposal ID (integer).
    Examples:
      tusdt governance get-proposal 0
      tusdt governance get-proposal 5 --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        proposal = client.get_proposal(keypair, proposal_id)
    except Exception as exc:
        print_error(str(exc))
        return

    if proposal is None:
        print_error(f"Proposal {proposal_id} not found")
        return

    print_dict(f"Proposal #{proposal_id}", proposal)


# ------------------------------------------------------------------
# has-voted
# ------------------------------------------------------------------


@governance_group.command("has-voted")
@click.argument("proposal_id", type=int, metavar="<proposal-id>")
@click.option("--coldkey", required=True, help="Coldkey SS58 address (e.g. 5GrwvaEF...)")
@click.option("--hotkey", required=True, help="Hotkey SS58 address (e.g. 5GrwvaEF...)")
@_network_option
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
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        result = client.has_voted(keypair, proposal_id, coldkey, hotkey)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict(
        "Vote Status",
        {
            "Proposal ID": proposal_id,
            "Coldkey": coldkey,
            "Hotkey": hotkey,
            "Has voted": result,
        },
    )


# ======================================================================
# Advanced (write) commands
# ======================================================================

# ------------------------------------------------------------------
# set-maintainer
# ------------------------------------------------------------------


@governance_group.command("set-maintainer")
@click.argument("address", type=str, metavar="<ss58-address>")
@_wallet_option
@_network_option
@click.pass_context
def set_maintainer_cmd(
    ctx: click.Context,
    address: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Set a new maintainer (maintainer only).

    \b
    ADDRESS is the SS58 address of the new maintainer.
    Examples:
      tusdt governance set-maintainer 5GrwvaEF... --wallet-name MyWallet
      tusdt governance set-maintainer 5GrwvaEF... --wallet-name MyWallet --network testnet
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
    print_info(f"Setting maintainer to {address}...")

    try:
        client = TUSDTClient(config)
        result = client.set_maintainer(keypair, address)
        print_success("Maintainer updated!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


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
@_wallet_option
@_network_option
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
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    members_list = list(members)
    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Setting council to {len(members_list)} member(s)...")

    try:
        client = TUSDTClient(config)
        result = client.set_council(keypair, members_list)
        print_success("Council updated!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# vault-set-params
# ------------------------------------------------------------------


@governance_group.command("vault-set-params")
@click.option(
    "--collateral-ratio", type=int, default=None, help="Collateral ratio in percent (e.g. 150 for 150%)"
)
@click.option(
    "--liquidation-ratio", type=int, default=None, help="Liquidation ratio in percent (e.g. 120 for 120%)"
)
@click.option("--interest-rate", type=int, default=None, help="Interest rate in percent (e.g. 5 for 5%)")
@click.option(
    "--liquidation-fee", type=int, default=None, help="Liquidation fee in percent (e.g. 10 for 10%)"
)
@click.option(
    "--borrow-cap", type=str, default=None, help="Borrow cap in human-readable units (e.g. 1000000.0)"
)
@click.option(
    "--auction-duration-ms", type=int, default=None, help="Auction duration in milliseconds (integer)"
)
@click.option(
    "--max-oracle-age-ms", type=int, default=None, help="Max oracle price age in milliseconds (integer)"
)
@click.option(
    "--transaction-fee", type=int, default=None, help="Transaction fee in basis points (e.g. 3 for 0.03%)"
)
@_wallet_option
@_network_option
@click.pass_context
def gov_vault_set_params_cmd(
    ctx: click.Context,
    collateral_ratio: int | None,
    liquidation_ratio: int | None,
    interest_rate: int | None,
    liquidation_fee: int | None,
    borrow_cap: str | None,
    auction_duration_ms: int | None,
    max_oracle_age_ms: int | None,
    transaction_fee: int | None,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Schedule a vault contract parameter update via governance.

    \b
    All parameters are optional; only supplied values will be updated.
    Examples:
      tusdt governance vault-set-params --collateral-ratio 150 --wallet-name MyWallet
      tusdt governance vault-set-params --interest-rate 5 --borrow-cap 1000000 --wallet-name MyWallet
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

    if not params:
        print_error("Provide at least one parameter to update")
        return

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Scheduling vault parameter update via governance: {params}")

    try:
        client = TUSDTClient(config)
        result = client.gov_vault_set_contract_params(keypair, params)
        print_success("Vault parameter update scheduled via governance!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# vault-cancel-update
# ------------------------------------------------------------------


@governance_group.command("vault-cancel-update")
@_wallet_option
@_network_option
@click.pass_context
def gov_vault_cancel_update_cmd(
    ctx: click.Context,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Cancel a pending vault contract parameter update via governance.

    \b
    Examples:
      tusdt governance vault-cancel-update --wallet-name MyWallet
      tusdt governance vault-cancel-update --wallet-name MyWallet --network testnet
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
    print_info("Cancelling pending vault parameter update via governance...")

    try:
        client = TUSDTClient(config)
        result = client.gov_vault_cancel_update(keypair)
        print_success("Vault parameter update cancelled via governance!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# vault-update-treasury
# ------------------------------------------------------------------


@governance_group.command("vault-update-treasury")
@click.argument("address", type=str, metavar="<ss58-address>")
@_wallet_option
@_network_option
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
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Updating vault treasury to {address} via governance...")

    try:
        client = TUSDTClient(config)
        result = client.gov_vault_update_treasury(keypair, address)
        print_success("Vault treasury updated via governance!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# vault-update-platform
# ------------------------------------------------------------------


@governance_group.command("vault-update-platform")
@click.argument("address", type=str, metavar="<ss58-address>")
@_wallet_option
@_network_option
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
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Updating vault platform to {address} via governance...")

    try:
        client = TUSDTClient(config)
        result = client.gov_vault_update_platform(keypair, address)
        print_success("Vault platform updated via governance!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# vault-unpause
# ------------------------------------------------------------------


@governance_group.command("vault-unpause")
@_wallet_option
@_network_option
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
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info("Unpausing vault contract via governance...")

    try:
        client = TUSDTClient(config)
        result = client.gov_vault_unpause(keypair)
        print_success("Vault unpaused via governance!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# vault-pause
# ------------------------------------------------------------------


@governance_group.command("vault-pause")
@_wallet_option
@_network_option
@click.pass_context
def gov_vault_pause_cmd(
    ctx: click.Context,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Pause the vault contract via governance.

    \b
    Examples:
      tusdt governance vault-pause --wallet-name MyWallet
      tusdt governance vault-pause --wallet-name MyWallet --network testnet
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
    print_info("Pausing vault contract via governance...")

    try:
        client = TUSDTClient(config)
        result = client.gov_vault_pause(keypair)
        print_success("Vault paused via governance!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# oracle-set-validator
# ------------------------------------------------------------------


@governance_group.command("oracle-set-validator")
@click.argument("address", type=str, metavar="<ss58-address>", required=False)
@click.option("--clear", is_flag=True, default=False, help="Clear the validator (set to None)")
@_wallet_option
@_network_option
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
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    validator = None if clear else address
    if not clear and not address:
        print_error("Provide an SS58 address or use --clear to remove the validator")
        return

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    action = "Clearing" if clear else f"Setting to {address}"
    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"{action} oracle validator via governance...")

    try:
        client = TUSDTClient(config)
        result = client.gov_oracle_set_validator(keypair, validator)
        print_success("Oracle validator updated via governance!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# oracle-set-deviation
# ------------------------------------------------------------------


@governance_group.command("oracle-set-deviation")
@click.argument("deviation", type=int, metavar="<deviation>")
@_wallet_option
@_network_option
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
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Setting oracle max price deviation to {deviation} via governance...")

    try:
        client = TUSDTClient(config)
        result = client.gov_oracle_set_max_price_deviation(keypair, deviation)
        print_success("Oracle max price deviation updated via governance!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# oracle-commit-round
# ------------------------------------------------------------------


@governance_group.command("oracle-commit-round")
@click.argument("price", type=int, metavar="<price>")
@_wallet_option
@_network_option
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
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Committing oracle round with price {price} via governance...")

    try:
        client = TUSDTClient(config)
        result = client.gov_oracle_commit_round(keypair, price)
        print_success("Oracle round committed via governance!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# auction-set-admin
# ------------------------------------------------------------------


@governance_group.command("auction-set-admin")
@click.argument("address", type=str, metavar="<ss58-address>", required=False)
@click.option("--clear", is_flag=True, default=False, help="Clear the admin (set to None)")
@_wallet_option
@_network_option
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
    print_info(f"{action} auction admin via governance...")

    try:
        client = TUSDTClient(config)
        result = client.gov_auction_set_admin(keypair, admin)
        print_success("Auction admin updated via governance!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# update-params
# ------------------------------------------------------------------


@governance_group.command("update-params")
@click.option("--netuid", type=int, default=None, help="Subnet UID (integer)")
@click.option("--voting-period-ms", type=int, default=None, help="Voting period in milliseconds (integer)")
@click.option(
    "--execution-delay-ms", type=int, default=None, help="Execution delay in milliseconds (integer)"
)
@click.option(
    "--minimum-quorum", type=str, default=None, help="Minimum quorum in human-readable units (e.g. 100000.0)"
)
@_wallet_option
@_network_option
@click.pass_context
def update_params_cmd(
    ctx: click.Context,
    netuid: int | None,
    voting_period_ms: int | None,
    execution_delay_ms: int | None,
    minimum_quorum: str | None,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Update governance contract parameters (maintainer only).

    \b
    All parameters are optional; only supplied values will be updated.
    Examples:
      tusdt governance update-params --minimum-quorum 50000 --wallet-name MyWallet
      tusdt governance update-params --voting-period-ms 86400000 --wallet-name MyWallet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 9)

    new_params: dict = {}
    if netuid is not None:
        new_params["netuid"] = netuid
    if voting_period_ms is not None:
        new_params["voting_period_ms"] = voting_period_ms
    if execution_delay_ms is not None:
        new_params["execution_delay_ms"] = execution_delay_ms
    if minimum_quorum is not None:
        new_params["minimum_quorum"] = parse_balance(minimum_quorum, decimals)

    if not new_params:
        print_error("Provide at least one parameter to update")
        return

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Updating governance parameters: {new_params}")

    try:
        client = TUSDTClient(config)
        result = client.update_governance_params(keypair, new_params)
        print_success("Governance parameters updated!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


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
@click.option("--hotkey", required=True, help="Hotkey SS58 address of the proposer (e.g. 5GrwvaEF...)")
@_wallet_option
@_network_option
@click.pass_context
def submit_proposal_cmd(
    ctx: click.Context,
    cid: str,
    kind: str,
    fund: str | None,
    token_kind_opt: str | None,
    funding_amount: str | None,
    funding_recipient: str | None,
    hotkey: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Submit a new governance proposal.

    \b
    For non-funding proposals, only --cid, --kind non-funding, and --hotkey are required.
    For funding proposals, also provide --fund, --token-kind, --funding-amount, and --funding-recipient.
    Examples:
      tusdt governance submit-proposal --cid "QmXyz..." --kind non-funding --hotkey 5GrwvaEF... --wallet-name MyWallet
      tusdt governance submit-proposal --cid "QmXyz..." --kind funding --fund emergency --token-kind tusdt --funding-amount 5000 --funding-recipient 5GrwvaEF... --hotkey 5GrwvaEF... --wallet-name MyWallet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 9)

    # Build ProposalKind
    if kind.lower() == "funding":
        if not all([fund, token_kind_opt, funding_amount, funding_recipient]):
            print_error(
                "Funding proposals require: --fund, --token-kind, --funding-amount, --funding-recipient"
            )
            return
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

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Submitting proposal (cid={cid}, kind={kind})...")

    try:
        client = TUSDTClient(config)
        result = client.submit_proposal(keypair, cid, kind_dict, hotkey)
        print_success("Proposal submitted!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


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
@_wallet_option
@_network_option
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
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 9)
    raw_balance = parse_balance(balance, decimals)

    # Convert each hex proof hash to a list of 32 bytes (MerkleHash = [u8; 32])
    proof_list = []
    for proof_hex in proofs:
        ph = proof_hex.strip()
        if ph.startswith("0x"):
            ph = ph[2:]
        proof_bytes = bytes.fromhex(ph)
        if len(proof_bytes) != 32:
            print_error(
                f"Each --proof must be exactly 32 bytes (64 hex chars), got {len(proof_bytes)} bytes"
            )
            return
        proof_list.append(list(proof_bytes))

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    vote_dir = "Support" if support else "Oppose"
    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Casting {vote_dir} vote on proposal {proposal_id} with balance {balance}...")

    try:
        client = TUSDTClient(config)
        result = client.vote(keypair, proposal_id, hotkey, support, raw_balance, multiplier_bps, proof_list)
        print_success("Vote cast!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# finalize-proposal
# ------------------------------------------------------------------


@governance_group.command("finalize-proposal")
@click.argument("proposal_id", type=int, metavar="<proposal-id>")
@_wallet_option
@_network_option
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
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Finalizing proposal {proposal_id}...")

    try:
        client = TUSDTClient(config)
        result = client.finalize_proposal(keypair, proposal_id)
        print_success("Proposal finalized!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# execute-proposal
# ------------------------------------------------------------------


@governance_group.command("execute-proposal")
@click.argument("proposal_id", type=int, metavar="<proposal-id>")
@_wallet_option
@_network_option
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
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Executing proposal {proposal_id}...")

    try:
        client = TUSDTClient(config)
        result = client.execute_proposal(keypair, proposal_id)
        print_success("Proposal executed!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# submit-snapshot
# ------------------------------------------------------------------


@governance_group.command("submit-snapshot")
@click.option(
    "--root", required=True, metavar="<hex-string>", help="Merkle root as hex-encoded 32 bytes (e.g. 0x...)"
)
@click.option("--circulating-supply", type=int, required=True, help="Circulating supply as raw u128 integer")
@click.option("--snapshot-block", type=int, required=True, help="Snapshot block number as u32 integer")
@_wallet_option
@_network_option
@click.pass_context
def submit_snapshot_cmd(
    ctx: click.Context,
    root: str,
    circulating_supply: int,
    snapshot_block: int,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Submit a Merkle snapshot for circulating supply verification.

    \b
    Examples:
      tusdt governance submit-snapshot --root 0xabcdef... --circulating-supply 1000000000000 --snapshot-block 5000000 --wallet-name MyWallet
      tusdt governance submit-snapshot --root 0xabcdef... --circulating-supply 1000000000000 --snapshot-block 5000000 --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    # Convert hex root to list of ints (32 bytes)
    root_hex = root.strip()
    if root_hex.startswith("0x"):
        root_hex = root_hex[2:]
    root_bytes = bytes.fromhex(root_hex.zfill(64))
    root_list = list(root_bytes)

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Submitting snapshot for block {snapshot_block} (supply={circulating_supply})...")

    try:
        client = TUSDTClient(config)
        result = client.submit_snapshot(keypair, root_list, circulating_supply, snapshot_block)
        print_success("Snapshot submitted!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))
