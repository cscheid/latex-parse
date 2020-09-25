# Making LaTeX to Markdown actually work

Background: I want to take my LaTeX papers (mostly a mix of VIS
submissions and ML-adjacent work with ICML and NeurIPS styles) and
make nice-looking web pages out of them.

* Why not pandoc? Pandoc failed pretty badly with my papers, and I
  want this to require as little changes in the papers as possible.

## How to run what we have so far

- Clone this
- `$ pip install textx`
- `$ ./drive.py test-files/0008.tex` (etc.)
