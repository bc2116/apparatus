# PR-42 — Require the patched PDF dependency

Focused maintenance before release on `pr-42-pdf-dependency`; dependency PR-35.
The locked pypdf 6.15.0 and package requirement `pypdf>=5.0` permit versions
affected by three upstream moderate advisories:

- [XForm extraction](https://github.com/py-pdf/pypdf/security/advisories/GHSA-763m-79hh-57f2)
  and [outline retrieval](https://github.com/py-pdf/pypdf/security/advisories/GHSA-23w6-3w8w-8484)
  have iteration/resource fixes in 6.16.1.
- [TreeObject insertion](https://github.com/py-pdf/pypdf/security/advisories/GHSA-jp53-mhqp-8xcg)
  has a loop fix in 6.16.0.

Raise the package floor to 6.16.1 and update only pypdf in the lockfile to that
patched version. Keep Python support, extraction behavior, other dependencies,
payload and runtime code unchanged. Update the changelog and this plan's status.
No exploit fixture, new parser, background process or broad dependency refresh
is needed.

Verify the resolved version and package metadata floor, run existing Library
and full `uv run pytest` coverage, and build the payload. Require independent
review and the existing actual Windows CI before merge. Record compatibility
results separately from the upstream advisory evidence; passing normal PDFs
does not independently reproduce every upstream security fix.
