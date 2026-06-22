"""Election CLI commands."""

from typing import Any

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

_ELECTION_ADVANCED = {
    "cast-approval",
    "trigger-emergency-election",
    "cancel-cycle",
}


def _format_phase(raw: Any) -> str:
    """Extract a human-readable Phase name from the contract result."""
    if isinstance(raw, dict):
        keys = list(raw.keys())
        if keys:
            return keys[0]
    if isinstance(raw, str):
        return raw
    return str(raw)


@click.group("election", cls=ModeAwareGroup, advanced_commands=_ELECTION_ADVANCED)
def election_group() -> None:
    """Election operations for the TUSDT system."""


# ======================================================================
# Basic (read) commands
# ======================================================================

# ------------------------------------------------------------------
# governance-address
# ------------------------------------------------------------------


@election_group.command("governance-address")
@_network_option
@click.pass_context
def election_governance(ctx: click.Context, network: str | None) -> None:
    """Show the governance address stored in the election contract.

    \b
    Examples:
      tusdt election governance-address
      tusdt election governance-address --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.get_election_governance(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Governance", {"Address": addr})


# ------------------------------------------------------------------
# min-candidate-stake
# ------------------------------------------------------------------


@election_group.command("min-candidate-stake")
@_network_option
@click.pass_context
def min_candidate_stake(ctx: click.Context, network: str | None) -> None:
    """Show the minimum candidate stake (alpha).

    \b
    Examples:
      tusdt election min-candidate-stake
      tusdt election min-candidate-stake --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        stake = client.get_min_candidate_stake(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    decimals = config.get("decimals", 9)
    print_dict("Minimum Candidate Stake", {"Alpha": format_balance(stake, decimals)})


# ------------------------------------------------------------------
# incumbent
# ------------------------------------------------------------------


@election_group.command("incumbent")
@_network_option
@click.pass_context
def incumbent(ctx: click.Context, network: str | None) -> None:
    """Show the current incumbent maintainer.

    \b
    Examples:
      tusdt election incumbent
      tusdt election incumbent --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.get_incumbent(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Incumbent", {"Address": addr})


# ------------------------------------------------------------------
# active-netuid
# ------------------------------------------------------------------


@election_group.command("active-netuid")
@_network_option
@click.pass_context
def active_netuid(ctx: click.Context, network: str | None) -> None:
    """Show the active governing subnet netuid.

    \b
    Examples:
      tusdt election active-netuid
      tusdt election active-netuid --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        netuid = client.get_active_netuid(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Active Netuid", {"Netuid": netuid})


# ------------------------------------------------------------------
# phase
# ------------------------------------------------------------------


@election_group.command("phase")
@_network_option
@click.pass_context
def phase(ctx: click.Context, network: str | None) -> None:
    """Show the current election phase.

    \b
    Examples:
      tusdt election phase
      tusdt election phase --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        raw = client.get_phase(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Phase", {"Phase": _format_phase(raw)})


# ------------------------------------------------------------------
# cycle-id
# ------------------------------------------------------------------


@election_group.command("cycle-id")
@_network_option
@click.pass_context
def cycle_id(ctx: click.Context, network: str | None) -> None:
    """Show the current election cycle ID.

    \b
    Examples:
      tusdt election cycle-id
      tusdt election cycle-id --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        cid = client.get_cycle_id(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Cycle ID", {"Cycle": cid})


# ------------------------------------------------------------------
# next-election-ts
# ------------------------------------------------------------------


@election_group.command("next-election-ts")
@_network_option
@click.pass_context
def next_election_ts(ctx: click.Context, network: str | None) -> None:
    """Show the earliest timestamp when the next election may be scheduled.

    \b
    Examples:
      tusdt election next-election-ts
      tusdt election next-election-ts --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        ts = client.get_next_election_ts(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Next Election", {"Timestamp": ts})


# ------------------------------------------------------------------
# terms-served
# ------------------------------------------------------------------


@election_group.command("terms-served")
@click.argument("who", type=str, metavar="<ss58-address>")
@_network_option
@click.pass_context
def terms_served(ctx: click.Context, who: str, network: str | None) -> None:
    """Show how many terms an account has served.

    \b
    WHO is the SS58 address of the account to query.
    Examples:
      tusdt election terms-served 5GrwvaEF...
      tusdt election terms-served 5GrwvaEF... --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        terms = client.get_terms_served(keypair, who)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Terms Served", {"Account": who, "Terms": terms})


# ------------------------------------------------------------------
# get-candidate
# ------------------------------------------------------------------


@election_group.command("get-candidate")
@click.argument("candidate", type=str, metavar="<ss58-address>")
@_network_option
@click.pass_context
def get_candidate(ctx: click.Context, candidate: str, network: str | None) -> None:
    """Show registration info for a candidate.

    \b
    CANDIDATE is the SS58 address of the candidate to query.
    Examples:
      tusdt election get-candidate 5GrwvaEF...
      tusdt election get-candidate 5GrwvaEF... --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        info = client.get_candidate(keypair, candidate)
    except Exception as exc:
        print_error(str(exc))
        return

    if info is None:
        print_info(f"Candidate {candidate} not found in current cycle")
        return

    print_dict(
        f"Candidate {candidate}",
        {
            "Netuid": info.get("netuid", "?"),
            "Registered At": info.get("registered_at", "?"),
        },
    )


# ------------------------------------------------------------------
# candidate-list
# ------------------------------------------------------------------


@election_group.command("candidate-list")
@_network_option
@click.pass_context
def candidate_list(ctx: click.Context, network: str | None) -> None:
    """List all registered candidates for the current cycle.

    \b
    Examples:
      tusdt election candidate-list
      tusdt election candidate-list --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        candidates = client.get_candidate_list(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    if not candidates:
        print_info("No candidates registered")
        return

    rows = [[str(i), addr] for i, addr in enumerate(candidates)]
    print_table("Candidates", ["#", "Address"], rows)


# ------------------------------------------------------------------
# approval-weight
# ------------------------------------------------------------------


@election_group.command("approval-weight")
@click.argument("candidate", type=str, metavar="<ss58-address>")
@_network_option
@click.pass_context
def approval_weight(ctx: click.Context, candidate: str, network: str | None) -> None:
    """Show the accumulated approval weight for a candidate.

    \b
    CANDIDATE is the SS58 address to query.
    Examples:
      tusdt election approval-weight 5GrwvaEF...
      tusdt election approval-weight 5GrwvaEF... --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        weight = client.get_approval_weight(keypair, candidate)
    except Exception as exc:
        print_error(str(exc))
        return

    decimals = config.get("decimals", 9)
    print_dict("Approval Weight", {"Candidate": candidate, "Weight": format_balance(weight, decimals)})


# ------------------------------------------------------------------
# total-participating-power
# ------------------------------------------------------------------


@election_group.command("total-participating-power")
@_network_option
@click.pass_context
def total_participating_power(ctx: click.Context, network: str | None) -> None:
    """Show the total summed voting power of all participants.

    \b
    Examples:
      tusdt election total-participating-power
      tusdt election total-participating-power --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        power = client.get_total_participating_power(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    decimals = config.get("decimals", 9)
    print_dict("Total Participating Power", {"Power": format_balance(power, decimals)})


# ------------------------------------------------------------------
# total-voted-balance
# ------------------------------------------------------------------


@election_group.command("total-voted-balance")
@_network_option
@click.pass_context
def total_voted_balance(ctx: click.Context, network: str | None) -> None:
    """Show the total raw alpha balance of all participants.

    \b
    Examples:
      tusdt election total-voted-balance
      tusdt election total-voted-balance --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        balance = client.get_total_voted_balance(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    decimals = config.get("decimals", 9)
    print_dict("Total Voted Balance", {"Balance": format_balance(balance, decimals)})


# ------------------------------------------------------------------
# quorum
# ------------------------------------------------------------------


@election_group.command("quorum")
@_network_option
@click.pass_context
def quorum(ctx: click.Context, network: str | None) -> None:
    """Show the quorum threshold for the current election cycle.

    \b
    Examples:
      tusdt election quorum
      tusdt election quorum --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        q = client.get_quorum_election(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    decimals = config.get("decimals", 9)
    print_dict("Quorum", {"Threshold": format_balance(q, decimals)})


# ------------------------------------------------------------------
# leading-candidate
# ------------------------------------------------------------------


@election_group.command("leading-candidate")
@_network_option
@click.pass_context
def leading_candidate(ctx: click.Context, network: str | None) -> None:
    """Show the current leading candidate and their approval weight.

    \b
    Examples:
      tusdt election leading-candidate
      tusdt election leading-candidate --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        data = client.get_leading_candidate(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    if data is None:
        print_info("No leading candidate")
        return

    decimals = config.get("decimals", 9)
    candidate_addr = data[0] if isinstance(data, (list, tuple)) else "?"
    weight = data[1] if isinstance(data, (list, tuple)) and len(data) > 1 else 0
    print_dict(
        "Leading Candidate",
        {
            "Candidate": candidate_addr,
            "Approval Weight": format_balance(weight, decimals),
        },
    )


# ------------------------------------------------------------------
# maintainer-elect
# ------------------------------------------------------------------


@election_group.command("maintainer-elect")
@_network_option
@click.pass_context
def maintainer_elect(ctx: click.Context, network: str | None) -> None:
    """Show the maintainer-elect awaiting activation.

    \b
    Examples:
      tusdt election maintainer-elect
      tusdt election maintainer-elect --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        data = client.get_maintainer_elect(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    if data is None:
        print_info("No maintainer-elect")
        return

    decimals = config.get("decimals", 9)
    print_dict(
        "Maintainer Elect",
        {
            "Who": data.get("who", "?"),
            "Netuid": data.get("netuid", "?"),
            "Approval Weight": format_balance(data.get("approval_weight", 0), decimals),
            "Decided At": data.get("decided_at", "?"),
        },
    )


# ------------------------------------------------------------------
# transition
# ------------------------------------------------------------------


@election_group.command("transition")
@_network_option
@click.pass_context
def transition(ctx: click.Context, network: str | None) -> None:
    """Show the active subnet transition, if any.

    \b
    Examples:
      tusdt election transition
      tusdt election transition --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        data = client.get_transition(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    if data is None:
        print_info("No active transition")
        return

    print_dict(
        "Transition",
        {
            "From Netuid": data.get("from_netuid", "?"),
            "To Netuid": data.get("to_netuid", "?"),
            "Ends At": data.get("ends_at", "?"),
        },
    )


# ------------------------------------------------------------------
# is-in-transition
# ------------------------------------------------------------------


@election_group.command("is-in-transition")
@_network_option
@click.pass_context
def is_in_transition(ctx: click.Context, network: str | None) -> None:
    """Check whether a subnet transition is active.

    \b
    Examples:
      tusdt election is-in-transition
      tusdt election is-in-transition --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        in_transition = client.is_in_transition(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Transition Status", {"In Transition": in_transition})


# ------------------------------------------------------------------
# voting-window
# ------------------------------------------------------------------


@election_group.command("voting-window")
@_network_option
@click.pass_context
def voting_window(ctx: click.Context, network: str | None) -> None:
    """Show the current voting window (opens at, ends at).

    \b
    Examples:
      tusdt election voting-window
      tusdt election voting-window --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        window = client.get_voting_window(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    if isinstance(window, (list, tuple)) and len(window) >= 2:
        print_dict(
            "Voting Window",
            {
                "Opens At": window[0],
                "Ends At": window[1],
            },
        )
    else:
        print_dict("Voting Window", {"Raw": window})


# ======================================================================
# Write (mutating) commands
# ======================================================================

# ------------------------------------------------------------------
# schedule-election
# ------------------------------------------------------------------


@election_group.command("schedule-election")
@_wallet_option
@_network_option
@click.pass_context
def schedule_election(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Schedule a new election cycle (permissionless).

    \b
    Must be called when the election is in Idle phase and the cadence
    anchor has been reached (or an emergency is pending).
    Examples:
      tusdt election schedule-election --wallet-name MyWallet
      tusdt election schedule-election --wallet-name MyWallet --network testnet
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
    print_info("Scheduling election...")

    try:
        client = TUSDTClient(config)
        result = client.schedule_election(keypair)
        print_success("Election scheduled!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# register-candidate
# ------------------------------------------------------------------


@election_group.command("register-candidate")
@click.argument("netuid", type=int, metavar="<netuid>")
@click.argument("hotkey", type=str, metavar="<ss58-address>")
@_wallet_option
@_network_option
@click.pass_context
def register_candidate(
    ctx: click.Context,
    netuid: int,
    hotkey: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Register as a candidate for the current election cycle.

    \b
    NETUID is the subnet the candidate intends to govern.
    HOTKEY is the SS58 address of the candidate's hotkey.
    The caller (coldkey) must have sufficient alpha stake in the subnet.
    Examples:
      tusdt election register-candidate 113 5GrwvaEF... --wallet-name MyWallet
      tusdt election register-candidate 42 5GrwvaEF... --wallet-name MyWallet --network testnet
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
    print_info(f"Registering as candidate for netuid {netuid} with hotkey {hotkey}...")

    try:
        client = TUSDTClient(config)
        result = client.register_candidate(keypair, netuid, hotkey)
        print_success("Candidate registered!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# cast-approval
# ------------------------------------------------------------------


@election_group.command("cast-approval")
@click.argument("candidate", type=str, metavar="<ss58-address>")
@click.option("--hotkey", required=True, help="Hotkey SS58 address of the voter (e.g. 5GrwvaEF...)")
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
def cast_approval(
    ctx: click.Context,
    candidate: str,
    hotkey: str,
    balance: str,
    multiplier_bps: int,
    proofs: tuple[str, ...],
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Cast an approval vote for a candidate.

    \b
    CANDIDATE is the SS58 address of the candidate to approve.
    Each --proof is a hex-encoded 32-byte Merkle proof hash; repeat for
    multiple proof nodes.  The first vote cast on or after the 5th of the
    month opens the voting window.
    Examples:
      tusdt election cast-approval 5GrwvaEF... --hotkey 5GrwvaEF... --balance 1000 --multiplier-bps 10000 --proof 0x5637... --wallet-name MyWallet
      tusdt election cast-approval 5FHneW... --hotkey 5GrwvaEF... --balance 500 --multiplier-bps 10000 --proof 0xabc... --proof 0xdef... --wallet-name MyWallet
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
            print_error(f"Each --proof must be exactly 32 bytes (64 hex chars), got {len(proof_bytes)} bytes")
            return
        proof_list.append(list(proof_bytes))

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Casting approval for {candidate} with balance {balance}...")

    try:
        client = TUSDTClient(config)
        result = client.cast_approval(keypair, candidate, hotkey, raw_balance, multiplier_bps, proof_list)
        print_success("Approval cast!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# finalize
# ------------------------------------------------------------------


@election_group.command("finalize")
@_wallet_option
@_network_option
@click.pass_context
def finalize(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Finalize the current election cycle (permissionless).

    \b
    Must be called after the voting window has closed.  If a candidate has
    >50% approval and quorum is met, the election transitions to Elected.
    Otherwise it returns to Idle.
    Examples:
      tusdt election finalize --wallet-name MyWallet
      tusdt election finalize --wallet-name MyWallet --network testnet
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
    print_info("Finalizing election...")

    try:
        client = TUSDTClient(config)
        result = client.finalize_election(keypair)
        print_success("Election finalized!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# activate
# ------------------------------------------------------------------


@election_group.command("activate")
@_wallet_option
@_network_option
@click.pass_context
def activate(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Activate the elected maintainer (permissionless).

    \b
    Must be called on or after the 15th of the month when the election is
    in Elected phase.  Installs the winner as the new maintainer and, if
    the netuid changed, opens a 6-month subnet transition.
    Examples:
      tusdt election activate --wallet-name MyWallet
      tusdt election activate --wallet-name MyWallet --network testnet
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
    print_info("Activating maintainer-elect...")

    try:
        client = TUSDTClient(config)
        result = client.activate_election(keypair)
        print_success("Maintainer activated!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# end-transition
# ------------------------------------------------------------------


@election_group.command("end-transition")
@_wallet_option
@_network_option
@click.pass_context
def end_transition(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """End the active subnet transition (permissionless).

    \b
    Must be called after the 6-month transition period has elapsed.
    Examples:
      tusdt election end-transition --wallet-name MyWallet
      tusdt election end-transition --wallet-name MyWallet --network testnet
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
    print_info("Ending subnet transition...")

    try:
        client = TUSDTClient(config)
        result = client.end_transition(keypair)
        print_success("Transition ended!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# trigger-emergency-election
# ------------------------------------------------------------------


@election_group.command("trigger-emergency-election")
@_wallet_option
@_network_option
@click.pass_context
def trigger_emergency_election(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Trigger an emergency election (incumbent only).

    \b
    Bypasses the cadence anchor so the next schedule-election call opens
    a new cycle immediately.
    Examples:
      tusdt election trigger-emergency-election --wallet-name MyWallet
      tusdt election trigger-emergency-election --wallet-name MyWallet --network testnet
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
    print_info("Triggering emergency election...")

    try:
        client = TUSDTClient(config)
        result = client.trigger_emergency_election(keypair)
        print_success("Emergency election triggered!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# cancel-cycle
# ------------------------------------------------------------------


@election_group.command("cancel-cycle")
@_wallet_option
@_network_option
@click.pass_context
def cancel_cycle(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Cancel the current election cycle (incumbent only).

    \b
    Can only cancel during the Registration phase (not Voting or Elected).
    Resets per-cycle state and returns to Idle.
    Examples:
      tusdt election cancel-cycle --wallet-name MyWallet
      tusdt election cancel-cycle --wallet-name MyWallet --network testnet
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
    print_info("Cancelling election cycle...")

    try:
        client = TUSDTClient(config)
        result = client.cancel_cycle(keypair)
        print_success("Election cycle cancelled!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))
