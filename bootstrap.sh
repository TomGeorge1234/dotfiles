#!/usr/bin/env bash
#
# bootstrap.sh — provision a fresh machine from this dotfiles repo.
#
# Idempotent: safe to re-run. It will
#   1. install oh-my-zsh (unattended, without touching ~/.zshrc),
#   2. pull the vendored zsh plugin submodules,
#   3. install GNU stow,
#   4. symlink everything in ./home into $HOME.
#
# Usage:
#   git clone --recurse-submodules https://github.com/TomGeorge1234/dotfiles.git ~/.dotfiles
#   cd ~/.dotfiles && ./bootstrap.sh

set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarn:\033[0m %s\n' "$*" >&2; }

# --- 1. oh-my-zsh ---------------------------------------------------------
if [[ -d "$HOME/.oh-my-zsh" ]]; then
  info "oh-my-zsh already installed."
else
  info "Installing oh-my-zsh (unattended)..."
  # ZSH=...          -> install target; set explicitly so an inherited $ZSH
  #                     (e.g. exported by an existing .zshrc) can't redirect it.
  # KEEP_ZSHRC=yes   -> don't create/replace ~/.zshrc (stow owns it).
  # RUNZSH=no CHSH=no -> don't drop us into a new shell or change login shell.
  ZSH="$HOME/.oh-my-zsh" KEEP_ZSHRC=yes RUNZSH=no CHSH=no \
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
fi

# --- 2. zsh plugins -------------------------------------------------------
# Cloned straight into oh-my-zsh's custom plugins dir (not vendored in this
# repo). Re-running pulls the latest. Declared here by URL.
ZSH_CUSTOM="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}"
clone_or_update() {
  local url="$1" dest="$2"
  if [[ -d "$dest/.git" ]]; then
    info "Updating $(basename "$dest")..."
    git -C "$dest" pull --ff-only --quiet
  else
    info "Cloning $(basename "$dest")..."
    git clone --depth 1 "$url" "$dest"
  fi
}
clone_or_update https://github.com/zsh-users/zsh-autosuggestions     "$ZSH_CUSTOM/plugins/zsh-autosuggestions"
clone_or_update https://github.com/zsh-users/zsh-syntax-highlighting "$ZSH_CUSTOM/plugins/zsh-syntax-highlighting"

# --- 3. stow --------------------------------------------------------------
if command -v stow >/dev/null 2>&1; then
  info "stow already installed."
elif [[ "$OSTYPE" == darwin* ]] && command -v brew >/dev/null 2>&1; then
  info "Installing stow via Homebrew..."
  brew install stow
elif command -v apt-get >/dev/null 2>&1; then
  info "Installing stow via apt..."
  sudo apt-get update && sudo apt-get install -y stow
else
  warn "Could not find a package manager to install stow."
  warn "Install it manually (see README) and re-run this script."
  exit 1
fi

# --- 4. stow the dotfiles -------------------------------------------------
info "Stowing dotfiles into $HOME..."
# --restow cleanly refreshes existing symlinks; remove conflicting real files first.
stow --dir="$DOTFILES_DIR" --target="$HOME" --restow home

info "Done. Open a new terminal (or 'exec zsh') to pick up the new config."
