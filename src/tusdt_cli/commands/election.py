"""Election CLI commands."""

import sys
from typing import Any

import click

from tusdt_cli.context import CLIContext
from tusdt_cli.globals import network_option, wallet_option
from tusdt_cli.utils import (
    ModeAwareGroup,
    format_balance,
    parse_balance,
)
from tusdt_cli.wallet import get_reader_keypair

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
            return str(keys[0])
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
@network_option
@click.pass_context
def election_governance(ctx: click.Context, network: str | None) -> None:
    """Show the governance address stored in the election contract.

    \b
    Examples:
      tusdt election governance-address
      tusdt election governance-address --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    addr = state.run_read(lambda c: c.get_election_governance(kp))
    state.output.detail("Governance", {"Address": addr})


# ------------------------------------------------------------------
# min-candidate-stake
# ------------------------------------------------------------------


@election_group.command("min-candidate-stake")
@network_option
@click.pass_context
def min_candidate_stake(ctx: click.Context, network: str | None) -> None:
    """Show the minimum candidate stake (alpha).

    \b
    Examples:
      tusdt election min-candidate-stake
      tusdt election min-candidate-stake --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    kp = get_reader_keypair(cfg)
    stake = state.run_read(lambda c: c.get_min_candidate_stake(kp))
    state.output.detail("Minimum Candidate Stake", {"Alpha": format_balance(stake, decimals)})


# ------------------------------------------------------------------
# incumbent
# ------------------------------------------------------------------


@election_group.command("incumbent")
@network_option
@click.pass_context
def incumbent(ctx: click.Context, network: str | None) -> None:
    """Show the current incumbent maintainer.

    \b
    Examples:
      tusdt election incumbent
      tusdt election incumbent --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    addr = state.run_read(lambda c: c.get_incumbent(kp))
    state.output.detail("Incumbent", {"Address": addr})


# ------------------------------------------------------------------
# active-netuid
# ------------------------------------------------------------------


@election_group.command("active-netuid")
@network_option
@click.pass_context
def active_netuid(ctx: click.Context, network: str | None) -> None:
    """Show the active governing subnet netuid.

    \b
    Examples:
      tusdt election active-netuid
      tusdt election active-netuid --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    netuid = state.run_read(lambda c: c.get_active_netuid(kp))
    state.output.detail("Active Netuid", {"Netuid": netuid})


# ------------------------------------------------------------------
# phase
# ------------------------------------------------------------------


@election_group.command("phase")
@network_option
@click.pass_context
def phase(ctx: click.Context, network: str | None) -> None:
    """Show the current election phase.

    \b
    Examples:
      tusdt election phase
      tusdt election phase --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    raw = state.run_read(lambda c: c.get_phase(kp))
    state.output.detail("Phase", {"Phase": _format_phase(raw)})


# ------------------------------------------------------------------
# cycle-id
# ------------------------------------------------------------------


@election_group.command("cycle-id")
@network_option
@click.pass_context
def cycle_id(ctx: click.Context, network: str | None) -> None:
    """Show the current election cycle ID.

    \b
    Examples:
      tusdt election cycle-id
      tusdt election cycle-id --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    cid = state.run_read(lambda c: c.get_cycle_id(kp))
    state.output.detail("Cycle ID", {"Cycle": cid})


# ------------------------------------------------------------------
# next-election-ts
# ------------------------------------------------------------------


@election_group.command("next-election-ts")
@network_option
@click.pass_context
def next_election_ts(ctx: click.Context, network: str | None) -> None:
    """Show the earliest timestamp when the next election may be scheduled.

    \b
    Examples:
      tusdt election next-election-ts
      tusdt election next-election-ts --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    ts = state.run_read(lambda c: c.get_next_election_ts(kp))
    state.output.detail("Next Election", {"Timestamp": ts})


# ------------------------------------------------------------------
# terms-served
# ------------------------------------------------------------------


@election_group.command("terms-served")
@click.argument("who", type=str, metavar="<ss58-address>")
@network_option
@click.pass_context
def terms_served(ctx: click.Context, who: str, network: str | None) -> None:
    """Show how many terms an account has served.

    \b
    WHO is the SS58 address of the account to query.
    Examples:
      tusdt election terms-served 5GrwvaEF...
      tusdt election terms-served 5GrwvaEF... --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    terms = state.run_read(lambda c: c.get_terms_served(kp, who))
    state.output.detail("Terms Served", {"Account": who, "Terms": terms})


# ------------------------------------------------------------------
# get-candidate
# ------------------------------------------------------------------


@election_group.command("get-candidate")
@click.argument("candidate", type=str, metavar="<ss58-address>")
@network_option
@click.pass_context
def get_candidate(ctx: click.Context, candidate: str, network: str | None) -> None:
    """Show registration info for a candidate.

    \b
    CANDIDATE is the SS58 address of the candidate to query.
    Examples:
      tusdt election get-candidate 5GrwvaEF...
      tusdt election get-candidate 5GrwvaEF... --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    info = state.run_read(lambda c: c.get_candidate(kp, candidate))

    if info is None:
        state.output.info(f"Candidate {candidate} not found in current cycle")
        return

    state.output.detail(
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
@network_option
@click.pass_context
def candidate_list(ctx: click.Context, network: str | None) -> None:
    """List all registered candidates for the current cycle.

    \b
    Examples:
      tusdt election candidate-list
      tusdt election candidate-list --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    candidates = state.run_read(lambda c: c.get_candidate_list(kp))

    if not candidates:
        state.output.info("No candidates registered")
        return

    rows = [[str(i), addr] for i, addr in enumerate(candidates)]
    state.output.table("Candidates", ["#", "Address"], rows)


# ------------------------------------------------------------------
# approval-weight
# ------------------------------------------------------------------


@election_group.command("approval-weight")
@click.argument("candidate", type=str, metavar="<ss58-address>")
@network_option
@click.pass_context
def approval_weight(ctx: click.Context, candidate: str, network: str | None) -> None:
    """Show the accumulated approval weight for a candidate.

    \b
    CANDIDATE is the SS58 address to query.
    Examples:
      tusdt election approval-weight 5GrwvaEF...
      tusdt election approval-weight 5GrwvaEF... --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    kp = get_reader_keypair(cfg)
    weight = state.run_read(lambda c: c.get_approval_weight(kp, candidate))
    state.output.detail(
        "Approval Weight", {"Candidate": candidate, "Weight": format_balance(weight, decimals)}
    )


# ------------------------------------------------------------------
# total-participating-power
# ------------------------------------------------------------------


@election_group.command("total-participating-power")
@network_option
@click.pass_context
def total_participating_power(ctx: click.Context, network: str | None) -> None:
    """Show the total summed voting power of all participants.

    \b
    Examples:
      tusdt election total-participating-power
      tusdt election total-participating-power --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    kp = get_reader_keypair(cfg)
    power = state.run_read(lambda c: c.get_total_participating_power(kp))
    state.output.detail("Total Participating Power", {"Power": format_balance(power, decimals)})


# ------------------------------------------------------------------
# total-voted-balance
# ------------------------------------------------------------------


@election_group.command("total-voted-balance")
@network_option
@click.pass_context
def total_voted_balance(ctx: click.Context, network: str | None) -> None:
    """Show the total raw alpha balance of all participants.

    \b
    Examples:
      tusdt election total-voted-balance
      tusdt election total-voted-balance --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    kp = get_reader_keypair(cfg)
    balance = state.run_read(lambda c: c.get_total_voted_balance(kp))
    state.output.detail("Total Voted Balance", {"Balance": format_balance(balance, decimals)})


# ------------------------------------------------------------------
# quorum
# ------------------------------------------------------------------


@election_group.command("quorum")
@network_option
@click.pass_context
def quorum(ctx: click.Context, network: str | None) -> None:
    """Show the quorum threshold for the current election cycle.

    \b
    Examples:
      tusdt election quorum
      tusdt election quorum --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    kp = get_reader_keypair(cfg)
    q = state.run_read(lambda c: c.get_quorum_election(kp))
    state.output.detail("Quorum", {"Threshold": format_balance(q, decimals)})


# ------------------------------------------------------------------
# leading-candidate
# ------------------------------------------------------------------


@election_group.command("leading-candidate")
@network_option
@click.pass_context
def leading_candidate(ctx: click.Context, network: str | None) -> None:
    """Show the current leading candidate and their approval weight.

    \b
    Examples:
      tusdt election leading-candidate
      tusdt election leading-candidate --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    kp = get_reader_keypair(cfg)
    data = state.run_read(lambda c: c.get_leading_candidate(kp))

    if data is None:
        state.output.info("No leading candidate")
        return

    candidate_addr = data[0] if isinstance(data, (list, tuple)) else "?"
    weight = data[1] if isinstance(data, (list, tuple)) and len(data) > 1 else 0
    state.output.detail(
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
@network_option
@click.pass_context
def maintainer_elect(ctx: click.Context, network: str | None) -> None:
    """Show the maintainer-elect awaiting activation.

    \b
    Examples:
      tusdt election maintainer-elect
      tusdt election maintainer-elect --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    kp = get_reader_keypair(cfg)
    data = state.run_read(lambda c: c.get_maintainer_elect(kp))

    if data is None:
        state.output.info("No maintainer-elect")
        return

    state.output.detail(
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
@network_option
@click.pass_context
def transition(ctx: click.Context, network: str | None) -> None:
    """Show the active subnet transition, if any.

    \b
    Examples:
      tusdt election transition
      tusdt election transition --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    data = state.run_read(lambda c: c.get_transition(kp))

    if data is None:
        state.output.info("No active transition")
        return

    state.output.detail(
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
@network_option
@click.pass_context
def is_in_transition(ctx: click.Context, network: str | None) -> None:
    """Check whether a subnet transition is active.

    \b
    Examples:
      tusdt election is-in-transition
      tusdt election is-in-transition --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    in_transition = state.run_read(lambda c: c.is_in_transition(kp))
    state.output.detail("Transition Status", {"In Transition": in_transition})


# ------------------------------------------------------------------
# voting-window
# ------------------------------------------------------------------


@election_group.command("voting-window")
@network_option
@click.pass_context
def voting_window(ctx: click.Context, network: str | None) -> None:
    """Show the current voting window (opens at, ends at).

    \b
    Examples:
      tusdt election voting-window
      tusdt election voting-window --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    window = state.run_read(lambda c: c.get_voting_window(kp))

    if isinstance(window, (list, tuple)) and len(window) >= 2:
        state.output.detail(
            "Voting Window",
            {
                "Opens At": window[0],
                "Ends At": window[1],
            },
        )
    else:
        state.output.detail("Voting Window", {"Raw": window})


# ======================================================================
# Write (mutating) commands
# ======================================================================

# ------------------------------------------------------------------
# schedule-election
# ------------------------------------------------------------------


@election_group.command("schedule-election")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    state.output.info("Scheduling election...")
    state.submit(lambda c, kp: c.schedule_election(kp))
    state.output.success("Election scheduled!")


# ------------------------------------------------------------------
# register-candidate
# ------------------------------------------------------------------


@election_group.command("register-candidate")
@click.argument("netuid", type=int, metavar="<netuid>")
@click.argument("hotkey", type=str, metavar="<ss58-address>")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    state.output.info(f"Registering as candidate for netuid {netuid} with hotkey {hotkey}...")
    state.submit(lambda c, kp: c.register_candidate(kp, netuid, hotkey))
    state.output.success("Candidate registered!")


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
@wallet_option
@network_option
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
            sys.exit(1)
        proof_list.append(list(proof_bytes))

    state.output.info(f"Casting approval for {candidate} with balance {balance}...")
    state.submit(
        lambda c, kp: c.cast_approval(kp, candidate, hotkey, raw_balance, multiplier_bps, proof_list)
    )
    state.output.success("Approval cast!")


# ------------------------------------------------------------------
# finalize
# ------------------------------------------------------------------


@election_group.command("finalize")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    state.output.info("Finalizing election...")
    state.submit(lambda c, kp: c.finalize_election(kp))
    state.output.success("Election finalized!")


# ------------------------------------------------------------------
# activate
# ------------------------------------------------------------------


@election_group.command("activate")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info("Activating maintainer-elect...")
    state.submit(lambda c, kp: c.activate_election(kp))
    state.output.success("Maintainer activated!")


# ------------------------------------------------------------------
# end-transition
# ------------------------------------------------------------------


@election_group.command("end-transition")
@wallet_option
@network_option
@click.pass_context
def end_transition(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """End the active subnet transition (permissionless).

    \b
    Must be called after the 6-month transition period has elapsed.
    Examples:
      tusdt election end-transition --wallet-name MyWallet
      tusdt election end-transition --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    state.output.info("Ending subnet transition...")
    state.submit(lambda c, kp: c.end_transition(kp))
    state.output.success("Transition ended!")


# ------------------------------------------------------------------
# trigger-emergency-election
# ------------------------------------------------------------------


@election_group.command("trigger-emergency-election")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    state.output.info("Triggering emergency election...")
    state.submit(lambda c, kp: c.trigger_emergency_election(kp))
    state.output.success("Emergency election triggered!")


# ------------------------------------------------------------------
# cancel-cycle
# ------------------------------------------------------------------


@election_group.command("cancel-cycle")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name

    state.output.info("Cancelling election cycle...")
    state.submit(lambda c, kp: c.cancel_cycle(kp))
    state.output.success("Election cycle cancelled!")
