# Contributing to BLIMP

Hi! First of all, thanks for your interest in contributing. Help in various forms is almost always
needed and in any case appreciated.

## Overview

BLIMP is written in Python 3.9 with the [discordpy] commands framework. For dependency management we
use [Nix] wrapping [poetry]. Complex input beyond the capabilities of discordpy is done using
[TOML], which is the least painful to write markup format i could come up with that has Python
bindings.

## Getting Started: Coding

If you want to add a new feature, please start out by creating an issue and opening a discussion
about it. Pull Requests coming out of the blue won't be accepted. If you want to pick up an existing
issue for implementation, leave a note there that you're doing so so that no one else starts on the
same work as you do accidentally. Then, you can start actually working on it:

### 1. Prerequisites

If you're on Linux or Mac, you'll want [Nix], if you're on Windows, just [poetry] should do fine. If
you don't install Nix, you will need to check that you have [Python 3.9] or later available.

You will need [git] in any case. You probably also want a visual git interface, e.g. that of Visual
Studio Code (which is a fine code editor too).

You also need a Discord bot token, which you can get from the [Applications page] of your Discord
account. You might also need to create a server to test your bot in.

### 2. Forking & Cloning

1. Create a fork, that is, a copy of BLIMP's repository, for your own GitHub account. There's a
button somewhere on the top right on the repository main site.
2. Clone your fork of BLIMP into a directory on your PC by following the instructions listed under
"Code"→"Clone" on your fork's GitHub page.

### 3. Initial Setup

1. Switch over into the directory you cloned BLIMP into and spin up a development shell using either
`nix-shell` or `poetry shell`, depending on what you installed earlier. This might take a while, so
grab yourself a cup of tea.
2. Open the file `blimp.cfg.example` with your text editor and update at the very least the value of
`discord.token` with the bot token you got from Discord. Without this, your bot won't be able to log
in. You might also want to change other values. Save the file as `blimp.cfg` in the same folder.
3. In your development shell, run `python -m blimp` to start the bot for the first time. It will
automatically create the needed database.

### 4. Development Workflow

1. Create a new branch for your feature: `git checkout -b just-write-stuff-into-here`. This allows
you to develop your feature concurrently to others working on other things.
2. Make whatever changes you think appropriate. If you need help with something while making the
changes, don't hesitate to ask in the support server or the issue you're working on! When you save
your changes, use `Ctrl-C` in your development shell to stop the bot and repeat `python -m blimp` to
restart it with your changes applied.
3. Once your changes are complete, run `isort blimp` and `black blimp` in your development shell to
format the codebase, followed by `pylint blimp` to see potential issues with your code. Once happy
with the results, stage your changes with git: `git add src/file1 src/file2 src/file_n` and commit
them: `git commit`. Please don't alter the version number of BLIMP, we'll change it after the merge
is done.
4. Push your work to your fork: `git push origin the-previously-picked-branch-name`. Then, go to the
[pull requests] page and click the button that should appear to create a pull request based on your
recently pushed branch. Write a short summary of your changes; if you think something you've done
warrants extra explanations, do so.
7. Wait for a review. If you want to change more things in your branch, add more commits; don't edit
your previous ones.
8. Wait for your request to be merged into the `main` branch.
9. Reset your working copy by checking out `main`: `git checkout main` and pulling from the main
repository: `git pull upstream main`.

[discordpy]: https://github.com/Rapptz/discord.py/
[Python 3.9]: https://www.python.org/downloads/
[git]: https://git-scm.com/
[Nix]: https://nixos.org
[poetry]: https://python-poetry.org
[Applications page]: https://discord.com/developers/applications
[pull requests]: https://github.com/The-Valley-Discord/blimp/pulls
[TOML]: https://toml.io/
