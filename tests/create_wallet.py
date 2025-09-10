# dwallet/scripts/create_wallet.py
import argparse
import os
from dotenv import load_dotenv
from core.keyring import create_wallet, preview_derived_address, import_private_key

def main():
    load_dotenv()  # 读取 .env（可选）
    parser = argparse.ArgumentParser(description="Create an empty ETH wallet (mnemonic → keystore).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="Generate a new mnemonic and keystore")
    p_new.add_argument("--password", required=True)
    p_new.add_argument("--base-path", default="m/44'/60'/0'/0")
    p_new.add_argument("--index", type=int, default=0)
    p_new.add_argument("--label", default=None)

    p_from_m = sub.add_parser("from-mnemonic", help="Use existing mnemonic to derive and store keystore")
    p_from_m.add_argument("--password", required=True)
    p_from_m.add_argument("--mnemonic", required=True)
    p_from_m.add_argument("--base-path", default="m/44'/60'/0'/0")
    p_from_m.add_argument("--index", type=int, default=0)
    p_from_m.add_argument("--label", default=None)

    p_prev = sub.add_parser("preview", help="Preview derived address without writing keystore/db")
    p_prev.add_argument("--mnemonic", required=True)
    p_prev.add_argument("--base-path", default="m/44'/60'/0'/0")
    p_prev.add_argument("--index", type=int, default=0)

    p_imp = sub.add_parser("import-privkey", help="(Dev) Import raw private key → keystore/db")
    p_imp.add_argument("--password", required=True)
    p_imp.add_argument("--priv", required=True)
    p_imp.add_argument("--label", default=None)

    args = parser.parse_args()

    if args.cmd == "new":
        addr, mnem, ks_path, path = create_wallet(
            password=args.password, mnemonic=None, base_path=args.base_path, index=args.index, label=args.label
        )
        print(f"Address:       {addr}")
        print(f"Derivation:    {path}")
        print(f"Keystore path: {ks_path}")
        print("Mnemonic:      " + (mnem or "(hidden; not returned when importing)"))

    elif args.cmd == "from-mnemonic":
        addr, mnem, ks_path, path = create_wallet(
            password=args.password, mnemonic=args.mnemonic, base_path=args.base_path, index=args.index, label=args.label
        )
        print(f"Address:       {addr}")
        print(f"Derivation:    {path}")
        print(f"Keystore path: {ks_path}")
        print("Mnemonic:      (hidden on import)")

    elif args.cmd == "preview":
        addr = preview_derived_address(args.mnemonic, base_path=args.base_path, index=args.index)
        print(f"Preview address @ {args.base_path}/{args.index}: {addr}")

    elif args.cmd == "import-privkey":
        addr, ks_path = import_private_key(args.password, args.priv, label=args.label)
        print(f"Address:       {addr}")
        print(f"Keystore path: {ks_path}")

if __name__ == "__main__":
    main()