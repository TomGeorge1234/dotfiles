# ==============================================================================
# 🚀 ZSH Configuration Startup (Unified & Optimized)
# ==============================================================================

# --- Oh-My-Zsh Core ---
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="robbyrussell"

# Plugins
# zsh-autosuggestions and zsh-syntax-highlighting are cloned into
# ~/.oh-my-zsh/custom/plugins by bootstrap.sh (not bundled with oh-my-zsh).
# zsh-syntax-highlighting must come LAST so it can wrap everything else.
plugins=(git tmux z python zsh-autosuggestions zsh-syntax-highlighting)

# Auto-start tmux only in real terminals, not embedded ones (VS Code, Emacs).
# This must be set before oh-my-zsh.sh sources the tmux plugin.
if [[ "$TERM_PROGRAM" != "vscode" && -z "$INSIDE_EMACS" ]]; then
  ZSH_TMUX_AUTOSTART=true
  ZSH_TMUX_AUTOCONNECT=true
  ZSH_TMUX_AUTOQUIT=false
fi

# --- Path Management ---
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/.bun/bin:$PATH"

# --- Git Alias ---
gacp() {
  git add -A && git commit -m "$1" && git push
}

# --- Environment Specific Logic ---

if [[ "$OSTYPE" == "darwin"* ]]; then
    # 🍎 MacOS (Local) Specifics
    
    # NVM Lazy Load
    export NVM_DIR="$HOME/.nvm"
    nvm() {
        unset -f nvm
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
        nvm "$@"
    }
    
    # Python/Pipx
    export PATH="$PATH:$HOME/Library/Python/3.9/bin"
    
    # Mila alias
    mila() {
      if [[ "$1" == "code" ]]; then
        shift
        local arg has_alloc=0
        for arg in "$@"; do
          case "$arg" in
            --alloc|--salloc|--sbatch) has_alloc=1; break ;;
          esac
        done
        if (( has_alloc )); then
          command mila code "$@"
        else
          command mila code "$@" --alloc --mem=16G --time=8:00:00
        fi
      elif [[ "$1" == "recode" ]]; then
        # Reconnect to an existing mila-code job instead of allocating a new one
        shift
        local JOB_ID=$(ssh mila "squeue -u \$USER --name=mila-code -h -o %i" | head -n 1)
        if [ -z "$JOB_ID" ]; then
          echo "No active mila-code job found."
          return 1
        fi
        echo "Found mila-code running on Job ID $JOB_ID. Reconnecting..."
        command mila code "$1" --job "$JOB_ID"
      else
        command mila "$@"
      fi
    }

elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # 🐧 Linux (Mila Cluster) Specifics
    
    # Slurm Convenience
    alias sq="squeue -u $USER"
    alias si="sinfo"
    
    # Bun completions
    [ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"
fi

# --- Initialize Oh-My-Zsh ---
source $ZSH/oh-my-zsh.sh

# >>> Codex installer >>>
export PATH="/home/mila/g/georget/.local/bin:$PATH"
# <<< Codex installer <<<
