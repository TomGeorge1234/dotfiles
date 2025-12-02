# ==============================================================================
# 🚀 ZSH Configuration Startup (Unified)
# ==============================================================================

# --- Oh-My-Zsh installation ---
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="agnoster" 
plugins=(
    git
    z
    zsh-autosuggestions
    zsh-syntax-highlighting
    python
    you-should-use
)

# --- Other paths to add --- 
export PATH="$HOME/.local/bin:$PATH"

# --- a naughty git alias for one-line pushing ---
function gacp() {
  git add -A
  git commit -m "$1"
  git push
}

# --- Environment Specific Logic ---

if [[ "$OSTYPE" == "darwin"* ]]; then
    # ==============================================
    # 🍎 MacOS (Local) Specifics
    # ==============================================
    
    # NVM (Node Version Manager)
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" 
    [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion" 

    # Mac Python/Pipx Paths (Using $HOME for portability)
    export PATH="$PATH:$HOME/Library/Python/3.9/bin"

elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # ==============================================
    # 🐧 Linux (Mila Cluster) Specifics
    # ==============================================
    
    # Mila/Slurm Convenience Aliases
    alias sq="squeue -u $USER"
    alias si="sinfo"
fi

# --- Initialize Oh-My-Zsh ---
# Must be loaded after plugins are defined
source $ZSH/oh-my-zsh.sh
