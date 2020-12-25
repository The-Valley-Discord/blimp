# Contributing to BLIMP

Hi! First of all, thanks for your interest in contributing. Help in various forms is almost always
needed and in any case appreciated.

## Overview

BLIMP is written in Python 3.9 with the [discordpy] commands framework. For dependency management we
use [Nix] wrapping [poetry]. Complex input beyond the capabilities of discordpy is done using
[TOML], which is the least painful to write markup format i could come up with that has Python
bindings.

## Getting Started

If you want to add a new feature, please start out by creating an issue and opening a discussion
about it. Pull Requests coming out of the blue won't be accepted. If you want to pick up an existing
issue for implementation, leave a note there that you're doing so so that no one else starts on the
same work as you do accidentally. Then, you can start actually working on it:

1. Install the dependencies: If you're on Linux or Mac, you'll want [Nix], if you're on Windows,
just [poetry] should do fine. You will need git in any case. You probably also want a visual git
interface, e.g. that of Visual Studio Code (which is a fine code editor).
2. Create a fork, that is, a copy of BLIMP's repository, for your own GitHub account. There's a
button somewhere on the top right on the repository main site.
2. Clone your fork of BLIMP into a directory on your PC: `git clone git@github.com:yourname/blimp`.
3. Switch over into that directory and spin up a development shell using either `nix-shell` or
`poetry shell`, depending on what you installed earlier. If you didn't install Nix, you'll also need
to make sure you have Python 3.9 installed aside from poetry.
4. Create a new branch for your feature: `git checkout -b anything_goes_here_it_doesnt_matter`. This
allows you to develop your feature concurrently to others working on other things.
5. Make your changes. To test them, you need a discord bot, which you can create on the
[Applications page] of your Discord account. You also need a server to test in. You can copy all the
necessary IDs and the bot token into `blimp.cfg.example` and save it as `blimp.cfg`. Then, in your
development shell, you'll be able to run your testing instance with `python39 -m blimp`. If you need
help with something while making the changes, don't hesitate to ask!
6. Once your changes are complete, run `isort blimp; black blimp` to format the codebase and
`pylint blimp` to see potential issues with your code. Once happy with the results, stage your
changes with git: `git add src/file1 src/file2 src/filen` and commit them: `git commit`. Please
don't alter the version number of BLIMP, we'll change it after the merge is done.
7. Push your work to your fork: `git push origin the-previously-picked-branch-name`. Then, go to the
[pull requests] page and click the button that should appear to create a pull request based on your
recently pushed branch. Write "hi" or something. If you think something you've done warrants extra
explanations, do so.
8. Wait for a review. If you want to change more things in your branch, add more commits; don't edit
your previous ones.
9. Wait for your request to be merged into the `main` branch.
10. Reset your working copy by checking out `main`: `git checkout main` and pulling from the main
repository: `git pull upstream main`.

[discordpy]: https://github.com/Rapptz/discord.py/
[Nix]: https://nixos.org
[poetry]: https://python-poetry.org
[Applications page]: https://discord.com/developers/applications
[pull requests]: https://github.com/The-Valley-Discord/blimp/pulls
