# ==============================================================================
# 🚀 ZSH Configuration Startup (Unified & Optimized)
# ==============================================================================

# --- Oh-My-Zsh Core ---
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="robbyrussell"

# Plugins
# Ensure these are installed in ~/.oh-my-zsh/custom/plugins
ZSH_TMUX_AUTOSTART=true
ZSH_TMUX_AUTOCONNECT=false
plugins=(git tmux z zsh-autosuggestions zsh-syntax-highlighting python)

# --- Path Management ---
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/.bun/bin:$PATH"

# --- Git Functionality (Right-Aligned) ---
setopt PROMPT_SUBST
# Function for right-aligned git branch
parse_git_branch() {
  git branch 2> /dev/null | sed -e '/^[^*]/d' -e 's/* \(.*\)/(\1)/'
}
RPROMPT='$(parse_git_branch)'

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
