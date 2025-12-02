## Dotfile 

To install, clone this directory in your home directory, install `stow`

```bash
brew install stow
```

or, if not on mac, from scratch

```bash
cd /tmp
wget http://ftp.gnu.org/gnu/stow/stow-2.3.1.tar.gz
tar -xzvf stow-2.3.1.tar.gz
cd stow-2.3.1
./configure --prefix=$HOME/.local
make
make install
``` 

Then "stow" the contents of this directory to create symlinks to the contained files. You may need to remove originals to avoid conflicts:

```
cd dotfiles
stow home
```
