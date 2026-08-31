"""Shared pipeline layer used by both deterministic and agentic runners.

Imports nothing from the agent or runner -- the dependency arrow points one way,
so the two runners cannot drift through this layer.
"""
