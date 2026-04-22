import argparse
import secrets
import string
from datetime import datetime


# --- CHARACTER SETS ---
LOWER = string.ascii_lowercase
UPPER = string.ascii_uppercase
DIGITS = string.digits
SYMBOLS = "!@#$%^&*()-_=+[]{}|;:,.<>?"


# --- GENERATORS ---
def generate_password(length, upper, digits, symbols):
    charset = LOWER
    if upper:
        charset += UPPER
    if digits:
        charset += DIGITS
    if symbols:
        charset += SYMBOLS

    return ''.join(secrets.choice(charset) for _ in range(length))


def generate_token(length):
    return secrets.token_hex(length)


def generate_urlsafe(length):
    return secrets.token_urlsafe(length)


def generate_env_bundle():
    return {
        "SECRET_KEY": secrets.token_urlsafe(50),
        "DB_PASSWORD": generate_password(24, True, True, True),
        "API_KEY": secrets.token_hex(32),
        "JWT_SECRET": secrets.token_urlsafe(32),
    }


# --- OUTPUT HELPERS ---
def save_to_file(content, filename):
    with open(filename, "w") as f:
        f.write(content)
    print(f"[+] Saved to {filename}")


def format_env(env_dict):
    lines = [f"# Generated on {datetime.utcnow().isoformat()}"]
    for k, v in env_dict.items():
        lines.append(f"{k}={v}")
    return "\n".join(lines)


# --- CLI ---
def main():
    parser = argparse.ArgumentParser(
        description="Secure Password & Key Generator CLI"
    )

    subparsers = parser.add_subparsers(dest="command")

    # PASSWORD
    pwd = subparsers.add_parser("password", help="Generate password")
    pwd.add_argument("-l", "--length", type=int, default=20)
    pwd.add_argument("--no-upper", action="store_true")
    pwd.add_argument("--no-digits", action="store_true")
    pwd.add_argument("--no-symbols", action="store_true")
    pwd.add_argument("-o", "--output", help="Save to file")

    # TOKEN
    tok = subparsers.add_parser("token", help="Generate hex token")
    tok.add_argument("-l", "--length", type=int, default=32)
    tok.add_argument("-o", "--output", help="Save to file")

    # URLSAFE
    url = subparsers.add_parser("urlsafe", help="Generate URL-safe token")
    url.add_argument("-l", "--length", type=int, default=32)
    url.add_argument("-o", "--output", help="Save to file")

    # ENV BUNDLE
    env = subparsers.add_parser("env", help="Generate .env secrets bundle")
    env.add_argument("-o", "--output", default=".env")

    args = parser.parse_args()

    if args.command == "password":
        result = generate_password(
            args.length,
            not args.no_upper,
            not args.no_digits,
            not args.no_symbols
        )

    elif args.command == "token":
        result = generate_token(args.length)

    elif args.command == "urlsafe":
        result = generate_urlsafe(args.length)

    elif args.command == "env":
        env_data = generate_env_bundle()
        result = format_env(env_data)
        save_to_file(result, args.output)
        return

    else:
        parser.print_help()
        return

    print(result)

    if args.output:
        save_to_file(result, args.output)


if __name__ == "__main__":
    main()