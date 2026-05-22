# System-wide bash defaults for Bark containers.
# Users can override these in ~/.bashrc on the persistent home mount.

PS1='\[\033[01;34m\]\w\[\033[00m\]\$ '
HISTFILE=~/.bash_history
HISTSIZE=1000
HISTFILESIZE=2000
shopt -s histappend
PROMPT_COMMAND="history -a"
alias ls='ls --color=auto'
alias grep='grep --color=auto'
