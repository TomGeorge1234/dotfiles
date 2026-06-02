# dotfiles

Personal dotfiles, managed with [GNU stow](https://www.gnu.org/software/stow/).
Everything under [`home/`](home/) is symlinked into `$HOME`.

## Quick start (fresh machine)

```bash
git clone https://github.com/TomGeorge1234/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
./bootstrap.sh
```

`bootstrap.sh` is idempotent and will:

1. install [oh-my-zsh](https://ohmyz.sh/) (without overwriting `~/.zshrc`),
2. clone the zsh plugins into `~/.oh-my-zsh/custom/plugins`,
3. install `stow`,
4. symlink the contents of `home/` into `$HOME`.

Then open a new terminal (or run `exec zsh`).

## What's inside

| File | Purpose |
| --- | --- |
| `home/.zshrc` | zsh + oh-my-zsh config, NVM lazy-load, `mila` helpers |
| `home/.zprofile` | login-shell environment |
| `home/.tmux.conf` | tmux config |
| `home/.vimrc` | vim config |
| `home/.gitconfig` | git config and aliases |
| `home/.ssh/config` | SSH host config (keys are **not** tracked) |

### zsh plugins

`zsh-autosuggestions` and `zsh-syntax-highlighting` aren't bundled with
oh-my-zsh. `bootstrap.sh` clones them into `~/.oh-my-zsh/custom/plugins/`;
re-running `./bootstrap.sh` pulls the latest.

## Prerequisites

`git` and `curl` (and `zsh`). On macOS, [Homebrew](https://brew.sh/) is used to
install `stow`; on Debian/Ubuntu, `apt`. To install `stow` from source instead:

```bash
cd /tmp
wget http://ftp.gnu.org/gnu/stow/stow-2.3.1.tar.gz
tar -xzvf stow-2.3.1.tar.gz
cd stow-2.3.1
./configure --prefix="$HOME/.local"
make && make install
```

## Manual stow

If you'd rather not run the bootstrap script:

```bash
cd ~/.dotfiles
stow home          # add --restow to refresh, --delete to remove
```

stow won't overwrite existing real files — remove or back them up first if it
reports a conflict.
