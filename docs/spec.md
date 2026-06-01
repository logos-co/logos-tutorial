# Tutorial YAML Spec Format

The executable-tutorial format and its runner now live in the shared **doctest**
tool. See the canonical reference:

- **Spec format:** [`logos-doctest/docs/spec.md`](https://github.com/logos-co/logos-doctest/blob/master/docs/spec.md)
  (or `repos/logos-doctest/docs/spec.md` inside the workspace)
- **Tool & CLI:** [logos-doctest](https://github.com/logos-co/logos-doctest)

The `*.test.yaml` specs in `tests/` use that format. Run and generate them by
invoking the `doctest` CLI directly via its flake:

```bash
# Execute a tutorial spec end-to-end
nix run github:logos-co/logos-doctest -- run tests/tutorial-wrapping-c-library.test.yaml --verbose

# Generate the .md tutorial from a spec
nix run github:logos-co/logos-doctest -- generate tests/tutorial-wrapping-c-library.test.yaml
```

To run against a local checkout, swap `github:logos-co/logos-doctest` for
`path:../logos-doctest` (or wherever your checkout lives).
