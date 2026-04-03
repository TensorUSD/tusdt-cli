# tusdt-cli

Command-line interface for interacting with the **TUSDT** ink! smart-contract
system (Vault, Auction, ERC-20 Token, Oracle) on the Bittensor network.

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

### 1. List wallets

```bash
tusdt wallet list
```

### 2. Vault operations

Anywhere an address is expected you can pass a **wallet name** instead and the
CLI resolves the SS58 address from `coldkeypub.txt` automatically.

```bash
# Create a vault (prompts for coldkey password)
tusdt vault create --amount 10 --wallet-name MyWallet

# View your vault (no password needed – reads coldkeypub.txt)
tusdt vault info MyWallet 0
# …or via --wallet-name
tusdt vault info --wallet-name MyWallet 0

# List all vaults for a wallet
tusdt vault list MyWallet
# …or via --wallet-name
tusdt vault list --wallet-name MyWallet

# Add more collateral
tusdt vault add-collateral 0 --amount 5 --wallet-name MyWallet

# Borrow against collateral
tusdt vault borrow 0 100 --wallet-name MyWallet

# Repay borrowed tokens
tusdt vault repay 0 50 --wallet-name MyWallet

# Release collateral
tusdt vault release-collateral 0 2 --wallet-name MyWallet

# Check max borrow capacity
tusdt vault max-borrow MyWallet 0
tusdt vault max-borrow --wallet-name MyWallet 0

# Check collateral value
tusdt vault collateral-value MyWallet 0
tusdt vault collateral-value --wallet-name MyWallet 0
```

### 3. Token operations

```bash
# Check balance (wallet name or SS58 address)
tusdt token balance MyWallet
tusdt token balance --wallet-name MyWallet

# Transfer tokens
tusdt token transfer RecipientWallet 100 --wallet-name MyWallet

# Approve spender
tusdt token approve SpenderWallet 1000 --wallet-name MyWallet

# Check allowance (both args accept wallet names)
tusdt token allowance MyWallet SpenderWallet
```

### 4. Auction operations

```bash
# List active liquidation auctions
tusdt auction list-active

# View auction details
tusdt auction info 0

# Place a bid (with optional hotkey for metadata)
tusdt auction bid 0 500 --wallet-name MyWallet --wallet-hotkey default

# Finalize a completed auction
tusdt auction finalize 0 --wallet-name MyWallet

# Withdraw refund for a non-winning bid
tusdt auction withdraw-refund 0 1 --wallet-name MyWallet

# Check your bid (resolves address from coldkeypub.txt, no password)
tusdt auction my-bid 0 --wallet-name MyWallet
```

### 5. Oracle operations

```bash
# View latest price
tusdt oracle price

# View current round
tusdt oracle round
```

## Network selection

Two networks are available: **finney** (mainnet, default) and **testnet**.

```bash
# Per-command override (not saved)
tusdt vault list MyWallet --network testnet
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
tusdt config set --vault 5Hh...
```

| Key                | Description                          | Default                                              |
|--------------------|--------------------------------------|------------------------------------------------------|
| `network`          | Active network preset                | `finney`                                             |
| `rpc`              | WebSocket RPC endpoint               | `wss://entrypoint-finney.opentensor.ai:443`          |
| `vault_address`    | Vault contract SS58 address          | `5HhJKNf7XjmppAyPeBKN5xQk6joNMWHTnEgup4msxfcKcYKp`   |
| `token_address`    | Token (ERC-20) contract SS58 address | `5GGqBAYWW84wvdTeZGM68dHng1UaWTxxc4ZzFhuQXF9zqK9J`   |
| `auction_address`  | Auction contract SS58 address        | `5Cninzamn4GVi1J1St578ENyNEDrMi5hXucY7rUj1WzREgAt`   |
| `oracle_address`   | Oracle contract SS58 address         | `5FqciR795agP8wEojv2TRegwN757EJURyzjDREUvzCX3cqZS`   |
| `vault_metadata`   | Path to vault ABI JSON               | bundled                                              |
| `token_metadata`   | Path to token ABI JSON               | bundled                                              |
| `auction_metadata` | Path to auction ABI JSON             | bundled                                              |
| `oracle_metadata`  | Path to oracle ABI JSON              | bundled                                              |
| `signer`           | Mnemonic seed phrase or keyfile path | —                                                    |
| `wallet_name`      | Default bittensor wallet name        | —                                                    |
| `wallet_path`      | Path to wallets directory            | `~/.bittensor/wallets`                               |
| `decimals`         | Decimal places for balance display   | `9`                                                  |

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
│  Explorer: https://taostats.io/hash/0xabc…?network=finney │
└────────────────────────────────────────────────────────────────┘
```

The `network` parameter in the URL matches the `--network` flag (or the
configured default).

## Repositories

- TUSDT smart contracts: https://github.com/TensorUSD/TUSDT-SmartContract.git
- tusdt-cli repository: https://github.com/TensorUSD/tusdt-cli

## License

MIT
