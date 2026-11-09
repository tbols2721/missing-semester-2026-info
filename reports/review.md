# Conversion checks and limitations

The manual retains the nine published lectures, exercises, and original source
files. Added study guides and technical reading notes are labeled as additions.
The course attribution, source revision, and adaptation notice remain in both
the manual and the license files.

## Automated validation

`make check` checks node names and native menu reachability, source hashes,
source-word preservation, section order, literal code text, and relative
indentation. It opens each node through GNU Info. Regeneration rejects unhandled
HTML and escapes difficult Texinfo target and URL characters.

`make selftest` damages temporary copies to verify that the checker rejects
missing text, changed code indentation, a missing node, a changed source hash,
and a removed modification notice. It does not modify the source checkout.

Repeat source-to-Info builds can be compared with
`reports/artifact-sha256.txt`. The committed manual can be read or rebuilt
without running a lecture example or contacting an AI service.

## Reading behavior

Long code lines remain intact. GNU Info's `Ctrl-x w` toggles wrapping. Course
links use offline targets; external references retain their full URLs. Video
recordings and image files are linked rather than embedded. Some lecture
content exists only in the recordings and is outside the text manual.

External HTTP checks are dated observations, not guarantees that a site remains
available or accepts automated clients. See [external-links.md](external-links.md).
The [README](../README.md) explains prerequisites, installation, and local
regeneration using the scripts in this checkout.
