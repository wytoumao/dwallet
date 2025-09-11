# configs/chain_registry.py
"""
Chain registry for resolving chain IDs and aliases.
Loads chain configurations from chains.yaml and provides utilities
to resolve chain names/aliases to numeric chain IDs.
"""
from __future__ import annotations

import os
from typing import Dict, List, Any, Union
import yaml


def load_chains_config() -> List[Dict[str, Any]]:
    """Load chains configuration from chains.yaml"""
    config_path = os.path.join(os.path.dirname(__file__), 'chains.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data.get('chains', [])


def build_chain_mapping() -> Dict[str, int]:
    """
    Build a mapping from chain names/aliases to chain IDs.
    Returns dict with lowercase keys for case-insensitive lookup.
    """
    chains = load_chains_config()
    mapping = {}

    for chain in chains:
        chain_id = chain['chainId']
        name = chain['name']

        # Add chain ID as string key
        mapping[str(chain_id)] = chain_id

        # Add full name (lowercase)
        mapping[name.lower()] = chain_id

        # Add common aliases based on name patterns
        if 'ethereum' in name.lower():
            if 'mainnet' in name.lower():
                mapping['ethereum'] = chain_id
                mapping['eth'] = chain_id
                mapping['mainnet'] = chain_id

        if 'base' in name.lower():
            if 'mainnet' in name.lower():
                mapping['base'] = chain_id
            elif 'sepolia' in name.lower():
                mapping['base-sepolia'] = chain_id
                mapping['basesepolia'] = chain_id

        if 'sepolia' in name.lower() and 'base' not in name.lower():
            mapping['sepolia'] = chain_id
            mapping['eth-sepolia'] = chain_id

    return mapping


# Global chain mapping cache
_CHAIN_MAPPING = None


def get_chain_mapping() -> Dict[str, int]:
    """Get chain mapping, loading it once and caching."""
    global _CHAIN_MAPPING
    if _CHAIN_MAPPING is None:
        _CHAIN_MAPPING = build_chain_mapping()
    return _CHAIN_MAPPING


def resolve_chain_id(chain: Union[int, str]) -> int:
    """
    Resolve chain identifier to numeric chain ID.

    Args:
        chain: Chain identifier - can be:
            - Numeric chain ID (int or str)
            - Chain name (case-insensitive)
            - Chain alias (e.g., 'base', 'sepolia', 'ethereum')

    Returns:
        int: Numeric chain ID

    Raises:
        ValueError: If chain identifier cannot be resolved

    Examples:
        resolve_chain_id(8453) -> 8453
        resolve_chain_id('8453') -> 8453
        resolve_chain_id('base') -> 8453
        resolve_chain_id('Base Mainnet') -> 8453
        resolve_chain_id('sepolia') -> 11155111
    """
    # If already numeric, return as int
    if isinstance(chain, int):
        return chain

    # If string representation of number
    if isinstance(chain, str) and chain.isdigit():
        return int(chain)

    # Look up in chain mapping
    if isinstance(chain, str):
        mapping = get_chain_mapping()
        chain_lower = chain.lower().strip()

        if chain_lower in mapping:
            return mapping[chain_lower]

    # If not found, raise error with helpful message
    mapping = get_chain_mapping()
    available_chains = sorted(set(k for k in mapping.keys() if not k.isdigit()))
    raise ValueError(
        f"Unknown chain identifier: {chain}. "
        f"Available options: {', '.join(available_chains)}"
    )


def get_chain_config(chain_id: int) -> Dict[str, Any]:
    """
    Get full chain configuration by chain ID.

    Args:
        chain_id: Numeric chain ID

    Returns:
        Dict with chain configuration

    Raises:
        ValueError: If chain ID not found
    """
    chains = load_chains_config()
    for chain in chains:
        if chain['chainId'] == chain_id:
            return chain

    raise ValueError(f"Chain ID {chain_id} not found in configuration")


def list_supported_chains() -> List[str]:
    """Return list of supported chain identifiers."""
    mapping = get_chain_mapping()
    return sorted(set(k for k in mapping.keys() if not k.isdigit()))
