"""Ops tooling — never imported by request paths.

Modules under ``wavervanir_api.tools`` are operator-driven CLIs (e.g. run via
``python -m wavervanir_api.tools.bootstrap_key``) and have access to
credential-minting helpers. The API itself never imports anything from this
package.
"""
