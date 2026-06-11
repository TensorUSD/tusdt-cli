# tusdt-cli

Command-line interface for the **TUSDT** stablecoin system — a set of ink!
smart contracts deployed on the Bittensor (subtensor) network.  TUSDT lets
users lock native TAO tokens as collateral in **vaults** to mint a
USD-pegged stablecoin.  This CLI gives you full control over:

- **Vaults** — create, deposit collateral, borrow TUSDT, repay, and release collateral
- **Token** — check balances, transfer TUSDT, and manage spending approvals
- **Auctions** — browse and bid on liquidation auctions for under-collateralised vaults
- **Oracle** — inspect the on-chain price feed that determines collateral ratios
- **Governance** — manage maintainer, council, proposals, voting, and cross-contract admin
- **Treasury** — manage fund balances, distribute revenue, and release funds

No web UI required — everything runs from your terminal.

## Installation

```bash
pip install tusdt-cli
```

## Local Development Installation

```bash
git clone https://github.com/TensorUSD/tusdt-cli
cd tusdt-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Or using [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/TensorUSD/tusdt-cli
cd tusdt-cli
uv sync
```

## Quickstart

The CLI comes pre-configured with the Finney RPC endpoint, contract addresses,
and bundled ABI metadata. No upfront configuration is required — pass
`--wallet-name` on any command that needs signing.

```bash
# Check CLI version
tusdt --version

# Get help for any command
tusdt --help
tusdt vault --help
tusdt vault create --help
```

### 1. List wallets

```bash
tusdt wallet list
```

### 2. Vault operations

Anywhere an address is expected you can pass a **wallet name** via `--wallet-name`
and the CLI resolves the SS58 address from `coldkeypub.txt` automatically or use `--owner` and supply ss58 address

```bash
# Create a vault with 10 TAO as collateral (prompts for coldkey password)
tusdt vault create --amount 10 --wallet-name MyWallet

# View vault #0 (no password needed – reads coldkeypub.txt)
#                ↓vault ID
tusdt vault info 0 --wallet-name MyWallet
tusdt vault info 0 --owner 5GrwvaEF...

# List all vaults for a wallet
tusdt vault list --wallet-name MyWallet
tusdt vault list --owner 5GrwvaEF...

# Add 5 TAO collateral to vault #0
#                          ↓vault ID
tusdt vault add-collateral 0 --amount 5 --wallet-name MyWallet

# Borrow 100 TUSDT from vault #0
#                  ↓vaultID ↓TUSDT amount
tusdt vault borrow 0        100 --wallet-name MyWallet

# Repay 50 TUSDT to vault #0
#                 ↓vault ID ↓TUSDT amount
tusdt vault repay 0         50 --wallet-name MyWallet

# Release 2 TAO collateral from vault #0
#                              ↓vaultID ↓TAO amount
tusdt vault release-collateral 0        2 --wallet-name MyWallet

# Check max borrow capacity for vault #0
#                      ↓vault ID
tusdt vault max-borrow 0 --wallet-name MyWallet

# Check collateral value for vault #0
#                            ↓vault ID
tusdt vault collateral-value 0 --wallet-name MyWallet
```

### 3. Token operations

```bash
# Check balance (wallet name or SS58 address)
tusdt token balance --wallet-name MyWallet
tusdt token balance --owner 5GrwvaEF...

# Transfer 100 TUSDT to another wallet
#                    ↓recipient (wallet name or SS58)  ↓TUSDT amount
tusdt token transfer RecipientWallet                  100 --wallet-name MyWallet

# Approve a spender to use up to 1000 of your TUSDT
#                   ↓spender(wallet name or SS58) ↓TUSDT amount
tusdt token approve SpenderWallet                 1000 --wallet-name MyWallet

# Check allowance (spender wallet name or SS58 address)
#                     ↓spender
tusdt token allowance SpenderWallet --wallet-name MyWallet
tusdt token allowance SpenderWallet --owner 5GrwvaEF...
```

### 4. Auction operations

```bash
# List active liquidation auctions
tusdt auction list-active

# View auction details
#                ↓ auction ID
tusdt auction info 0

# Place a 500 TUSDT bid on auction #0
#                 ↓auctionID ↓TUSDT bid amount
tusdt auction bid 0          500 --wallet-name MyWallet --wallet-hotkey default

# Finalize a completed auction
#                      ↓ auction ID
tusdt auction finalize 0 --wallet-name MyWallet

# Withdraw refund for a non-winning bid
#                             ↓auctionID ↓bid ID
tusdt auction withdraw-refund 0          1 --wallet-name MyWallet

# Check your bid on auction #0 (no password, reads coldkeypub.txt)
#                    ↓ auction ID
tusdt auction my-bid 0 --wallet-name MyWallet
```

### 5. Oracle operations

```bash
# View latest price
tusdt oracle price

# View current round
tusdt oracle round
```

### 6. Governance operations

```bash
# View maintainer and council
tusdt governance maintainer
tusdt governance council

# Check if an account is on the council
tusdt governance is-council 5GrwvaEF...

# View governance parameters and current epoch
tusdt governance params
tusdt governance current-epoch

# View proposals
tusdt governance proposal-count
tusdt governance get-proposal 0

# Check if a (coldkey, hotkey) pair has voted
tusdt governance has-voted 0 --coldkey 5GrwvaEF... --hotkey 5GrwvaEF...

# View quorum for an epoch
tusdt governance quorum 42

# Submit a proposal
tusdt governance submit-proposal \
  --cid "QmXyz..." --kind non-funding \
  --hotkey 5GrwvaEF... --wallet-name MyWallet

# Cast a vote
tusdt governance vote 0 \
  --hotkey 5GrwvaEF... --support \
  --balance 1000 --multiplier-bps 10000 \
  --proof 0xabcdef --wallet-name MyWallet

# Finalize and execute a proposal
tusdt governance finalize-proposal 0 --wallet-name MyWallet
tusdt governance execute-proposal 0 --wallet-name MyWallet
```

### 7. Treasury operations

```bash
# View treasury governance and token address
tusdt treasury governance
tusdt treasury token

# Check fund balances
tusdt treasury fund-balance-tusdt emergency
tusdt treasury fund-balance-native insurance

# View pending distributions
tusdt treasury pending-tusdt
tusdt treasury pending-native

# Distribute pending funds
tusdt treasury distribute --wallet-name MyWallet

# Release funds from a fund
tusdt treasury release emergency \
  --token-kind tusdt --amount 5000 \
  --recipient 5GrwvaEF... --wallet-name MyWallet
```

## Network selection

Two networks are available: **finney** (mainnet, default) and **testnet**.

```bash
# Per-command override (not saved)
tusdt vault list --wallet-name MyWallet --network testnet
tusdt oracle price --network testnet

# Save as default
tusdt config set --network testnet

# Switch back
tusdt config set --network finney
```

## Configuration

Configuration is stored in `~/.tusdt-cli/config.json`.
Most users won't need to edit it — `--wallet-name` and `--network` on
each command cover the common cases.

```bash
# View current config
tusdt config show

# Pre-configure a wallet (avoids passing --wallet-name every time)
tusdt config set --wallet-name MyWallet

# Use a mnemonic seed phrase instead
tusdt config set --signer "word1 word2 word3 ... word12"

# Override contract addresses or RPC
tusdt config set --rpc wss://custom-endpoint:443
tusdt config set --vault 5GxJ...
tusdt config set --governance 5CEP...
tusdt config set --treasury 5Fcj...
```

| Key                    | Description                            | Default                                              |
|------------------------|----------------------------------------|------------------------------------------------------|
| `network`              | Active network preset                  | `finney`                                             |
| `rpc`                  | WebSocket RPC endpoint                 | `wss://entrypoint-finney.opentensor.ai:443`          |
| `vault_address`        | Vault contract SS58 address            | `5GxJw8kTpapdHRW5KUXQLVDpXMMnA61mbzS6nF6jWsEeWExV` |
| `token_address`        | Token (ERC-20) contract SS58 address   | `5CJ4HtCPdoMfdNUk6B7vZ348XryeXAnb5BmDNGejob1FziNH` |
| `auction_address`      | Auction contract SS58 address          | `5HipAvNRiuh9mpTKztPLTvwyYkhzuSqxe1wsUy1fbRwbZUbQ` |
| `oracle_address`       | Oracle contract SS58 address           | `5Dfz8xgQoCsaWWrDxjeCuKB8R6AtYymWZDDDAe2q7NE8tL8A` |
| `governance_address`   | Governance contract SS58 address       | `5CEPPTnB2YtEv7Cf8TXrFkdr6BPkDAUhDJbiT38t1A1g83g5` |
| `treasury_address`     | Treasury contract SS58 address         | `5FcjwHj8NkAMbPzkqzYweeC7KW4LffLW7KEKAR62Dx2cft2f` |
| `vault_metadata`       | Path to vault ABI JSON                 | bundled                                              |
| `token_metadata`       | Path to token ABI JSON                 | bundled                                              |
| `auction_metadata`     | Path to auction ABI JSON               | bundled                                              |
| `oracle_metadata`      | Path to oracle ABI JSON                | bundled                                              |
| `governance_metadata`  | Path to governance ABI JSON            | bundled                                              |
| `treasury_metadata`    | Path to treasury ABI JSON              | bundled                                              |
| `signer`               | Mnemonic seed phrase or keyfile path   | —                                                    |
| `wallet_name`          | Default bittensor wallet name          | —                                                    |
| `wallet_hotkey`        | Default hotkey name                    | `default`                                            |
| `wallet_path`          | Path to wallets directory              | `~/.bittensor/wallets`                               |
| `decimals`             | Decimal places for balance display     | `9`                                                  |
| `access_mode`          | Command visibility (`user` or `dev`)   | `user`                                               |

## Networks

| Network   | RPC endpoint                                |
|-----------|---------------------------------------------|
| `finney`  | `wss://entrypoint-finney.opentensor.ai:443` |
| `testnet` | `wss://test.finney.opentensor.ai:443`       |

## Transaction output

All write operations (create vault, borrow, transfer, bid, etc.) display a
progress spinner and, on success, print the extrinsic hash with a
[Taostats](https://taostats.io) explorer link:

```
Finalized
┌─ Transaction ──────────────────────────────────────────────────┐
│  Extrinsic: 0xabc123…                                          │
│  Block: 0xdef456…                                              │
│  Explorer: https://taostats.io/hash/0xabc…?network=finney      │
└────────────────────────────────────────────────────────────────┘
```

The `network` parameter in the URL matches the `--network` flag (or the
configured default).

## Linting

```bash
ruff check src/          # Lint
ruff format src/         # Format
ruff check --fix src/    # Auto-fix lint issues
```

## Building & Publishing

```bash
# Install build tools
pip install build twine

# Clean old dist files
rm -rf dist/

# Build the package (wheel + sdist)
python -m build

# Check the build (optional but recommended)
twine check dist/*

# Publish to PyPI using an API token
TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-xxxx twine upload dist/*

# Publish to TestPyPI first (optional, for validation)
TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-xxxx twine upload --repository testpypi dist/*
```

After publishing, users can install with `pip install tusdt-cli` (or `pip install --upgrade tusdt-cli` to upgrade).

## Contributing

Contributions are welcome. To get started:

1. Fork the repository and clone your fork
2. Install in development mode: `pip install -e .` (or `uv sync`)
3. Create a branch for your change: `git checkout -b my-feature`
4. Make your changes and test locally
5. Submit a pull request against `main`

Please keep pull requests focused — one feature or fix per PR.

## Repositories

- TUSDT smart contracts: https://github.com/TensorUSD/TUSDT-SmartContract.git
- tusdt-cli repository: https://github.com/TensorUSD/tusdt-cli

## License

MIT
