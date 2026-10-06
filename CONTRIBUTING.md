# Contributing

Small, tested improvements are welcome. Keep existing settings/defaults and per-height preview memory working. Treat generated G-code as machine instructions, not merely a drawing.

1. Run the unit tests and GUI smoke test in [BUILD.md](docs/BUILD.md).
2. Add a regression test for every converter fix. Cover both M82 and M83 when extrusion state changes.
3. Verify exit position, extrusion mode, feedrate, preserved features, and unsupported-command refusal.
4. Document new controls, defaults, hover help, and profile persistence.
5. Submit a focused pull request with before/after behavior and test results.

Do not remove validation simply to accept a failing slice. Unknown firmware commands require evidence of their state effects. Avoid sharing proprietary models or machine-start G-code publicly; use minimal synthetic reproductions. Never commit signing keys, certificates with private keys, tokens, or printer credentials.
