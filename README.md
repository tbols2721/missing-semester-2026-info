# Missing Semester 2026 — GNU Info edition

A terminal manual for all nine lectures in [MIT's Missing Semester 2026](https://missing.csail.mit.edu/2026/).

The manual keeps the full published notes, exercises, code blocks, and text diagrams. Each lecture has an added study guide, objectives, and technical reading notes. Lecture and section links work offline. A concept index supports quick lookup.

Clone the repository, then read the included build without installing it:

```sh
git clone https://github.com/tbols2721/missing-semester-2026-info.git
cd missing-semester-2026-info
info -f ./info/missing-semester-2026.info
```

Install it in your user Info directory:

```sh
make install
info missing-semester-2026
info missing-semester-2026 Git
info missing-semester-2026 Quality
```

The default destination is `~/.local/share/info`. Reader discovery and Bash completion vary by installation. Add this user directory to `INFOPATH` if it is not discovered. Add the following to `~/.bashrc`. If your `~/.bash_profile` does not load `~/.bashrc`, also add it there for login shells. This keeps existing Info paths and the default system paths:

```sh
case ":${INFOPATH-}:" in
  *":$HOME/.local/share/info:"*) ;;
  *) INFOPATH="$HOME/.local/share/info:${INFOPATH-}" ;;
esac
export INFOPATH
```

Open a new shell, type `info `, and press Tab twice. `missing-semester-2026` should appear with the other manuals.

In Info, use **Tab** and **Return** to follow a link, **m** to select a menu entry, **u** to go up, **l** to go back, **Space** to read forward, **i** to search the index, and **q** to quit. Long code lines stay intact in the file. The reader can wrap them on screen; **Ctrl-x w** toggles wrapping.

| Date | Lecture | Menu entry |
| --- | --- | --- |
| Jan 12 | Course Overview + Introduction to the Shell | `Shell` |
| Jan 13 | Command-line Environment | `CLI` |
| Jan 14 | Development Environment and Tools | `Development` |
| Jan 15 | Debugging and Profiling | `Debugging` |
| Jan 16 | Version Control and Git | `Git` |
| Jan 20 | Packaging and Shipping Code | `Shipping` |
| Jan 21 | Agentic Coding | `Agents` |
| Jan 22 | Beyond the Code | `Beyond Code` |
| Jan 23 | Code Quality | `Quality` |

The manual has 144 nodes. Course links point to the matching offline lecture or section. Web references retain their labels and full URLs. Emacs Info and many terminal emulators can open web URLs. Stand-alone GNU Info uses native navigation for the manual; web browsing depends on your terminal or browser.

Videos are linked, with one recording per lecture. They are not transcribed. Images have labels and URLs. Git's text diagrams are preserved. Hidden website comments are omitted. Original source files are retained without changes in `sources/2026/`.

To rebuild from the checked-in Texinfo, install GNU Texinfo and Make, then run `make`. To regenerate from the lecture sources, also install Python 3.10 or later and Pandoc:

```sh
make regenerate
make check
make selftest
make check-links  # optional; needs network access
```

The original build used Python 3.12, Pandoc 3.1.3, and GNU Texinfo 7.1; later rebuilds can use different versions. `make check` confirms all nodes, menus, internal targets, source text, text order within each section, source hashes, and code text with relative indentation. `make selftest` confirms that damaged text, indentation, nodes, source files, and attribution fail validation. External HTTP checks are recorded separately because websites can block automated requests. See [validation](reports/validation.md), [external links](reports/external-links.md), and [review notes](reports/review.md).

Maintenance scripts are included as readable source under `scripts/`. Their default root is the containing checkout, so they can be invoked from any working directory. `make tools` checks that they are present; it does not extract an archive or write to a sibling project. Use `SCRIPT_DIR=/path/to/scripts` only if you intentionally keep another copy. The checked-in Texinfo and Info files can be read or rebuilt without Pandoc or the converter.

The build is offline. It does not execute the lecture examples or send their contents to an AI service.

The course is by Anish Athalye, Jon Gjengset, Jose Javier Gonzalez, and contributors. The source snapshot is commit `1d695c94ccafdce3f06d6b9dfe3e6f106097693a` of [missing-semester/missing-semester](https://github.com/missing-semester/missing-semester). This edition is an adaptation under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). See [LICENSE](LICENSE).

## Contributions and privacy

Read [PRIVACY.md](PRIVACY.md) before sharing terminal output or committing build
reports. Keep personal paths, shell prompts, recordings, and credentials out of
issues and source files. Preserve the original course attribution and adaptation
notice when changing the manual.

Original maintenance scripts use [MIT](LICENSE-CODE). The lecture material and
manual adaptation retain [CC BY-NC-SA 4.0](LICENSE); the script license does not
relicense that content.
